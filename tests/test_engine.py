from gestureos.interaction.engine import GestureEngine
from gestureos.interaction.state_machine import IntentPhase
from gestureos.vision.features import FeatureExtractor
from gestureos.vision.normalization import normalize_frame_features
from gestureos.vision.smoothing import FeatureSmoother
from tests.test_state_machine import FakeClock
from tests.vision_helpers import make_open_hand, make_pinch_hand


def _run_pipeline(raw_hand_sequence, engine, extractor, smoother):
    intents_per_frame = []
    for raw_hands in raw_hand_sequence:
        frame = extractor.process(raw_hands)
        frame = normalize_frame_features(frame)
        frame = smoother.smooth_frame(frame)
        intents_per_frame.append(engine.process(frame))
    return intents_per_frame


def test_sustained_pinch_across_frames_produces_start_hold_end() -> None:
    clock = FakeClock()
    engine = GestureEngine(min_hold_time_s=0.05, cooldown_s=0.1, vote_window_size=3, clock=clock)
    extractor = FeatureExtractor()
    smoother = FeatureSmoother()

    sequence = []
    # A few pinch frames (builds vote + confirm timer)...
    for _ in range(5):
        sequence.append((make_pinch_hand(),))
    # ...then the hand opens (gesture ends).
    for _ in range(3):
        sequence.append((make_open_hand(),))

    all_intents = []
    for raw_hands in sequence:
        frame = smoother.smooth_frame(normalize_frame_features(extractor.process(raw_hands)))
        all_intents.extend(engine.process(frame))
        clock.advance(0.03)

    phases = [i.phase for i in all_intents]
    assert IntentPhase.START in phases
    assert IntentPhase.END in phases
    # START must come before END.
    assert phases.index(IntentPhase.START) < phases.index(IntentPhase.END)


def test_brief_single_frame_flicker_produces_no_intent() -> None:
    clock = FakeClock()
    engine = GestureEngine(min_hold_time_s=0.15, cooldown_s=0.1, vote_window_size=5, clock=clock)
    extractor = FeatureExtractor()
    smoother = FeatureSmoother()

    all_intents = []
    # Only one pinch frame among open-hand frames — should never confirm.
    sequence = [
        (make_open_hand(),),
        (make_open_hand(),),
        (make_pinch_hand(),),
        (make_open_hand(),),
        (make_open_hand(),),
    ]
    for raw_hands in sequence:
        frame = smoother.smooth_frame(normalize_frame_features(extractor.process(raw_hands)))
        all_intents.extend(engine.process(frame))
        clock.advance(0.03)

    assert all_intents == []


def test_no_hands_in_frame_produces_no_intents() -> None:
    clock = FakeClock()
    engine = GestureEngine(clock=clock)
    extractor = FeatureExtractor()
    smoother = FeatureSmoother()

    frame = smoother.smooth_frame(normalize_frame_features(extractor.process(())))
    intents = engine.process(frame)

    assert intents == ()
