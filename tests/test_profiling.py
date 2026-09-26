import time

import pytest

from gestureos.utils.profiling import PipelineProfiler, StageTimer


def test_stage_timer_starts_at_zero() -> None:
    timer = StageTimer()

    assert timer.average_ms == 0.0


def test_stage_timer_records_elapsed_time() -> None:
    timer = StageTimer()

    with timer:
        time.sleep(0.01)

    assert timer.average_ms > 0.0


def test_stage_timer_averages_over_multiple_calls() -> None:
    timer = StageTimer(window_size=10)

    for _ in range(3):
        with timer:
            time.sleep(0.001)

    assert timer.average_ms > 0.0


def test_profiler_exposes_all_default_stages() -> None:
    profiler = PipelineProfiler()

    for stage_name in ("capture", "tracking", "features", "gesture_engine", "routing"):
        assert profiler.stage(stage_name) is not None


def test_profiler_unknown_stage_raises() -> None:
    profiler = PipelineProfiler()

    with pytest.raises(ValueError):
        profiler.stage("not_a_real_stage")


def test_profiler_same_stage_returns_same_timer() -> None:
    profiler = PipelineProfiler()

    assert profiler.stage("capture") is profiler.stage("capture")


def test_profiler_summary_has_one_entry_per_stage() -> None:
    profiler = PipelineProfiler()

    summary = profiler.summary()

    assert set(summary.keys()) == set(profiler.stages)


def test_profiler_total_ms_sums_all_stage_averages() -> None:
    profiler = PipelineProfiler()
    with profiler.stage("capture"):
        time.sleep(0.001)
    with profiler.stage("tracking"):
        time.sleep(0.001)

    total = profiler.total_ms
    expected = profiler.stage("capture").average_ms + profiler.stage("tracking").average_ms

    assert total >= expected  # other (untouched) stages contribute 0 but don't subtract


def test_profiler_custom_stages() -> None:
    profiler = PipelineProfiler(stages=("only_stage",))

    assert profiler.stage("only_stage") is not None
    with pytest.raises(ValueError):
        profiler.stage("capture")


def test_format_summary_includes_every_stage_and_total() -> None:
    profiler = PipelineProfiler()

    text = profiler.format_summary()

    for stage_name in profiler.stages:
        assert stage_name in text
    assert "total" in text
