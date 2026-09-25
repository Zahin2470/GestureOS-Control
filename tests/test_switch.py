import pytest

from gestureos.commands.switch import SwipeController, SwipeDirection
from gestureos.vision.features import Point2D


def test_first_update_after_begin_only_sets_reference() -> None:
    controller = SwipeController()
    controller.begin(Point2D(0.5, 0.5))

    result = controller.update(Point2D(0.5, 0.5))

    assert result is None


def test_movement_below_threshold_produces_no_swipe() -> None:
    controller = SwipeController(swipe_distance=0.12)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))

    result = controller.update(Point2D(0.55, 0.5))  # 0.05 < 0.12

    assert result is None


def test_rightward_movement_past_threshold_fires_right() -> None:
    controller = SwipeController(swipe_distance=0.12)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))

    result = controller.update(Point2D(0.65, 0.5))

    assert result == SwipeDirection.RIGHT


def test_leftward_movement_past_threshold_fires_left() -> None:
    controller = SwipeController(swipe_distance=0.12)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))

    result = controller.update(Point2D(0.35, 0.5))

    assert result == SwipeDirection.LEFT


def test_flip_direction_reverses_the_result() -> None:
    normal = SwipeController(swipe_distance=0.12, flip_direction=False)
    flipped = SwipeController(swipe_distance=0.12, flip_direction=True)
    for c in (normal, flipped):
        c.begin(Point2D(0.5, 0.5))
        c.update(Point2D(0.5, 0.5))

    assert normal.update(Point2D(0.65, 0.5)) == SwipeDirection.RIGHT
    assert flipped.update(Point2D(0.65, 0.5)) == SwipeDirection.LEFT


def test_only_one_swipe_fires_per_hold() -> None:
    controller = SwipeController(swipe_distance=0.12)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))
    first = controller.update(Point2D(0.65, 0.5))
    second = controller.update(Point2D(0.80, 0.5))  # continuing past threshold again

    assert first == SwipeDirection.RIGHT
    assert second is None


def test_new_begin_resets_the_consumed_flag() -> None:
    controller = SwipeController(swipe_distance=0.12)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))
    controller.update(Point2D(0.65, 0.5))  # consumes this hold's swipe

    controller.end()
    controller.begin(Point2D(0.2, 0.2))
    controller.update(Point2D(0.2, 0.2))
    result = controller.update(Point2D(0.35, 0.2))

    assert result == SwipeDirection.RIGHT


def test_no_hand_present_produces_no_swipe() -> None:
    controller = SwipeController()
    controller.begin(Point2D(0.5, 0.5))

    result = controller.update(None)

    assert result is None


def test_update_before_begin_produces_no_swipe() -> None:
    controller = SwipeController()

    result = controller.update(Point2D(0.5, 0.5))

    assert result is None


def test_invalid_swipe_distance_rejected() -> None:
    with pytest.raises(ValueError):
        SwipeController(swipe_distance=0)
    with pytest.raises(ValueError):
        SwipeController(swipe_distance=-0.1)
