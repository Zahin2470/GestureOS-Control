"""
Structured logging for GestureOS.

Produces lines like:

    INFO gesture=pinch confidence=0.94 command=mouse.click
    WARN camera_frame_missing

Hard rule (Section 32): never log camera frames, screenshots, raw screen
contents, passwords, or typed user data. Callers must only pass scalar
key/value pairs — nothing image- or buffer-shaped belongs in a log call.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Any

from gestureos.constants import get_log_dir

_CONFIGURED = False


class KeyValueFormatter(logging.Formatter):
    """Formats a record as ``LEVEL message key=value key=value ...``."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname} {record.getMessage()}"
        extra_fields: dict[str, Any] = getattr(record, "fields", {}) or {}
        if extra_fields:
            pairs = " ".join(f"{k}={v}" for k, v in extra_fields.items())
            base = f"{base} {pairs}".rstrip()
        return base


def setup_logging(debug: bool = False, log_to_file: bool = True) -> logging.Logger:
    """Configure and return the ``gestureos`` root logger.

    Idempotent: calling this more than once will not duplicate handlers.
    """
    global _CONFIGURED
    logger = logging.getLogger("gestureos")

    if _CONFIGURED:
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
        return logger

    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = KeyValueFormatter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_to_file:
        try:
            log_dir: Path = get_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "gestureos.log",
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            # Non-fatal: fall back to console-only logging rather than
            # crashing the app because a log directory couldn't be made.
            logger.warning("log_file_unavailable", extra={"fields": {}})

    logger.propagate = False
    _CONFIGURED = True
    return logger


def log(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    """Convenience wrapper for structured logging.

    Example:
        log(logger, logging.INFO, "gesture", gesture="pinch", confidence=0.94)
        -> "INFO gesture gesture=pinch confidence=0.94"
    """
    logger.log(level, message, extra={"fields": fields})
