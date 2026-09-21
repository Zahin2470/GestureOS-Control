"""
Feature extraction (Section 9).

Converts raw hand landmarks into stable, high-level features. Nothing
downstream (gesture logic, command routing) will ever see a raw
landmark — only the structured signals defined here:

    hand_present, handedness, wrist, palm_center, index_tip, thumb_tip,
    finger_extension_states, pinch_distance, palm_orientation, velocity,
    motion_direction, two_hand_state

Geometry here is still in raw normalized image space (0-1); scale
invariance is added by ``normalization.py``, and jitter reduction by
``smoothing.py`` — kept as separate stages per the pipeline diagram in
the master spec.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from gestureos.vision.tracker import Landmark, LandmarkIndex, RawHand

_EXTENSION_RATIO = 1.15  # tip must be this much farther from the wrist
# than its PIP/MCP joint to be considered "extended". Orientation
# invariant (no assumption about which way the hand is rotated).

_FINGER_JOINTS: dict[str, tuple[LandmarkIndex, LandmarkIndex]] = {
    "thumb": (LandmarkIndex.THUMB_MCP, LandmarkIndex.THUMB_TIP),
    "index": (LandmarkIndex.INDEX_PIP, LandmarkIndex.INDEX_TIP),
    "middle": (LandmarkIndex.MIDDLE_PIP, LandmarkIndex.MIDDLE_TIP),
    "ring": (LandmarkIndex.RING_PIP, LandmarkIndex.RING_TIP),
    "pinky": (LandmarkIndex.PINKY_PIP, LandmarkIndex.PINKY_TIP),
}

_MOTION_EPSILON = 1e-4  # below this per-frame displacement, call it "none"


class MotionDirection(str, Enum):
    NONE = "none"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class TwoHandState(str, Enum):
    NONE = "none"
    SINGLE = "single"
    BOTH = "both"


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class FingerExtensionStates:
    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool


@dataclass(frozen=True)
class HandFeatures:
    """Structured signals for a single tracked hand in one frame."""

    hand_present: bool
    handedness: str | None = None
    wrist: Point2D | None = None
    palm_center: Point2D | None = None
    index_tip: Point2D | None = None
    thumb_tip: Point2D | None = None
    finger_extension_states: FingerExtensionStates | None = None
    palm_width: float | None = None  # scale reference; used by normalization.py
    pinch_distance: float | None = None
    palm_orientation: float | None = None  # radians
    velocity: Point2D | None = None  # per-frame delta of palm_center
    motion_direction: MotionDirection = MotionDirection.NONE

    @staticmethod
    def absent() -> HandFeatures:
        return HandFeatures(hand_present=False)


@dataclass(frozen=True)
class FrameFeatures:
    """All hands detected in one frame, plus the aggregate two-hand state."""

    two_hand_state: TwoHandState
    hands: tuple[HandFeatures, ...]  # 0, 1, or 2 elements


def _distance(a: Landmark, b: Landmark) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _midpoint(points: tuple[Landmark, ...]) -> Point2D:
    x = sum(p.x for p in points) / len(points)
    y = sum(p.y for p in points) / len(points)
    return Point2D(x, y)


def _finger_extension(hand: RawHand) -> FingerExtensionStates:
    wrist = hand.landmark(LandmarkIndex.WRIST)
    states: dict[str, bool] = {}
    for finger, (joint_idx, tip_idx) in _FINGER_JOINTS.items():
        joint = hand.landmark(joint_idx)
        tip = hand.landmark(tip_idx)
        states[finger] = _distance(wrist, tip) > _distance(wrist, joint) * _EXTENSION_RATIO
    return FingerExtensionStates(**states)


def _motion_direction(velocity: Point2D) -> MotionDirection:
    if abs(velocity.x) < _MOTION_EPSILON and abs(velocity.y) < _MOTION_EPSILON:
        return MotionDirection.NONE
    if abs(velocity.x) >= abs(velocity.y):
        return MotionDirection.RIGHT if velocity.x > 0 else MotionDirection.LEFT
    return MotionDirection.DOWN if velocity.y > 0 else MotionDirection.UP


class FeatureExtractor:
    """Stateful only in the sense of remembering the previous frame's
    palm position per handedness label, so it can compute velocity.
    Everything else is a pure function of the current frame's landmarks.
    """

    def __init__(self) -> None:
        self._previous_palm_center: dict[str, Point2D] = {}

    def reset(self) -> None:
        self._previous_palm_center.clear()

    def process(self, raw_hands: tuple[RawHand, ...]) -> FrameFeatures:
        seen_labels = {hand.handedness for hand in raw_hands}
        # Drop stale velocity history for hands no longer in frame, so a
        # hand that disappears and reappears doesn't produce a fake
        # "teleport" velocity spike.
        for label in list(self._previous_palm_center):
            if label not in seen_labels:
                del self._previous_palm_center[label]

        hand_features = tuple(self._extract_one(hand) for hand in raw_hands)

        if len(hand_features) == 0:
            two_hand_state = TwoHandState.NONE
        elif len(hand_features) == 1:
            two_hand_state = TwoHandState.SINGLE
        else:
            two_hand_state = TwoHandState.BOTH

        return FrameFeatures(two_hand_state=two_hand_state, hands=hand_features)

    def _extract_one(self, hand: RawHand) -> HandFeatures:
        wrist_lm = hand.landmark(LandmarkIndex.WRIST)
        index_mcp = hand.landmark(LandmarkIndex.INDEX_MCP)
        middle_mcp = hand.landmark(LandmarkIndex.MIDDLE_MCP)
        ring_mcp = hand.landmark(LandmarkIndex.RING_MCP)
        pinky_mcp = hand.landmark(LandmarkIndex.PINKY_MCP)
        index_tip_lm = hand.landmark(LandmarkIndex.INDEX_TIP)
        thumb_tip_lm = hand.landmark(LandmarkIndex.THUMB_TIP)

        palm_center = _midpoint((wrist_lm, index_mcp, middle_mcp, ring_mcp, pinky_mcp))
        palm_width = _distance(index_mcp, pinky_mcp)
        pinch_distance = _distance(thumb_tip_lm, index_tip_lm)
        palm_orientation = math.atan2(
            middle_mcp.y - wrist_lm.y, middle_mcp.x - wrist_lm.x
        )

        previous = self._previous_palm_center.get(hand.handedness)
        if previous is None:
            velocity = Point2D(0.0, 0.0)
        else:
            velocity = Point2D(palm_center.x - previous.x, palm_center.y - previous.y)
        self._previous_palm_center[hand.handedness] = palm_center

        return HandFeatures(
            hand_present=True,
            handedness=hand.handedness,
            wrist=Point2D(wrist_lm.x, wrist_lm.y),
            palm_center=palm_center,
            index_tip=Point2D(index_tip_lm.x, index_tip_lm.y),
            thumb_tip=Point2D(thumb_tip_lm.x, thumb_tip_lm.y),
            finger_extension_states=_finger_extension(hand),
            palm_width=palm_width,
            pinch_distance=pinch_distance,
            palm_orientation=palm_orientation,
            velocity=velocity,
            motion_direction=_motion_direction(velocity),
        )
