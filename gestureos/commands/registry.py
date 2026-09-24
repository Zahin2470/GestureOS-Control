"""
Command registry (Sections 20-21).

Maps a confirmed gesture Intent (gesture + phase) to a CommandType.
Deliberately a small, explicit table: later phases (scroll, app
switching, media, Spaces) add bindings here — one dict entry each —
without touching the router or safety layer.

Phase 4 bound PINCH start/end to MOUSE_DOWN/MOUSE_UP. Phase 6 adds
PINCH+HOLD → MOUSE_MOVE, so the router can track cursor position while
a pinch is held (drag.py then decides, frame by frame, whether that
movement is big enough to actually move the cursor yet).
"""

from __future__ import annotations

from gestureos.commands.types import CommandType
from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import Intent, IntentPhase

_BINDINGS: dict[tuple[GestureType, IntentPhase], CommandType] = {
    (GestureType.PINCH, IntentPhase.START): CommandType.MOUSE_DOWN,
    (GestureType.PINCH, IntentPhase.HOLD): CommandType.MOUSE_MOVE,
    (GestureType.PINCH, IntentPhase.END): CommandType.MOUSE_UP,
}


def resolve_command_type(intent: Intent) -> CommandType | None:
    """Return the CommandType bound to this intent, or None if this
    gesture/phase combination has no binding yet (most of them don't,
    in Phase 4 — that's expected, not an error).
    """
    return _BINDINGS.get((intent.gesture, intent.phase))
