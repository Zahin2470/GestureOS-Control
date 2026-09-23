import pytest

from gestureos.interaction.confidence import StableCandidate
from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import GestureStateMachine, IntentPhase


class FakeClock:
    """Manually advanceable clock for deterministic timing tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _machine(**overrides) -> tuple[GestureStateMachine, FakeClock]:
    clock = FakeClock()
    defaults = dict(
        activate_threshold=0.6,
        release_threshold=0.4,
        min_hold_time_s=0.15,
        cooldown_s=0.35,
        clock=clock,
    )
    defaults.update(overrides)
    return GestureStateMachine(**defaults), clock


def _candidate(gesture: GestureType, confidence: float = 0.9, handedness: str = "right"):
    return StableCandidate(gesture=gesture, confidence=confidence, handedness=handedness)


def test_no_intent_from_a_single_confident_frame_below_min_hold_time() -> None:
    machine, clock = _machine(min_hold_time_s=0.15)

    intent = machine.update(_candidate(GestureType.PINCH))

    assert intent is None


def test_start_intent_fires_after_min_hold_time_elapses() -> None:
    machine, clock = _machine(min_hold_time_s=0.15)

    machine.update(_candidate(GestureType.PINCH))  # begins CONFIRMING
    clock.advance(0.10)
    assert machine.update(_candidate(GestureType.PINCH)) is None  # still under 0.15s

    clock.advance(0.10)  # total 0.20s >= 0.15s
    intent = machine.update(_candidate(GestureType.PINCH))

    assert intent is not None
    assert intent.gesture == GestureType.PINCH
    assert intent.phase == IntentPhase.START


def test_low_confidence_candidate_never_starts_confirming() -> None:
    machine, clock = _machine(activate_threshold=0.6)

    intent = machine.update(_candidate(GestureType.PINCH, confidence=0.3))
    clock.advance(1.0)
    intent2 = machine.update(_candidate(GestureType.PINCH, confidence=0.3))

    assert intent is None
    assert intent2 is None


def test_gesture_switch_during_confirming_aborts_to_idle() -> None:
    machine, clock = _machine(min_hold_time_s=0.15)

    machine.update(_candidate(GestureType.PINCH))
    clock.advance(0.05)
    machine.update(_candidate(GestureType.OPEN_PALM, confidence=0.9))  # switched — aborts
    clock.advance(0.20)
    intent = machine.update(_candidate(GestureType.OPEN_PALM, confidence=0.9))

    # Aborting resets the confirm timer, so open_palm needs its own full
    # min_hold_time_s from the frame it took over.
    assert intent is None


def test_hold_intents_fire_while_gesture_remains_active() -> None:
    machine, clock = _machine(min_hold_time_s=0.1)
    machine.update(_candidate(GestureType.PINCH))
    clock.advance(0.15)
    start = machine.update(_candidate(GestureType.PINCH))
    assert start.phase == IntentPhase.START

    clock.advance(0.05)
    hold = machine.update(_candidate(GestureType.PINCH))

    assert hold is not None
    assert hold.phase == IntentPhase.HOLD
    assert hold.gesture == GestureType.PINCH


def test_hysteresis_keeps_gesture_active_at_moderate_confidence_dip() -> None:
    machine, clock = _machine(
        min_hold_time_s=0.1, activate_threshold=0.6, release_threshold=0.4
    )
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))
    clock.advance(0.15)
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))  # START

    clock.advance(0.05)
    # Confidence dips below activate_threshold but stays above release_threshold.
    hold = machine.update(_candidate(GestureType.PINCH, confidence=0.5))

    assert hold is not None
    assert hold.phase == IntentPhase.HOLD


def test_end_intent_fires_when_confidence_drops_below_release_threshold() -> None:
    machine, clock = _machine(
        min_hold_time_s=0.1, activate_threshold=0.6, release_threshold=0.4
    )
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))
    clock.advance(0.15)
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))  # START

    clock.advance(0.05)
    end = machine.update(_candidate(GestureType.NONE, confidence=0.0))

    assert end is not None
    assert end.phase == IntentPhase.END
    assert end.gesture == GestureType.PINCH


def test_no_new_gesture_can_start_during_cooldown() -> None:
    machine, clock = _machine(min_hold_time_s=0.1, cooldown_s=0.35)
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))
    clock.advance(0.15)
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))  # START
    clock.advance(0.05)
    machine.update(_candidate(GestureType.NONE, confidence=0.0))  # END -> COOLDOWN

    clock.advance(0.10)  # still within 0.35s cooldown
    intent = machine.update(_candidate(GestureType.PINCH, confidence=0.9))

    assert intent is None


def test_new_gesture_can_start_once_cooldown_elapses() -> None:
    machine, clock = _machine(min_hold_time_s=0.1, cooldown_s=0.35)
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))
    clock.advance(0.15)
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))  # START
    clock.advance(0.05)
    machine.update(_candidate(GestureType.NONE, confidence=0.0))  # END -> COOLDOWN

    clock.advance(0.40)  # cooldown elapsed
    machine.update(_candidate(GestureType.PINCH, confidence=0.9))  # begins CONFIRMING again
    clock.advance(0.15)
    intent = machine.update(_candidate(GestureType.PINCH, confidence=0.9))

    assert intent is not None
    assert intent.phase == IntentPhase.START


def test_full_lifecycle_produces_exactly_one_start_and_one_end() -> None:
    machine, clock = _machine(min_hold_time_s=0.1, cooldown_s=0.2)
    intents = []

    intents.append(machine.update(_candidate(GestureType.PINCH, confidence=0.9)))
    clock.advance(0.15)
    intents.append(machine.update(_candidate(GestureType.PINCH, confidence=0.9)))
    clock.advance(0.05)
    intents.append(machine.update(_candidate(GestureType.PINCH, confidence=0.9)))
    clock.advance(0.05)
    intents.append(machine.update(_candidate(GestureType.NONE, confidence=0.0)))

    phases = [i.phase for i in intents if i is not None]
    assert phases == [IntentPhase.START, IntentPhase.HOLD, IntentPhase.END]


def test_invalid_threshold_ordering_rejected() -> None:
    with pytest.raises(ValueError):
        GestureStateMachine(activate_threshold=0.3, release_threshold=0.6)
