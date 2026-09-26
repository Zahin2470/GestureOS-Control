"""
In-app settings adjustment (Section 26 — Settings).

A small keyboard-driven list of adjustable settings, decoupled from any
rendering: app.py drives it with key events and renders whatever
``.display_rows()`` currently reports. Each item's (min, max) matches
what ``models.ControlSettings.validate()``/``AudioSettings.validate()``
would clamp to anyway — adjusting a setting through this panel can never
produce a value that validate() would silently change later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gestureos.models import Settings


@dataclass(frozen=True)
class SettingItem:
    label: str
    get: Callable[[Settings], float]
    set: Callable[[Settings, float], None]
    step: float
    minimum: float
    maximum: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _format(value: float) -> str:
    return f"{value:.2f}"


def _build_items() -> tuple[SettingItem, ...]:
    return (
        SettingItem(
            "Cursor sensitivity",
            lambda s: s.control.cursor_sensitivity,
            lambda s, v: setattr(s.control, "cursor_sensitivity", v),
            step=0.1,
            minimum=0.1,
            maximum=5.0,
        ),
        SettingItem(
            "Cursor smoothing",
            lambda s: s.control.smoothing,
            lambda s, v: setattr(s.control, "smoothing", v),
            step=0.05,
            minimum=0.0,
            maximum=1.0,
        ),
        SettingItem(
            "Scroll sensitivity",
            lambda s: s.control.scroll_sensitivity,
            lambda s, v: setattr(s.control, "scroll_sensitivity", v),
            step=0.1,
            minimum=0.1,
            maximum=5.0,
        ),
        SettingItem(
            "Audio volume",
            lambda s: s.audio.volume,
            lambda s, v: setattr(s.audio, "volume", v),
            step=0.1,
            minimum=0.0,
            maximum=1.0,
        ),
    )


class SettingsPanel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.selected_index = 0
        self.items: tuple[SettingItem, ...] = _build_items()

    def move_selection(self, delta: int) -> None:
        count = len(self.items)
        self.selected_index = (self.selected_index + delta) % count

    def adjust_selected(self, direction: int) -> float:
        """direction: +1 to increase, -1 to decrease. Returns the new value."""
        item = self.items[self.selected_index]
        current = item.get(self.settings)
        new_value = _clamp(current + item.step * direction, item.minimum, item.maximum)
        item.set(self.settings, new_value)
        return new_value

    def display_rows(self) -> list[str]:
        rows = []
        for i, item in enumerate(self.items):
            marker = ">" if i == self.selected_index else " "
            value = _format(item.get(self.settings))
            rows.append(f"{marker} {item.label}: {value}")
        return rows
