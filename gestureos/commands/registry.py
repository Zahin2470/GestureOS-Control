"""
Command registry (Sections 20-21).

Maps a confirmed gesture Intent (gesture + phase) to a CommandType.
Deliberately a small, explicit table: later phases (media, Spaces) add
bindings here — one dict entry each — without touching the router or
safety layer.

Phase 4 bound PINCH start/end to MOUSE_DOWN/MOUSE_UP. Phase 6 added
PINCH+HOLD → MOUSE_MOVE, so the router can track cursor position while
a pinch is held (drag.py then decides, frame by frame, whether that
movement is big enough to actually move the cursor yet). Phase 7 binds
all three TWO_FINGER_SCROLL phases to SCROLL — the router (via
scroll.py) uses source_phase to know whether to start, continue, or end
the scroll tracking. Phase 8 binds all three FIST phases to APP_SWITCH
the same way — the router (via switch.py) turns a big enough horizontal
swipe into a single switch_app_next/previous call.
"""

from __future__ import annotations

from gestureos.commands.types import CommandType
from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import Intent, IntentPhase

_BINDINGS: dict[tuple[GestureType, IntentPhase], CommandType] = {
    (GestureType.PINCH, IntentPhase.START): CommandType.MOUSE_DOWN,
    (GestureType.PINCH, IntentPhase.HOLD): CommandType.MOUSE_MOVE,
    (GestureType.PINCH, IntentPhase.END): CommandType.MOUSE_UP,
    (GestureType.TWO_FINGER_SCROLL, IntentPhase.START): CommandType.SCROLL,
    (GestureType.TWO_FINGER_SCROLL, IntentPhase.HOLD): CommandType.SCROLL,
    (GestureType.TWO_FINGER_SCROLL, IntentPhase.END): CommandType.SCROLL,
    (GestureType.FIST, IntentPhase.START): CommandType.APP_SWITCH,
    (GestureType.FIST, IntentPhase.HOLD): CommandType.APP_SWITCH,
    (GestureType.FIST, IntentPhase.END): CommandType.APP_SWITCH,
}


def resolve_command_type(intent: Intent) -> CommandType | None:
    """Return the CommandType bound to this intent, or None if this
    gesture/phase combination has no binding yet.
    """
    return _BINDINGS.get((intent.gesture, intent.phase))
