import pytest

from gestureos.interaction.cooldown import CooldownGate


def test_key_is_ready_before_first_trigger() -> None:
    gate = CooldownGate(cooldown_s=1.0)

    assert gate.is_ready("pinch", now=0.0) is True


def test_key_not_ready_immediately_after_trigger() -> None:
    gate = CooldownGate(cooldown_s=1.0)
    gate.mark_triggered("pinch", now=10.0)

    assert gate.is_ready("pinch", now=10.5) is False


def test_key_ready_once_cooldown_elapses() -> None:
    gate = CooldownGate(cooldown_s=1.0)
    gate.mark_triggered("pinch", now=10.0)

    assert gate.is_ready("pinch", now=11.0) is True


def test_keys_are_independent() -> None:
    gate = CooldownGate(cooldown_s=1.0)
    gate.mark_triggered("pinch", now=10.0)

    assert gate.is_ready("fist", now=10.1) is True


def test_reset_single_key() -> None:
    gate = CooldownGate(cooldown_s=1.0)
    gate.mark_triggered("pinch", now=10.0)
    gate.mark_triggered("fist", now=10.0)

    gate.reset("pinch")

    assert gate.is_ready("pinch", now=10.1) is True
    assert gate.is_ready("fist", now=10.1) is False


def test_reset_all_keys() -> None:
    gate = CooldownGate(cooldown_s=1.0)
    gate.mark_triggered("pinch", now=10.0)
    gate.mark_triggered("fist", now=10.0)

    gate.reset()

    assert gate.is_ready("pinch", now=10.1) is True
    assert gate.is_ready("fist", now=10.1) is True


def test_negative_cooldown_rejected() -> None:
    with pytest.raises(ValueError):
        CooldownGate(cooldown_s=-1.0)
