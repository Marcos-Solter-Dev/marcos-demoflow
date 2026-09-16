from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Any
import json

ActionType = Literal[
    "smart_click", "click", "move", "scroll", "wait",
    "type_text", "hotkey", "focus", "reload", "dom_visit", "site_scroll", "continuous_scroll"
]


@dataclass
class WindowInfo:
    id: str
    title: str
    owner: str
    left: int
    top: int
    width: int
    height: int

    @property
    def label(self) -> str:
        owner = f"{self.owner} — " if self.owner else ""
        title = self.title or "(sem título)"
        return f"{owner}{title} [{self.width}×{self.height}]"


@dataclass
class RecordingConfig:
    fps: int = 30
    output_width: int | None = None
    output_height: int | None = None
    cursor_style: str = "ring"
    show_clicks: bool = True
    countdown: int = 3

    def normalized(self) -> "RecordingConfig":
        self.fps = max(10, min(60, int(self.fps)))
        if self.output_width is not None:
            self.output_width = max(320, int(self.output_width))
        if self.output_height is not None:
            self.output_height = max(240, int(self.output_height))
        if self.cursor_style not in {"ring", "dot", "hidden"}:
            self.cursor_style = "ring"
        self.countdown = max(0, min(10, int(self.countdown)))
        return self


@dataclass
class Action:
    type: ActionType
    name: str
    x_rel: float | None = None
    y_rel: float | None = None
    amount: int | None = None
    duration: float = 0.8
    text: str | None = None
    keys: list[str] | None = None
    transition: str = "crossfade"
    zoom: float = 1.18
    settle: float = 0.38
    pause_after: float = 0.08
    selector: str | None = None
    element_label: str | None = None
    element_kind: str | None = None
    auto_click: bool = False
    doc_x: float | None = None
    doc_y: float | None = None
    capture_scroll_y: float | None = None
    target_scroll_y: float | None = None
    viewport_height: float | None = None
    doc_height: float | None = None
    element_offset_x: float | None = None
    element_offset_y: float | None = None
    page_url: str | None = None
    scroll_speed: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Action":
        allowed = set(Action.__dataclass_fields__)
        filtered = {k: v for k, v in data.items() if k in allowed}
        return Action(**filtered)


@dataclass
class Project:
    actions: list[Action]
    recording: RecordingConfig


def save_project(path: str, actions: list[Action], recording: RecordingConfig) -> None:
    payload = {
        "format": "Marcos DemoFlow",
        "version": 9,
        "recording": asdict(recording.normalized()),
        "actions": [a.to_dict() for a in actions],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_project(path: str) -> Project:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    actions = [Action.from_dict(item) for item in data.get("actions", [])]
    rec_data = data.get("recording") or {}
    allowed = set(RecordingConfig.__dataclass_fields__)
    rec = RecordingConfig(**{k: v for k, v in rec_data.items() if k in allowed}).normalized()
    return Project(actions=actions, recording=rec)


def save_actions(path: str, actions: list[Action]) -> None:
    save_project(path, actions, RecordingConfig())


def load_actions(path: str) -> list[Action]:
    return load_project(path).actions
