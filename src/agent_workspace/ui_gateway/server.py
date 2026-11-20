from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, cast

from agent_workspace.config import default_database_path
from agent_workspace.storage.slow_work import report_slow_work_with
from agent_workspace.storage.sqlite import SQLiteEventStore, trust_databases_validated_here
from agent_workspace.storage.stream_compaction import compact_finished_streams
from agent_workspace.ui_gateway.backups import run_daily_backup
from agent_workspace.ui_gateway.data_care import apply_pending_restore
from agent_workspace.ui_gateway.gateway_code import (
    CODE_LONG_COMMANDS,
    CODE_QUERY_COMMANDS,
    EDITOR_MODEL_COMMANDS,
)
from agent_workspace.ui_gateway.gateway_common import _LOGGER
from agent_workspace.ui_gateway.gateway_data import DATA_LONG_COMMANDS, DATA_QUERY_COMMANDS
from agent_workspace.ui_gateway.gateway_debug import DEBUG_LONG_COMMANDS, DEBUG_QUERY_COMMANDS
from agent_workspace.ui_gateway.gateway_git import (
    GIT_GITHUB_COMMANDS,
    GIT_MODEL_COMMANDS,
    GIT_QUERY_COMMANDS,
)
from agent_workspace.ui_gateway.gateway_latex import LATEX_LONG_COMMANDS
from agent_workspace.ui_gateway.gateway_project import PROJECT_COMMANDS, PROJECT_LONG_COMMANDS
from agent_workspace.ui_gateway.gateway_science import SCIENCE_LONG_COMMANDS
from agent_workspace.ui_gateway.gateway_shell import SHELL_QUERY_COMMANDS
from agent_workspace.ui_gateway.gateway_specs import SPEC_COMMANDS
from agent_workspace.ui_gateway.gateway_tour import TOUR_MODEL_COMMANDS, TOUR_QUERY_COMMANDS
from agent_workspace.ui_gateway.protocol import (
    MAX_MESSAGE_BYTES,
    CommandEnvelope,
    ProtocolError,
    encode_message,
    parse_command_line,
)
from agent_workspace.ui_gateway.runtime import GatewayError, GatewayReply, GatewayRuntime

# One model request each, run off the command thread so the window stays responsive.
_MAIN_PROCESS_REPLIES = frozenset({"app.activity.result"})

_MODEL_CALL_COMMANDS = frozenset(
    {
        "prompt.optimize",
        "audio.transcribe",
        "workspace.review.ai",
        *EDITOR_MODEL_COMMANDS,
        *GIT_MODEL_COMMANDS,
        *TOUR_MODEL_COMMANDS,
    }
)


