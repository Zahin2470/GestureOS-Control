from gestureos.commands.router import CommandRouter
from gestureos.commands.safety import SafetyPolicy
from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import Intent, IntentPhase
from gestureos.macos.fake_adapter import FakeMacOSAdapter
from gestureos.models import ControlState


def _intent(gesture: GestureType, phase: IntentPhase, timestamp: float = 0.0) -> Intent:
    return Intent(
        gesture=gesture, phase=phase, confidence=0.9, handedness="right", timestamp=timestamp
    )


def test_pinch_start_dispatches_mouse_down_on_adapter() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    command = router.route_intent(_intent(GestureType.PINCH, IntentPhase.START))

    assert command is not None
    assert len(adapter.calls_of("mouse_down")) == 1


def test_pinch_end_dispatches_mouse_up_on_adapter() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START))
    command = router.route_intent(_intent(GestureType.PINCH, IntentPhase.END))

    assert command is not None
    assert len(adapter.calls_of("mouse_up")) == 1


def test_unbound_gesture_dispatches_nothing() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    command = router.route_intent(_intent(GestureType.OPEN_PALM, IntentPhase.START))

    assert command is None
    assert adapter.calls == []


def test_paused_control_blocks_mouse_down_but_not_mouse_up() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.PAUSED)
    router = CommandRouter(adapter=adapter, safety=safety)

    down = router.route_intent(_intent(GestureType.PINCH, IntentPhase.START))
    up = router.route_intent(_intent(GestureType.PINCH, IntentPhase.END))

    assert down is None
    assert up is not None
    assert adapter.calls_of("mouse_down") == []
    assert len(adapter.calls_of("mouse_up")) == 1


def test_route_intents_processes_a_batch_and_drops_unbound_ones() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    intents = (
        _intent(GestureType.OPEN_PALM, IntentPhase.START),  # unbound
        _intent(GestureType.PINCH, IntentPhase.START),  # bound
    )

    commands = router.route_intents(intents)

    assert len(commands) == 1
    assert commands[0].type.value == "mouse_down"
