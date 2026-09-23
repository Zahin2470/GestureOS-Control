"""
Fake macOS adapter (Section 27 — Simulation Mode).

Implements the full MacOSAdapter contract but never touches the real
mouse, keyboard, or any macOS API — every call is only recorded and
logged. This is what GestureOS uses whenever RunMode is SIMULATION, and
what every command-routing test in this project uses instead of a real
Mac. Nothing in this module imports PyObjC/Quartz or anything
macOS-specific, so it runs identically on any platform.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger("gestureos.macos.fake_adapter")


@dataclass(frozen=True)
class RecordedCall:
    """One simulated command, for tests/HUD inspection — never for
    driving real OS state.
    """

    method: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    timestamp: float = 0.0


class FakeMacOSAdapter:
    """Records every call instead of performing it."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self.calls: list[RecordedCall] = []

    def _record(self, method: str, *args: object, **kwargs: object) -> None:
        call = RecordedCall(method=method, args=args, kwargs=kwargs, timestamp=self._clock())
        self.calls.append(call)
        logger.info("simulated_command", extra={"fields": {"method": method}})

    def move_cursor(self, x: float, y: float) -> None:
        self._record("move_cursor", x, y)

    def mouse_down(self, button: str = "left") -> None:
        self._record("mouse_down", button=button)

    def mouse_up(self, button: str = "left") -> None:
        self._record("mouse_up", button=button)

    def scroll(self, dx: float, dy: float) -> None:
        self._record("scroll", dx, dy)

    def key_press(self, key: str) -> None:
        self._record("key_press", key)

    def switch_app_next(self) -> None:
        self._record("switch_app_next")

    def switch_app_previous(self) -> None:
        self._record("switch_app_previous")

    def launch_app(self, name: str) -> None:
        self._record("launch_app", name)

    def media_play_pause(self) -> None:
        self._record("media_play_pause")

    def space_next(self) -> None:
        self._record("space_next")

    def space_previous(self) -> None:
        self._record("space_previous")

    def reset(self) -> None:
        self.calls.clear()

    def calls_of(self, method: str) -> list[RecordedCall]:
        return [c for c in self.calls if c.method == method]
