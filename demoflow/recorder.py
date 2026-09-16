from __future__ import annotations
import threading
import time
from pathlib import Path
import numpy as np
import cv2
import mss
import pyautogui

from .models import WindowInfo, RecordingConfig
from .easing import ease_in_out_cubic, lerp


class ScreenRecorder:
    def __init__(self, window: WindowInfo, output_path: str, config: RecordingConfig | None = None):
        self.window = window
        self.output_path = str(output_path)
        self.config = (config or RecordingConfig()).normalized()
        self.fps = self.config.fps

        self._stop = threading.Event()
        self._live_enabled = threading.Event()
        self._live_enabled.set()
        self._writer_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._writer: cv2.VideoWriter | None = None

        self._ripple_until = 0.0
        self._ripple_center: tuple[int, int] | None = None
        self._ripple_duration = 0.42

        self._camera_start = (1.0, 0.5, 0.5)
        self._camera_target = (1.0, 0.5, 0.5)
        self._camera_t0 = time.monotonic()
        self._camera_duration = 0.0

    @property
    def capture_size(self) -> tuple[int, int]:
        return self.window.width, self.window.height

    @property
    def output_size(self) -> tuple[int, int]:
        if self.config.output_width and self.config.output_height:
            return self.config.output_width, self.config.output_height
        return self.window.width, self.window.height

    def start(self) -> None:
        Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
        width, height = self.output_size
        # OpenCV costuma funcionar melhor com dimensões pares em vídeo.
        width -= width % 2
        height -= height % 2
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(self.output_path, fourcc, float(self.fps), (width, height))
        if not self._writer.isOpened():
            raise RuntimeError("Não foi possível criar o MP4. Tente outro caminho de saída.")
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._live_enabled.set()
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=3.0)
        with self._writer_lock:
            if self._writer:
                self._writer.release()
                self._writer = None

    def pause_live(self) -> None:
        self._live_enabled.clear()

    def resume_live(self) -> None:
        self._live_enabled.set()

    def trigger_click_ripple(self, x_abs: int, y_abs: int) -> None:
        if not self.config.show_clicks:
            return
        self._ripple_center = (
            int(x_abs - self.window.left),
            int(y_abs - self.window.top),
        )
        self._ripple_until = time.monotonic() + self._ripple_duration

    def set_camera_target(self, scale: float, x_rel: float, y_rel: float, duration: float = 0.45) -> None:
        scale = max(1.0, min(1.8, float(scale)))
        x_rel = max(0.0, min(1.0, float(x_rel)))
        y_rel = max(0.0, min(1.0, float(y_rel)))
        with self._state_lock:
            current = self._camera_params_unlocked()
            self._camera_start = current
            self._camera_target = (scale, x_rel, y_rel)
            self._camera_t0 = time.monotonic()
            self._camera_duration = max(0.01, float(duration))

    def _camera_params_unlocked(self) -> tuple[float, float, float]:
        if self._camera_duration <= 0:
            return self._camera_target
        raw = (time.monotonic() - self._camera_t0) / self._camera_duration
        if raw >= 1.0:
            self._camera_duration = 0.0
            self._camera_start = self._camera_target
            return self._camera_target
        t = ease_in_out_cubic(raw)
        return (
            lerp(self._camera_start[0], self._camera_target[0], t),
            lerp(self._camera_start[1], self._camera_target[1], t),
            lerp(self._camera_start[2], self._camera_target[2], t),
        )

    def _camera_params(self) -> tuple[float, float, float]:
        with self._state_lock:
            return self._camera_params_unlocked()

    def _grab_raw(self, sct: mss.mss | None = None) -> np.ndarray:
        region = {
            "left": self.window.left,
            "top": self.window.top,
            "width": self.window.width,
            "height": self.window.height,
        }
        if sct is None:
            with mss.mss() as local:
                shot = np.array(local.grab(region), dtype=np.uint8)
        else:
            shot = np.array(sct.grab(region), dtype=np.uint8)
        return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)

    def capture(self) -> np.ndarray:
        return self._prepare_frame(self._grab_raw())

    def _apply_camera(self, frame: np.ndarray) -> np.ndarray:
        scale, x_rel, y_rel = self._camera_params()
        if scale <= 1.001:
            return frame

        h, w = frame.shape[:2]
        crop_w = max(2, int(w / scale))
        crop_h = max(2, int(h / scale))
        cx = int(x_rel * w)
        cy = int(y_rel * h)
        x0 = max(0, min(w - crop_w, cx - crop_w // 2))
        y0 = max(0, min(h - crop_h, cy - crop_h // 2))
        crop = frame[y0:y0 + crop_h, x0:x0 + crop_w]
        return cv2.resize(crop, (w, h), interpolation=cv2.INTER_CUBIC)

    def _draw_cursor(self, frame: np.ndarray) -> None:
        if self.config.cursor_style == "hidden":
            return
        try:
            mx, my = pyautogui.position()
            cx = int(mx - self.window.left)
            cy = int(my - self.window.top)
            if not (0 <= cx < self.window.width and 0 <= cy < self.window.height):
                return

            # Quando a câmera está ampliada, converte o cursor para o frame transformado.
            scale, x_rel, y_rel = self._camera_params()
            if scale > 1.001:
                w, h = self.window.width, self.window.height
                crop_w = max(2, int(w / scale))
                crop_h = max(2, int(h / scale))
                ccx, ccy = int(x_rel * w), int(y_rel * h)
                x0 = max(0, min(w - crop_w, ccx - crop_w // 2))
                y0 = max(0, min(h - crop_h, ccy - crop_h // 2))
                cx = int((cx - x0) * w / crop_w)
                cy = int((cy - y0) * h / crop_h)

            if self.config.cursor_style == "dot":
                cv2.circle(frame, (cx, cy), 5, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (cx, cy), 6, (40, 40, 40), 1, cv2.LINE_AA)
            else:
                cv2.circle(frame, (cx, cy), 8, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.circle(frame, (cx, cy), 3, (35, 35, 35), -1, cv2.LINE_AA)
        except Exception:
            pass

    def _draw_ripple(self, frame: np.ndarray) -> None:
        if not self.config.show_clicks:
            return
        now = time.monotonic()
        if not self._ripple_center or now >= self._ripple_until:
            return
        x, y = self._ripple_center
        scale, x_rel, y_rel = self._camera_params()
        if scale > 1.001:
            w, h = self.window.width, self.window.height
            crop_w = max(2, int(w / scale))
            crop_h = max(2, int(h / scale))
            ccx, ccy = int(x_rel * w), int(y_rel * h)
            x0 = max(0, min(w - crop_w, ccx - crop_w // 2))
            y0 = max(0, min(h - crop_h, ccy - crop_h // 2))
            x = int((x - x0) * w / crop_w)
            y = int((y - y0) * h / crop_h)
        progress = 1.0 - ((self._ripple_until - now) / self._ripple_duration)
        radius = int(10 + 30 * max(0.0, min(1.0, progress)))
        thickness = max(1, int(3 * (1.0 - progress)))
        cv2.circle(frame, (x, y), radius, (255, 255, 255), thickness, cv2.LINE_AA)

    def _fit_output(self, frame: np.ndarray) -> np.ndarray:
        target_w, target_h = self.output_size
        target_w -= target_w % 2
        target_h -= target_h % 2
        h, w = frame.shape[:2]
        if (w, h) == (target_w, target_h):
            return frame

        scale = min(target_w / w, target_h / h)
        new_w = max(2, int(w * scale))
        new_h = max(2, int(h * scale))
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        canvas[y:y + new_h, x:x + new_w] = resized
        return canvas

    def _prepare_frame(self, frame: np.ndarray) -> np.ndarray:
        frame = self._apply_camera(frame)
        self._draw_cursor(frame)
        self._draw_ripple(frame)
        return self._fit_output(frame)

    def _write(self, frame: np.ndarray) -> None:
        with self._writer_lock:
            if self._writer:
                self._writer.write(frame)

    def inject_transition(self, before: np.ndarray, after: np.ndarray, kind: str, duration: float = 0.55) -> None:
        kind = kind if kind in {"crossfade", "zoom", "slide"} else "crossfade"
        duration = max(0.18, min(2.0, float(duration)))
        count = max(2, int(self.fps * duration))
        h, w = before.shape[:2]

        def zoom(frame: np.ndarray, scale: float) -> np.ndarray:
            nw, nh = max(w, int(w * scale)), max(h, int(h * scale))
            resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
            x0, y0 = (nw - w) // 2, (nh - h) // 2
            return resized[y0:y0 + h, x0:x0 + w]

        for i in range(count):
            if self._stop.is_set():
                return
            t = ease_in_out_cubic(i / (count - 1))
            if kind == "zoom":
                a = zoom(before, 1.0 + 0.035 * t)
                b = zoom(after, 1.035 - 0.035 * t)
                frame = cv2.addWeighted(a, 1.0 - t, b, t, 0.0)
            elif kind == "slide":
                offset = int(w * t)
                frame = np.zeros_like(before)
                if offset < w:
                    frame[:, :w - offset] = before[:, offset:]
                if offset > 0:
                    frame[:, w - offset:] = after[:, :offset]
            else:
                frame = cv2.addWeighted(before, 1.0 - t, after, t, 0.0)
            self._write(frame)

    def _loop(self) -> None:
        period = 1.0 / self.fps
        deadline = time.perf_counter()
        with mss.mss() as sct:
            while not self._stop.is_set():
                if self._live_enabled.is_set():
                    self._write(self._prepare_frame(self._grab_raw(sct)))
                deadline += period
                delay = deadline - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    deadline = time.perf_counter()
