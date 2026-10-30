"""Debugging the project's Python with debugpy over the Debug Adapter Protocol: the user's own
debugging in the editor (breakpoints, stepping, the variables) and the agent's debug_python,
which runs a script to a breakpoint and reports what the program held there.

debugpy runs in the project's own Python. When that Python does not have it, it is installed
into the app's tools folder (pip --target, one folder per Python version) and found there."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

REQUEST_SECONDS = 15.0
START_SECONDS = 30.0
INSTALL_SECONDS = 300.0
MAX_OUTPUT_CHARS = 200_000
MAX_VALUE_CHARS = 1000
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class DebugError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def project_python(root: Path, which: Callable[[str], str | None] = shutil.which) -> str | None:
    """The Python the project runs with: its virtual environment, else the one on PATH."""
    for folder in (".venv", "venv", "env"):
        for relative in ("Scripts/python.exe", "bin/python"):
            candidate = root / folder / relative
            if candidate.is_file():
                return str(candidate)
    for name in ("python", "python3"):
        found = which(name)
        # The Microsoft Store stub only opens the Store.
        if found and "WindowsApps" not in found:
            return found
    return None


def _run(
    argv: list[str], *, env: dict[str, str] | None = None, seconds: float = 20.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=seconds,
        check=False,
        env=env,
        stdin=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )


class DebugpyHome:
    """Where debugpy is for a given Python: its own site-packages, or the app's tools folder."""

    def __init__(self, tools_dir: Path) -> None:
        self.base = tools_dir / "debugpy"
        self._versions: dict[str, str] = {}

    def _version(self, python: str) -> str:
        if python not in self._versions:
            result = _run([python, "-c", "import sys; print('%d%d' % sys.version_info[:2])"])
            if result.returncode != 0 or not result.stdout.strip().isdigit():
                raise DebugError("python_unusable", (result.stderr or result.stdout)[-500:])
            self._versions[python] = result.stdout.strip()
        return self._versions[python]

    def folder(self, python: str) -> Path:
        return self.base / f"py{self._version(python)}"

    def find(self, python: str) -> Path | str | None:
        """The folder to put on PYTHONPATH, "" when the Python has debugpy itself, or None."""
        folder = self.folder(python)
        if (folder / "debugpy" / "__init__.py").is_file():
            return folder
        if _run([python, "-c", "import debugpy"]).returncode == 0:
            return ""
        return None

    def install(self, python: str) -> Path:
        folder = self.folder(python)
        folder.mkdir(parents=True, exist_ok=True)
        result = _run(
            [
                python,
                "-m",
                "pip",
                "install",
                "--target",
                str(folder),
                "--upgrade",
                "--disable-pip-version-check",
                "--no-input",
                "debugpy",
            ],
            seconds=INSTALL_SECONDS,
        )
        if result.returncode != 0 or not (folder / "debugpy" / "__init__.py").is_file():
            raise DebugError("debugpy_install_failed", (result.stderr or result.stdout)[-1500:])
        return folder


