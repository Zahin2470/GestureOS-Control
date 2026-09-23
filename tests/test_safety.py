import pytest

from gestureos.commands.safety import SafetyPolicy
from gestureos.commands.types import Command, CommandType
from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import IntentPhase
from gestureos.models import ControlState


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _command(command_type: CommandType, timestamp: float = 0.0) -> Command:
    return Command(
        type=command_type,
        source_gesture=GestureType.PINCH,
        source_phase=IntentPhase.START,
        handedness="right",
        timestamp=timestamp,
    )


def test_command_allowed_when_control_active() -> None:
    policy = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)

    decision = policy.check(_command(CommandType.MOUSE_DOWN))

    assert decision.allowed is True


def test_command_blocked_when_control_paused() -> None:
    policy = SafetyPolicy(get_control_state=lambda: ControlState.PAUSED)

    decision = policy.check(_command(CommandType.MOUSE_DOWN))

    assert decision.allowed is False
    assert decision.reason == "control_paused"


def test_mouse_up_allowed_even_when_control_paused() -> None:
    policy = SafetyPolicy(get_control_state=lambda: ControlState.PAUSED)

    decision = policy.check(_command(CommandType.MOUSE_UP))

    assert decision.allowed is True


def test_rapid_commands_are_rate_limited() -> None:
    clock = FakeClock()
    policy = SafetyPolicy(
        get_control_state=lambda: ControlState.ACTIVE,
        max_commands_per_second=10.0,  # min interval 0.1s
        clock=clock,
    )

    first = policy.check(_command(CommandType.SCROLL))
    clock.advance(0.02)  # well under 0.1s
    second = policy.check(_command(CommandType.SCROLL))

    assert first.allowed is True
    assert second.allowed is False
    assert second.reason == "rate_limited"


def test_commands_allowed_again_after_min_interval_elapses() -> None:
    clock = FakeClock()
    policy = SafetyPolicy(
        get_control_state=lambda: ControlState.ACTIVE,
        max_commands_per_second=10.0,
        clock=clock,
    )

    policy.check(_command(CommandType.SCROLL))
    clock.advance(0.15)
    decision = policy.check(_command(CommandType.SCROLL))

    assert decision.allowed is True


def test_mouse_up_never_consumes_the_rate_limit_budget() -> None:
    clock = FakeClock()
    policy = SafetyPolicy(
        get_control_state=lambda: ControlState.ACTIVE,
        max_commands_per_second=10.0,
        clock=clock,
    )

    policy.check(_command(CommandType.SCROLL))  # consumes the budget at t=0
    clock.advance(0.01)
    # MOUSE_UP bypasses the limiter entirely and doesn't reset its timer.
    up_decision = policy.check(_command(CommandType.MOUSE_UP))
    clock.advance(0.01)
    scroll_decision = policy.check(_command(CommandType.SCROLL))  # still within 0.1s of t=0

    assert up_decision.allowed is True
    assert scroll_decision.allowed is False


def test_invalid_rate_rejected() -> None:
    with pytest.raises(ValueError):
        SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, max_commands_per_second=0)
