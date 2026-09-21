"""
Hand landmark tracking (Section 9).

Wraps MediaPipe's Hands solution behind a narrow interface so the rest of
the vision pipeline (features, normalization, smoothing) depends on
GestureOS's own ``RawHand``/``Landmark`` types, not MediaPipe's runtime
objects directly. That keeps MediaPipe swappable and lets everything
downstream of tracking be unit tested with synthetic landmark data — no
camera or MediaPipe runtime required for those tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

logger = logging.getLogger("gestureos.vision.tracker")

NUM_LANDMARKS = 21


class LandmarkIndex(IntEnum):
    """MediaPipe Hands landmark ordering (21 points per hand)."""

    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


@dataclass(frozen=True)
class Landmark:
    """A single hand landmark, normalized to 0-1 image space."""

    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class RawHand:
    """One tracked hand for a single frame, in GestureOS's own format."""

    landmarks: tuple[Landmark, ...]
    handedness: str  # "left" | "right"
    handedness_confidence: float

    def __post_init__(self) -> None:
        if len(self.landmarks) != NUM_LANDMARKS:
            raise ValueError(
                f"expected {NUM_LANDMARKS} landmarks, got {len(self.landmarks)}"
            )

    def landmark(self, index: LandmarkIndex) -> Landmark:
        return self.landmarks[index]


class HandTrackerBackend(Protocol):
    """Minimal surface this module needs from a tracking backend."""

    def process(self, frame: object) -> object: ...
    def close(self) -> None: ...


class HandTracker:
    """Adapts a MediaPipe Hands instance (or an injected fake) into
    GestureOS's ``RawHand`` representation.
    """

    def __init__(
        self,
        max_num_hands: int = 2,
        detection_confidence: float = 0.7,
        tracking_confidence: float = 0.7,
        backend: HandTrackerBackend | None = None,
    ) -> None:
        self.max_num_hands = max_num_hands
        self.detection_confidence = detection_confidence
        self.tracking_confidence = tracking_confidence
        self._backend = backend
        self._owns_backend = backend is None

    def start(self) -> None:
        if self._backend is not None:
            return
        import mediapipe as mp  # Lazy import: tests inject a fake backend
        # and never need a real MediaPipe install for this call.

        self._backend = mp.solutions.hands.Hands(
            max_num_hands=self.max_num_hands,
            min_detection_confidence=self.detection_confidence,
            min_tracking_confidence=self.tracking_confidence,
        )
        logger.info(
            "tracker_started",
            extra={"fields": {"max_hands": self.max_num_hands}},
        )

    def process(self, frame: object) -> tuple[RawHand, ...]:
        if self._backend is None:
            raise RuntimeError("HandTracker.process() called before start()")
        result = self._backend.process(frame)
        return _result_to_raw_hands(result)

    def close(self) -> None:
        if self._backend is not None and self._owns_backend:
            self._backend.close()
        self._backend = None
        logger.info("tracker_stopped", extra={"fields": {}})

    def __enter__(self) -> HandTracker:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _result_to_raw_hands(result: object) -> tuple[RawHand, ...]:
    multi_landmarks = getattr(result, "multi_hand_landmarks", None)
    multi_handedness = getattr(result, "multi_handedness", None)
    if not multi_landmarks:
        return ()

    hands: list[RawHand] = []
    for i, hand_landmarks in enumerate(multi_landmarks):
        landmarks = tuple(
            Landmark(x=lm.x, y=lm.y, z=getattr(lm, "z", 0.0))
            for lm in hand_landmarks.landmark
        )
        label = "right"
        confidence = 1.0
        if multi_handedness and i < len(multi_handedness):
            classification = multi_handedness[i].classification[0]
            label = classification.label.lower()
            confidence = classification.score
        hands.append(
            RawHand(landmarks=landmarks, handedness=label, handedness_confidence=confidence)
        )
    return tuple(hands)
