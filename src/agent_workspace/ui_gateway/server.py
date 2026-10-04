from __future__ import annotations

import json
import sys
import threading
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field
from typing import BinaryIO

from agent_workspace.ui_gateway.protocol import (
    MAX_MESSAGE_BYTES,
    CommandEnvelope,
    ProtocolError,
    encode_message,
    parse_command_line,
)
from agent_workspace.ui_gateway.runtime import GatewayError, GatewayReply, GatewayRuntime


@dataclass(slots=True)
class GatewayServer:
    input_stream: BinaryIO
    output_stream: BinaryIO
    runtime: GatewayRuntime = field(default_factory=GatewayRuntime)
    handshaken: bool = False
    _response_order_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _output_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _next_wire_sequence: int = field(default=1, init=False)
    _stopping: threading.Event = field(default_factory=threading.Event, init=False)
    _provider_test_slot: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(1),
        init=False,
    )
    _provider_test_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="gateway-provider-test",
        ),
        init=False,
    )
    _git_delivery_slot: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(1),
        init=False,
    )
    _git_delivery_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="gateway-git-delivery",
        ),
        init=False,
    )
    _query_slots: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(2), init=False
    )
    _query_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="gateway-query"
        ),
        init=False,
    )

    def run(self) -> int:
        pump = threading.Thread(target=self._pump_events, name="gateway-events", daemon=True)
        pump.start()
        try:
            while line := self.input_stream.readline(MAX_MESSAGE_BYTES + 2):
                if self._process_line(line, concurrent_commands=True):
                    return 0
            return 0
        finally:
            self._provider_test_executor.shutdown(wait=True, cancel_futures=True)
            self._query_executor.shutdown(wait=True, cancel_futures=True)
            self._git_delivery_executor.shutdown(wait=True, cancel_futures=True)
            self._stopping.set()
            pump.join(timeout=1)
            with suppress(GatewayError):
                self.runtime.close()

    def _process_line(self, line: bytes, *, concurrent_commands: bool = False) -> bool:
        request_id, session_id = _request_context(line)
        try:
            command = parse_command_line(line)
        except ProtocolError as error:
            with self._response_order_lock:
                return self._write_error_response(request_id, session_id, str(error))
        if command.type in {"provider.test", "provider.health"} and concurrent_commands:
            return self._schedule_provider_test(command, request_id, session_id)
        if (
            command.type in {"workspace.git.deliver", "workspace.review.pr.create"}
            and concurrent_commands
        ):
            return self._schedule_git_delivery(command, request_id, session_id)
        if (
            command.type
            in {
                "workspace.review.create",
                "workspace.review.pr.refresh",
                "system.doctor",
                "session.history",
                "workspace.collaborations.list",
                "workspace.collaborations.get",
                "workspace.collaborations.cancel",
                "workspace.collaborations.resume",
                "workspace.deliveries.list",
                "workspace.deliveries.get",
                "workspace.deliveries.cancel",
                "workspace.deliveries.resume",
            }
            and concurrent_commands
        ):
            return self._schedule_query(command, request_id, session_id)
        if command.type in {"provider.test", "provider.health"}:
            return self._dispatch_and_respond(command, request_id, session_id)
        with self._response_order_lock:
            return self._dispatch_and_respond(command, request_id, session_id)

    def _schedule_query(
        self, command: CommandEnvelope, request_id: str, session_id: str | None
    ) -> bool:
        if not self._query_slots.acquire(blocking=False):
            return self._write_error_response(request_id, session_id, "runtime_busy")
        try:
            future = self._query_executor.submit(
                self._dispatch_and_respond, command, request_id, session_id
            )
        except RuntimeError:
            self._query_slots.release()
            return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._query_slots.release())
        return False

    def _schedule_provider_test(
        self,
        command: CommandEnvelope,
        request_id: str,
        session_id: str | None,
    ) -> bool:
        if not self._provider_test_slot.acquire(blocking=False):
            with self._response_order_lock:
                return self._write_error_response(request_id, session_id, "runtime_busy")
        try:
            future = self._provider_test_executor.submit(
                self._dispatch_and_respond,
                command,
                request_id,
                session_id,
            )
        except RuntimeError:
            self._provider_test_slot.release()
            with self._response_order_lock:
                return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._provider_test_slot.release())
        return False

    def _schedule_git_delivery(
        self,
        command: CommandEnvelope,
        request_id: str,
        session_id: str | None,
    ) -> bool:
        if not self._git_delivery_slot.acquire(blocking=False):
            with self._response_order_lock:
                return self._write_error_response(request_id, session_id, "runtime_busy")
        try:
            future = self._git_delivery_executor.submit(
                self._dispatch_and_respond,
                command,
                request_id,
                session_id,
            )
        except RuntimeError:
            self._git_delivery_slot.release()
            with self._response_order_lock:
                return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._git_delivery_slot.release())
        return False

    def _dispatch_and_respond(
        self,
        command: CommandEnvelope,
        request_id: str,
        session_id: str | None,
    ) -> bool:
        try:
            reply = self._dispatch(command)
            response = reply.to_document(command.request_id)
            should_stop = reply.should_stop
        except (ProtocolError, GatewayError) as error:
            return self._write_error_response(request_id, session_id, str(error))
        self._write_response(response, request_id, session_id)
        return should_stop

    def _write_response(
        self,
        response: Mapping[str, object],
        request_id: str,
        session_id: str | None,
    ) -> None:
        with self._output_lock:
            try:
                self._write(response)
            except ProtocolError as error:
                response = self.runtime.error_reply(request_id, str(error), session_id)
                self._write(response)
            self._write_pending_events()

    def _write_error_response(
        self,
        request_id: str,
        session_id: str | None,
        error_code: str,
    ) -> bool:
        response = self.runtime.error_reply(request_id, error_code, session_id)
        self._write_response(response, request_id, session_id)
        return error_code == "message_too_large"

    def _dispatch(self, command: CommandEnvelope) -> GatewayReply:
        if command.type == "app.handshake":
            reply = self.runtime.execute(command)
            self.handshaken = True
            return reply
        if not self.handshaken:
            raise ProtocolError("handshake_required")
        return self.runtime.execute(command)

    def _pump_events(self) -> None:
        while not self._stopping.wait(0.02):
            with self._response_order_lock, self._output_lock:
                self._write_pending_events()

    def _write_pending_events(self) -> None:
        for event in self.runtime.drain_events():
            self._write(event)

    def _write(self, message: Mapping[str, object]) -> None:
        document = dict(message)
        if document.get("kind") in {"response", "event"}:
            document["sequence"] = self._next_wire_sequence
            self._next_wire_sequence += 1
        self.output_stream.write(encode_message(document))
        self.output_stream.flush()


def _request_context(line: bytes) -> tuple[str, str | None]:
    try:
        document = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "invalid-request", None
    if not isinstance(document, Mapping):
        return "invalid-request", None
    request_id = document.get("requestId")
    session_id = document.get("sessionId")
    return (
        request_id if isinstance(request_id, str) and request_id else "invalid-request",
        session_id if isinstance(session_id, str) and session_id else None,
    )


def main() -> int:
    return GatewayServer(sys.stdin.buffer, sys.stdout.buffer).run()
