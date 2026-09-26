"""
Latency profiling (Phase 11).

A thin wrapper around the Stopwatch/RollingAverage utilities built in
Phase 1 (utils/timing.py), giving each pipeline stage — capture,
tracking, feature extraction, the gesture engine, and command
routing — its own rolling-average latency. Surfaced in the app's HUD
and periodically logged, so a real slowdown on a real Mac is visible
directly rather than only inferable from a dropped frame rate.
"""

from __future__ import annotations

from gestureos.utils.timing import RollingAverage, Stopwatch


class StageTimer:
    """Measures one named pipeline stage's per-call duration, in
    milliseconds, as a rolling average over its window.
    """

    def __init__(self, window_size: int = 60) -> None:
        self._average = RollingAverage(window_size)
        self._stopwatch = Stopwatch()

    def __enter__(self) -> StageTimer:
        self._stopwatch.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        elapsed_ms = self._stopwatch.stop() * 1000.0
        self._average.add(elapsed_ms)

    @property
    def average_ms(self) -> float:
        return self._average.value


_DEFAULT_STAGES = ("capture", "tracking", "features", "gesture_engine", "routing")


class PipelineProfiler:
    """Owns one StageTimer per named pipeline stage."""

    def __init__(self, stages: tuple[str, ...] = _DEFAULT_STAGES, window_size: int = 60) -> None:
        self.stages = stages
        self._timers: dict[str, StageTimer] = {name: StageTimer(window_size) for name in stages}

    def stage(self, name: str) -> StageTimer:
        timer = self._timers.get(name)
        if timer is None:
            raise ValueError(f"unknown pipeline stage {name!r}; expected one of {self.stages}")
        return timer

    def summary(self) -> dict[str, float]:
        """Per-stage rolling-average latency, in milliseconds."""
        return {name: timer.average_ms for name, timer in self._timers.items()}

    @property
    def total_ms(self) -> float:
        """Sum of every stage's current average — an approximation of
        total per-frame pipeline latency (stages run sequentially, so
        this is a reasonable estimate, not a separately-measured value).
        """
        return sum(timer.average_ms for timer in self._timers.values())

    def format_summary(self) -> str:
        parts = [f"{name} {timer.average_ms:.1f}ms" for name, timer in self._timers.items()]
        return " ".join(parts) + f" | total {self.total_ms:.1f}ms"
