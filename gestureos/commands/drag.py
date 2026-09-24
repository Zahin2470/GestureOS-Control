"""
Click vs. drag (Section 12 refinement for Phase 6).

A pinch that barely moves before releasing should feel like a stable
click, not a drag that nudges the cursor by a stray pixel. This adds a
small "drag engagement" deadzone: while a pinch is held, the cursor only
starts actually moving once the hand has moved beyond a threshold from
where the pinch started. Below that threshold, the cursor stays exactly
where the click began.

Beyond that, GestureOS does not need to decide "was this a click or a
drag" itself — that's standard AppKit behavior in whatever application
receives the mouse_down / mouse_dragged / mouse_up event sequence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from gestureos.vision.features import Point2D


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


@dataclass
class _DragState:
    engaged: bool
    start_position: Point2D | None


class DragController:
    """Tracks one in-progress pinch and decides, frame by frame, whether
    the cursor should move yet. One instance per hand/pointer.
    """

    def __init__(self, engage_distance: float = 0.02) -> None:
        if engage_distance < 0:
            raise ValueError("engage_distance must be >= 0")
        self.engage_distance = engage_distance
        self._state: _DragState | None = None

    def reset(self) -> None:
        self._state = None

    def begin(self, position: Point2D | None) -> None:
        """Call when the pinch starts (MOUSE_DOWN)."""
        self._state = _DragState(engaged=False, start_position=position)

    def update(self, position: Point2D | None) -> Point2D | None:
        """Call on every subsequent frame the pinch is held (MOUSE_MOVE).

        Returns the position the cursor should move to, or None if the
        drag hasn't engaged yet — meaning the cursor should stay put.
        """
        if self._state is None or position is None:
            return None

        if not self._state.engaged:
            if self._state.start_position is None:
                self._state.start_position = position
                return None
            if _distance(position, self._state.start_position) < self.engage_distance:
                return None
            self._state.engaged = True

        return position

    def end(self) -> None:
        """Call when the pinch ends (MOUSE_UP)."""
        self._state = None

    @property
    def is_engaged(self) -> bool:
        return self._state is not None and self._state.engaged
