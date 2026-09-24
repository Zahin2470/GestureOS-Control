"""
Cursor mapping (Section 12 — Air Cursor).

Maps a normalized (0-1 image-space) fingertip position to an absolute
screen pixel coordinate:

  1. optional mirroring (so moving your hand right moves the cursor
     right, matching what you see in a "selfie view")
  2. active-region remap — only the center portion of the camera frame
     maps to the full screen, so reaching a screen edge doesn't require
     moving your hand to the edge of the camera's view
  3. sensitivity — gain applied around the center of the active region
  4. smoothing — an EMA pass on the final screen-space point, to keep
     the cursor from jittering even after upstream vision smoothing

This module is pure geometry: it never queries the real screen size or
touches any macOS API. The caller supplies screen dimensions (from
macos/screen.py on a real Mac, or a fixed size in tests).
"""

from __future__ import annotations

from dataclasses import dataclass

from gestureos.vision.features import Point2D
from gestureos.vision.smoothing import Point2DSmoother


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class ActiveRegion:
    """The portion of the normalized camera frame that maps to the full
    screen. Values outside this region clamp to the nearest screen edge.
    """

    x_min: float = 0.15
    x_max: float = 0.85
    y_min: float = 0.15
    y_max: float = 0.85

    def __post_init__(self) -> None:
        if not (0.0 <= self.x_min < self.x_max <= 1.0):
            raise ValueError("require 0 <= x_min < x_max <= 1")
        if not (0.0 <= self.y_min < self.y_max <= 1.0):
            raise ValueError("require 0 <= y_min < y_max <= 1")


class CursorMapper:
    def __init__(
        self,
        screen_width: float,
        screen_height: float,
        active_region: ActiveRegion | None = None,
        mirror: bool = True,
        sensitivity: float = 1.0,
        smoothing_alpha: float | None = 0.5,
    ) -> None:
        if screen_width <= 0 or screen_height <= 0:
            raise ValueError("screen dimensions must be positive")
        if sensitivity <= 0:
            raise ValueError("sensitivity must be positive")

        self.screen_width = screen_width
        self.screen_height = screen_height
        self.active_region = active_region if active_region is not None else ActiveRegion()
        self.mirror = mirror
        self.sensitivity = sensitivity
        self._smoother: Point2DSmoother | None = (
            Point2DSmoother(alpha=smoothing_alpha) if smoothing_alpha else None
        )

    def reset(self) -> None:
        if self._smoother is not None:
            self._smoother.reset()

    def map(self, normalized_point: Point2D) -> Point2D:
        """Map one normalized (0-1) camera-space point to a screen pixel
        coordinate. Always returns a point within the screen bounds.
        """
        x = 1.0 - normalized_point.x if self.mirror else normalized_point.x
        y = normalized_point.y

        region = self.active_region
        rel_x = (x - region.x_min) / (region.x_max - region.x_min)
        rel_y = (y - region.y_min) / (region.y_max - region.y_min)

        # Sensitivity is a gain applied around the region's center: >1
        # reaches the screen edges with less hand movement, <1 dampens.
        rel_x = _clamp01((rel_x - 0.5) * self.sensitivity + 0.5)
        rel_y = _clamp01((rel_y - 0.5) * self.sensitivity + 0.5)

        screen_point = Point2D(rel_x * self.screen_width, rel_y * self.screen_height)

        if self._smoother is not None:
            screen_point = self._smoother.update(screen_point)

        return screen_point
