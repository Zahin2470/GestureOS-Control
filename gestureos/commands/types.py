"""
Command vocabulary.

A Command is what a confirmed gesture Intent turns into once the
registry (registry.py) has decided it means something actionable. The
router (router.py) is the only thing that turns a Command into a real
(or simulated) macOS side effect, after the safety policy (safety.py)
has approved it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import IntentPhase


class CommandType(str, Enum):
    MOUSE_DOWN = "mouse_down"
    MOUSE_MOVE = "mouse_move"
    MOUSE_UP = "mouse_up"
    SCROLL = "scroll"
    SWITCH_APP_NEXT = "switch_app_next"
    SWITCH_APP_PREVIOUS = "switch_app_previous"
    LAUNCH_APP = "launch_app"
    MEDIA_PLAY_PAUSE = "media_play_pause"
    SPACE_NEXT = "space_next"
    SPACE_PREVIOUS = "space_previous"


# Commands that release/undo state already in progress (a held mouse
# button, in Phase 4) rather than starting something new. The safety
# policy always lets these through — see safety.py for why.
RELEASE_COMMAND_TYPES = frozenset({CommandType.MOUSE_UP})


@dataclass(frozen=True)
class Command:
    type: CommandType
    source_gesture: GestureType
    source_phase: IntentPhase
    handedness: str | None
    timestamp: float
    params: dict[str, Any] = field(default_factory=dict)
