"""
Real macOS adapter (Section 12 for cursor; Section 6 for click/drag;
Phase 7 for scroll; Phase 8 for app switching + safe launching; Phase 9
for media + Spaces; key_press still lands in a later phase).

Implements MacOSAdapter against real Quartz CGEvents and AppKit.
Everything except ``key_press`` is now functional — every remaining
unimplemented method raises NotImplementedError with a pointer to the
phase that will implement it, rather than silently doing nothing (a
silent no-op on a real adapter would be a safety problem: better to
fail loudly and let the command router log and drop it — see router.py's
exception handling).

``launch_app`` itself never decides what's "safe" to launch — that
allowlist check happens one layer up, in SafetyPolicy, before this
adapter is ever called (Phase 8 — "safe launcher"). This class just
does what it's told.

``media_play_pause`` uses macOS's undocumented-but-widely-relied-on
system-defined NSEvent technique for simulating a hardware media key,
since there is no public CGEvent constant for it (unlike everything
else in this file, which uses documented Quartz/AppKit APIs).
``space_next``/``space_previous`` simulate the default Mission Control
keyboard shortcut (Control+Left/Right Arrow) rather than that — Spaces
switching has no equivalent "media key" ambiguity.

The concrete Quartz/AppKit calls live behind a small injectable backend
Protocol, the same pattern used by camera.py and tracker.py, so this
adapter's dispatch logic is unit-testable without a real macOS process.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger("gestureos.macos.real_adapter")

_SUPPORTED_BUTTONS = ("left", "right")
_KVK_TAB = 0x30
_KVK_LEFT_ARROW = 0x7B
_KVK_RIGHT_ARROW = 0x7C
_NX_KEYTYPE_PLAY = 16


class QuartzMouseBackend(Protocol):
    def move_cursor(self, x: float, y: float, dragging: bool = False) -> None: ...
    def mouse_down(self, button: str = "left") -> None: ...
    def mouse_up(self, button: str = "left") -> None: ...
    def scroll(self, dx: float, dy: float) -> None: ...
    def switch_app_next(self) -> None: ...
    def switch_app_previous(self) -> None: ...
    def launch_app(self, name: str) -> None: ...
    def media_play_pause(self) -> None: ...
    def space_next(self) -> None: ...
    def space_previous(self) -> None: ...


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

    def post_key_combo(key_code: int, flags: int) -> None:
        down = Quartz.CGEventCreateKeyboardEvent(None, key_code, True)
        Quartz.CGEventSetFlags(down, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        up = Quartz.CGEventCreateKeyboardEvent(None, key_code, False)
        Quartz.CGEventSetFlags(up, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def post_cmd_tab(shift: bool) -> None:
        flags = Quartz.kCGEventFlagMaskCommand
        if shift:
            flags |= Quartz.kCGEventFlagMaskShift
        post_key_combo(_KVK_TAB, flags)

    def post_ctrl_arrow(right: bool) -> None:
        key_code = _KVK_RIGHT_ARROW if right else _KVK_LEFT_ARROW
        post_key_combo(key_code, Quartz.kCGEventFlagMaskControl)

    def post_media_key(key_type: int) -> None:
        from AppKit import NSEvent, NSSystemDefined  # Lazy: only needed here.

        for key_down in (True, False):
            data1 = (key_type << 16) | ((0xA if key_down else 0xB) << 8)
            event = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                NSSystemDefined,
                (0, 0),
                0xA00 if key_down else 0xB00,
                0,
                0,
                0,
                8,
                data1,
                -1,
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event.CGEvent())

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

        def scroll(self, dx: float, dy: float) -> None:
            # wheel1 = vertical, wheel2 = horizontal, in the units given
            # (pixels here). Sign convention matches "natural scrolling"
            # per scroll.py's docstring — unverified on real hardware.
            event = Quartz.CGEventCreateScrollWheelEvent(
                None, Quartz.kCGScrollEventUnitPixel, 2, round(dy), round(dx)
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

        def switch_app_next(self) -> None:
            # A single quick Cmd+Tab: switches straight to the previous
            # app, same as a real one-tap press (not a held cycling UI).
            post_cmd_tab(shift=False)

        def switch_app_previous(self) -> None:
            # Cmd+Shift+Tab cycles the other direction.
            post_cmd_tab(shift=True)

        def launch_app(self, name: str) -> None:
            from AppKit import NSWorkspace  # Lazy: only needed on real launch.

            success = NSWorkspace.sharedWorkspace().launchApplication_(name)
            if not success:
                raise RuntimeError(f"NSWorkspace could not launch {name!r}")

        def media_play_pause(self) -> None:
            post_media_key(_NX_KEYTYPE_PLAY)

        def space_next(self) -> None:
            # Default Mission Control shortcut: Control+Right Arrow.
            post_ctrl_arrow(right=True)

        def space_previous(self) -> None:
            post_ctrl_arrow(right=False)

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

    # -- Phase 5-9: functional --------------------------------------------

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

    def scroll(self, dx: float, dy: float) -> None:
        backend = self._ensure_backend()
        backend.scroll(dx, dy)
        logger.debug("scroll", extra={"fields": {}})

    def switch_app_next(self) -> None:
        backend = self._ensure_backend()
        backend.switch_app_next()
        logger.debug("switch_app_next", extra={"fields": {}})

    def switch_app_previous(self) -> None:
        backend = self._ensure_backend()
        backend.switch_app_previous()
        logger.debug("switch_app_previous", extra={"fields": {}})

    def launch_app(self, name: str) -> None:
        backend = self._ensure_backend()
        backend.launch_app(name)
        logger.debug("launch_app", extra={"fields": {"name": name}})

    def media_play_pause(self) -> None:
        backend = self._ensure_backend()
        backend.media_play_pause()
        logger.debug("media_play_pause", extra={"fields": {}})

    def space_next(self) -> None:
        backend = self._ensure_backend()
        backend.space_next()
        logger.debug("space_next", extra={"fields": {}})

    def space_previous(self) -> None:
        backend = self._ensure_backend()
        backend.space_previous()
        logger.debug("space_previous", extra={"fields": {}})

    # -- Later phases: declared now for a stable contract, not yet real -

    def key_press(self, key: str) -> None:
        raise NotImplementedError("Key press support lands in a later phase")
