"""
Gesture engine — ties gestures.py, confidence.py, and state_machine.py
together into a single entry point: ``FrameFeatures`` in, zero or more
``Intent``s out. This is the last vision/interaction-side stage before
the safety/command layer (Phase 4) takes over.
"""

from __future__ import annotations

from collections.abc import Callable

from gestureos.interaction.confidence import ConfidenceTracker
from gestureos.interaction.gestures import classify_gesture
from gestureos.interaction.state_machine import GestureStateMachine, Intent
from gestureos.vision.features import FrameFeatures


class GestureEngine:
    def __init__(
        self,
        activate_threshold: float = 0.6,
        release_threshold: float = 0.4,
        min_hold_time_s: float = 0.15,
        cooldown_s: float = 0.35,
        vote_window_size: int = 5,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._confidence_tracker = ConfidenceTracker(window_size=vote_window_size)
        self._activate_threshold = activate_threshold
        self._release_threshold = release_threshold
        self._min_hold_time_s = min_hold_time_s
        self._cooldown_s = cooldown_s
        self._clock = clock
        self._machines: dict[str | None, GestureStateMachine] = {}

    def reset(self) -> None:
        self._confidence_tracker.reset()
        self._machines.clear()

    def _machine_for(self, handedness: str | None) -> GestureStateMachine:
        machine = self._machines.get(handedness)
        if machine is None:
            machine = GestureStateMachine(
                activate_threshold=self._activate_threshold,
                release_threshold=self._release_threshold,
                min_hold_time_s=self._min_hold_time_s,
                cooldown_s=self._cooldown_s,
                clock=self._clock,
            )
            self._machines[handedness] = machine
        return machine

    def process(self, frame: FrameFeatures) -> tuple[Intent, ...]:
        intents: list[Intent] = []
        for hand in frame.hands:
            candidate = classify_gesture(hand)
            stable = self._confidence_tracker.update(candidate)
            machine = self._machine_for(hand.handedness)
            intent = machine.update(stable)
            if intent is not None:
                intents.append(intent)
        return tuple(intents)
