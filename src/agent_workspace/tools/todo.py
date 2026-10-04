from __future__ import annotations

from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore, ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, TodoItem, TodoStatus, ToolSpec

from .base import ToolArgumentError, json_result, require_string


class TodoTool:
    _SPEC = ToolSpec(
        name="todo",
        description=(
            "Manage durable Todo items for the current session. Actions: list; add requires "
            "content (optional zero-based position; a new item always starts pending); update "
            "requires id and at least one of content, status (pending, in_progress, completed), "
            "or position; complete and delete require id."
        ),
        input_schema={
            "oneOf": [
                {
                    "type": "object",
                    "properties": {"action": {"const": "list"}},
                    "required": ["action"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "add"},
                        "content": {"type": "string", "minLength": 1, "maxLength": 10000},
                        "position": {"type": "integer", "minimum": 0},
                        "status": {"const": TodoStatus.PENDING.value},
                    },
                    "required": ["action", "content"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "update"},
                        "id": {"type": "string", "minLength": 1},
                        "content": {"type": "string", "minLength": 1, "maxLength": 10000},
                        "status": {"enum": [status.value for status in TodoStatus]},
                        "position": {"type": "integer", "minimum": 0},
                    },
                    "required": ["action", "id"],
                    "anyOf": [
                        {"required": ["content"]},
                        {"required": ["status"]},
                        {"required": ["position"]},
                    ],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "complete"},
                        "id": {"type": "string", "minLength": 1},
                    },
                    "required": ["action", "id"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "delete"},
                        "id": {"type": "string", "minLength": 1},
                    },
                    "required": ["action", "id"],
                    "additionalProperties": False,
                },
            ]
        },
        side_effect="session_state",
        capability=Capability.TODO,
        provider_input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "update", "complete", "delete"],
                },
                "id": {"type": "string", "minLength": 1},
                "content": {"type": "string", "minLength": 1, "maxLength": 10000},
                "status": {"type": "string", "enum": [status.value for status in TodoStatus]},
                "position": {"type": "integer", "minimum": 0},
            },
            "required": ["action"],
            "additionalProperties": False,
            "allOf": [
                {
                    "if": {
                        "properties": {"action": {"const": "add"}},
                        "required": ["action"],
                    },
                    "then": {
                        "required": ["content"],
                        "properties": {"status": {"const": TodoStatus.PENDING.value}},
                    },
                },
                {
                    "if": {
                        "properties": {"action": {"const": "update"}},
                        "required": ["action"],
                    },
                    "then": {
                        "required": ["id"],
                        "anyOf": [
                            {"required": ["content"]},
                            {"required": ["status"]},
                            {"required": ["position"]},
                        ],
                    },
                },
                {
                    "if": {
                        "properties": {"action": {"const": "complete"}},
                        "required": ["action"],
                    },
                    "then": {"required": ["id"]},
                },
                {
                    "if": {
                        "properties": {"action": {"const": "delete"}},
                        "required": ["action"],
                    },
                    "then": {"required": ["id"]},
                },
            ],
        },
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("todo requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        action = require_string(arguments, "action")
        todos = self._store.list_todos(context.session_id)
        if action == "list":
            return json_result({"todos": [_todo_data(todo) for todo in todos]})
        if action == "add":
            content = require_string(arguments, "content")
            position = arguments.get("position", len(todos))
            if not isinstance(position, int) or isinstance(position, bool) or position < 0:
                raise ToolArgumentError("'position' must be a non-negative integer")
            todo_id = str(uuid4())
            await self._upsert(
                context,
                todo_id,
                content,
                TodoStatus.PENDING,
                position,
            )
            return json_result({"todo_id": todo_id, "status": TodoStatus.PENDING.value})

        todo_id = require_string(arguments, "id")
        existing = next((todo for todo in todos if todo.id == todo_id), None)
        if existing is None:
            raise ToolArgumentError(f"unknown todo id: {todo_id}")
        if action == "delete":
            await context.record_event(
                Event(
                    session_id=context.session_id,
                    type="todo.deleted",
                    data={"todo_id": todo_id, "attempt_id": context.attempt_id},
                    causation_id=context.started_event_id,
                    correlation_id=context.correlation_id,
                )
            )
            return json_result({"todo_id": todo_id, "deleted": True})
        if action == "complete":
            status = TodoStatus.COMPLETED
        elif action == "update":
            raw_status = arguments.get("status", existing.status.value)
            if not isinstance(raw_status, str):
                raise ToolArgumentError("'status' must be a string")
            status = TodoStatus(raw_status)
        else:
            raise ToolArgumentError(f"unsupported todo action: {action}")
        content_value = arguments.get("content", existing.content)
        if not isinstance(content_value, str) or not content_value:
            raise ToolArgumentError("'content' must be a non-empty string")
        position_value = arguments.get("position", existing.position)
        if (
            not isinstance(position_value, int)
            or isinstance(position_value, bool)
            or position_value < 0
        ):
            raise ToolArgumentError("'position' must be a non-negative integer")
        await self._upsert(
            context,
            todo_id,
            content_value,
            status,
            position_value,
        )
        return json_result({"todo_id": todo_id, "status": status.value})

    async def _upsert(
        self,
        context: ToolExecutionContext,
        todo_id: str,
        content: str,
        status: TodoStatus,
        position: int,
    ) -> None:
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="todo.upserted",
                data={
                    "todo_id": todo_id,
                    "attempt_id": context.attempt_id,
                    "content": content,
                    "status": status.value,
                    "position": position,
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )


def _todo_data(todo: TodoItem) -> dict[str, object]:
    return {
        "id": todo.id,
        "content": todo.content,
        "status": todo.status.value,
        "position": todo.position,
    }
