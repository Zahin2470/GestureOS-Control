"""
Accessibility permission handling (Section 5, referenced by Phase 5).

Controlling the cursor/keyboard on macOS via CGEvent requires the
Accessibility permission (System Settings → Privacy & Security →
Accessibility). This module checks and can prompt for that permission.

Both functions take an injectable backend so they're unit-testable
without a real macOS process or a real permission prompt — the default
backend lazily imports ApplicationServices only when actually called.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum

logger = logging.getLogger("gestureos.macos.permissions")

HOW_TO_GRANT = (
    "System Settings → Privacy & Security → Accessibility, then enable GestureOS "
    "(you may need to quit and reopen GestureOS afterward)."
)


class PermissionStatus(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"  # not running on macOS, or the check itself failed


def _default_is_trusted_backend() -> bool:
    from ApplicationServices import AXIsProcessTrusted

    return bool(AXIsProcessTrusted())


def _default_prompt_backend() -> bool:
    from ApplicationServices import AXIsProcessTrustedWithOptions

    options = {"AXTrustedCheckOptionPrompt": True}
    return bool(AXIsProcessTrustedWithOptions(options))


def check_accessibility_permission(
    backend: Callable[[], bool] = _default_is_trusted_backend,
) -> PermissionStatus:
    """Check current status without prompting the user."""
    try:
        granted = backend()
    except Exception as exc:  # noqa: BLE001 - e.g. not running on macOS at all
        logger.warning(
            "accessibility_check_unavailable", extra={"fields": {"error": type(exc).__name__}}
        )
        return PermissionStatus.UNAVAILABLE

    status = PermissionStatus.GRANTED if granted else PermissionStatus.DENIED
    logger.info("accessibility_permission_checked", extra={"fields": {"status": status.value}})
    return status


def request_accessibility_permission(
    backend: Callable[[], bool] = _default_prompt_backend,
) -> PermissionStatus:
    """Trigger the system permission prompt if not already granted."""
    try:
        granted = backend()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "accessibility_prompt_unavailable", extra={"fields": {"error": type(exc).__name__}}
        )
        return PermissionStatus.UNAVAILABLE

    status = PermissionStatus.GRANTED if granted else PermissionStatus.DENIED
    logger.info("accessibility_permission_requested", extra={"fields": {"status": status.value}})
    return status


def describe_status(status: PermissionStatus) -> str | None:
    """A short, user-facing hint for anything other than GRANTED."""
    if status is PermissionStatus.GRANTED:
        return None
    if status is PermissionStatus.DENIED:
        return f"GestureOS needs Accessibility permission to control the cursor. {HOW_TO_GRANT}"
    return "Could not check Accessibility permission (not running on macOS?)."
