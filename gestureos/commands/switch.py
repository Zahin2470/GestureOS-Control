"""
App switching via swipe (Phase 8).

A held FIST gesture that moves far enough horizontally triggers one
switch_app_next/previous command — a fist-grab-and-swipe, the same way
a real trackpad's app-switch gesture works. Only one switch fires per
FIST hold: once the threshold is crossed, the controller "consumes" the
swipe and won't fire again until the FIST ends and a new one begins, so
continuing to move your fist afterward doesn't rapid-fire app switches.

Direction convention: increasing x (hand moving toward the camera's
right) triggers "next". ``flip_direction=True`` reverses this — like
scroll.py's natural_scrolling flag, this can't be verified against a
real Mac from here, so it's made easy to flip.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from gestureos.vision.features import Point2D


class SwipeDirection(str, Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class _SwipeState:
    start_position: Point2D | None
    consumed: bool


class SwipeController:
    def __init__(self, swipe_distance: float = 0.12, flip_direction: bool = False) -> None:
        if swipe_distance <= 0:
            raise ValueError("swipe_distance must be positive")
        self.swipe_distance = swipe_distance
        self.flip_direction = flip_direction
        self._state: _SwipeState | None = None

    def reset(self) -> None:
        self._state = None

    def begin(self, position: Point2D | None) -> None:
        """Call when the FIST gesture starts."""
        self._state = _SwipeState(start_position=position, consumed=False)

    def update(self, position: Point2D | None) -> SwipeDirection | None:
        """Call on every subsequent frame the FIST is held.

        Returns the swipe direction the moment the threshold is first
        crossed, and None on every other frame (including after the
        swipe has already fired once this hold).
        """
        if self._state is None or self._state.consumed or position is None:
            return None
        if self._state.start_position is None:
            self._state.start_position = position
            return None

        dx = position.x - self._state.start_position.x
        if abs(dx) < self.swipe_distance:
            return None

        self._state.consumed = True
        moved_right = dx > 0
        if self.flip_direction:
            moved_right = not moved_right
        return SwipeDirection.RIGHT if moved_right else SwipeDirection.LEFT

    def end(self) -> None:
        """Call when the FIST gesture ends."""
        self._state = None
