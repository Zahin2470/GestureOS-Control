"""
Real macOS adapter (Section 12 for cursor; Section 6 for click/drag;
other methods land in later phases).

Implements MacOSAdapter against real Quartz CGEvents. ``move_cursor``,
``mouse_down``, and ``mouse_up`` are functional as of Phase 6 — every
other method raises NotImplementedError with a pointer to the phase
that will implement it, rather than silently doing nothing (a silent
no-op on a real adapter would be a safety problem: better to fail
loudly and let the command router log and drop it — see router.py's
exception handling).

The concrete Quartz calls live behind a small injectable backend
Protocol, the same pattern used by camera.py and tracker.py, so this
adapter's dispatch logic is unit-testable without a real macOS process.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger("gestureos.macos.real_adapter")

_SUPPORTED_BUTTONS = ("left", "right")


class QuartzMouseBackend(Protocol):
    def move_cursor(self, x: float, y: float, dragging: bool = False) -> None: ...
    def mouse_down(self, button: str = "left") -> None: ...
    def mouse_up(self, button: str = "left") -> None: ...


def _default_quartz_backend() -> QuartzMouseBackend:
    import Quartz  # Lazy import: this module must be importable on any
    # platform; only calling these methods on a real Mac needs Quartz.

    move_event_types = {
        False: Quartz.kCGEventMouseMoved,
        True: Quartz.kCGEventLeftMouseDragged,
    }
    down_event_types = {
        "left": Quartz.kCGEventLeftMouseDown,
        "right": Quartz.kCGEventRightMouseDown,
    }
    up_event_types = {
        "left": Quartz.kCGEventLeftMouseUp,
        "right": Quartz.kCGEventRightMouseUp,
    }
    cg_buttons = {
        "left": Quartz.kCGMouseButtonLeft,
        "right": Quartz.kCGMouseButtonRight,
    }

    class _RealQuartzBackend:
        def _current_location(self):
            return Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))

        def move_cursor(self, x: float, y: float, dragging: bool = False) -> None:
            event = Quartz.CGEventCreateMouseEvent(
                None, move_event_types[dragging], (x, y), Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

        def mouse_down(self, button: str = "left") -> None:
            location = self._current_location()
            event = Quartz.CGEventCreateMouseEvent(
                None, down_event_types[button], location, cg_buttons[button]
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

        def mouse_up(self, button: str = "left") -> None:
            location = self._current_location()
            event = Quartz.CGEventCreateMouseEvent(
                None, up_event_types[button], location, cg_buttons[button]
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

    @staticmethod
    def _validate_button(button: str) -> None:
        if button not in _SUPPORTED_BUTTONS:
            raise ValueError(f"unsupported button {button!r}; expected one of {_SUPPORTED_BUTTONS}")

    # -- Phase 5-6: functional -------------------------------------------

    def move_cursor(self, x: float, y: float, dragging: bool = False) -> None:
        backend = self._ensure_backend()
        backend.move_cursor(x, y, dragging=dragging)
        logger.debug("cursor_moved", extra={"fields": {"dragging": dragging}})

    def mouse_down(self, button: str = "left") -> None:
        self._validate_button(button)
        backend = self._ensure_backend()
        backend.mouse_down(button)
        logger.debug("mouse_down", extra={"fields": {"button": button}})

    def mouse_up(self, button: str = "left") -> None:
        self._validate_button(button)
        backend = self._ensure_backend()
        backend.mouse_up(button)
        logger.debug("mouse_up", extra={"fields": {"button": button}})

    # -- Later phases: declared now for a stable contract, not yet real -

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
