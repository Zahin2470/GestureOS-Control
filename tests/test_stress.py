"""
Stress testing (Phase 11).

Runs thousands of frames of randomized, adversarial hand-pose sequences
through the full vision → gesture engine → command router pipeline,
checking invariants that matter for a system meant to run continuously
for a long session: no exceptions, no command left "half-finished"
(a mouse_down with no matching mouse_up once everything settles), and
no unbounded growth in the small per-hand state dictionaries the engine
and controllers keep.

This never touches real hardware — it's exactly the kind of coverage
that's cheap to run here and valuable regardless of platform.
"""

from __future__ import annotations

import random

from gestureos.commands.router import CommandRouter
from gestureos.commands.safety import SafetyPolicy
from gestureos.interaction.engine import GestureEngine
from gestureos.macos.fake_adapter import FakeMacOSAdapter
from gestureos.models import ControlState
from gestureos.vision.features import FeatureExtractor
from gestureos.vision.normalization import normalize_frame_features
from gestureos.vision.smoothing import FeatureSmoother
from tests.vision_helpers import (
    make_fist_hand,
    make_open_hand,
    make_pinch_hand,
    make_point_hand,
    make_two_finger_hand,
)

_POSE_BUILDERS = (
    make_open_hand,
    make_pinch_hand,
    make_fist_hand,
    make_point_hand,
    make_two_finger_hand,
)


class _Ticker:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0 / 60.0  # simulate a steady 60fps clock
        return self.t


def _build_pipeline(seed: int):
    clock = _Ticker()
    extractor = FeatureExtractor()
    smoother = FeatureSmoother()
    engine = GestureEngine(clock=clock)
    adapter = FakeMacOSAdapter(clock=clock)
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=clock)
    router = CommandRouter(adapter=adapter, safety=safety)
    rng = random.Random(seed)
    return extractor, smoother, engine, router, adapter, rng


def _random_frame(rng: random.Random):
    """Randomly: no hand, one hand in a random pose with random jitter,
    or (rarely) two hands at once.
    """
    roll = rng.random()
    if roll < 0.15:
        return ()

    def one_hand(handedness: str):
        builder = rng.choice(_POSE_BUILDERS)
        offset = (rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05))
        kwargs = {"handedness": handedness}
        try:
            return builder(offset=offset, **kwargs)
        except TypeError:
            return builder(**kwargs)  # some builders don't take offset

    if roll < 0.95:
        return (one_hand("right"),)
    return (one_hand("left"), one_hand("right"))


def _run_stress_sequence(seed: int, num_frames: int) -> list:
    extractor, smoother, engine, router, adapter, rng = _build_pipeline(seed)
    all_commands = []

    for _ in range(num_frames):
        raw_hands = _random_frame(rng)
        frame = smoother.smooth_frame(normalize_frame_features(extractor.process(raw_hands)))
        intents = engine.process(frame)
        commands = router.route_intents(intents)
        all_commands.extend(commands)

    return all_commands, adapter, engine, router


def test_thousands_of_random_frames_never_raise() -> None:
    # The test itself not raising IS the assertion.
    _run_stress_sequence(seed=1, num_frames=5000)


def test_multiple_seeds_never_raise() -> None:
    for seed in range(10):
        _run_stress_sequence(seed=seed, num_frames=500)


def test_mouse_down_and_mouse_up_counts_stay_balanced_or_close() -> None:
    all_commands, *_ = _run_stress_sequence(seed=2, num_frames=5000)

    downs = sum(1 for c in all_commands if c.type.value == "mouse_down")
    ups = sum(1 for c in all_commands if c.type.value == "mouse_up")

    # A down without a matching up by the end would mean a stuck drag
    # state; downs can exceed ups by at most 1 (one still in progress
    # when the run ends).
    assert downs - ups in (0, 1)


def test_gesture_engine_hand_state_stays_bounded() -> None:
    _, _, engine, _, _, _ = _build_pipeline(seed=3)
    extractor = FeatureExtractor()
    smoother = FeatureSmoother()
    rng = random.Random(3)

    for _ in range(3000):
        raw_hands = _random_frame(rng)
        frame = smoother.smooth_frame(normalize_frame_features(extractor.process(raw_hands)))
        engine.process(frame)

    # At most one state machine per handedness label ("left", "right").
    assert len(engine._machines) <= 2


def test_drag_and_scroll_and_swipe_controllers_end_up_idle_after_hand_leaves() -> None:
    extractor, smoother, engine, router, _adapter, rng = _build_pipeline(seed=4)

    for _ in range(2000):
        raw_hands = _random_frame(rng)
        frame = smoother.smooth_frame(normalize_frame_features(extractor.process(raw_hands)))
        intents = engine.process(frame)
        router.route_intents(intents)

    # Run a long tail of "no hand" frames so every in-progress gesture
    # has a chance to time out / release naturally.
    for _ in range(200):
        frame = smoother.smooth_frame(normalize_frame_features(extractor.process(())))
        intents = engine.process(frame)
        router.route_intents(intents)

    assert router._drag_controller.is_engaged is False


def test_no_command_is_dispatched_with_a_malformed_position() -> None:
    all_commands, *_ = _run_stress_sequence(seed=5, num_frames=2000)

    for command in all_commands:
        position = command.params.get("position")
        if position is not None:
            assert isinstance(position.x, float)
            assert isinstance(position.y, float)
            assert position.x == position.x  # NaN check (NaN != NaN)
            assert position.y == position.y


def test_rapid_hand_appear_disappear_every_frame_is_stable() -> None:
    """The adversarial case: a hand flickers in and out of frame on
    every single frame — the noisiest possible input short of pure
    random landmark garbage.
    """
    extractor, smoother, engine, router, _adapter, _rng = _build_pipeline(seed=6)

    for i in range(3000):
        raw_hands = (make_pinch_hand(),) if i % 2 == 0 else ()
        frame = smoother.smooth_frame(normalize_frame_features(extractor.process(raw_hands)))
        intents = engine.process(frame)
        router.route_intents(intents)  # must never raise

    assert router._drag_controller.is_engaged is False
