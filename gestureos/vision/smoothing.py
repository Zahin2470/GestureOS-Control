"""
Smoothing (Section 10 — the geometry-smoothing half of it).

A single noisy frame must never reach gesture logic un-smoothed. This
module applies exponential smoothing to per-hand position/distance
signals across frames. The *temporal confirmation* half of Section 10
(minimum hold duration, hysteresis, activation/release thresholds,
cooldown) belongs to the gesture state machine in Phase 3 — this module
only reduces landmark jitter, it does not decide whether a gesture is
"real".
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from gestureos.vision.features import FrameFeatures, HandFeatures, Point2D


class ExponentialSmoother:
    """EMA over a scalar stream: value = alpha*new + (1-alpha)*previous."""

    def __init__(self, alpha: float = 0.5) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self._value: float | None = None

    def update(self, value: float) -> float:
        if self._value is None:
            self._value = value
        else:
            self._value = self.alpha * value + (1.0 - self.alpha) * self._value
        return self._value

    def reset(self) -> None:
        self._value = None


class Point2DSmoother:
    """EMA over a 2D point stream (e.g. palm center, index fingertip)."""

    def __init__(self, alpha: float = 0.5) -> None:
        self._x = ExponentialSmoother(alpha)
        self._y = ExponentialSmoother(alpha)

    def update(self, point: Point2D) -> Point2D:
        return Point2D(self._x.update(point.x), self._y.update(point.y))

    def reset(self) -> None:
        self._x.reset()
        self._y.reset()


@dataclass
class _HandSmootherState:
    palm_center: Point2DSmoother
    index_tip: Point2DSmoother
    pinch_distance: ExponentialSmoother
    velocity: Point2DSmoother


class FeatureSmoother:
    """Applies per-hand EMA smoothing across frames, keyed by handedness.

    A hand's smoother state resets the moment that hand disappears from
    frame, so a re-appearing hand starts fresh rather than snapping back
    toward stale history.
    """

    def __init__(
        self,
        position_alpha: float = 0.5,
        distance_alpha: float = 0.5,
        velocity_alpha: float = 0.4,
    ) -> None:
        self._position_alpha = position_alpha
        self._distance_alpha = distance_alpha
        self._velocity_alpha = velocity_alpha
        self._states: dict[str, _HandSmootherState] = {}

    def reset(self) -> None:
        self._states.clear()

    def smooth_frame(self, frame: FrameFeatures) -> FrameFeatures:
        seen_labels = {hand.handedness for hand in frame.hands if hand.hand_present}
        for label in list(self._states):
            if label not in seen_labels:
                del self._states[label]

        smoothed_hands = tuple(self._smooth_one(hand) for hand in frame.hands)
        return replace(frame, hands=smoothed_hands)

    def _smooth_one(self, hand: HandFeatures) -> HandFeatures:
        if not hand.hand_present or hand.handedness is None:
            return hand

        state = self._states.get(hand.handedness)
        if state is None:
            state = _HandSmootherState(
                palm_center=Point2DSmoother(self._position_alpha),
                index_tip=Point2DSmoother(self._position_alpha),
                pinch_distance=ExponentialSmoother(self._distance_alpha),
                velocity=Point2DSmoother(self._velocity_alpha),
            )
            self._states[hand.handedness] = state

        new_palm_center = (
            state.palm_center.update(hand.palm_center) if hand.palm_center else hand.palm_center
        )
        new_index_tip = (
            state.index_tip.update(hand.index_tip) if hand.index_tip else hand.index_tip
        )
        new_pinch = (
            state.pinch_distance.update(hand.pinch_distance)
            if hand.pinch_distance is not None
            else None
        )
        new_velocity = (
            state.velocity.update(hand.velocity) if hand.velocity is not None else None
        )

        return replace(
            hand,
            palm_center=new_palm_center,
            index_tip=new_index_tip,
            pinch_distance=new_pinch,
            velocity=new_velocity,
        )
