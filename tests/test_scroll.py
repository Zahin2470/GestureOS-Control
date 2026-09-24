import pytest

from gestureos.commands.scroll import ScrollController
from gestureos.vision.features import Point2D


def test_first_update_after_begin_only_sets_reference() -> None:
    controller = ScrollController()
    controller.begin(Point2D(0.5, 0.5))

    result = controller.update(Point2D(0.5, 0.5))

    assert result is None


def test_movement_below_threshold_produces_no_delta() -> None:
    controller = ScrollController(min_movement=0.01)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))  # sets reference

    result = controller.update(Point2D(0.501, 0.5))  # tiny movement

    assert result is None


def test_movement_above_threshold_produces_a_delta() -> None:
    controller = ScrollController(min_movement=0.01)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))

    result = controller.update(Point2D(0.5, 0.6))  # moved down by 0.1

    assert result is not None
    dx, dy = result
    assert dy != 0.0


def test_natural_scrolling_moving_down_scrolls_down() -> None:
    controller = ScrollController(natural_scrolling=True, min_movement=0.0)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))

    _, dy = controller.update(Point2D(0.5, 0.6))  # hand moved down

    assert dy > 0  # content follows the hand downward


def test_disabling_natural_scrolling_flips_the_sign() -> None:
    natural = ScrollController(natural_scrolling=True, min_movement=0.0)
    inverted = ScrollController(natural_scrolling=False, min_movement=0.0)
    for c in (natural, inverted):
        c.begin(Point2D(0.5, 0.5))
        c.update(Point2D(0.5, 0.5))

    _, natural_dy = natural.update(Point2D(0.5, 0.6))
    _, inverted_dy = inverted.update(Point2D(0.5, 0.6))

    assert natural_dy == -inverted_dy


def test_higher_sensitivity_produces_a_bigger_delta() -> None:
    low = ScrollController(sensitivity=1.0, min_movement=0.0)
    high = ScrollController(sensitivity=2.0, min_movement=0.0)
    for c in (low, high):
        c.begin(Point2D(0.5, 0.5))
        c.update(Point2D(0.5, 0.5))

    _, low_dy = low.update(Point2D(0.5, 0.6))
    _, high_dy = high.update(Point2D(0.5, 0.6))

    assert abs(high_dy) > abs(low_dy)


def test_no_hand_present_produces_no_delta() -> None:
    controller = ScrollController()
    controller.begin(Point2D(0.5, 0.5))

    result = controller.update(None)

    assert result is None


def test_update_before_begin_produces_no_delta() -> None:
    controller = ScrollController()

    result = controller.update(Point2D(0.5, 0.5))

    assert result is None


def test_end_clears_state_so_next_begin_starts_fresh() -> None:
    controller = ScrollController(min_movement=0.01)
    controller.begin(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.5))
    controller.update(Point2D(0.5, 0.9))  # big movement while active

    controller.end()
    controller.begin(Point2D(0.2, 0.2))
    result = controller.update(Point2D(0.2, 0.2))  # same as new reference

    assert result is None  # not a leftover delta from before end()


def test_invalid_sensitivity_rejected() -> None:
    with pytest.raises(ValueError):
        ScrollController(sensitivity=0)


def test_invalid_min_movement_rejected() -> None:
    with pytest.raises(ValueError):
        ScrollController(min_movement=-0.1)
