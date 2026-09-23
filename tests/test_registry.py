from gestureos.commands.registry import resolve_command_type
from gestureos.commands.types import CommandType
from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import Intent, IntentPhase


def _intent(gesture: GestureType, phase: IntentPhase) -> Intent:
    return Intent(gesture=gesture, phase=phase, confidence=0.9, handedness="right", timestamp=0.0)


def test_pinch_start_maps_to_mouse_down() -> None:
    command_type = resolve_command_type(_intent(GestureType.PINCH, IntentPhase.START))

    assert command_type == CommandType.MOUSE_DOWN


def test_pinch_end_maps_to_mouse_up() -> None:
    command_type = resolve_command_type(_intent(GestureType.PINCH, IntentPhase.END))

    assert command_type == CommandType.MOUSE_UP


def test_pinch_hold_has_no_binding_yet() -> None:
    command_type = resolve_command_type(_intent(GestureType.PINCH, IntentPhase.HOLD))

    assert command_type is None


def test_unbound_gesture_returns_none() -> None:
    command_type = resolve_command_type(_intent(GestureType.OPEN_PALM, IntentPhase.START))

    assert command_type is None


def test_fist_and_point_are_unbound_in_phase_4() -> None:
    assert resolve_command_type(_intent(GestureType.FIST, IntentPhase.START)) is None
    assert resolve_command_type(_intent(GestureType.POINT, IntentPhase.START)) is None
