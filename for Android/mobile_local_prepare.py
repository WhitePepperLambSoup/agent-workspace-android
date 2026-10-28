"""Preparing the on-device model: it reads its whole system prompt once, ahead of the first message.

On a phone the on-device model reads the ~10k-token system prompt and tool list at 30-60 tokens a
second: about six minutes for Qwen3.5 0.8B on a Snapdragon 888 before the first word of "hello",
twenty for 2B. It keeps what it read on disk for that exact prompt (llama.cpp prefix files; every
conversation shares one prompt, mobile_prompt_cache.SHARED_ON_DEVICE), so later conversations start
in about a second. Right after the user switches to the model, a hidden conversation sends one short
message; once the model starts answering, the task stops and the conversation is deleted.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from mobile_local_models import native_engine_status
from mobile_protocol import MobileTaskRequest

_TITLE = "准备本机模型"
_PROMPT = "你好"
_LIMIT_SECONDS = 3 * 3600
_FINISHED = {"succeeded", "failed", "cancelled", "interrupted"}
_state: dict[str, Any] = {"job": None}


def preparing() -> bool:
    job = _state["job"]
    return job is not None and not job.done()


def start(api: Any, controller: Any, *, poll: float = 2.0) -> dict[str, str]:
    """Starts preparing in the background (once at a time)."""
    if preparing():
        return {"state": "preparing"}
    _state["job"] = asyncio.get_running_loop().create_task(
        _prepare(api, controller, poll), name="local-model-prepare"
    )
    return {"state": "started"}


def _state_name(task: Any) -> str:
    state = getattr(task, "state", "")
    return str(getattr(state, "value", state))


async def _prepare(api: Any, controller: Any, poll: float) -> None:
    session_id = None
    try:
        document = await asyncio.to_thread(api.create_session, _TITLE)
        session_id = document["id"]
        # Out of the conversation list while it runs (archived), deleted when done.
        await api._archive_session(session_id, True)
        started = time.time()
        task = await controller.submit(MobileTaskRequest(session_id=session_id, prompt=_PROMPT))
        deadline = time.monotonic() + _LIMIT_SECONDS
        while time.monotonic() < deadline:
            current = controller.tasks.get(task.task_id)
            if _state_name(current) in _FINISHED:
                break
            native = await asyncio.to_thread(native_engine_status)
            last = native.get("last_generation") or {}
            answering = native.get("generation_phase") == "token_generation" or (
                float(last.get("completed_at") or 0) >= started
            )
            # Reading the prompt is what takes the time; once it answers (or asks to use a tool)
            # the prompt is saved and the rest is not needed.
            if answering or _state_name(current) == "waiting_approval":
                with contextlib.suppress(Exception):
                    await controller.cancel(task.task_id)
                break
            await asyncio.sleep(poll)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(controller.wait(task.task_id), 120)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.getLogger(__name__).exception("preparing the on-device model failed")
    finally:
        if session_id is not None:
            with contextlib.suppress(Exception):
                await api._delete_sessions([session_id])
