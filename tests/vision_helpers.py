"""Test helpers for building synthetic hand landmark data without a
camera or a working MediaPipe install.
"""

from __future__ import annotations

from gestureos.vision.tracker import NUM_LANDMARKS, Landmark, LandmarkIndex, RawHand

# A relaxed open-hand pose: fingers extended outward from a wrist at the
# bottom of the frame. Coordinates are arbitrary but geometrically
# plausible normalized (0-1) image-space values.
_OPEN_HAND_XY: dict[LandmarkIndex, tuple[float, float]] = {
    LandmarkIndex.WRIST: (0.50, 0.80),
    LandmarkIndex.THUMB_CMC: (0.45, 0.75),
    LandmarkIndex.THUMB_MCP: (0.40, 0.68),
    LandmarkIndex.THUMB_IP: (0.36, 0.60),
    LandmarkIndex.THUMB_TIP: (0.32, 0.52),
    LandmarkIndex.INDEX_MCP: (0.46, 0.60),
    LandmarkIndex.INDEX_PIP: (0.45, 0.45),
    LandmarkIndex.INDEX_DIP: (0.44, 0.35),
    LandmarkIndex.INDEX_TIP: (0.44, 0.25),
    LandmarkIndex.MIDDLE_MCP: (0.50, 0.58),
    LandmarkIndex.MIDDLE_PIP: (0.50, 0.42),
    LandmarkIndex.MIDDLE_DIP: (0.50, 0.30),
    LandmarkIndex.MIDDLE_TIP: (0.50, 0.18),
    LandmarkIndex.RING_MCP: (0.54, 0.60),
    LandmarkIndex.RING_PIP: (0.55, 0.45),
    LandmarkIndex.RING_DIP: (0.56, 0.35),
    LandmarkIndex.RING_TIP: (0.56, 0.25),
    LandmarkIndex.PINKY_MCP: (0.58, 0.62),
    LandmarkIndex.PINKY_PIP: (0.60, 0.50),
    LandmarkIndex.PINKY_DIP: (0.61, 0.42),
    LandmarkIndex.PINKY_TIP: (0.62, 0.35),
}


def make_open_hand(
    handedness: str = "right",
    confidence: float = 0.98,
    offset: tuple[float, float] = (0.0, 0.0),
) -> RawHand:
    """An open-hand pose (all fingers extended), optionally translated."""
    dx, dy = offset
    landmarks = tuple(
        Landmark(x=_OPEN_HAND_XY[i][0] + dx, y=_OPEN_HAND_XY[i][1] + dy)
        for i in range(NUM_LANDMARKS)
    )
    return RawHand(landmarks=landmarks, handedness=handedness, handedness_confidence=confidence)


def make_pinch_hand(
    handedness: str = "right",
    confidence: float = 0.98,
    pinch_gap: float = 0.01,
) -> RawHand:
    """A hand with thumb tip and index tip brought close together, all
    other fingers curled (not extended).
    """
    base = dict(_OPEN_HAND_XY)
    # Bring thumb and index tips together near the palm.
    base[LandmarkIndex.THUMB_TIP] = (0.47, 0.55)
    base[LandmarkIndex.THUMB_IP] = (0.46, 0.58)
    base[LandmarkIndex.INDEX_TIP] = (0.47, 0.55 + pinch_gap)
    # Curl the remaining fingers: tip closer to wrist than its PIP joint.
    for finger_pip, finger_tip in (
        (LandmarkIndex.MIDDLE_PIP, LandmarkIndex.MIDDLE_TIP),
        (LandmarkIndex.RING_PIP, LandmarkIndex.RING_TIP),
        (LandmarkIndex.PINKY_PIP, LandmarkIndex.PINKY_TIP),
    ):
        pip_x, pip_y = base[finger_pip]
        base[finger_tip] = (pip_x, pip_y + 0.05)

    landmarks = tuple(Landmark(x=base[i][0], y=base[i][1]) for i in range(NUM_LANDMARKS))
    return RawHand(landmarks=landmarks, handedness=handedness, handedness_confidence=confidence)


def make_fist_hand(
    handedness: str = "right",
    confidence: float = 0.98,
) -> RawHand:
    """All five fingers curled toward the palm (tip closer to wrist than
    its PIP/MCP joint for every finger).
    """
    base = dict(_OPEN_HAND_XY)
    for joint_idx, tip_idx in (
        (LandmarkIndex.THUMB_MCP, LandmarkIndex.THUMB_TIP),
        (LandmarkIndex.INDEX_PIP, LandmarkIndex.INDEX_TIP),
        (LandmarkIndex.MIDDLE_PIP, LandmarkIndex.MIDDLE_TIP),
        (LandmarkIndex.RING_PIP, LandmarkIndex.RING_TIP),
        (LandmarkIndex.PINKY_PIP, LandmarkIndex.PINKY_TIP),
    ):
        jx, jy = base[joint_idx]
        base[tip_idx] = (jx, jy + 0.03)

    landmarks = tuple(Landmark(x=base[i][0], y=base[i][1]) for i in range(NUM_LANDMARKS))
    return RawHand(landmarks=landmarks, handedness=handedness, handedness_confidence=confidence)


def make_point_hand(
    handedness: str = "right",
    confidence: float = 0.98,
) -> RawHand:
    """Only the index finger extended; thumb, middle, ring, pinky curled."""
    base = dict(_OPEN_HAND_XY)
    for joint_idx, tip_idx in (
        (LandmarkIndex.THUMB_MCP, LandmarkIndex.THUMB_TIP),
        (LandmarkIndex.MIDDLE_PIP, LandmarkIndex.MIDDLE_TIP),
        (LandmarkIndex.RING_PIP, LandmarkIndex.RING_TIP),
        (LandmarkIndex.PINKY_PIP, LandmarkIndex.PINKY_TIP),
    ):
        jx, jy = base[joint_idx]
        base[tip_idx] = (jx, jy + 0.03)
    # Index finger tip is left at its open-hand (extended) position.

    landmarks = tuple(Landmark(x=base[i][0], y=base[i][1]) for i in range(NUM_LANDMARKS))
    return RawHand(landmarks=landmarks, handedness=handedness, handedness_confidence=confidence)


def make_two_finger_hand(
    handedness: str = "right",
    confidence: float = 0.98,
    offset: tuple[float, float] = (0.0, 0.0),
) -> RawHand:
    """Index and middle fingers extended together; thumb, ring, pinky
    curled — the two-finger scroll pose.
    """
    base = dict(_OPEN_HAND_XY)
    for joint_idx, tip_idx in (
        (LandmarkIndex.THUMB_MCP, LandmarkIndex.THUMB_TIP),
        (LandmarkIndex.RING_PIP, LandmarkIndex.RING_TIP),
        (LandmarkIndex.PINKY_PIP, LandmarkIndex.PINKY_TIP),
    ):
        jx, jy = base[joint_idx]
        base[tip_idx] = (jx, jy + 0.03)
    # Index and middle fingers are left at their open-hand (extended) positions.

    dx, dy = offset
    landmarks = tuple(
        Landmark(x=base[i][0] + dx, y=base[i][1] + dy) for i in range(NUM_LANDMARKS)
    )
    return RawHand(landmarks=landmarks, handedness=handedness, handedness_confidence=confidence)
