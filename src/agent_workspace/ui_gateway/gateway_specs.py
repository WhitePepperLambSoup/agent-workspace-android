"""The Specs tab: specs of the open folder, approving their documents, and the prompts that ask
the agent to write the next document or build the tasks."""

from __future__ import annotations

from typing import Any

from agent_workspace.coding.specs import SpecBook, SpecError
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

SPEC_COMMANDS = frozenset(
    {"spec.list", "spec.create", "spec.get", "spec.approve", "spec.reopen", "spec.prompt"}
)


class SpecCommands(GatewayState):
    def _spec_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        book = SpecBook(self._open_folder())
        payload: dict[str, Any] = command.payload
        try:
            if command.type == "spec.list":
                result: dict[str, object] = {"specs": book.list()}
            elif command.type == "spec.create":
                title, goal = payload.get("title"), payload.get("goal", "")
                if not isinstance(title, str) or not isinstance(goal, str):
                    raise GatewayError("invalid_command")
                result = {"spec": book.create(title, goal)}
            elif command.type == "spec.get":
                result = {"spec": book.get(payload.get("id"))}
            elif command.type == "spec.approve":
                result = {"spec": book.approve(payload.get("id"), payload.get("step"))}
            elif command.type == "spec.reopen":
                result = {"spec": book.reopen(payload.get("id"), payload.get("step"))}
            else:
                language = payload.get("language", "en-US")
                task = payload.get("task")
                if not isinstance(language, str) or (
                    task is not None and not isinstance(task, str)
                ):
                    raise GatewayError("invalid_command")
                prompt = book.prompt(payload.get("id"), payload.get("step"), language, task)
                result = {"prompt": prompt}
        except SpecError as error:
            raise GatewayError(error.code) from None
        except OSError:
            raise GatewayError("spec_unwritable") from None
        return self._reply(f"{command.type}.result", result, session_id=None)


__all__ = ["SPEC_COMMANDS", "SpecCommands"]