@dataclass(slots=True)
class GatewayServer:
    input_stream: BinaryIO
    output_stream: BinaryIO
    runtime: GatewayRuntime = field(default_factory=GatewayRuntime)
    handshaken: bool = False
    _response_order_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _output_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _next_wire_sequence: int = field(default=1, init=False)
    _drain_failure: str | None = field(default=None, init=False)
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
    # Queries run two at a time; a few more wait their turn rather than fail, so a page that asks
    # several at once (Operations lists collaborations and deliveries while the Inspector reads
    # usage) is not told the runtime is busy.
    _query_slots: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(8), init=False
    )
    _query_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="gateway-query"
        ),
        init=False,
    )
    # Commands that wait for a model or a speech service: seconds each, and while they ran on
    # the reader thread no other command was read and no event was written.
    _model_call_slots: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(2), init=False
    )
    _model_call_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="gateway-model-call"
        ),
        init=False,
    )

    # Compiling a document or installing Tectonic takes seconds to minutes: one at a time.
    _latex_slot: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(1), init=False
    )
    _latex_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="gateway-latex"
        ),
        init=False,
    )

    # Downloading a language server or running the project's checks (minutes): one at a time.
    _code_job_slot: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(1), init=False
    )
    _code_job_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="gateway-code-job"
        ),
        init=False,
    )

    # Asking GitHub for CI runs, a failed log or the issues: network calls of up to 90 s,
    # kept apart from the queries the window waits on.
    _github_slots: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(4), init=False
    )
    _github_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="gateway-github"
        ),
        init=False,
    )

    # Installing the scientific environment (minutes) or redrawing a corrected figure.
    _science_slot: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(1), init=False
    )
    _science_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="gateway-science"
        ),
        init=False,
    )

    def run(self) -> int:
        pump = threading.Thread(target=self._pump_events, name="gateway-events", daemon=True)
        pump.start()
        try:
            while line := self.input_stream.readline(MAX_MESSAGE_BYTES + 2):
                if len(line) > MAX_MESSAGE_BYTES and not line.endswith(b"\n"):
                    # Too long to be one message. Read past the rest of the line, so the next
                    # command starts clean, and answer this one: stopping here would end every
                    # conversation the sidecar runs.
                    self._skip_rest_of_line()
                    with self._response_order_lock:
                        self._write_error_response(
                            _oversized_request_id(line), None, "message_too_large"
                        )
                    continue
                if self._process_line(line, concurrent_commands=True):
                    return 0
            return 0
        finally:
            # A compile still running would hold the shutdown for minutes.
            stop_latex = getattr(self.runtime, "stop_latex", None)
            if callable(stop_latex):
                stop_latex()
            self._latex_executor.shutdown(wait=True, cancel_futures=True)
            stop_science = getattr(self.runtime, "stop_science", None)
            if callable(stop_science):
                stop_science()
            self._science_executor.shutdown(wait=True, cancel_futures=True)
            self._code_job_executor.shutdown(wait=True, cancel_futures=True)
            self._github_executor.shutdown(wait=True, cancel_futures=True)
            self._provider_test_executor.shutdown(wait=True, cancel_futures=True)
            self._model_call_executor.shutdown(wait=True, cancel_futures=True)
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
        if command.type in _MODEL_CALL_COMMANDS and concurrent_commands:
            return self._schedule_model_call(command, request_id, session_id)
        if command.type in LATEX_LONG_COMMANDS and concurrent_commands:
            return self._schedule_latex(command, request_id, session_id)
        if command.type in SCIENCE_LONG_COMMANDS and concurrent_commands:
            return self._schedule_science(command, request_id, session_id)
        if command.type in CODE_LONG_COMMANDS and concurrent_commands:
            return self._schedule_code_job(command, request_id, session_id)
        if command.type in PROJECT_LONG_COMMANDS and concurrent_commands:
            return self._schedule_code_job(command, request_id, session_id)
        if command.type in PROJECT_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in CODE_QUERY_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in DATA_QUERY_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in DATA_LONG_COMMANDS and concurrent_commands:
            return self._schedule_code_job(command, request_id, session_id)
        if command.type in SHELL_QUERY_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in DEBUG_QUERY_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in DEBUG_LONG_COMMANDS and concurrent_commands:
            return self._schedule_code_job(command, request_id, session_id)
        if command.type in TOUR_QUERY_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in SPEC_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in GIT_QUERY_COMMANDS and concurrent_commands:
            return self._schedule_query(command, request_id, session_id)
        if command.type in GIT_GITHUB_COMMANDS and concurrent_commands:
            return self._schedule_github(command, request_id, session_id)
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
                "session.reply.read",
                # git diff on a large repository takes a while.
                "workspace.git.diff",
                "workspace.collaborations.list",
                "workspace.collaborations.get",
                "workspace.collaborations.cancel",
                "workspace.collaborations.resume",
                "workspace.deliveries.list",
                "workspace.deliveries.get",
                "workspace.deliveries.cancel",
                "workspace.deliveries.resume",
                # Copying large files, or fetching a web page, would hold up the window.
                "knowledge.add",
                "knowledge.search",
                "document.preview",
                # Reading a month of usage, moving a batch back or scanning watched folders.
                "usage.bill",
                "session.rewind",
                "turn.files.diff",
                "turn.files.undo",
                "turn.files.hunk.undo",
                "files.batches.undo",
                "knowledge.watch.add",
                "knowledge.watch.scan",
                # Reading a document's sources, or its SyncTeX file.
                "latex.check",
                "latex.synctex",
                # Asking the scholarly databases or Zotero; writing a .bib file.
                "references.search",
                "references.zotero",
                "references.add",
                "references.cite",
                "references.import",
                "references.export",
                "references.check",
                # Writing a long answer as a Word file; building the document templates.
                "answer.export",
                "templates.list",
                "templates.create",
                # A model's answer, or text recognition of a picture.
                "quick.run",
                "quick.table",
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

    def _schedule_latex(
        self, command: CommandEnvelope, request_id: str, session_id: str | None
    ) -> bool:
        if not self._latex_slot.acquire(blocking=False):
            return self._write_error_response(request_id, session_id, "latex_busy")
        try:
            future = self._latex_executor.submit(
                self._dispatch_and_respond, command, request_id, session_id
            )
        except RuntimeError:
            self._latex_slot.release()
            return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._latex_slot.release())
        return False

    def _schedule_science(
        self, command: CommandEnvelope, request_id: str, session_id: str | None
    ) -> bool:
        if not self._science_slot.acquire(blocking=False):
            return self._write_error_response(request_id, session_id, "science_busy")
        try:
            future = self._science_executor.submit(
                self._dispatch_and_respond, command, request_id, session_id
            )
        except RuntimeError:
            self._science_slot.release()
            return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._science_slot.release())
        return False

    def _schedule_github(
        self, command: CommandEnvelope, request_id: str, session_id: str | None
    ) -> bool:
        if not self._github_slots.acquire(blocking=False):
            return self._write_error_response(request_id, session_id, "runtime_busy")
        try:
            future = self._github_executor.submit(
                self._dispatch_and_respond, command, request_id, session_id
            )
        except RuntimeError:
            self._github_slots.release()
            return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._github_slots.release())
        return False

    def _schedule_code_job(
        self, command: CommandEnvelope, request_id: str, session_id: str | None
    ) -> bool:
        if not self._code_job_slot.acquire(blocking=False):
            return self._write_error_response(request_id, session_id, "runtime_busy")
        try:
            future = self._code_job_executor.submit(
                self._dispatch_and_respond, command, request_id, session_id
            )
        except RuntimeError:
            self._code_job_slot.release()
            return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._code_job_slot.release())
        return False

    def _schedule_model_call(
        self, command: CommandEnvelope, request_id: str, session_id: str | None
    ) -> bool:
        if not self._model_call_slots.acquire(blocking=False):
            return self._write_error_response(request_id, session_id, "runtime_busy")
        try:
            future = self._model_call_executor.submit(
                self._dispatch_and_respond, command, request_id, session_id
            )
        except RuntimeError:
            self._model_call_slots.release()
            return self._write_error_response(request_id, session_id, "runtime_busy")
        future.add_done_callback(lambda _future: self._model_call_slots.release())
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
            # The window treats a reply with no epoch as one from another run of the sidecar and
            # reads its whole state again; each command need not remember to add it.
            epoch = getattr(self.runtime, "epoch", None)
            if epoch is not None:
                cast(dict[str, object], response["payload"]).setdefault("epoch", epoch)
            should_stop = reply.should_stop
        except (ProtocolError, GatewayError) as error:
            return self._write_error_response(request_id, session_id, str(error))
        except Exception as error:
            # A fault in one command must not end the sidecar and every conversation running in
            # it, or leave the window waiting for this reply. runtime_error is the protocol's
            # general code; the window's views fall back to their own message for it.
            _LOGGER.exception("command %s failed", command.type)
            code = "storage_unavailable" if isinstance(error, sqlite3.Error) else "runtime_error"
            return self._write_error_response(request_id, session_id, code)
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
        # Never a reason to stop: an oversized line is read to its end before this (run).
        return False

    def _skip_rest_of_line(self) -> None:
        while chunk := self.input_stream.readline(MAX_MESSAGE_BYTES):
            if chunk.endswith(b"\n"):
                return

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
        # Called from the event pump and after every reply, so a fault here would stop the events
        # for good or end the command thread. A write to a closed pipe still ends them.
        try:
            events = self.runtime.drain_events()
        except Exception as error:
            # The pump polls many times a second: one line for a fault that repeats.
            if repr(error) != self._drain_failure:
                self._drain_failure = repr(error)
                _LOGGER.exception("reading runtime events failed")
            return
        self._drain_failure = None
        for event in events:
            try:
                self._write(event)
            except ProtocolError as error:
                # It took a number first, so the window sees a gap and reads the state again.
                _LOGGER.error("event %s was not sent: %s", event.get("type"), error)

    def _write(self, message: Mapping[str, object]) -> None:
        document = dict(message)
        # The numbers are the window's: it reads a missing one as a lost message. A reply that goes
        # only to the main process, which the window never sees, must not take one.
        if document.get("kind") in {"response", "event"} and document.get("type") not in (
            _MAIN_PROCESS_REPLIES
        ):
            document["sequence"] = self._next_wire_sequence
            self._next_wire_sequence += 1
        self.output_stream.write(encode_message(document))
        self.output_stream.flush()


