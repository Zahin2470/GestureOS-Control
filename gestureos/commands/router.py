"""
Command router (Sections 20-22).

    Intent -> registry lookup -> Command -> safety policy -> adapter call

This is where an Intent produced by the gesture engine (Phase 3) either
becomes a real (or, in Phase 4, simulated) macOS side effect, or gets
dropped — either because no command is bound to it, or because the
safety policy blocked it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from gestureos.commands.registry import resolve_command_type
from gestureos.commands.safety import SafetyPolicy
from gestureos.commands.types import Command, CommandType
from gestureos.interaction.state_machine import Intent
from gestureos.macos.adapter import MacOSAdapter

logger = logging.getLogger("gestureos.commands.router")


class CommandRouter:
    def __init__(self, adapter: MacOSAdapter, safety: SafetyPolicy) -> None:
        self._adapter = adapter
        self._safety = safety
        self._dispatch: dict[CommandType, Callable[[Command], None]] = {
            CommandType.MOUSE_DOWN: lambda cmd: self._adapter.mouse_down(
                cmd.params.get("button", "left")
            ),
            CommandType.MOUSE_UP: lambda cmd: self._adapter.mouse_up(
                cmd.params.get("button", "left")
            ),
            CommandType.SCROLL: lambda cmd: self._adapter.scroll(
                cmd.params.get("dx", 0.0), cmd.params.get("dy", 0.0)
            ),
            CommandType.SWITCH_APP_NEXT: lambda cmd: self._adapter.switch_app_next(),
            CommandType.SWITCH_APP_PREVIOUS: lambda cmd: self._adapter.switch_app_previous(),
            CommandType.LAUNCH_APP: lambda cmd: self._adapter.launch_app(
                cmd.params.get("name", "")
            ),
            CommandType.MEDIA_PLAY_PAUSE: lambda cmd: self._adapter.media_play_pause(),
            CommandType.SPACE_NEXT: lambda cmd: self._adapter.space_next(),
            CommandType.SPACE_PREVIOUS: lambda cmd: self._adapter.space_previous(),
        }

    def route_intent(self, intent: Intent) -> Command | None:
        """Process one Intent. Returns the Command that was actually
        dispatched, or None if nothing happened (unbound gesture, or
        blocked by the safety policy).
        """
        command_type = resolve_command_type(intent)
        if command_type is None:
            return None

        command = Command(
            type=command_type,
            source_gesture=intent.gesture,
            source_phase=intent.phase,
            handedness=intent.handedness,
            timestamp=intent.timestamp,
        )

        decision = self._safety.check(command)
        if not decision.allowed:
            logger.info(
                "command_blocked",
                extra={"fields": {"command": command_type.value, "reason": decision.reason}},
            )
            return None

        handler = self._dispatch.get(command_type)
        if handler is None:
            logger.warning(
                "command_unhandled", extra={"fields": {"command": command_type.value}}
            )
            return None

        try:
            handler(command)
        except NotImplementedError as exc:
            logger.warning(
                "command_not_implemented",
                extra={"fields": {"command": command_type.value, "reason": str(exc)}},
            )
            return None
        except Exception as exc:  # noqa: BLE001 - adapters may raise all sorts of OS errors
            logger.error(
                "command_dispatch_failed",
                extra={"fields": {"command": command_type.value, "error": type(exc).__name__}},
            )
            return None

        logger.info(
            "command_executed",
            extra={
                "fields": {
                    "command": command_type.value,
                    "gesture": intent.gesture.value,
                    "handedness": intent.handedness,
                }
            },
        )
        return command

    def route_intents(self, intents: tuple[Intent, ...]) -> tuple[Command, ...]:
        commands = [self.route_intent(intent) for intent in intents]
        return tuple(c for c in commands if c is not None)
