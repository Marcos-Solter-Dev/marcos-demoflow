from __future__ import annotations
import math
import platform
import threading
import time
import pyautogui

from .models import WindowInfo, Action
from .recorder import ScreenRecorder
from .windowing import focus_window
from .easing import ease_in_out_cubic, ease_in_out_sine, cubic_bezier_point
from .chrome_tabs import ChromeTab, activate_chrome_tab
from .dom_inspector import (
    scroll_element_into_view, get_element_screen_geometry,
    scroll_page_to, scroll_page_continuous, get_continuous_scroll_status, cancel_continuous_scroll, get_document_point_screen_geometry, get_page_scroll_state,
)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.025


class TargetNotVisibleError(RuntimeError):
    pass


class DemoEngine:
    def __init__(self, window: WindowInfo, recorder: ScreenRecorder | None = None, chrome_tab: ChromeTab | None = None):
        self.window = window
        self.recorder = recorder
        self.chrome_tab = chrome_tab
        self.stop_event = threading.Event()
        self.on_status = lambda text: None

    def stop(self) -> None:
        self.stop_event.set()

    def _check(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Execução interrompida.")

    @staticmethod
    def _auto_scroll_duration(distance_px: float, viewport_height: float) -> float:
        distance = abs(float(distance_px))
        viewport = max(320.0, float(viewport_height or 800.0))
        pages = distance / viewport
        return max(0.55, min(4.80, 0.48 + pages * 0.72))

    def _ensure_action_visible(self, action: Action) -> None:
        """Garante que um alvo salvo no documento esteja realmente na viewport."""
        if self.chrome_tab is None or action.doc_x is None or action.doc_y is None:
            return

        ok, geometry, error = get_document_point_screen_geometry(
            self.chrome_tab,
            action.doc_x,
            action.doc_y,
            selector=action.selector,
            element_offset_x=action.element_offset_x,
            element_offset_y=action.element_offset_y,
        )

        viewport_h = max(320.0, float(action.viewport_height or (geometry or {}).get("inner_height", 800.0)))
        current_scroll = float((geometry or {}).get("scroll_y", 0.0))
        viewport_y = float((geometry or {}).get("viewport_y", -999999.0))
        visible = bool(geometry and geometry.get("visible", False))
        safely_visible = visible and (viewport_h * 0.10 <= viewport_y <= viewport_h * 0.90)

        if not safely_visible:
            if action.target_scroll_y is not None:
                target = max(0.0, float(action.target_scroll_y))
            else:
                target = max(0.0, float(action.doc_y) - viewport_h * 0.48)

            distance = target - current_scroll
            duration = self._auto_scroll_duration(distance, viewport_h)
            self.on_status(f"Auto-scroll para o alvo em Y {float(action.doc_y):.0f}px…")
            ok_scroll, scroll_error = scroll_page_to(self.chrome_tab, target, duration=duration)
            if not ok_scroll:
                raise TargetNotVisibleError(
                    f"Não consegui rolar até '{action.element_label or action.name}': {scroll_error}"
                )
            self._wait(duration + 0.08)

            ok, geometry, error = get_document_point_screen_geometry(
                self.chrome_tab,
                action.doc_x,
                action.doc_y,
                selector=action.selector,
                element_offset_x=action.element_offset_x,
                element_offset_y=action.element_offset_y,
            )

        if not ok or not geometry or not bool(geometry.get("visible", False)):
            raise TargetNotVisibleError(
                f"Alvo não ficou visível: {action.element_label or action.name}. "
                "A ação foi pulada para evitar clicar no vazio."
            )

        vy = float(geometry.get("viewport_y", 0.0))
        ih = max(1.0, float(geometry.get("inner_height", viewport_h)))
        if vy < -2 or vy > ih + 2:
            raise TargetNotVisibleError(
                f"Alvo fora da viewport: {action.element_label or action.name}. "
                "A ação foi pulada para evitar clicar no vazio."
            )

    def _absolute(self, action: Action) -> tuple[int, int]:
        if self.chrome_tab is not None and action.doc_x is not None and action.doc_y is not None:
            self._ensure_action_visible(action)
            ok, geometry, error = get_document_point_screen_geometry(
                self.chrome_tab,
                action.doc_x,
                action.doc_y,
                selector=action.selector,
                element_offset_x=action.element_offset_x,
                element_offset_y=action.element_offset_y,
            )
            if ok and geometry and bool(geometry.get("visible", False)):
                return int(round(geometry["screen_x"])), int(round(geometry["screen_y"]))
            raise TargetNotVisibleError(
                f"Não consegui localizar '{action.element_label or action.name}' depois do scroll."
            )

        if action.x_rel is None or action.y_rel is None:
            raise ValueError("Ação sem posição.")
        x = self.window.left + int(self.window.width * action.x_rel)
        y = self.window.top + int(self.window.height * action.y_rel)
        return x, y

    def _smooth_move(self, x: int, y: int, duration: float) -> None:
        sx, sy = pyautogui.position()
        duration = max(0.08, min(4.0, float(duration)))
        dx, dy = x - sx, y - sy
        distance = max(1.0, math.hypot(dx, dy))

        perp_x, perp_y = -dy / distance, dx / distance
        curve = max(-90.0, min(90.0, distance * 0.08))
        sign = 1.0 if (dx + dy) >= 0 else -1.0
        p0 = (float(sx), float(sy))
        p1 = (sx + dx * 0.28 + perp_x * curve * sign, sy + dy * 0.28 + perp_y * curve * sign)
        p2 = (sx + dx * 0.72 - perp_x * curve * 0.55 * sign, sy + dy * 0.72 - perp_y * curve * 0.55 * sign)
        p3 = (float(x), float(y))

        steps = max(10, int(duration * 100))
        start = time.perf_counter()
        for i in range(1, steps + 1):
            self._check()
            t = ease_in_out_sine(i / steps)
            px, py = cubic_bezier_point(p0, p1, p2, p3, t)
            pyautogui.moveTo(round(px), round(py), _pause=False)
            target_time = start + duration * (i / steps)
            delay = target_time - time.perf_counter()
            if delay > 0:
                time.sleep(delay)

    def _smooth_scroll(self, amount: int, duration: float) -> None:
        amount = int(amount)
        if amount == 0:
            return
        duration = max(0.2, min(6.0, float(duration)))
        steps = max(12, int(duration * 55))
        sent = 0
        for i in range(1, steps + 1):
            self._check()
            t = ease_in_out_cubic(i / steps)
            target = round(amount * t)
            delta = target - sent
            if delta:
                pyautogui.scroll(delta, _pause=False)
                sent += delta
            time.sleep(duration / steps)

    def _wait(self, seconds: float) -> None:
        end = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end:
            self._check()
            time.sleep(0.025)

    def _smart_click(self, action: Action) -> None:
        x, y = self._absolute(action)
        self._smooth_move(x, y, action.duration)
        self._check()

        if not self.recorder:
            pyautogui.click(x, y)
            return

        before = self.recorder.capture()
        self.recorder.pause_live()
        try:
            self.recorder.trigger_click_ripple(x, y)
            pyautogui.click(x, y)
            self._wait(max(0.12, action.settle))
            after = self.recorder.capture()
            self.recorder.inject_transition(before, after, action.transition, duration=0.55)
        finally:
            self.recorder.resume_live()

    def _focus(self, action: Action) -> None:
        try:
            px, py = self._absolute(action)
        except TargetNotVisibleError:
            raise
        if not self.recorder:
            self._smooth_move(px, py, min(0.55, max(0.28, action.duration * 0.45)))
            self._wait(action.duration)
            return
        try:
            x_rel = max(0.0, min(1.0, (px - self.window.left) / max(1, self.window.width)))
            y_rel = max(0.0, min(1.0, (py - self.window.top) / max(1, self.window.height)))
        except Exception:
            mx, my = pyautogui.position()
            x_rel = (mx - self.window.left) / max(1, self.window.width)
            y_rel = (my - self.window.top) / max(1, self.window.height)
        self.recorder.set_camera_target(action.zoom, x_rel, y_rel, duration=0.42)
        self._wait(0.46)
        self._wait(max(0.0, action.duration))
        self.recorder.set_camera_target(1.0, x_rel, y_rel, duration=0.42)
        self._wait(0.46)

    def _site_scroll(self, action: Action) -> None:
        if self.chrome_tab is None or action.target_scroll_y is None:
            # Projetos sem aba/DOM continuam executáveis; apenas não há como
            # reproduzir um scroll de documento exato.
            self.on_status(f"Scroll de página indisponível: {action.name}")
            self._wait(min(0.25, max(0.05, action.duration)))
            return

        target = max(0.0, float(action.target_scroll_y))

        # Se o usuário capturou o alvo lá embaixo e apertou Gravar sem voltar
        # ao topo, reposicionamos silenciosamente para o ponto de partida que
        # a timeline esperava. Assim o scroll cinematográfico aparece no vídeo.
        if action.capture_scroll_y is not None:
            source = max(0.0, float(action.capture_scroll_y))
            ok_state, state, _ = get_page_scroll_state(self.chrome_tab)
            current = float(state.get("scroll_y", source)) if ok_state and state else source
            if abs(current - source) > 36.0:
                if self.recorder:
                    self.recorder.pause_live()
                try:
                    scroll_page_to(self.chrome_tab, source, behavior="auto")
                    self._wait(0.10)
                finally:
                    if self.recorder:
                        self.recorder.resume_live()

        self.on_status(f"Rolando até Y {target:.0f}px…")
        ok, error = scroll_page_to(self.chrome_tab, target, duration=action.duration)
        if not ok:
            self.on_status(f"Não consegui rolar até a posição salva: {error}")
            self._wait(0.12)
            return
        # O JS usa exatamente a duração armazenada na timeline.
        self._wait(max(0.08, action.duration) + 0.05)


    def _continuous_scroll(self, action: Action) -> None:
        if self.chrome_tab is None:
            self.on_status("Scroll contínuo indisponível: selecione uma aba do Chrome.")
            self._wait(0.12)
            return

        source = max(0.0, float(action.capture_scroll_y or 0.0))
        speed = max(120.0, min(1200.0, float(action.scroll_speed or 460.0)))

        ok_state, state, _ = get_page_scroll_state(self.chrome_tab)
        current = float(state.get("scroll_y", source)) if ok_state and state else source
        if abs(current - source) > 24.0:
            if self.recorder:
                self.recorder.pause_live()
            try:
                scroll_page_to(self.chrome_tab, source, behavior="auto")
                self._wait(0.12)
            finally:
                if self.recorder:
                    self.recorder.resume_live()

        # Recalcula imediatamente antes do movimento.
        ok_state, live, _ = get_page_scroll_state(self.chrome_tab)
        live_doc = float(live.get("doc_height", action.doc_height or 0.0)) if ok_state and live else float(action.doc_height or 0.0)
        live_view = float(live.get("viewport_height", action.viewport_height or 800.0)) if ok_state and live else float(action.viewport_height or 800.0)
        live_distance = max(0.0, live_doc - live_view - source)
        estimate = (live_distance / speed + 1.0) if speed > 0 and live_distance > 0 else 0.0

        self.on_status(
            f"Scroll contínuo · {live_distance:.0f}px · ~{estimate:.1f}s · {speed:.0f}px/s"
        )

        ok, started, error = scroll_page_continuous(
            self.chrome_tab,
            speed_px_s=speed,
        )
        if not ok:
            self.on_status(f"Não consegui iniciar o scroll contínuo: {error}")
            self._wait(0.12)
            return

        deadline = time.monotonic() + 300.0
        last_report = 0.0

        try:
            while True:
                self._check()

                if time.monotonic() > deadline:
                    cancel_continuous_scroll(self.chrome_tab)
                    self.on_status("Scroll contínuo interrompido: limite de segurança de 5 min.")
                    return

                ok_status, status, status_error = get_continuous_scroll_status(self.chrome_tab)
                if not ok_status or not status:
                    self._wait(0.20)
                    continue

                current_y = float(status.get("currentY", 0.0))
                max_y = float(status.get("maxScroll", 0.0))
                elapsed = float(status.get("elapsedMs", 0.0)) / 1000.0

                now = time.monotonic()
                if now - last_report >= 0.8:
                    self.on_status(
                        f"Scroll contínuo · {current_y:.0f}/{max_y:.0f}px · {elapsed:.1f}s"
                    )
                    last_report = now

                if bool(status.get("done", False)):
                    self.on_status(
                        f"Rodapé alcançado suavemente · {max_y:.0f}px · {elapsed:.1f}s"
                    )
                    return

                if bool(status.get("cancelled", False)):
                    return

                self._wait(0.22)
        except InterruptedError:
            cancel_continuous_scroll(self.chrome_tab)
            raise

    def _reload(self, action: Action) -> None:
        self.on_status("Recarregando página para capturar a entrada…")
        if self.chrome_tab is not None:
            activate_chrome_tab(self.chrome_tab)
            self._wait(0.18)
        if platform.system() == "Darwin":
            pyautogui.hotkey("command", "r")
        else:
            pyautogui.hotkey("ctrl", "r")
        self._wait(max(0.8, action.duration))

    def _dom_visit(self, action: Action) -> None:
        if not self.chrome_tab or not action.selector:
            self.on_status(f"Ignorando '{action.name}': aba/elemento automático indisponível.")
            self._wait(0.15)
            return

        ok, error = scroll_element_into_view(self.chrome_tab, action.selector)
        if not ok:
            self.on_status(f"Elemento não encontrado, pulando: {action.element_label or action.name}")
            self._wait(0.12)
            return

        # O scrollIntoView é suave; dá tempo para o navegador chegar ao alvo.
        self._wait(0.72)
        ok, geometry, error = get_element_screen_geometry(self.chrome_tab, action.selector)
        if not ok or not geometry:
            self.on_status(f"Não consegui localizar na tela: {action.element_label or action.name}")
            self._wait(0.12)
            return

        x = int(round(geometry["screen_x"]))
        y = int(round(geometry["screen_y"]))
        self._smooth_move(x, y, min(0.62, max(0.30, action.duration)))

        x_rel = max(0.0, min(1.0, (x - self.window.left) / max(1, self.window.width)))
        y_rel = max(0.0, min(1.0, (y - self.window.top) / max(1, self.window.height)))
        if self.recorder and action.zoom > 1.001:
            self.recorder.set_camera_target(action.zoom, x_rel, y_rel, duration=0.34)
            self._wait(0.36)

        if action.auto_click:
            self.on_status(f"Clique automático seguro: {action.element_label or action.name}")
            if self.recorder:
                before = self.recorder.capture()
                self.recorder.pause_live()
                try:
                    self.recorder.trigger_click_ripple(x, y)
                    pyautogui.click(x, y)
                    self._wait(max(0.25, action.settle))
                    after = self.recorder.capture()
                    self.recorder.inject_transition(before, after, action.transition, duration=0.42)
                finally:
                    self.recorder.resume_live()
            else:
                pyautogui.click(x, y)
                self._wait(max(0.25, action.settle))

            # Botões seguros podem abrir popovers/modais. Escape tende a fechar sem navegar.
            if action.element_kind == "button":
                self._wait(0.30)
                pyautogui.press("esc")
                self._wait(0.18)
        else:
            self._wait(max(0.20, action.duration))

        if self.recorder and action.zoom > 1.001:
            self.recorder.set_camera_target(1.0, x_rel, y_rel, duration=0.34)
            self._wait(0.36)

    def execute(self, actions: list[Action]) -> None:
        focus_window(self.window)
        if self.chrome_tab is not None:
            activate_chrome_tab(self.chrome_tab)
        self._wait(0.45)
        total = len(actions)
        for idx, action in enumerate(actions, start=1):
            self._check()
            self.on_status(f"{idx}/{total} — {action.name}")

            try:
                if action.type == "smart_click":
                    self._smart_click(action)
                elif action.type == "click":
                    x, y = self._absolute(action)
                    self._smooth_move(x, y, action.duration)
                    if self.recorder:
                        self.recorder.trigger_click_ripple(x, y)
                    pyautogui.click(x, y)
                elif action.type == "move":
                    x, y = self._absolute(action)
                    self._smooth_move(x, y, action.duration)
                elif action.type == "scroll":
                    self._smooth_scroll(action.amount or 0, action.duration)
                elif action.type == "site_scroll":
                    self._site_scroll(action)
                elif action.type == "continuous_scroll":
                    self._continuous_scroll(action)
                elif action.type == "wait":
                    self._wait(action.duration)
                elif action.type == "type_text":
                    pyautogui.write(action.text or "", interval=max(0.01, min(0.12, action.duration / 40)))
                elif action.type == "hotkey":
                    keys = action.keys or []
                    if keys:
                        pyautogui.hotkey(*keys)
                elif action.type == "focus":
                    self._focus(action)
                elif action.type == "reload":
                    self._reload(action)
                elif action.type == "dom_visit":
                    self._dom_visit(action)
                else:
                    raise ValueError(f"Ação desconhecida: {action.type}")
            except TargetNotVisibleError as exc:
                self.on_status(str(exc))
                self._wait(0.20)

            if action.pause_after > 0:
                self._wait(action.pause_after)

        self.on_status("Concluído.")
