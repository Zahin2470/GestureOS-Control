"""
Central constants for GestureOS.

Nothing in this module may contain a machine-specific absolute path or a
username (Engineering Rules #16-17). All paths are resolved at runtime
relative to the user's home directory or the platform's standard
application-support location.
"""

from __future__ import annotations

import sys
from pathlib import Path

# --------------------------------------------------------------------------
# App metadata
# --------------------------------------------------------------------------

APP_NAME = "GestureOS"
APP_VERSION = "0.1.0"  # Phase 1 — macOS + VS Code foundation

# --------------------------------------------------------------------------
# Platform
# --------------------------------------------------------------------------

IS_MACOS = sys.platform == "darwin"

# --------------------------------------------------------------------------
# Filesystem locations
#
# macOS is the only fully supported target (see Section 1 of the master
# spec), but a minimal portability shim is kept here so the project can
# still be opened and unit-tested on a non-macOS development machine.
# --------------------------------------------------------------------------


def get_app_data_dir() -> Path:
    """Return the directory GestureOS uses for local settings/logs/profiles.

    macOS:   ~/Library/Application Support/GestureOS
    Other:   ~/.gestureos   (dev/test fallback only — not a supported target)
    """
    home = Path.home()
    if IS_MACOS:
        base = home / "Library" / "Application Support" / APP_NAME
    else:
        base = home / ".gestureos"
    return base


def get_log_dir() -> Path:
    return get_app_data_dir() / "logs"


def get_settings_path() -> Path:
    return get_app_data_dir() / "settings.json"


def get_profiles_dir() -> Path:
    return get_app_data_dir() / "profiles"


# --------------------------------------------------------------------------
# Window / UI defaults (Phase 1 basic shell; expanded in later phases)
# --------------------------------------------------------------------------

DEFAULT_WINDOW_SIZE = (900, 560)
DEFAULT_WINDOW_TITLE = APP_NAME
TARGET_FPS = 60

# --------------------------------------------------------------------------
# CLI defaults
# --------------------------------------------------------------------------

DEFAULT_CAMERA_INDEX = 0
DEFAULT_PROFILE_NAME = "default"
