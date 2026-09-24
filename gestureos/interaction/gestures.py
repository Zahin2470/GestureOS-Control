"""
Gesture vocabulary (Section 10) — per-frame pose classification.

Turns one frame's normalized+smoothed HandFeatures into a raw
GestureCandidate: a best-guess gesture type and a continuous confidence
score. This stage is purely geometric and stateless — it has no memory
of previous frames. Temporal stability (debounce, hysteresis, minimum
hold duration) is added later by confidence.py and state_machine.py.

Vocabulary is intentionally small and grows only as later phases need
it (point → cursor, pinch → click/drag, two_finger_scroll → scroll,
open_palm / fist reserved for later bindings). Adding a gesture is
adding one `_..._score()` function and one entry in the `scores` dict
in `classify_gesture` — nothing else has to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from gestureos.vision.features import HandFeatures

# Normalized (palm-width) pinch distance beyond which a hand counts as
# "fully open" for scoring purposes — i.e. the distance at which pinch
# confidence bottoms out at 0.
_PINCH_OPEN_REFERENCE = 1.0

# A raw per-frame candidate needs at least this much score to be reported
# as a real gesture rather than NONE.
_MIN_GESTURE_SCORE = 0.5


class GestureType(str, Enum):
    NONE = "none"
    PINCH = "pinch"
    OPEN_PALM = "open_palm"
    FIST = "fist"
    POINT = "point"
    TWO_FINGER_SCROLL = "two_finger_scroll"


@dataclass(frozen=True)
class GestureCandidate:
    """One frame's best-guess gesture, before any temporal stabilization."""

    gesture: GestureType
    confidence: float  # 0..1
    handedness: str | None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _pinch_score(features: HandFeatures) -> float:
    if features.pinch_distance is None:
        return 0.0
    return _clamp01(1.0 - features.pinch_distance / _PINCH_OPEN_REFERENCE)


def _open_palm_score(features: HandFeatures) -> float:
    states = features.finger_extension_states
    if states is None:
        return 0.0
    extended = sum([states.thumb, states.index, states.middle, states.ring, states.pinky])
    return extended / 5.0


def _fist_score(features: HandFeatures) -> float:
    states = features.finger_extension_states
    if states is None:
        return 0.0
    extended = sum([states.thumb, states.index, states.middle, states.ring, states.pinky])
    return 1.0 - (extended / 5.0)


def _point_score(features: HandFeatures) -> float:
    states = features.finger_extension_states
    if states is None:
        return 0.0
    others_curled = sum(
        [not states.thumb, not states.middle, not states.ring, not states.pinky]
    )
    return (1.0 if states.index else 0.0) * (others_curled / 4.0)


def _two_finger_scroll_score(features: HandFeatures) -> float:
    states = features.finger_extension_states
    if states is None:
        return 0.0
    both_extended = 1.0 if (states.index and states.middle) else 0.0
    others_curled = sum([not states.thumb, not states.ring, not states.pinky]) / 3.0
    return both_extended * others_curled


def classify_gesture(features: HandFeatures) -> GestureCandidate:
    """Classify a single frame's features into the best-matching gesture.

    Expects ``features`` to already be scale-normalized (Section 9) and
    smoothed (Section 10) — this function itself does neither.
    """
    if not features.hand_present:
        return GestureCandidate(GestureType.NONE, confidence=1.0, handedness=None)

    scores: dict[GestureType, float] = {
        GestureType.PINCH: _pinch_score(features),
        GestureType.OPEN_PALM: _open_palm_score(features),
        GestureType.FIST: _fist_score(features),
        GestureType.POINT: _point_score(features),
        GestureType.TWO_FINGER_SCROLL: _two_finger_scroll_score(features),
    }
    best_gesture, best_score = max(scores.items(), key=lambda item: item[1])

    if best_score < _MIN_GESTURE_SCORE:
        return GestureCandidate(
            GestureType.NONE, confidence=1.0 - best_score, handedness=features.handedness
        )

    return GestureCandidate(best_gesture, confidence=best_score, handedness=features.handedness)