_REQUEST_ID_FIELD = re.compile(rb'"requestId"\s*:\s*"([A-Za-z0-9._:-]{1,128})"')


def _oversized_request_id(line: bytes) -> str:
    """The request id of a message too long to parse, from its start, so the window's request
    gets its answer instead of waiting for one."""
    found = _REQUEST_ID_FIELD.search(line[:4096])
    return found.group(1).decode("ascii") if found else "invalid-request"


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


def _check_database_first(database: Path) -> None:
    """Do the first open's full check here, where only the window waits, and is told why. Left to
    the restored conversation's host, which has seconds to start, a check past those left the
    runtime stopped. A damaged database is for the window's recovery to report, as before."""
    if database.is_file():
        with suppress(Exception), SQLiteEventStore(database):
            pass


_BUSY_MARK = "aw-sidecar-busy"
_BUSY_EVERY_SECONDS = 5.0


def _busy_reporter() -> Callable[[], None]:
    """A line on stderr now and then (desktop/src/main/sidecar.ts): stdout is the protocol's."""
    last = 0.0

    def report() -> None:
        nonlocal last
        now = time.monotonic()
        if now - last < _BUSY_EVERY_SECONDS:
            return
        last = now
        with suppress(Exception):
            sys.__stderr__.write(f"{_BUSY_MARK}\n")  # type: ignore[union-attr]
            sys.__stderr__.flush()  # type: ignore[union-attr]

    return report


