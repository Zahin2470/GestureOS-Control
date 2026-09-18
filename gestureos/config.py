"""
Local settings persistence (Section 26).

Settings live in a single JSON file under the platform app-data directory
(see constants.get_settings_path). Nothing here talks to the network or a
cloud service — GestureOS is local-only by design (Section 33).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from gestureos.constants import get_settings_path
from gestureos.models import Settings

logger = logging.getLogger("gestureos.config")


class Config:
    """Owns the on-disk settings file and the in-memory Settings object."""

    def __init__(self, path: Path | None = None) -> None:
        self.path: Path = path or get_settings_path()
        self.settings: Settings = Settings()

    def load(self) -> Settings:
        """Load settings from disk.

        Falls back to defaults (and logs a warning) if the file is
        missing, unreadable, or contains invalid JSON — a corrupted
        settings file must never crash the app (Section 31).
        """
        if not self.path.exists():
            logger.info("settings_not_found", extra={"fields": {"path": str(self.path)}})
            self.settings = Settings()
            return self.settings

        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("settings root must be a JSON object")
            self.settings = Settings.from_dict(data)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning(
                "settings_corrupted_using_defaults",
                extra={"fields": {"path": str(self.path), "error": type(exc).__name__}},
            )
            self.settings = Settings()

        return self.settings

    def save(self) -> None:
        """Persist the current settings to disk, atomically."""
        self.settings.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(self.settings.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)
        logger.info("settings_saved", extra={"fields": {"path": str(self.path)}})

    def reset_to_defaults(self) -> Settings:
        self.settings = Settings()
        return self.settings
