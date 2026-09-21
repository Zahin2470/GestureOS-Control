from gestureos.vision.features import FeatureExtractor
from gestureos.vision.normalization import normalize_frame_features
from tests.vision_helpers import make_open_hand


def _scale_hand(hand, factor: float):
    """Return a RawHand-shaped copy scaled toward the wrist, simulating
    the same hand pose photographed closer to (factor>1) or farther from
    (factor<1) the camera.
    """
    from gestureos.vision.tracker import Landmark, RawHand

    anchor = hand.landmarks[0]  # wrist
    scaled = tuple(
        Landmark(
            x=anchor.x + (lm.x - anchor.x) * factor,
            y=anchor.y + (lm.y - anchor.y) * factor,
        )
        for lm in hand.landmarks
    )
    return RawHand(
        landmarks=scaled,
        handedness=hand.handedness,
        handedness_confidence=hand.handedness_confidence,
    )


def test_normalized_pinch_distance_is_scale_invariant() -> None:
    near_hand = make_open_hand()
    far_hand = _scale_hand(near_hand, 0.5)  # same pose, half the size (farther away)

    extractor = FeatureExtractor()
    near_frame = normalize_frame_features(extractor.process((near_hand,)))
    far_frame = normalize_frame_features(extractor.process((far_hand,)))

    near_pinch = near_frame.hands[0].pinch_distance
    far_pinch = far_frame.hands[0].pinch_distance
    assert near_pinch is not None and far_pinch is not None
    assert abs(near_pinch - far_pinch) < 1e-9


def test_raw_pinch_distance_is_not_scale_invariant() -> None:
    near_hand = make_open_hand()
    far_hand = _scale_hand(near_hand, 0.5)

    extractor = FeatureExtractor()
    near_frame = extractor.process((near_hand,))
    far_frame = extractor.process((far_hand,))

    near_pinch = near_frame.hands[0].pinch_distance
    far_pinch = far_frame.hands[0].pinch_distance
    assert near_pinch is not None and far_pinch is not None
    assert abs(near_pinch - far_pinch) > 1e-6


def test_normalization_is_a_noop_when_hand_absent() -> None:
    extractor = FeatureExtractor()
    frame = extractor.process(())

    normalized = normalize_frame_features(frame)

    assert normalized.hands == ()
