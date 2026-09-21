from gestureos.vision.features import (
    FeatureExtractor,
    MotionDirection,
    TwoHandState,
)
from tests.vision_helpers import make_open_hand, make_pinch_hand


def test_no_hands_reports_absent_and_none_state() -> None:
    extractor = FeatureExtractor()

    frame = extractor.process(())

    assert frame.two_hand_state == TwoHandState.NONE
    assert frame.hands == ()


def test_single_open_hand_reports_present_with_geometry() -> None:
    extractor = FeatureExtractor()
    raw = (make_open_hand(),)

    frame = extractor.process(raw)

    assert frame.two_hand_state == TwoHandState.SINGLE
    assert len(frame.hands) == 1
    hand = frame.hands[0]
    assert hand.hand_present is True
    assert hand.handedness == "right"
    assert hand.palm_center is not None
    assert hand.palm_width is not None and hand.palm_width > 0
    assert hand.pinch_distance is not None and hand.pinch_distance > 0


def test_open_hand_all_fingers_extended() -> None:
    extractor = FeatureExtractor()
    frame = extractor.process((make_open_hand(),))

    states = frame.hands[0].finger_extension_states
    assert states is not None
    assert all([states.thumb, states.index, states.middle, states.ring, states.pinky])


def test_pinch_hand_curled_fingers_not_extended() -> None:
    extractor = FeatureExtractor()
    frame = extractor.process((make_pinch_hand(),))

    states = frame.hands[0].finger_extension_states
    assert states is not None
    assert states.middle is False
    assert states.ring is False
    assert states.pinky is False


def test_pinch_distance_smaller_for_pinch_pose_than_open_pose() -> None:
    extractor = FeatureExtractor()
    open_frame = extractor.process((make_open_hand(),))
    pinch_frame = extractor.process((make_pinch_hand(),))

    open_pinch_distance = open_frame.hands[0].pinch_distance
    pinch_pinch_distance = pinch_frame.hands[0].pinch_distance
    assert open_pinch_distance is not None and pinch_pinch_distance is not None
    assert pinch_pinch_distance < open_pinch_distance


def test_two_hands_reports_both_state() -> None:
    extractor = FeatureExtractor()
    raw = (make_open_hand("left"), make_open_hand("right"))

    frame = extractor.process(raw)

    assert frame.two_hand_state == TwoHandState.BOTH
    assert len(frame.hands) == 2


def test_first_sighting_has_zero_velocity() -> None:
    extractor = FeatureExtractor()

    frame = extractor.process((make_open_hand(),))

    velocity = frame.hands[0].velocity
    assert velocity is not None
    assert velocity.x == 0.0
    assert velocity.y == 0.0
    assert frame.hands[0].motion_direction == MotionDirection.NONE


def test_moving_hand_reports_direction() -> None:
    extractor = FeatureExtractor()
    extractor.process((make_open_hand(offset=(0.0, 0.0)),))

    frame = extractor.process((make_open_hand(offset=(0.10, 0.0)),))

    hand = frame.hands[0]
    assert hand.velocity is not None
    assert hand.velocity.x > 0
    assert hand.motion_direction == MotionDirection.RIGHT


def test_hand_disappearing_and_reappearing_resets_velocity() -> None:
    extractor = FeatureExtractor()
    extractor.process((make_open_hand(offset=(0.0, 0.0)),))
    extractor.process(())  # hand leaves frame

    frame = extractor.process((make_open_hand(offset=(0.30, 0.30)),))

    # Without the reset, this large jump would register as a huge
    # velocity spike instead of a fresh sighting.
    assert frame.hands[0].velocity == type(frame.hands[0].velocity)(0.0, 0.0)
