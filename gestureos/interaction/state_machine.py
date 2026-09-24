"""
Gesture state machine (Sections 10-11).

Turns a stabilized per-frame gesture signal (confidence.py) into discrete
Intent events, with:

  - minimum hold duration before a candidate becomes "real" (debounce)
  - hysteresis: a confident detection is needed to *start* a gesture,
    but only a moderate drop in confidence *ends* one — so a gesture
    doesn't flicker on/off right at the boundary
  - a cooldown after a gesture ends, before the same hand can start a
    new one (Section 11 — stateful pinch system), so a noisy
    release-then-immediate-re-pinch can't double-fire

One machine instance tracks one hand's lifecycle. ``GestureEngine`` (in
engine.py) owns one machine per handedness label so both hands gesture
independently.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from gestureos.interaction.confidence import StableCandidate
from gestureos.interaction.cooldown import CooldownGate
from gestureos.interaction.gestures import GestureType
from gestureos.vision.features import Point2D

logger = logging.getLogger("gestureos.interaction.state_machine")


class IntentPhase(str, Enum):
    START = "start"
    HOLD = "hold"
    END = "end"


@dataclass(frozen=True)
class Intent:
    """A confirmed, temporally-stable gesture event — the last thing the
    vision/interaction side produces before the safety/command layer
    (Phase 4) takes over.
    """

    gesture: GestureType
    phase: IntentPhase
    confidence: float
    handedness: str | None
    timestamp: float
    position: Point2D | None = None  # normalized (0-1) fingertip position
    # at the moment of this event. None unless GestureEngine attaches it.
    # Unused before Phase 6 (cursor/drag); earlier phases never read it.


class _State(str, Enum):
    IDLE = "idle"
    CONFIRMING = "confirming"
    ACTIVE = "active"
    COOLDOWN = "cooldown"


class GestureStateMachine:
    """Tracks one hand's gesture lifecycle across frames."""

    def __init__(
        self,
        activate_threshold: float = 0.6,
        release_threshold: float = 0.4,
        min_hold_time_s: float = 0.15,
        cooldown_s: float = 0.35,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not 0.0 <= release_threshold <= activate_threshold <= 1.0:
            raise ValueError(
                "require 0 <= release_threshold <= activate_threshold <= 1"
            )
        self.activate_threshold = activate_threshold
        self.release_threshold = release_threshold
        self.min_hold_time_s = min_hold_time_s
        self.cooldown_gate = CooldownGate(cooldown_s)
        self._clock = clock or time.monotonic

        self._state = _State.IDLE
        self._candidate_gesture: GestureType = GestureType.NONE
        self._confirm_started_at: float | None = None
        self._active_gesture: GestureType | None = None
        self._cooldown_gesture: GestureType | None = None

    def update(self, candidate: StableCandidate) -> Intent | None:
        now = self._clock()
        if self._state is _State.IDLE:
            return self._update_idle(candidate, now)
        if self._state is _State.CONFIRMING:
            return self._update_confirming(candidate, now)
        if self._state is _State.ACTIVE:
            return self._update_active(candidate, now)
        return self._update_cooldown(candidate, now)

    # ------------------------------------------------------------------

    def _update_idle(self, candidate: StableCandidate, now: float) -> Intent | None:
        if candidate.gesture == GestureType.NONE:
            return None
        if candidate.confidence < self.activate_threshold:
            return None
        if not self.cooldown_gate.is_ready(candidate.gesture, now):
            return None

        self._state = _State.CONFIRMING
        self._candidate_gesture = candidate.gesture
        self._confirm_started_at = now
        return None

    def _update_confirming(self, candidate: StableCandidate, now: float) -> Intent | None:
        if (
            candidate.gesture != self._candidate_gesture
            or candidate.confidence < self.release_threshold
        ):
            self._reset_to_idle()
            return None

        assert self._confirm_started_at is not None
        if now - self._confirm_started_at < self.min_hold_time_s:
            return None

        self._state = _State.ACTIVE
        self._active_gesture = self._candidate_gesture
        logger.info(
            "gesture_start",
            extra={"fields": {"gesture": self._active_gesture.value, "handedness": candidate.handedness}},
        )
        return Intent(
            gesture=self._active_gesture,
            phase=IntentPhase.START,
            confidence=candidate.confidence,
            handedness=candidate.handedness,
            timestamp=now,
        )

    def _update_active(self, candidate: StableCandidate, now: float) -> Intent | None:
        assert self._active_gesture is not None
        if (
            candidate.gesture == self._active_gesture
            and candidate.confidence >= self.release_threshold
        ):
            return Intent(
                gesture=self._active_gesture,
                phase=IntentPhase.HOLD,
                confidence=candidate.confidence,
                handedness=candidate.handedness,
                timestamp=now,
            )

        ended_gesture = self._active_gesture
        handedness = candidate.handedness
        self.cooldown_gate.mark_triggered(ended_gesture, now)
        self._state = _State.COOLDOWN
        self._cooldown_gesture = ended_gesture
        self._active_gesture = None
        logger.info(
            "gesture_end",
            extra={"fields": {"gesture": ended_gesture.value, "handedness": handedness}},
        )
        return Intent(
            gesture=ended_gesture,
            phase=IntentPhase.END,
            confidence=candidate.confidence,
            handedness=handedness,
            timestamp=now,
        )

    def _update_cooldown(self, candidate: StableCandidate, now: float) -> Intent | None:
        assert self._cooldown_gesture is not None
        if self.cooldown_gate.is_ready(self._cooldown_gesture, now):
            self._reset_to_idle()
            # Don't waste a frame: let the candidate that arrived on the
            # same update() call be evaluated immediately as IDLE, rather
            # than requiring an extra frame just to notice cooldown ended.
            return self._update_idle(candidate, now)
        return None

    def _reset_to_idle(self) -> None:
        self._state = _State.IDLE
        self._candidate_gesture = GestureType.NONE
        self._confirm_started_at = None
        self._cooldown_gesture = None
