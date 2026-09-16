from __future__ import annotations
from .models import WindowInfo
import platform
import subprocess


def _dedupe(items: list[WindowInfo]) -> list[WindowInfo]:
    out: list[WindowInfo] = []
    seen = set()
    for w in items:
        key = (w.owner, w.title, w.left, w.top, w.width, w.height)
        if key in seen or w.width < 200 or w.height < 120:
            continue
        seen.add(key)
        out.append(w)
    return out


def _windows_win32() -> list[WindowInfo]:
    import pygetwindow as gw
    result: list[WindowInfo] = []
    for i, win in enumerate(gw.getAllWindows()):
        title = (win.title or "").strip()
        if not title:
            continue
        try:
            result.append(WindowInfo(
                id=f"win:{i}:{title}",
                title=title,
                owner="",
                left=int(win.left), top=int(win.top),
                width=int(win.width), height=int(win.height),
            ))
        except Exception:
            continue
    return _dedupe(result)


def _windows_macos() -> list[WindowInfo]:
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
    )
    raw = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    result: list[WindowInfo] = []
    for item in raw:
        bounds = item.get("kCGWindowBounds", {})
        layer = int(item.get("kCGWindowLayer", 0))
        if layer != 0:
            continue
        width = int(bounds.get("Width", 0))
        height = int(bounds.get("Height", 0))
        if width < 200 or height < 120:
            continue
        result.append(WindowInfo(
            id=str(item.get("kCGWindowNumber", "")),
            title=str(item.get("kCGWindowName") or "(janela)").strip(),
            owner=str(item.get("kCGWindowOwnerName") or "").strip(),
            left=int(bounds.get("X", 0)), top=int(bounds.get("Y", 0)),
            width=width, height=height,
        ))
    return _dedupe(result)


def _windows_linux() -> list[WindowInfo]:
    proc = subprocess.run(["wmctrl", "-lG"], capture_output=True, text=True, check=False)
    result: list[WindowInfo] = []
    for line in proc.stdout.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        wid, _, x, y, w, h, host, title = parts
        try:
            result.append(WindowInfo(
                id=wid, title=title.strip(), owner=host,
                left=int(x), top=int(y), width=int(w), height=int(h),
            ))
        except ValueError:
            pass
    return _dedupe(result)


def list_windows(browser_only: bool = False) -> list[WindowInfo]:
    system = platform.system()
    try:
        if system == "Windows":
            wins = _windows_win32()
        elif system == "Darwin":
            wins = _windows_macos()
        else:
            wins = _windows_linux()
    except Exception:
        wins = []

    if browser_only:
        keywords = ("chrome", "google chrome", "chromium", "edge", "brave", "firefox", "arc", "opera")
        filtered = [w for w in wins if any(k in f"{w.owner} {w.title}".lower() for k in keywords)]
        if filtered:
            return filtered
    return wins


def focus_window(window: WindowInfo) -> None:
    system = platform.system()
    if system == "Windows":
        try:
            import pygetwindow as gw
            candidates = [w for w in gw.getAllWindows() if (w.title or "").strip() == window.title]
            if candidates:
                target = candidates[0]
                if target.isMinimized:
                    target.restore()
                target.activate()
        except Exception:
            pass
    elif system == "Darwin" and window.owner:
        owner = window.owner.replace('"', '')
        subprocess.run(["osascript", "-e", f'tell application "{owner}" to activate'], check=False, capture_output=True)
    elif system == "Linux":
        subprocess.run(["wmctrl", "-ia", window.id], check=False, capture_output=True)
