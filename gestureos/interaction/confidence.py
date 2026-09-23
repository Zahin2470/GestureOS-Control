"""
Temporal voting (Section 10).

A single noisy frame can momentarily flip the per-frame classification
in gestures.py (a finger landmark jitters across the extension
threshold, etc.). This module smooths that out with a rolling-window
majority vote per hand before the state machine ever sees a candidate —
so "real" gesture changes still get through quickly, but single-frame
flicker doesn't.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from gestureos.interaction.gestures import GestureCandidate, GestureType


@dataclass(frozen=True)
class StableCandidate:
    """A temporally-voted gesture signal for one hand."""

    gesture: GestureType
    confidence: float
    handedness: str | None


class ConfidenceTracker:
    """Per-hand rolling-window majority vote over recent GestureCandidates.

    Keyed by handedness so both hands are tracked independently.
    """

    def __init__(self, window_size: int = 5, min_vote_fraction: float = 0.6) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if not 0.0 < min_vote_fraction <= 1.0:
            raise ValueError("min_vote_fraction must be in (0, 1]")
        self.window_size = window_size
        self.min_vote_fraction = min_vote_fraction
        self._windows: dict[str | None, deque] = {}

    def reset(self) -> None:
        self._windows.clear()

    def update(self, candidate: GestureCandidate) -> StableCandidate:
        key = candidate.handedness
        window = self._windows.setdefault(key, deque(maxlen=self.window_size))
        window.append(candidate)

        counts = Counter(c.gesture for c in window)
        best_gesture, best_count = counts.most_common(1)[0]
        vote_fraction = best_count / len(window)

        if best_gesture == GestureType.NONE or vote_fraction < self.min_vote_fraction:
            return StableCandidate(GestureType.NONE, confidence=0.0, handedness=key)

        matching = [c.confidence for c in window if c.gesture == best_gesture]
        avg_confidence = sum(matching) / len(matching)
        return StableCandidate(best_gesture, confidence=avg_confidence, handedness=key)
