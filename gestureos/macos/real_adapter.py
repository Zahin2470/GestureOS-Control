"""
Real macOS adapter (Section 12 for cursor; other methods land in later
phases).

Implements MacOSAdapter against real Quartz CGEvents. Only
``move_cursor`` is functional in Phase 5 — every other method raises
NotImplementedError with a pointer to the phase that will implement it,
rather than silently doing nothing (silent no-ops on a real adapter
would be a safety problem: better to fail loudly and let the command
router log and drop it — see router.py's exception handling).

The concrete Quartz calls live behind a small injectable backend
Protocol, the same pattern used by camera.py and tracker.py, so this
adapter's dispatch logic is unit-testable without a real macOS process.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger("gestureos.macos.real_adapter")


class QuartzMouseBackend(Protocol):
    def move_cursor(self, x: float, y: float) -> None: ...


def _default_quartz_backend() -> QuartzMouseBackend:
    import Quartz  # Lazy import: this module must be importable on any
    # platform; only calling move_cursor() on a real Mac needs Quartz.

    class _RealQuartzBackend:
        def move_cursor(self, x: float, y: float) -> None:
            event = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    return _RealQuartzBackend()


class RealMacOSAdapter:
    """The macOS adapter used when RunMode is NORMAL (not SIMULATION)."""

    def __init__(
        self,
        backend_factory: Callable[[], QuartzMouseBackend] = _default_quartz_backend,
    ) -> None:
        self._backend_factory = backend_factory
        self._backend: QuartzMouseBackend | None = None

    def _ensure_backend(self) -> QuartzMouseBackend:
        if self._backend is None:
            self._backend = self._backend_factory()
        return self._backend

    # -- Phase 5: functional -------------------------------------------

    def move_cursor(self, x: float, y: float) -> None:
        backend = self._ensure_backend()
        backend.move_cursor(x, y)
        logger.debug("cursor_moved", extra={"fields": {}})

    # -- Later phases: declared now for a stable contract, not yet real -

    def mouse_down(self, button: str = "left") -> None:
        raise NotImplementedError("Click support lands in Phase 6")

    def mouse_up(self, button: str = "left") -> None:
        raise NotImplementedError("Click support lands in Phase 6")

    def scroll(self, dx: float, dy: float) -> None:
        raise NotImplementedError("Scroll support lands in Phase 7")

    def key_press(self, key: str) -> None:
        raise NotImplementedError("Key press support lands in a later phase")

    def switch_app_next(self) -> None:
        raise NotImplementedError("App switching lands in Phase 8")

    def switch_app_previous(self) -> None:
        raise NotImplementedError("App switching lands in Phase 8")

    def launch_app(self, name: str) -> None:
        raise NotImplementedError("App launching lands in Phase 8")

    def media_play_pause(self) -> None:
        raise NotImplementedError("Media controls land in Phase 9")

    def space_next(self) -> None:
        raise NotImplementedError("Spaces support lands in Phase 9")

    def space_previous(self) -> None:
        raise NotImplementedError("Spaces support lands in Phase 9")
