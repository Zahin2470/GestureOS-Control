from gestureos.interaction.gestures import GestureType, classify_gesture
from gestureos.vision.features import FeatureExtractor
from gestureos.vision.normalization import normalize_hand_features
from tests.vision_helpers import (
    make_fist_hand,
    make_open_hand,
    make_pinch_hand,
    make_point_hand,
)


def _classify_pose(raw_hand) -> GestureType:
    extractor = FeatureExtractor()
    frame = extractor.process((raw_hand,))
    normalized = normalize_hand_features(frame.hands[0])
    return classify_gesture(normalized).gesture


def test_absent_hand_classifies_as_none() -> None:
    from gestureos.vision.features import HandFeatures

    candidate = classify_gesture(HandFeatures.absent())

    assert candidate.gesture == GestureType.NONE
    assert candidate.confidence == 1.0
    assert candidate.handedness is None


def test_open_hand_classifies_as_open_palm() -> None:
    assert _classify_pose(make_open_hand()) == GestureType.OPEN_PALM


def test_pinch_hand_classifies_as_pinch() -> None:
    assert _classify_pose(make_pinch_hand()) == GestureType.PINCH


def test_fist_hand_classifies_as_fist() -> None:
    assert _classify_pose(make_fist_hand()) == GestureType.FIST


def test_point_hand_classifies_as_point() -> None:
    assert _classify_pose(make_point_hand()) == GestureType.POINT


def test_candidate_carries_handedness_through() -> None:
    extractor = FeatureExtractor()
    frame = extractor.process((make_pinch_hand(handedness="left"),))
    normalized = normalize_hand_features(frame.hands[0])

    candidate = classify_gesture(normalized)

    assert candidate.handedness == "left"


def test_pinch_confidence_increases_as_fingers_close() -> None:
    extractor = FeatureExtractor()

    wide_frame = extractor.process((make_pinch_hand(pinch_gap=0.08),))
    tight_frame = extractor.process((make_pinch_hand(pinch_gap=0.005),))

    wide = classify_gesture(normalize_hand_features(wide_frame.hands[0]))
    tight = classify_gesture(normalize_hand_features(tight_frame.hands[0]))

    assert tight.confidence > wide.confidence
