#!/usr/bin/env python3
"""
GestureOS entry point.

    python main.py
    python main.py --debug
    python main.py --simulate
    python main.py --camera 0
    python main.py --profile default

Section 34 defines this full CLI surface up front so the contract is
stable across phases. --debug, --simulate, and (as of Phase 10)
--camera are all fully wired. --profile is still accepted and stored
but has no effect — full named-profile support (switching entire
binding sets) is a future enhancement beyond this project's 12-phase
plan, not something any phase here commits to building.

This file intentionally contains no macOS-specific or vision-specific
logic (Engineering Rule #6) — it only parses arguments and starts the
app shell.
"""

from __future__ import annotations

import argparse
import sys

from gestureos.config import Config
from gestureos.constants import APP_NAME, APP_VERSION, DEFAULT_CAMERA_INDEX, DEFAULT_PROFILE_NAME
from gestureos.models import RunMode
from gestureos.utils.logging import setup_logging


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=f"{APP_NAME} — touchless control for macOS.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in Simulation Mode — never touches real macOS state.",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        metavar="INDEX",
        help="Camera device index to use.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=DEFAULT_PROFILE_NAME,
        metavar="NAME",
        help="Gesture profile name to record in settings. Not yet functional.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    logger = setup_logging(debug=args.debug)
    logger.info(
        "startup",
        extra={
            "fields": {
                "version": APP_VERSION,
                "debug": args.debug,
                "simulate": args.simulate,
                "camera": args.camera,
                "profile": args.profile,
            }
        },
    )

    if args.profile != DEFAULT_PROFILE_NAME:
        logger.debug(
            "profile_flag_not_yet_functional",
            extra={"fields": {"requested_profile": args.profile}},
        )

    config = Config()
    config.load()
    if args.profile != DEFAULT_PROFILE_NAME:
        config.settings.active_profile = args.profile
    if args.camera != DEFAULT_CAMERA_INDEX:
        config.settings.vision.camera_index = args.camera

    run_mode = RunMode.SIMULATION if args.simulate else RunMode.NORMAL

    # Imported here (not at module scope) so `--version`/`--help` and
    # non-UI tests never pay the cost of importing pygame.
    from gestureos.app import build_app

    app = build_app(config, run_mode)
    if not app.setup():
        logger.error("startup_failed", extra={"fields": {"reason": "display_init_failed"}})
        print(
            f"{APP_NAME} could not open a display window. "
            "See the log file for details.",
            file=sys.stderr,
        )
        return 1

    try:
        return app.run()
    except KeyboardInterrupt:
        logger.info("shutdown_keyboard_interrupt", extra={"fields": {}})
        app.cleanup()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
