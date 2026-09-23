"""
macOS adapter interface.

Declares the full contract every command binding will eventually
dispatch against — cursor, click/drag, scroll, app switching, media,
Spaces — even though Phase 4's command registry only wires up a subset
of it (mouse_down/mouse_up, via pinch). Declaring the whole surface now
follows the same "stable contract up front" pattern used by main.py's
CLI: later phases implement real macOS behavior (PyObjC/Quartz) behind
this same interface without the router or safety layer having to change.

This module contains no macOS-specific code and imports nothing
platform-specific — it is a pure typing contract.
"""

from __future__ import annotations

from typing import Protocol


class MacOSAdapter(Protocol):
    def move_cursor(self, x: float, y: float) -> None: ...

    def mouse_down(self, button: str = "left") -> None: ...

    def mouse_up(self, button: str = "left") -> None: ...

    def scroll(self, dx: float, dy: float) -> None: ...

    def key_press(self, key: str) -> None: ...

    def switch_app_next(self) -> None: ...

    def switch_app_previous(self) -> None: ...

    def launch_app(self, name: str) -> None: ...

    def media_play_pause(self) -> None: ...

    def space_next(self) -> None: ...

    def space_previous(self) -> None: ...
