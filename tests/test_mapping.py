import pytest

from gestureos.vision.features import Point2D
from gestureos.vision.mapping import ActiveRegion, CursorMapper


def test_center_of_active_region_maps_to_center_of_screen() -> None:
    mapper = CursorMapper(1000, 800, mirror=False, sensitivity=1.0, smoothing_alpha=None)

    result = mapper.map(Point2D(0.5, 0.5))

    assert result.x == pytest.approx(500.0)
    assert result.y == pytest.approx(400.0)


def test_active_region_min_corner_maps_to_screen_origin() -> None:
    region = ActiveRegion(x_min=0.2, x_max=0.8, y_min=0.2, y_max=0.8)
    mapper = CursorMapper(1000, 800, active_region=region, mirror=False, smoothing_alpha=None)

    result = mapper.map(Point2D(0.2, 0.2))

    assert result.x == pytest.approx(0.0)
    assert result.y == pytest.approx(0.0)


def test_position_outside_active_region_clamps_to_screen_edge() -> None:
    region = ActiveRegion(x_min=0.2, x_max=0.8, y_min=0.2, y_max=0.8)
    mapper = CursorMapper(1000, 800, active_region=region, mirror=False, smoothing_alpha=None)

    result = mapper.map(Point2D(0.0, 1.0))  # well outside the region on both axes

    assert result.x == pytest.approx(0.0)
    assert result.y == pytest.approx(800.0)


def test_mirroring_flips_the_x_axis() -> None:
    mapper_mirrored = CursorMapper(1000, 800, mirror=True, smoothing_alpha=None)
    mapper_unmirrored = CursorMapper(1000, 800, mirror=False, smoothing_alpha=None)

    mirrored = mapper_mirrored.map(Point2D(0.65, 0.5))
    unmirrored = mapper_unmirrored.map(Point2D(0.65, 0.5))

    # Mirrored: moving right in camera space should move the mapped x
    # the opposite direction relative to center compared to unmirrored.
    assert (mirrored.x - 500.0) == pytest.approx(-(unmirrored.x - 500.0))


def test_higher_sensitivity_reaches_screen_edge_with_less_movement() -> None:
    low = CursorMapper(1000, 800, mirror=False, sensitivity=1.0, smoothing_alpha=None)
    high = CursorMapper(1000, 800, mirror=False, sensitivity=2.0, smoothing_alpha=None)

    point = Point2D(0.6, 0.5)  # slightly off-center

    low_result = low.map(point)
    high_result = high.map(point)

    # Higher sensitivity amplifies displacement from center more.
    assert abs(high_result.x - 500.0) > abs(low_result.x - 500.0)


def test_sensitivity_is_still_clamped_to_screen_bounds() -> None:
    mapper = CursorMapper(1000, 800, mirror=False, sensitivity=5.0, smoothing_alpha=None)

    result = mapper.map(Point2D(0.9, 0.9))

    assert 0.0 <= result.x <= 1000.0
    assert 0.0 <= result.y <= 800.0


def test_smoothing_reduces_a_single_frame_jump() -> None:
    mapper = CursorMapper(1000, 800, mirror=False, smoothing_alpha=0.3)
    for _ in range(5):
        stable = mapper.map(Point2D(0.5, 0.5))

    jumped = mapper.map(Point2D(0.9, 0.5))
    raw_jump = abs(0.9 * 1000 - stable.x)  # roughly, ignoring the small active-region offset
    smoothed_jump = abs(jumped.x - stable.x)

    assert smoothed_jump < raw_jump


def test_smoothing_can_be_disabled() -> None:
    mapper = CursorMapper(1000, 800, mirror=False, smoothing_alpha=None)

    first = mapper.map(Point2D(0.5, 0.5))
    second = mapper.map(Point2D(0.9, 0.5))

    # No smoothing state carried over — second call reflects only its
    # own input, not a blend with the first.
    assert second.x != pytest.approx(first.x)


def test_reset_clears_smoothing_history() -> None:
    mapper = CursorMapper(1000, 800, mirror=False, smoothing_alpha=0.3)
    mapper.map(Point2D(0.2, 0.2))
    mapper.reset()

    result = mapper.map(Point2D(0.8, 0.8))
    fresh_mapper = CursorMapper(1000, 800, mirror=False, smoothing_alpha=0.3)
    fresh_result = fresh_mapper.map(Point2D(0.8, 0.8))

    assert result.x == pytest.approx(fresh_result.x)
    assert result.y == pytest.approx(fresh_result.y)


def test_invalid_screen_dimensions_rejected() -> None:
    with pytest.raises(ValueError):
        CursorMapper(0, 800)
    with pytest.raises(ValueError):
        CursorMapper(1000, -1)


def test_invalid_sensitivity_rejected() -> None:
    with pytest.raises(ValueError):
        CursorMapper(1000, 800, sensitivity=0)


def test_invalid_active_region_rejected() -> None:
    with pytest.raises(ValueError):
        ActiveRegion(x_min=0.8, x_max=0.2)
    with pytest.raises(ValueError):
        ActiveRegion(y_min=1.0, y_max=1.0)
