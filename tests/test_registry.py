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


def test_pinch_hold_maps_to_mouse_move() -> None:
    command_type = resolve_command_type(_intent(GestureType.PINCH, IntentPhase.HOLD))

    assert command_type == CommandType.MOUSE_MOVE


def test_unbound_gesture_phase_returns_none() -> None:
    # OPEN_PALM is now bound at START (media play/pause), but HOLD is
    # deliberately left unbound so a held palm doesn't repeatedly toggle.
    command_type = resolve_command_type(_intent(GestureType.OPEN_PALM, IntentPhase.HOLD))

    assert command_type is None


def test_open_palm_start_maps_to_media_play_pause() -> None:
    command_type = resolve_command_type(_intent(GestureType.OPEN_PALM, IntentPhase.START))

    assert command_type == CommandType.MEDIA_PLAY_PAUSE


def test_open_palm_end_has_no_binding() -> None:
    assert resolve_command_type(_intent(GestureType.OPEN_PALM, IntentPhase.END)) is None


def test_point_all_phases_map_to_space_switch() -> None:
    assert (
        resolve_command_type(_intent(GestureType.POINT, IntentPhase.START))
        == CommandType.SPACE_SWITCH
    )
    assert (
        resolve_command_type(_intent(GestureType.POINT, IntentPhase.HOLD))
        == CommandType.SPACE_SWITCH
    )
    assert (
        resolve_command_type(_intent(GestureType.POINT, IntentPhase.END))
        == CommandType.SPACE_SWITCH
    )


def test_two_finger_scroll_all_phases_map_to_scroll() -> None:
    assert (
        resolve_command_type(_intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.START))
        == CommandType.SCROLL
    )
    assert (
        resolve_command_type(_intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.HOLD))
        == CommandType.SCROLL
    )
    assert (
        resolve_command_type(_intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.END))
        == CommandType.SCROLL
    )


def test_fist_all_phases_map_to_app_switch() -> None:
    assert (
        resolve_command_type(_intent(GestureType.FIST, IntentPhase.START))
        == CommandType.APP_SWITCH
    )
    assert (
        resolve_command_type(_intent(GestureType.FIST, IntentPhase.HOLD))
        == CommandType.APP_SWITCH
    )
    assert (
        resolve_command_type(_intent(GestureType.FIST, IntentPhase.END))
        == CommandType.APP_SWITCH
    )
