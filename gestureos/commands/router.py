"""
Command router (Sections 20-22, refined for click/drag in Phase 6,
scroll in Phase 7, and app switching in Phase 8).

    Intent -> registry lookup -> Command -> safety policy -> adapter call

This is where an Intent produced by the gesture engine (Phase 3) either
becomes a real (or, in Phase 4, simulated) macOS side effect, or gets
dropped — either because no command is bound to it, because the safety
policy blocked it, because the drag hasn't moved far enough yet to
engage (drag.py), because the scroll gesture hasn't moved enough this
frame to produce a nonzero delta (scroll.py), or because the swipe
hasn't crossed its threshold yet (switch.py).

MOUSE_DOWN, MOUSE_MOVE, MOUSE_UP, SCROLL, and APP_SWITCH are handled
explicitly rather than through the generic dispatch table, because they
share state (an in-progress drag, scroll, or swipe) that the other,
stateless commands don't need.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from gestureos.commands.drag import DragController
from gestureos.commands.registry import resolve_command_type
from gestureos.commands.safety import SafetyPolicy
from gestureos.commands.scroll import ScrollController
from gestureos.commands.switch import SwipeController, SwipeDirection
from gestureos.commands.types import Command, CommandType
from gestureos.interaction.state_machine import Intent, IntentPhase
from gestureos.macos.adapter import MacOSAdapter
from gestureos.vision.features import Point2D
from gestureos.vision.mapping import CursorMapper

logger = logging.getLogger("gestureos.commands.router")


class CommandRouter:
    def __init__(
        self,
        adapter: MacOSAdapter,
        safety: SafetyPolicy,
        cursor_mapper: CursorMapper | None = None,
        drag_controller: DragController | None = None,
        scroll_controller: ScrollController | None = None,
        swipe_controller: SwipeController | None = None,
    ) -> None:
        self._adapter = adapter
        self._safety = safety
        self._cursor_mapper = cursor_mapper
        self._drag_controller = drag_controller or DragController()
        self._scroll_controller = scroll_controller or ScrollController()
        self._swipe_controller = swipe_controller or SwipeController()
        self._dispatch: dict[CommandType, Callable[[Command], bool]] = {
            CommandType.SWITCH_APP_NEXT: self._always(lambda cmd: self._adapter.switch_app_next()),
            CommandType.SWITCH_APP_PREVIOUS: self._always(
                lambda cmd: self._adapter.switch_app_previous()
            ),
            CommandType.LAUNCH_APP: self._always(
                lambda cmd: self._adapter.launch_app(cmd.params.get("name", ""))
            ),
            CommandType.MEDIA_PLAY_PAUSE: self._always(lambda cmd: self._adapter.media_play_pause()),
            CommandType.SPACE_NEXT: self._always(lambda cmd: self._adapter.space_next()),
            CommandType.SPACE_PREVIOUS: self._always(lambda cmd: self._adapter.space_previous()),
        }

    @staticmethod
    def _always(fn: Callable[[Command], None]) -> Callable[[Command], bool]:
        def wrapped(cmd: Command) -> bool:
            fn(cmd)
            return True

        return wrapped

    def _map(self, position: Point2D) -> Point2D:
        if self._cursor_mapper is None:
            return position  # no mapper configured (e.g. most tests) —
            # pass the normalized position straight through.
        return self._cursor_mapper.map(position)

    def _handle_mouse_down(self, command: Command) -> bool:
        position = command.params.get("position")
        self._drag_controller.begin(position)
        if position is not None:
            mapped = self._map(position)
            self._adapter.move_cursor(mapped.x, mapped.y, dragging=False)
        self._adapter.mouse_down(command.params.get("button", "left"))
        return True

    def _handle_mouse_move(self, command: Command) -> bool:
        raw_position = command.params.get("position")
        engaged_position = self._drag_controller.update(raw_position)
        if engaged_position is None:
            return False  # still inside the click deadzone — cursor stays put
        mapped = self._map(engaged_position)
        self._adapter.move_cursor(mapped.x, mapped.y, dragging=True)
        return True

    def _handle_mouse_up(self, command: Command) -> bool:
        raw_position = command.params.get("position")
        if raw_position is not None and self._drag_controller.is_engaged:
            mapped = self._map(raw_position)
            self._adapter.move_cursor(mapped.x, mapped.y, dragging=True)
        self._drag_controller.end()
        self._adapter.mouse_up(command.params.get("button", "left"))
        return True

    def _handle_scroll(self, command: Command) -> bool:
        position = command.params.get("position")
        if command.source_phase is IntentPhase.START:
            self._scroll_controller.begin(position)
            return False  # nothing to scroll yet — just establishing a reference point
        if command.source_phase is IntentPhase.END:
            self._scroll_controller.end()
            return False

        delta = self._scroll_controller.update(position)
        if delta is None:
            return False  # not enough movement yet this frame
        dx, dy = delta
        self._adapter.scroll(dx, dy)
        return True

    def _handle_app_switch(self, command: Command) -> bool:
        position = command.params.get("position")
        if command.source_phase is IntentPhase.START:
            self._swipe_controller.begin(position)
            return False  # just establishing a reference point
        if command.source_phase is IntentPhase.END:
            self._swipe_controller.end()
            return False

        direction = self._swipe_controller.update(position)
        if direction is None:
            return False  # threshold not crossed yet this hold
        if direction is SwipeDirection.RIGHT:
            self._adapter.switch_app_next()
        else:
            self._adapter.switch_app_previous()
        return True

    def route_intent(self, intent: Intent) -> Command | None:
        """Process one Intent. Returns the Command that was actually
        dispatched, or None if nothing happened (unbound gesture,
        blocked by the safety policy, or — for MOUSE_MOVE/SCROLL/
        APP_SWITCH — still inside a deadzone/reference-setting frame).
        """
        command_type = resolve_command_type(intent)
        if command_type is None:
            return None

        params: dict[str, object] = {}
        if intent.position is not None:
            params["position"] = intent.position

        command = Command(
            type=command_type,
            source_gesture=intent.gesture,
            source_phase=intent.phase,
            handedness=intent.handedness,
            timestamp=intent.timestamp,
            params=params,
        )

        decision = self._safety.check(command)
        if not decision.allowed:
            logger.info(
                "command_blocked",
                extra={"fields": {"command": command_type.value, "reason": decision.reason}},
            )
            return None

        if command_type is CommandType.MOUSE_DOWN:
            handler: Callable[[Command], bool] = self._handle_mouse_down
        elif command_type is CommandType.MOUSE_MOVE:
            handler = self._handle_mouse_move
        elif command_type is CommandType.MOUSE_UP:
            handler = self._handle_mouse_up
        elif command_type is CommandType.SCROLL:
            handler = self._handle_scroll
        elif command_type is CommandType.APP_SWITCH:
            handler = self._handle_app_switch
        else:
            found = self._dispatch.get(command_type)
            if found is None:
                logger.warning(
                    "command_unhandled", extra={"fields": {"command": command_type.value}}
                )
                return None
            handler = found

        try:
            executed = handler(command)
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

        if not executed:
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
