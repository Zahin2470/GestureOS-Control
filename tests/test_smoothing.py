import pytest

from gestureos.vision.features import FeatureExtractor, Point2D
from gestureos.vision.smoothing import (
    ExponentialSmoother,
    FeatureSmoother,
    Point2DSmoother,
)
from tests.vision_helpers import make_open_hand


def test_exponential_smoother_first_update_returns_value_unchanged() -> None:
    smoother = ExponentialSmoother(alpha=0.5)

    assert smoother.update(10.0) == 10.0


def test_exponential_smoother_converges_toward_repeated_value() -> None:
    smoother = ExponentialSmoother(alpha=0.5)
    smoother.update(0.0)

    for _ in range(20):
        result = smoother.update(10.0)

    assert result == pytest.approx(10.0, abs=1e-3)


def test_exponential_smoother_rejects_invalid_alpha() -> None:
    with pytest.raises(ValueError):
        ExponentialSmoother(alpha=0.0)
    with pytest.raises(ValueError):
        ExponentialSmoother(alpha=1.5)


def test_exponential_smoother_reset_forgets_history() -> None:
    smoother = ExponentialSmoother(alpha=0.5)
    smoother.update(10.0)
    smoother.reset()

    assert smoother.update(3.0) == 3.0


def test_point2d_smoother_smooths_each_axis_independently() -> None:
    smoother = Point2DSmoother(alpha=0.5)
    smoother.update(Point2D(0.0, 100.0))

    result = smoother.update(Point2D(10.0, 100.0))

    assert result.x == pytest.approx(5.0)
    assert result.y == pytest.approx(100.0)


def test_feature_smoother_reduces_single_frame_jitter() -> None:
    extractor = FeatureExtractor()
    smoother = FeatureSmoother(position_alpha=0.3)

    # Feed several stable frames, then one noisy outlier frame.
    for _ in range(5):
        frame = extractor.process((make_open_hand(offset=(0.0, 0.0)),))
        smoothed = smoother.smooth_frame(frame)

    stable_x = smoothed.hands[0].palm_center.x

    noisy_frame = extractor.process((make_open_hand(offset=(0.5, 0.0)),))
    smoothed_noisy = smoother.smooth_frame(noisy_frame)

    jump = abs(smoothed_noisy.hands[0].palm_center.x - stable_x)
    raw_jump = abs(noisy_frame.hands[0].palm_center.x - stable_x)
    assert jump < raw_jump


def test_feature_smoother_resets_state_when_hand_disappears() -> None:
    extractor = FeatureExtractor()
    smoother = FeatureSmoother(position_alpha=0.3)

    for _ in range(5):
        frame = extractor.process((make_open_hand(offset=(0.0, 0.0)),))
        smoother.smooth_frame(frame)

    # Hand leaves, then reappears far away — smoothing should not drag
    # the new position back toward the old one.
    smoother.smooth_frame(extractor.process(()))
    frame = extractor.process((make_open_hand(offset=(0.3, 0.3)),))
    smoothed = smoother.smooth_frame(frame)

    assert smoothed.hands[0].palm_center.x == pytest.approx(frame.hands[0].palm_center.x)
