"""Let the agent ask a paired phone to do something; the phone's user agrees first.

The desktop supplies the launcher. A request waits on the phone until its user accepts or
rejects it (it expires after 10 minutes unanswered); the phone's own agent then does the work
under the phone's own protections and reports back. The call waits for the end, a refusal,
expiry or ``wait_minutes``, and returns the phone's answer or why there is none. Stopping the
turn withdraws the request, and the phone stops what it was doing.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

_MAX_TASK = 8000
_MAX_DEVICE = 128
_DEFAULT_WAIT_MINUTES = 15
_MAX_WAIT_MINUTES = 60
_POLL_SECONDS = 2.0
FINISHED_STATES = frozenset({"succeeded", "failed", "rejected", "expired", "cancelled"})


@dataclass(frozen=True, slots=True)
class PhoneJobRequest:
    session_id: str
    task: str
    operate_phone: bool = False
    device: str | None = None


@dataclass(frozen=True, slots=True)
class PhoneJobOutcome:
    job_id: str
    device: str
    # waiting, accepted, running, succeeded, failed, rejected, expired or cancelled
    state: str
    result: str | None = None
    error: str | None = None


class PhoneJobLauncher(Protocol):
    def offered(self) -> bool:
        """Whether a paired phone takes requests at all (the tool is not offered otherwise)."""
        ...

    def submit(self, request: PhoneJobRequest) -> PhoneJobOutcome:
        """Queue the request for the phone; ToolError says why it cannot be sent."""
        ...

    def poll(self, job_id: str) -> PhoneJobOutcome: ...

    def cancel(self, job_id: str) -> None: ...


def parse_request(arguments: dict[str, Any], session_id: str) -> tuple[PhoneJobRequest, int]:
    task = arguments.get("task")
    if not isinstance(task, str) or not task.strip() or len(task) > _MAX_TASK:
        raise ToolArgumentError(f"'task' must be a non-empty string of at most {_MAX_TASK} chars")
    operate = arguments.get("operate_phone", False)
    if type(operate) is not bool:
        raise ToolArgumentError("'operate_phone' must be true or false")
    device = arguments.get("device")
    if device is not None and (
        not isinstance(device, str) or not device.strip() or len(device) > _MAX_DEVICE
    ):
        raise ToolArgumentError("'device' must be a phone's name or id")
    wait = arguments.get("wait_minutes", _DEFAULT_WAIT_MINUTES)
    if type(wait) is not int or not 1 <= wait <= _MAX_WAIT_MINUTES:
        raise ToolArgumentError(f"'wait_minutes' must be 1 to {_MAX_WAIT_MINUTES}")
    request = PhoneJobRequest(
        session_id, task.strip(), operate, device.strip() if isinstance(device, str) else None
    )
    return request, wait


def _document(outcome: PhoneJobOutcome, *, waited: bool = False) -> str:
    document: dict[str, object] = {
        "job_id": outcome.job_id,
        "phone": outcome.device,
        "state": outcome.state,
    }
    if outcome.result is not None:
        document["result"] = outcome.result
    if outcome.error is not None:
        document["error"] = outcome.error
    reasons = {
        "rejected": "the phone's user declined the request",
        "expired": "nobody answered the request on the phone within 10 minutes",
        "cancelled": "the request was withdrawn",
    }
    if outcome.state in reasons:
        document["reason"] = reasons[outcome.state]
    elif waited:
        document["reason"] = (
            "still not finished; the phone may finish it later, but this call stopped waiting"
        )
    return json_result(document)


class PhoneTaskTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="phone_task",
        description=(
            "Ask the user's paired phone to do something only the phone can do: send a file or "
            "message from a phone app such as WeChat, check whether a text message (for example "
            "a verification code) has arrived, look something up in a phone app, or take an "
            "action on the phone. The phone's user is asked first and may decline; the phone's "
            "own assistant then does it, and the phone's protections still apply (it will not "
            "read out card numbers, ID numbers or codes, uninstall apps, and so on). Set "
            "'operate_phone' when it needs tapping the screen or using other apps. Write the "
            "task so that someone without this conversation can do it, including any text to "
            "send. Name the phone in 'device' when there is more than one. The call waits until "
            "the phone is done, declines, or 'wait_minutes' pass, and returns the phone's answer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "minLength": 1, "maxLength": _MAX_TASK},
                "operate_phone": {"type": "boolean"},
                "device": {"type": "string", "minLength": 1, "maxLength": _MAX_DEVICE},
                "wait_minutes": {"type": "integer", "minimum": 1, "maximum": _MAX_WAIT_MINUTES},
            },
            "required": ["task"],
            "additionalProperties": False,
        },
        # The task goes to another device, so it is approved like any outside request.
        side_effect="network",
        capability=Capability.NETWORK_READ,
    )

    def __init__(self, launcher: PhoneJobLauncher, *, poll_seconds: float = _POLL_SECONDS) -> None:
        self.launcher = launcher
        self._poll_seconds = poll_seconds

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def offered(self) -> bool:
        try:
            return self.launcher.offered()
        except Exception:
            return False

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        wait = arguments.get("wait_minutes", _DEFAULT_WAIT_MINUTES)
        minutes = (
            wait if type(wait) is int and 1 <= wait <= _MAX_WAIT_MINUTES else _MAX_WAIT_MINUTES
        )
        return minutes * 60.0 + 30.0

    async def execute(self, arguments: dict[str, Any]) -> str:
        raise ToolError("phone_task runs only inside a conversation")

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        request, wait_minutes = parse_request(arguments, context.session_id)
        outcome = await asyncio.to_thread(self.launcher.submit, request)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_minutes * 60.0
        try:
            while outcome.state not in FINISHED_STATES:
                if loop.time() >= deadline:
                    return _document(outcome, waited=True)
                await asyncio.sleep(self._poll_seconds)
                outcome = await asyncio.to_thread(self.launcher.poll, outcome.job_id)
        except asyncio.CancelledError:
            # The turn was stopped: withdraw the request so the phone stops too.
            await asyncio.shield(asyncio.to_thread(self.launcher.cancel, outcome.job_id))
            raise
        return _document(outcome)


__all__ = [
    "FINISHED_STATES",
    "PhoneJobLauncher",
    "PhoneJobOutcome",
    "PhoneJobRequest",
    "PhoneTaskTool",
    "parse_request",
]
