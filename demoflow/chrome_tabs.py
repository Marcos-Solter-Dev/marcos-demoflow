from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
import platform
import subprocess


@dataclass(frozen=True)
class ChromeTab:
    window_index: int
    tab_index: int
    title: str
    url: str

    @property
    def label(self) -> str:
        title = (self.title or "(sem título)").strip().replace("\n", " ")
        if len(title) > 72:
            title = title[:69] + "…"
        try:
            host = urlparse(self.url).netloc.replace("www.", "")
        except Exception:
            host = ""
        return f"{title} — {host}" if host else title


def _run_osascript(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)


def list_chrome_tabs() -> list[ChromeTab]:
    if platform.system() != "Darwin":
        return []
    delim = "<|DF|>"
    script = f'''
if application "Google Chrome" is not running then return ""
tell application "Google Chrome"
    set outputText to ""
    repeat with wi from 1 to count of windows
        set tabCount to count of tabs of window wi
        repeat with ti from 1 to tabCount
            set tabTitle to title of tab ti of window wi
            set tabURL to URL of tab ti of window wi
            set outputText to outputText & (wi as text) & "{delim}" & (ti as text) & "{delim}" & tabTitle & "{delim}" & tabURL & linefeed
        end repeat
    end repeat
    return outputText
end tell
'''
    proc = _run_osascript(script)
    if proc.returncode != 0:
        return []
    result: list[ChromeTab] = []
    for raw in proc.stdout.splitlines():
        parts = raw.split(delim, 3)
        if len(parts) != 4:
            continue
        try:
            wi = int(parts[0]); ti = int(parts[1])
        except ValueError:
            continue
        result.append(ChromeTab(window_index=wi, tab_index=ti, title=parts[2].strip(), url=parts[3].strip()))
    return result


def activate_chrome_tab(tab: ChromeTab) -> tuple[bool, str]:
    if platform.system() != "Darwin":
        return False, "Seleção direta de abas está disponível no macOS nesta versão."
    script = f'''
if application "Google Chrome" is not running then return "CHROME_NOT_RUNNING"
tell application "Google Chrome"
    if (count of windows) < {tab.window_index} then return "WINDOW_NOT_FOUND"
    if (count of tabs of window {tab.window_index}) < {tab.tab_index} then return "TAB_NOT_FOUND"
    set active tab index of window {tab.window_index} to {tab.tab_index}
    try
        set minimized of window {tab.window_index} to false
    end try
    try
        set index of window {tab.window_index} to 1
    end try
    activate
    return "OK"
end tell
'''
    proc = _run_osascript(script)
    response = (proc.stdout or "").strip()
    if proc.returncode == 0 and response.endswith("OK"):
        return True, ""
    return False, (proc.stderr or response or "Não foi possível ativar a aba.").strip()


def get_active_chrome_tab() -> ChromeTab | None:
    if platform.system() != "Darwin":
        return None
    delim = "<|DF|>"
    script = f'''
if application "Google Chrome" is not running then return ""
tell application "Google Chrome"
    if (count of windows) < 1 then return ""
    set wi to 1
    set ti to active tab index of window wi
    set tabTitle to title of tab ti of window wi
    set tabURL to URL of tab ti of window wi
    return (wi as text) & "{delim}" & (ti as text) & "{delim}" & tabTitle & "{delim}" & tabURL
end tell
'''
    proc = _run_osascript(script)
    if proc.returncode != 0:
        return None
    parts = (proc.stdout or "").strip().split(delim, 3)
    if len(parts) != 4:
        return None
    try:
        return ChromeTab(window_index=int(parts[0]), tab_index=int(parts[1]), title=parts[2].strip(), url=parts[3].strip())
    except (TypeError, ValueError):
        return None