def main() -> int:
    # Long tool results of earlier tasks (a fetched page, a large file) go on to the model as
    # their start only; the agent reads them again when it needs them. Set to 0 to keep them.
    os.environ.setdefault("AGENT_WORKSPACE_TRIM_EARLIER_TOOL_RESULTS", "1")
    # The diagnostic trace writes each model request as the messages it adds rather than the
    # whole conversation again, and keeps two weeks and at most 100 MB of traces.
    os.environ.setdefault("AGENT_WORKSPACE_RAW_TRACE", "1")
    os.environ.setdefault("AGENT_WORKSPACE_RAW_TRACE_REQUEST_DELTAS", "1")
    os.environ.setdefault("AGENT_WORKSPACE_RAW_TRACE_MAX_TOTAL_BYTES", str(100 * 1024 * 1024))
    os.environ.setdefault("AGENT_WORKSPACE_RAW_TRACE_MAX_AGE_DAYS", "14")
    # A task left working for hours survives a dead connection and a few minutes without a network.
    os.environ.setdefault("AGENT_WORKSPACE_PROVIDER_IDLE_SECONDS", "300")
    os.environ.setdefault("AGENT_WORKSPACE_STREAM_RECOVERY_DELAYS", "5,15,30,60,120,180")
    # Tool calls take a worker process that has already started: a sandbox run needs four or five,
    # and starting each took most of the time such a run spent, around a quarter of a long task.
    os.environ.setdefault("AGENT_WORKSPACE_TOOL_WORKER_SPARES", "2")
    # Conversation switches open the database again; replaying its whole history
    # each time made them miss the host start deadline on a long history. A database
    # this app closed cleanly is not replayed again at the next start either.
    trust_databases_validated_here(across_restarts=True)
    # A long check of a large history says it is at work, so the window waits for it.
    report_slow_work_with(_busy_reporter())
    # A backup the user chose is put back now, while nothing has the database open.
    database = default_database_path().expanduser().resolve()
    apply_pending_restore(database)
    _check_database_first(database)
    runtime = GatewayRuntime(
        daily_backup=run_daily_backup, stream_compaction=compact_finished_streams
    )
    return GatewayServer(sys.stdin.buffer, sys.stdout.buffer, runtime).run()
