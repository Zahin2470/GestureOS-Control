"""
Cursor calibration wizard (Section 25 — Calibration).

A short guided flow that lets the user define their own comfortable
"active region" (see vision/mapping.py) instead of using the hardcoded
default: move your hand to two corners of the range you want to control
the cursor from, and GestureOS remembers it.

This module is pure state-machine logic — it has no dependency on
pygame or any rendering. The app shell (app.py) drives it with hand
positions each frame and renders whatever ``.prompt`` currently says.
"""

from __future__ import annotations

from enum import Enum

from gestureos.vision.features import Point2D
from gestureos.vision.mapping import ActiveRegion

_DEFAULT_MARGIN = 0.05  # shrink the captured rectangle inward slightly
# so the calibrated region isn't flush against the exact two points you
# happened to be holding your hand at.

_MIN_SPAN = 0.1  # a captured region narrower than this (degenerate —
# corners too close together, or the margin ate the whole span) falls
# back to the library default rather than producing an unusable region.


class CalibrationStep(str, Enum):
    WAIT_FOR_HAND = "wait_for_hand"
    TOP_LEFT = "top_left"
    BOTTOM_RIGHT = "bottom_right"
    DONE = "done"


_PROMPTS: dict[CalibrationStep, str] = {
    CalibrationStep.WAIT_FOR_HAND: "Show one hand to the camera to begin calibration.",
    CalibrationStep.TOP_LEFT: (
        "Move your hand to the top-left of your comfortable range, then press SPACE."
    ),
    CalibrationStep.BOTTOM_RIGHT: (
        "Now move to the bottom-right of your range, then press SPACE."
    ),
    CalibrationStep.DONE: "Calibration complete.",
}


class CalibrationWizard:
    """Advance with ``update(hand_position)`` every frame; call
    ``confirm()`` when the user presses the confirm key for the
    current step.
    """

    def __init__(self, margin: float = _DEFAULT_MARGIN) -> None:
        self.margin = margin
        self.step = CalibrationStep.WAIT_FOR_HAND
        self._top_left: Point2D | None = None
        self._bottom_right: Point2D | None = None
        self._last_position: Point2D | None = None
        self.result: ActiveRegion | None = None

    @property
    def prompt(self) -> str:
        return _PROMPTS[self.step]

    @property
    def is_done(self) -> bool:
        return self.step is CalibrationStep.DONE

    def update(self, hand_position: Point2D | None) -> None:
        """Call every frame with the current primary hand position (or
        None if no hand is visible).
        """
        self._last_position = hand_position
        if self.step is CalibrationStep.WAIT_FOR_HAND and hand_position is not None:
            self.step = CalibrationStep.TOP_LEFT

    def confirm(self) -> bool:
        """Call when the user presses the confirm key. Returns True if
        this confirmation advanced the wizard (there was a valid hand
        position to capture) — False if pressed too early (no hand
        visible yet, or calibration already finished).
        """
        if self._last_position is None:
            return False

        if self.step is CalibrationStep.TOP_LEFT:
            self._top_left = self._last_position
            self.step = CalibrationStep.BOTTOM_RIGHT
            return True

        if self.step is CalibrationStep.BOTTOM_RIGHT:
            self._bottom_right = self._last_position
            self.step = CalibrationStep.DONE
            self.result = self._build_region()
            return True

        return False

    def _build_region(self) -> ActiveRegion:
        assert self._top_left is not None
        assert self._bottom_right is not None
        x_min = min(self._top_left.x, self._bottom_right.x) + self.margin
        x_max = max(self._top_left.x, self._bottom_right.x) - self.margin
        y_min = min(self._top_left.y, self._bottom_right.y) + self.margin
        y_max = max(self._top_left.y, self._bottom_right.y) - self.margin

        if x_max - x_min < _MIN_SPAN or y_max - y_min < _MIN_SPAN:
            return ActiveRegion()  # degenerate capture — fall back to the default

        x_min = max(0.0, x_min)
        y_min = max(0.0, y_min)
        x_max = min(1.0, x_max)
        y_max = min(1.0, y_max)
        return ActiveRegion(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)
