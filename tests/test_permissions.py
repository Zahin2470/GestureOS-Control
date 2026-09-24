from gestureos.macos.permissions import (
    PermissionStatus,
    check_accessibility_permission,
    describe_status,
    request_accessibility_permission,
)


def test_check_reports_granted() -> None:
    status = check_accessibility_permission(backend=lambda: True)

    assert status == PermissionStatus.GRANTED


def test_check_reports_denied() -> None:
    status = check_accessibility_permission(backend=lambda: False)

    assert status == PermissionStatus.DENIED


def test_check_reports_unavailable_when_backend_raises() -> None:
    def broken_backend() -> bool:
        raise RuntimeError("not on macOS")

    status = check_accessibility_permission(backend=broken_backend)

    assert status == PermissionStatus.UNAVAILABLE


def test_request_reports_granted_after_prompt() -> None:
    status = request_accessibility_permission(backend=lambda: True)

    assert status == PermissionStatus.GRANTED


def test_request_reports_denied_after_prompt() -> None:
    status = request_accessibility_permission(backend=lambda: False)

    assert status == PermissionStatus.DENIED


def test_request_reports_unavailable_when_backend_raises() -> None:
    def broken_backend() -> bool:
        raise RuntimeError("not on macOS")

    status = request_accessibility_permission(backend=broken_backend)

    assert status == PermissionStatus.UNAVAILABLE


def test_describe_status_is_none_when_granted() -> None:
    assert describe_status(PermissionStatus.GRANTED) is None


def test_describe_status_gives_a_hint_when_denied() -> None:
    message = describe_status(PermissionStatus.DENIED)

    assert message is not None
    assert "Accessibility" in message


def test_describe_status_gives_a_hint_when_unavailable() -> None:
    message = describe_status(PermissionStatus.UNAVAILABLE)

    assert message is not None
