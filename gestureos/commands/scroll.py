"""
Scroll (Phase 7).

Converts frame-to-frame movement of a held TWO_FINGER_SCROLL gesture
into scroll deltas — the same drag/tracking idea as DragController, but
scroll-wheel events are inherently incremental ("scroll by this much
more"), not absolute positions, so this tracks the *previous* frame's
position rather than the gesture's start position.

Direction convention matches macOS's default "natural scrolling":
moving the hand down scrolls the content down (content follows the
hand), matching a trackpad. This can't be verified against a real Mac
in this environment — if it comes out inverted in practice,
``natural_scrolling=False`` flips it.
"""

from __future__ import annotations

from dataclasses import dataclass

from gestureos.vision.features import Point2D

# Converts normalized (0-1 frame-relative) movement into a pixel-scale
# scroll amount. Not tunable against real hardware here — a reasonable
# starting point, expected to need adjustment once run on a real Mac.
_PIXELS_PER_NORMALIZED_UNIT = 600.0


@dataclass
class _ScrollState:
    last_position: Point2D | None


class ScrollController:
    def __init__(
        self,
        sensitivity: float = 1.0,
        min_movement: float = 0.002,
        natural_scrolling: bool = True,
    ) -> None:
        if sensitivity <= 0:
            raise ValueError("sensitivity must be positive")
        if min_movement < 0:
            raise ValueError("min_movement must be >= 0")
        self.sensitivity = sensitivity
        self.min_movement = min_movement
        self.natural_scrolling = natural_scrolling
        self._state: _ScrollState | None = None

    def reset(self) -> None:
        self._state = None

    def begin(self, position: Point2D | None) -> None:
        """Call when the scroll gesture starts."""
        self._state = _ScrollState(last_position=position)

    def update(self, position: Point2D | None) -> tuple[float, float] | None:
        """Call on every subsequent frame the gesture is held.

        Returns (dx, dy) scroll units for this frame, or None if there
        isn't enough new movement to produce a nonzero scroll yet.
        """
        if self._state is None or position is None:
            return None
        if self._state.last_position is None:
            self._state.last_position = position
            return None

        raw_dx = position.x - self._state.last_position.x
        raw_dy = position.y - self._state.last_position.y
        self._state.last_position = position

        if abs(raw_dx) < self.min_movement and abs(raw_dy) < self.min_movement:
            return None

        sign = 1.0 if self.natural_scrolling else -1.0
        scale = _PIXELS_PER_NORMALIZED_UNIT * self.sensitivity * sign
        return raw_dx * scale, raw_dy * scale

    def end(self) -> None:
        """Call when the scroll gesture ends."""
        self._state = None