class DapClient:
    """The Debug Adapter Protocol over a process's stdin and stdout."""

    def __init__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        on_event: Callable[[dict[str, Any]], None],
    ) -> None:
        try:
            self.process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=_NO_WINDOW,
            )
        except OSError as error:
            raise DebugError("adapter_start_failed", str(error)) from None
        self._on_event = on_event
        self._seq = 0
        self._lock = threading.Lock()
        self._pending: dict[int, Future[dict[str, Any]]] = {}
        self.stderr: deque[str] = deque(maxlen=200)
        threading.Thread(target=self._read, name="dap-read", daemon=True).start()
        threading.Thread(target=self._read_errors, name="dap-errors", daemon=True).start()

    def _read_errors(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.stderr.append(line.decode("utf-8", errors="replace").rstrip())

    def _read(self) -> None:
        stream = self.process.stdout
        assert stream is not None
        try:
            while True:
                length = 0
                while True:
                    line = stream.readline()
                    if not line:
                        return
                    if line in (b"\r\n", b"\n"):
                        break
                    name, _, value = line.decode("ascii", errors="replace").partition(":")
                    if name.strip().lower() == "content-length":
                        length = int(value.strip())
                message = json.loads(stream.read(length).decode("utf-8"))
                self._dispatch(message)
        except (OSError, ValueError):
            return
        finally:
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(DebugError("adapter_closed"))

    def _dispatch(self, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == "response":
            future = self._pending.pop(int(message.get("request_seq", -1)), None)
            if future is None or future.done():
                return
            if message.get("success"):
                future.set_result(message.get("body") or {})
            else:
                future.set_exception(
                    DebugError(
                        "debug_request_failed",
                        str(message.get("message") or message.get("command")),
                    )
                )
        elif kind == "event":
            with contextlib.suppress(Exception):
                self._on_event(message)
        elif kind == "request":
            # The adapter asks to run the program in a terminal: this client has none.
            self._send(
                {
                    "type": "response",
                    "request_seq": message.get("seq"),
                    "success": False,
                    "command": message.get("command"),
                    "message": "not supported",
                }
            )

    def _send(self, message: dict[str, Any]) -> None:
        body = json.dumps(message).encode("utf-8")
        stream = self.process.stdin
        if stream is None:
            raise DebugError("adapter_closed")
        with self._lock:
            try:
                stream.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
                stream.flush()
            except OSError:
                raise DebugError("adapter_closed") from None

    def send(self, command: str, arguments: dict[str, Any] | None = None) -> Future[dict[str, Any]]:
        future: Future[dict[str, Any]] = Future()
        with self._lock:
            self._seq += 1
            seq = self._seq
            self._pending[seq] = future
        message: dict[str, Any] = {"seq": seq, "type": "request", "command": command}
        if arguments is not None:
            message["arguments"] = arguments
        self._send(message)
        return future

    def request(
        self,
        command: str,
        arguments: dict[str, Any] | None = None,
        seconds: float = REQUEST_SECONDS,
    ) -> dict[str, Any]:
        try:
            return self.send(command, arguments).result(timeout=seconds)
        except FutureTimeout:
            raise DebugError("debug_timeout", command) from None

    def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.process.stdin is not None:
                self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()


def _short(value: object) -> str:
    text = str(value)
    return text if len(text) <= MAX_VALUE_CHARS else text[: MAX_VALUE_CHARS - 1] + "…"


class DebugSession:
    """One program run under the debugger, from launch until it ends or is stopped."""

    def __init__(
        self,
        root: Path,
        *,
        python: str,
        debugpy_path: Path | str,
        program: str | None = None,
        module: str | None = None,
        args: list[str] | None = None,
        breakpoints: dict[str, list[dict[str, Any]]] | None = None,
        stop_on_exception: str = "uncaught",
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.state = "starting"
        self.reason = ""
        self.description = ""
        self.thread_id: int | None = None
        self.exit_code: int | None = None
        self.output: deque[str] = deque()
        self._output_chars = 0
        self.events: queue.SimpleQueue[tuple[str, dict[str, object]]] = queue.SimpleQueue()
        self._changed = threading.Condition()
        self._on_change = on_change
        self._initialized = threading.Event()
        env = dict(os.environ)
        if debugpy_path:
            env["PYTHONPATH"] = os.pathsep.join(
                [str(debugpy_path), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])]
            )
        env["PYTHONIOENCODING"] = "utf-8"
        self.client = DapClient(
            [python, "-m", "debugpy.adapter"], cwd=root, env=env, on_event=self._event
        )
        try:
            self._start(
                python, env, program, module, args or [], breakpoints or {}, stop_on_exception
            )
        except BaseException:
            self.close()
            raise

    # -- start

    def _start(
        self,
        python: str,
        env: dict[str, str],
        program: str | None,
        module: str | None,
        args: list[str],
        breakpoints: dict[str, list[dict[str, Any]]],
        stop_on_exception: str,
    ) -> None:
        self.client.request(
            "initialize",
            {
                "clientID": "agent-workspace",
                "adapterID": "debugpy",
                "linesStartAt1": True,
                "columnsStartAt1": True,
                "pathFormat": "path",
                "supportsVariableType": True,
            },
        )
        target: dict[str, Any] = {"module": module} if module else {"program": program}
        launched = self.client.send(
            "launch",
            {
                **target,
                "args": args,
                "cwd": str(self.root),
                "python": [python],
                "console": "internalConsole",
                "redirectOutput": True,
                "justMyCode": True,
                "env": {"PYTHONPATH": env.get("PYTHONPATH", "")} if env.get("PYTHONPATH") else {},
            },
        )
        if not self._initialized.wait(START_SECONDS):
            raise DebugError("debug_start_timeout", "\n".join(self.client.stderr)[-1500:])
        for path, lines in breakpoints.items():
            self.set_breakpoints(path, lines)
        filters = {"none": [], "uncaught": ["uncaught"], "raised": ["raised", "uncaught"]}
        self.client.request(
            "setExceptionBreakpoints", {"filters": filters.get(stop_on_exception, ["uncaught"])}
        )
        self.client.request("configurationDone")
        try:
            launched.result(timeout=START_SECONDS)
        except FutureTimeout:
            raise DebugError("debug_start_timeout") from None
        if self.state == "starting":
            self._set_state("running")

    # -- events

    def _set_state(self, state: str, **data: object) -> None:
        with self._changed:
            if state == self.state == "running":
                return
            self.state = state
            self._changed.notify_all()
        self.events.put(("debug.state", {"state": state, **data}))
        if self._on_change is not None:
            self._on_change()

    def _event(self, message: dict[str, Any]) -> None:
        name = message.get("event")
        body = message.get("body") or {}
        if name == "initialized":
            self._initialized.set()
        elif name == "stopped":
            self.reason = str(body.get("reason") or "")
            self.description = str(body.get("text") or body.get("description") or "")
            thread = body.get("threadId")
            self.thread_id = thread if isinstance(thread, int) else self.thread_id
            self._set_state(
                "stopped", reason=self.reason, description=self.description, threadId=self.thread_id
            )
        elif name == "continued":
            self._set_state("running")
        elif name == "output":
            category = str(body.get("category") or "console")
            text = str(body.get("output") or "")
            if category in {"telemetry"} or not text:
                return
            self.output.append(text)
            self._output_chars += len(text)
            while self._output_chars > MAX_OUTPUT_CHARS and len(self.output) > 1:
                self._output_chars -= len(self.output.popleft())
            self.events.put(("debug.output", {"category": category, "text": text[:20_000]}))
        elif name == "exited":
            code = body.get("exitCode")
            self.exit_code = code if isinstance(code, int) else None
        elif name == "terminated":
            self._set_state("terminated", exitCode=self.exit_code)

    def wait(self, states: set[str], seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        with self._changed:
            while self.state not in states:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._changed.wait(remaining)
        return True

    # -- the program while it is stopped

    def relative(self, path: str) -> str | None:
        try:
            return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
        except (OSError, ValueError):
            return None

    def stack(self, thread_id: int | None = None, levels: int = 30) -> list[dict[str, object]]:
        thread = thread_id or self.thread_id
        if thread is None:
            return []
        body = self.client.request(
            "stackTrace", {"threadId": thread, "startFrame": 0, "levels": levels}
        )
        frames = []
        for frame in body.get("stackFrames") or []:
            source = frame.get("source") or {}
            path = str(source.get("path") or "")
            frames.append(
                {
                    "id": frame.get("id"),
                    "name": str(frame.get("name") or ""),
                    "path": path,
                    "relativePath": self.relative(path) if path else None,
                    "line": frame.get("line"),
                    "column": frame.get("column"),
                }
            )
        return frames

    def scopes(self, frame_id: int) -> list[dict[str, object]]:
        body = self.client.request("scopes", {"frameId": frame_id})
        return [
            {
                "name": str(scope.get("name") or ""),
                "reference": scope.get("variablesReference"),
                "expensive": bool(scope.get("expensive")),
            }
            for scope in body.get("scopes") or []
        ]

    def variables(self, reference: int, limit: int = 200) -> list[dict[str, object]]:
        body = self.client.request("variables", {"variablesReference": reference})
        return [
            {
                "name": str(item.get("name") or ""),
                "value": _short(item.get("value", "")),
                "type": str(item.get("type") or ""),
                "reference": item.get("variablesReference") or 0,
            }
            for item in (body.get("variables") or [])[:limit]
        ]

    def evaluate(self, expression: str, frame_id: int | None) -> dict[str, object]:
        arguments: dict[str, Any] = {"expression": expression, "context": "repl"}
        if frame_id is not None:
            arguments["frameId"] = frame_id
        try:
            body = self.client.request("evaluate", arguments)
        except DebugError as error:
            if error.code == "debug_request_failed":
                # pydevd answers with its own traceback; the last line is the user's error.
                lines = [line for line in error.detail.splitlines() if line.strip()]
                return {"error": lines[-1].strip() if lines else error.detail}
            raise
        return {
            "result": _short(body.get("result", "")),
            "type": str(body.get("type") or ""),
            "reference": body.get("variablesReference") or 0,
        }

    def exception(self, thread_id: int | None = None) -> dict[str, object] | None:
        """The exception the program stopped at, when it did."""
        thread = thread_id or self.thread_id
        if self.reason != "exception" or thread is None:
            return None
        try:
            body = self.client.request("exceptionInfo", {"threadId": thread})
        except DebugError:
            return {"type": self.description, "message": ""}
        details = body.get("details") or {}
        return {
            "type": str(body.get("exceptionId") or self.description),
            "message": _short(details.get("message") or body.get("description") or ""),
        }

    def control(self, action: str, thread_id: int | None = None) -> None:
        commands = {
            "continue": "continue",
            "next": "next",
            "stepIn": "stepIn",
            "stepOut": "stepOut",
            "pause": "pause",
        }
        if action not in commands:
            raise DebugError("invalid_action")
        thread = thread_id or self.thread_id
        if thread is None and action != "pause":
            raise DebugError("not_stopped")
        # Running before the request goes: the program may stop or end again before its answer.
        resumed = action != "pause" and self.state == "stopped"
        if resumed:
            self._set_state("running")
        try:
            self.client.request(commands[action], {"threadId": thread or 0})
        except DebugError:
            if resumed and self.state == "running":
                self._set_state("stopped", reason=self.reason, threadId=self.thread_id)
            raise

    def set_breakpoints(self, path: str, lines: list[dict[str, Any]]) -> list[dict[str, object]]:
        source = path if Path(path).is_absolute() else str((self.root / path).resolve())
        body = self.client.request(
            "setBreakpoints",
            {
                "source": {"path": source},
                "breakpoints": [
                    {
                        "line": int(item["line"]),
                        **({"condition": item["condition"]} if item.get("condition") else {}),
                    }
                    for item in lines
                ],
            },
        )
        return [
            {
                "line": point.get("line"),
                "verified": bool(point.get("verified")),
                "message": point.get("message"),
            }
            for point in body.get("breakpoints") or []
        ]

    def output_tail(self, chars: int = 4000) -> str:
        return "".join(self.output)[-chars:]

    def close(self) -> None:
        if self.client.process.poll() is None:
            with contextlib.suppress(DebugError):
                self.client.request("disconnect", {"terminateDebuggee": True}, seconds=5)
        self.client.close()
        if self.state != "terminated":
            self._set_state("terminated", exitCode=self.exit_code)


class DebugDesk:
    """The window's one debugging session, its events for the window, and debugpy's home."""

    def __init__(self, tools_dir: Path) -> None:
        self.home = DebugpyHome(tools_dir)
        self.session: DebugSession | None = None
        # A session just stopped: its last events (the end) still go to the window.
        self._last: DebugSession | None = None
        self._lock = threading.Lock()

    def status(self, root: Path) -> dict[str, object]:
        python = project_python(root)
        found = self.home.find(python) if python else None
        session = self.session
        return {
            "python": python,
            "debugpy": found is not None,
            "session": None
            if session is None
            else {
                "state": session.state,
                "reason": session.reason,
                "description": session.description,
                "threadId": session.thread_id,
                "exitCode": session.exit_code,
            },
        }

    def install(self, root: Path) -> dict[str, object]:
        python = project_python(root)
        if python is None:
            raise DebugError("python_missing")
        self.home.install(python)
        return self.status(root)

    def start(
        self,
        root: Path,
        *,
        program: str | None,
        module: str | None,
        args: list[str],
        breakpoints: dict[str, list[dict[str, Any]]],
    ) -> DebugSession:
        python = project_python(root)
        if python is None:
            raise DebugError("python_missing")
        found = self.home.find(python)
        if found is None:
            raise DebugError("debugpy_missing")
        self.stop()
        session = DebugSession(
            root,
            python=python,
            debugpy_path=found,
            program=program,
            module=module,
            args=args,
            breakpoints=breakpoints,
        )
        with self._lock:
            self.session = session
        return session

    def current(self) -> DebugSession:
        session = self.session
        if session is None or session.state == "terminated":
            raise DebugError("no_debug_session")
        return session

    def stop(self) -> None:
        with self._lock:
            session, self.session = self.session, None
        if session is not None:
            session.close()
            self._last = session

    def drain(self) -> list[tuple[str, dict[str, object]]]:
        events: list[tuple[str, dict[str, object]]] = []
        for session in (self._last, self.session):
            if session is None:
                continue
            while True:
                try:
                    events.append(session.events.get_nowait())
                except queue.Empty:
                    break
        self._last = None
        return events

    def close(self) -> None:
        self.stop()


class DebugPythonTool:
    """The agent's look inside a running program: to a breakpoint, then what it held there."""

    _spec = ToolSpec(
        name="debug_python",
        description=(
            "Run a Python script of the project (or a module such as pytest, with its args) "
            "under the debugger and stop at a breakpoint or an uncaught exception, to see what "
            "the program held there: the call stack, the local variables of the stopped frame "
            "and the values of the expressions you give. Use it when a test fails or code "
            "misbehaves and reading it does not settle why. breakpoints are a project file and a "
            "line (with an optional condition). The run ends at the first stop or when the "
            "program ends; run again with other breakpoints to look elsewhere."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 500},
                "module": {"type": "string", "minLength": 1, "maxLength": 200},
                "args": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 1000},
                    "maxItems": 50,
                },
                "breakpoints": {
                    "type": "array",
                    "maxItems": 20,
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "minLength": 1, "maxLength": 500},
                            "line": {"type": "integer", "minimum": 1},
                            "condition": {"type": "string", "maxLength": 500},
                        },
                        "required": ["path", "line"],
                        "additionalProperties": False,
                    },
                },
                "expressions": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 500},
                    "maxItems": 10,
                },
                "stop_on_exception": {"type": "boolean"},
                "timeout": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, workspace: Path, home: DebugpyHome) -> None:
        self.root = workspace
        self.paths = WorkspacePaths(workspace)
        self.home = home

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        if bool(arguments.get("path")) == bool(arguments.get("module")):
            raise ToolArgumentError("give either path (a script) or module (such as pytest)")
        return json_result(await asyncio.to_thread(self._run, arguments))

    def _run(self, arguments: dict[str, Any]) -> dict[str, object]:
        python = project_python(self.root)
        if python is None:
            raise ToolError("no Python found for this project (no .venv and none on PATH)")
        notes: list[str] = []
        try:
            found = self.home.find(python)
            if found is None:
                found = self.home.install(python)
                notes.append("debugpy was installed into the app's tools folder for this Python")
        except DebugError as error:
            raise ToolError(
                f"debugpy is not available: {error.code} {error.detail}".strip()
            ) from None
        program = None
        if arguments.get("path"):
            try:
                program = str(self.paths.resolve(str(arguments["path"])))
            except WorkspacePathError as error:
                raise ToolArgumentError(str(error)) from None
        breakpoints: dict[str, list[dict[str, Any]]] = {}
        for point in arguments.get("breakpoints") or []:
            try:
                where = str(self.paths.resolve(point["path"]))
            except WorkspacePathError as error:
                raise ToolArgumentError(str(error)) from None
            breakpoints.setdefault(where, []).append(point)
        try:
            session = DebugSession(
                self.root,
                python=python,
                debugpy_path=found,
                program=program,
                module=arguments.get("module"),
                args=list(arguments.get("args") or []),
                breakpoints=breakpoints,
                stop_on_exception="uncaught"
                if arguments.get("stop_on_exception", True)
                else "none",
            )
        except DebugError as error:
            raise ToolError(
                f"the debugger could not start: {error.code} {error.detail}".strip()
            ) from None
        try:
            ended = session.wait({"stopped", "terminated"}, float(arguments.get("timeout", 60)))
            if session.state != "stopped":
                return {
                    "stopped": False,
                    "timed_out": not ended,
                    "exit_code": session.exit_code,
                    "output": session.output_tail(),
                    **({"notes": notes} if notes else {}),
                }
            frames = session.stack(levels=12)
            top = next(
                (frame for frame in frames if frame["relativePath"]), frames[0] if frames else None
            )
            local: list[dict[str, object]] = []
            values: dict[str, object] = {}
            if top is not None and isinstance(top["id"], int):
                for scope in session.scopes(top["id"]):
                    if scope["name"] == "Locals" and isinstance(scope["reference"], int):
                        local = session.variables(scope["reference"], limit=40)
                for expression in arguments.get("expressions") or []:
                    values[expression] = session.evaluate(expression, top["id"])
            return {
                "stopped": True,
                "reason": session.reason,
                **({"exception": session.exception()} if session.reason == "exception" else {}),
                "at": None
                if top is None
                else f"{top['relativePath'] or top['path']}:{top['line']} in {top['name']}",
                "stack": [
                    f"{frame['relativePath'] or frame['path']}:{frame['line']} in {frame['name']}"
                    for frame in frames
                ],
                "locals": {item["name"]: f"{item['value']} ({item['type']})" for item in local},
                **({"expressions": values} if values else {}),
                "output": session.output_tail(),
                **({"notes": notes} if notes else {}),
            }
        finally:
            session.close()


__all__ = [
    "DapClient",
    "DebugDesk",
    "DebugError",
    "DebugPythonTool",
    "DebugSession",
    "DebugpyHome",
    "project_python",
]
