import pytest

from gestureos.macos.permission_flow import (
    ACCESSIBILITY_PANE_URL,
    PermissionFlow,
    open_accessibility_settings,
)
from gestureos.macos.permissions import PermissionStatus


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_open_accessibility_settings_calls_the_right_url() -> None:
    calls = []

    def fake_open(url: str) -> bool:
        calls.append(url)
        return True

    result = open_accessibility_settings(open_url=fake_open)

    assert result is True
    assert calls == [ACCESSIBILITY_PANE_URL]


def test_open_accessibility_settings_handles_failure_gracefully() -> None:
    def broken_open(url: str) -> bool:
        raise RuntimeError("not on macOS")

    result = open_accessibility_settings(open_url=broken_open)

    assert result is False


def test_flow_starts_unavailable_before_first_check() -> None:
    flow = PermissionFlow(checker=lambda: PermissionStatus.GRANTED)

    assert flow.status == PermissionStatus.UNAVAILABLE


def test_check_now_updates_status_immediately() -> None:
    flow = PermissionFlow(checker=lambda: PermissionStatus.GRANTED)

    status = flow.check_now()

    assert status == PermissionStatus.GRANTED
    assert flow.status == PermissionStatus.GRANTED


def test_poll_checks_on_first_call() -> None:
    clock = FakeClock()
    flow = PermissionFlow(
        recheck_interval_s=3.0, clock=clock, checker=lambda: PermissionStatus.DENIED
    )

    status = flow.poll()

    assert status == PermissionStatus.DENIED


def test_poll_does_not_recheck_before_interval_elapses() -> None:
    clock = FakeClock()
    call_count = 0

    def checker() -> PermissionStatus:
        nonlocal call_count
        call_count += 1
        return PermissionStatus.DENIED

    flow = PermissionFlow(recheck_interval_s=3.0, clock=clock, checker=checker)
    flow.poll()
    clock.advance(1.0)
    flow.poll()

    assert call_count == 1


def test_poll_rechecks_once_interval_elapses() -> None:
    clock = FakeClock()
    call_count = 0

    def checker() -> PermissionStatus:
        nonlocal call_count
        call_count += 1
        return PermissionStatus.DENIED

    flow = PermissionFlow(recheck_interval_s=3.0, clock=clock, checker=checker)
    flow.poll()
    clock.advance(3.5)
    flow.poll()

    assert call_count == 2


def test_poll_notices_permission_granted_while_running() -> None:
    clock = FakeClock()
    statuses = iter([PermissionStatus.DENIED, PermissionStatus.GRANTED])
    flow = PermissionFlow(recheck_interval_s=1.0, clock=clock, checker=lambda: next(statuses))

    flow.poll()
    assert flow.needs_attention is True

    clock.advance(2.0)
    flow.poll()

    assert flow.status == PermissionStatus.GRANTED
    assert flow.needs_attention is False


def test_needs_attention_true_for_denied_and_unavailable() -> None:
    flow_denied = PermissionFlow(checker=lambda: PermissionStatus.DENIED)
    flow_denied.check_now()
    flow_unavailable = PermissionFlow(checker=lambda: PermissionStatus.UNAVAILABLE)
    flow_unavailable.check_now()

    assert flow_denied.needs_attention is True
    assert flow_unavailable.needs_attention is True


def test_needs_attention_false_once_granted() -> None:
    flow = PermissionFlow(checker=lambda: PermissionStatus.GRANTED)
    flow.check_now()

    assert flow.needs_attention is False


def test_invalid_recheck_interval_rejected() -> None:
    with pytest.raises(ValueError):
        PermissionFlow(recheck_interval_s=0)
