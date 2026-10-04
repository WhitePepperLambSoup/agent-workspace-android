from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import monotonic
from typing import Any, cast
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from agent_workspace.application.runtime import ApplicationRuntime
from agent_workspace.core.models import Autonomy
from agent_workspace.core.session import Session

_MAX_BODY_BYTES = 1024 * 1024
_RUN_TIMEOUT_SECONDS = 900.0

_CONSOLE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Workspace Console</title>
<style>
body{font:15px system-ui,sans-serif;margin:2rem;background:#111;color:#eee}
button,input{padding:.5rem .8rem;font:inherit}
#sessions{display:grid;gap:.5rem;margin:1rem 0}
.card{background:#1e1e2e;padding:.75rem 1rem;border-radius:8px;cursor:pointer}
#log{white-space:pre-wrap;background:#0b0b12;padding:1rem;border-radius:8px;min-height:8rem}
</style>
</head>
<body>
<h1>Agent Workspace Console</h1>
<input id="token" type="password" placeholder="Bearer token" style="width:22rem">
<button id="load">Load sessions</button>
<button id="health">Health</button>
<div id="sessions"></div>
<textarea id="prompt" rows="3" style="width:80%"
  placeholder="Prompt for selected session"></textarea>
<button id="run">Run prompt</button>
<pre id="log"></pre>
<script>
const state={token:"",session:null};
const $=id=>document.getElementById(id);
function log(msg){$("log").textContent+=msg+"\\n";}
async function api(path,opts={}){
  const headers={
    Authorization:"Bearer "+state.token,
    "Content-Type":"application/json",
    ...(opts.headers||{})
  };
  const res=await fetch(path,{...opts,headers});
  const data=await res.json();
  if(!res.ok) throw new Error(data.error||res.status);
  return data;
}
$("load").onclick=async()=>{
 state.token=$("token").value.trim();
 try{
   const data=await api("/sessions");
   const container=$("sessions");
   container.textContent="";
   data.sessions.forEach(s=>{
     const card=document.createElement("div");
     card.className="card";
     card.dataset.id=s.id;
     const titleEl=document.createElement("b");
     titleEl.textContent=s.title;
     card.appendChild(titleEl);
     card.appendChild(document.createTextNode(` · ${s.mode}/${s.autonomy}`));
     card.appendChild(document.createElement("br"));
     card.appendChild(document.createTextNode(s.id));
     card.onclick=()=>{
       state.session=s.id;
       log("selected "+state.session);
     };
     container.appendChild(card);
   });
   log("loaded "+data.sessions.length+" sessions");
 }catch(e){log(String(e.message));}
};
$("health").onclick=async()=>{
  try{log(JSON.stringify(await api("/health")));}
  catch(e){log(String(e.message));}
};
$("run").onclick=async()=>{
 try{
  if(!state.session) throw new Error("select a session");
  const path=`/sessions/${state.session}/run`;
  const data=await api(path,{
    method:"POST",
    body:JSON.stringify({prompt:$("prompt").value})
  });
  log(data.text||JSON.stringify(data));
 }catch(e){log(String(e.message));}
};
</script>
</body>
</html>"""


class ServeApiError(RuntimeError):
    pass


@dataclass(slots=True)
class _ServeRun:
    run_id: str
    session_id: str
    prompt: str
    model: str
    state: str = "queued"
    text: str = ""
    error: str | None = None
    created_at: float = field(default_factory=monotonic)
    updated_at: float = field(default_factory=monotonic)
    task: asyncio.Task[None] | None = None
    events: list[dict[str, object]] = field(default_factory=list)
    approval: dict[str, object] | None = None
    retry_of: str | None = None
    retry_child_id: str | None = None


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    server_version = "AgentWorkspaceServe/0.1"

    @property
    def _api(self) -> ServeApi:
        return self.server.api  # type: ignore[attr-defined,no-any-return]

    @property
    def runtime(self) -> ApplicationRuntime:
        return self._api.runtime

    def log_message(self, format: str, *args: object) -> None:
        return

    def _validate_host(self) -> bool:
        host_header = self.headers.get("Host", "").strip()
        if not host_header:
            return False
        if host_header.startswith("["):
            closing_idx = host_header.find("]")
            raw_host = host_header[: closing_idx + 1] if closing_idx != -1 else host_header
        else:
            raw_host = host_header.split(":", 1)[0]
        allowed = {"127.0.0.1", "localhost", "[::1]", "::1"}
        if self._api.host:
            configured = self._api.host.strip().lower()
            allowed.add(configured)
            if configured.startswith("[") and configured.endswith("]"):
                allowed.add(configured[1:-1])
            else:
                allowed.add(f"[{configured}]")
        return raw_host.lower() in allowed

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        expected = f"Bearer {self._api.token}"
        return secrets.compare_digest(header, expected)

    def _reply(self, status: int, payload: object) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-RateLimit-Limit", "60")
        self.send_header("X-RateLimit-Remaining", "59")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._validate_host():
            self._reply(400, {"error": "invalid host header"})
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query_token = parse_qs(parsed.query).get("token", [""])[0]
        if path == "/console":
            authorized = self._authorized()
            if (
                not authorized
                and query_token
                # Deprecated: Passing token via query parameter is supported for backward
                # compatibility, but may expose sensitive tokens in browser history, logs,
                # or Referer headers.
                and secrets.compare_digest(query_token, self._api.token)
            ):
                authorized = True
            if not authorized:
                self._reply(401, {"error": "unauthorized"})
                return
            body = (self._api.console_html or _CONSOLE_HTML).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        asset = self._api.static_assets.get(path)
        if asset is not None:
            if not (
                self._authorized()
                or (query_token and secrets.compare_digest(query_token, self._api.token))
            ):
                self._reply(401, {"error": "unauthorized"})
                return
            content_type, body = asset
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/health":
            self._reply(200, {"ok": True})
            return
        if len(parts := [part for part in path.split("/") if part]) == 2 and parts[0] == "runs":
            try:
                payload = self._api.run_status(parts[1])
            except KeyError:
                self._reply(404, {"error": "unknown run"})
                return
            self._reply(200, payload)
            return
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "events":
            try:
                after = int(parse_qs(parsed.query).get("after", [""])[0])
            except ValueError:
                after = 0
            header_cursor = self.headers.get("Last-Event-ID")
            if header_cursor:
                with contextlib.suppress(ValueError):
                    after = max(after, int(header_cursor))
            try:
                events = self._api.run_events(parts[1], after=after)
            except KeyError:
                self._reply(404, {"error": "unknown run"})
                return
            self._stream_run_events(events)
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) == 1 and parts[0] == "sessions":
            self._reply(200, {"sessions": self._api.list_sessions()})
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "events":
            if not self._api.session_exists(parts[1]):
                self._reply(404, {"error": "unknown session"})
                return
            self._reply(200, {"events": self._api.list_events(parts[1])})
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "comments":
            if not self._api.session_exists(parts[1]):
                self._reply(404, {"error": "unknown session"})
                return
            self._reply(200, {"comments": self._api.list_comments(parts[1])})
            return
        if (
            len(parts) == 4
            and parts[0] == "sessions"
            and parts[2] == "events"
            and parts[3] == "stream"
        ):
            if not self._api.session_exists(parts[1]):
                self._reply(404, {"error": "unknown session"})
                return
            query = parse_qs(urlparse(self.path).query)
            try:
                after_sequence = int(query.get("after", ["0"])[0])
                max_events = int(query.get("max_events", ["0"])[0])
                max_seconds = float(query.get("max_seconds", ["10"])[0])
            except ValueError:
                self._reply(400, {"error": "invalid stream parameters"})
                return
            self._stream_events(
                parts[1],
                after_sequence=after_sequence,
                max_events=max_events,
                max_seconds=max_seconds,
            )
            return
        self._reply(404, {"error": "not found"})

    def _stream_run_events(self, events: list[dict[str, object]]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        if events:
            self.send_header("X-Last-Event-ID", str(events[-1]["id"]))
        self.end_headers()
        try:
            for event in events:
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                self.wfile.write(f"id: {event['id']}\ndata: {payload}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _stream_events(
        self,
        session_id: str,
        *,
        after_sequence: int,
        max_events: int,
        max_seconds: float,
    ) -> None:
        import time

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        sent = 0
        event_limit = max_events if max_events > 0 else 1_000_000
        deadline = time.monotonic() + max(max_seconds, 0.1)
        try:
            while sent < event_limit and time.monotonic() < deadline:
                cursor = after_sequence if after_sequence > 0 else None
                if hasattr(self.runtime.store, "list_events_paged"):
                    raw_events = self.runtime.store.list_events_paged(
                        session_id,
                        cursor=cursor,
                        limit=100,
                    )
                else:
                    raw_events = [
                        event
                        for event in self.runtime.store.list_events(session_id)
                        if (event.sequence or 0) > after_sequence
                    ]
                events = [
                    {
                        "id": event.id,
                        "type": event.type,
                        "sequence": event.sequence,
                        "created_at": event.created_at,
                        "data": event.data,
                    }
                    for event in raw_events
                    if (event.sequence or 0) > after_sequence
                ]
                if events:
                    for event in events:
                        if sent >= event_limit:
                            break
                        payload = json.dumps(
                            event,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                        seq = event.get("sequence")
                        if seq is not None and isinstance(seq, int):
                            after_sequence = max(after_sequence, seq)
                        sent += 1
                else:
                    time.sleep(0.25)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_POST(self) -> None:
        if not self._validate_host():
            self._reply(400, {"error": "invalid host header"})
            return
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        path = urlparse(self.path).path
        parts = [part for part in path.split("/") if part]
        raw_length = self.headers.get("Content-Length", "0").strip()
        try:
            length = int(raw_length) if raw_length else 0
        except ValueError:
            self._reply(400, {"error": "invalid Content-Length"})
            return
        if length < 0:
            self._reply(400, {"error": "invalid Content-Length"})
            return
        if length > _MAX_BODY_BYTES:
            self._reply(413, {"error": "payload too large"})
            return
        raw_body = self.rfile.read(length)
        try:
            payload: Any = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid JSON"})
            return
        if not isinstance(payload, dict):
            self._reply(400, {"error": "body must be a JSON object"})
            return
        if (
            len(parts) == 3
            and parts[0] == "runs"
            and parts[2]
            in {
                "cancel",
                "retry",
                "approval",
            }
        ):
            try:
                if parts[2] == "cancel":
                    result = self._api.cancel_run(parts[1])
                    self._reply(202, result)
                    return
                if parts[2] == "retry":
                    result = self._api.retry_run(parts[1])
                    self._reply(202, result)
                    return
                result = self._api.resolve_run_approval(parts[1], payload)
                self._reply(200, result)
                return
            except KeyError:
                self._reply(404, {"error": "unknown run"})
                return
            except ServeApiError as exc:
                self._reply(409, {"error": str(exc)})
                return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "run":
            prompt = payload.get("prompt")
            model = payload.get("model")
            if not isinstance(prompt, str) or not prompt.strip():
                self._reply(400, {"error": "prompt is required"})
                return
            if model is not None and not isinstance(model, str):
                self._reply(400, {"error": "model must be a string"})
                return
            async_requested = payload.get("async") is True or "respond-async" in self.headers.get(
                "Prefer", ""
            )
            if async_requested:
                try:
                    started = self._api.start_run(parts[1], prompt, model)
                except KeyError:
                    self._reply(404, {"error": "unknown session"})
                    return
                except Exception as exc:
                    self._reply(500, {"error": " ".join(str(exc).split())[:2000]})
                    return
                self._reply(202, started)
                return
            try:
                turn_result = self._api.run_turn(parts[1], prompt, model)
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except Exception as exc:
                self._reply(500, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(200, {"session_id": turn_result[0], "text": turn_result[1]})
            return
        if len(parts) == 1 and parts[0] == "sessions":
            title = payload.get("title", "New session")
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                self._reply(400, {"error": "title is required (max 200 chars)"})
                return
            try:
                session = self._api.create_session(title.strip())
            except ValueError as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(201, session)
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "comment":
            text = payload.get("text")
            author = payload.get("author", "api")
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                self._reply(400, {"error": "text is required (max 4000 chars)"})
                return
            try:
                comment_id = self._api.add_comment(parts[1], text, str(author))
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            self._reply(200, {"comment_id": comment_id})
            return
        self._reply(404, {"error": "not found"})


class ServeApi:
    """Minimal authenticated JSON API for remote companions and IDE bridges."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: str | None = None,
        default_model: str | None = None,
        console_html: str | None = None,
        static_assets: Mapping[str, tuple[str, bytes]] | None = None,
    ) -> None:
        self.runtime = runtime
        self.host = host
        self.port = port
        self.token = token or secrets.token_urlsafe(32)
        self.default_model = default_model
        self.console_html = console_html
        self.static_assets = dict(static_assets or {})
        self._loop = asyncio.get_running_loop()
        # HTTP handlers run on worker threads, while callers in tests and
        # embedders may invoke the API directly on this loop's thread. Keep a
        # fast guard for synchronous wrappers so they never wait on themselves.
        self._loop_thread_id = threading.get_ident()
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self._server.api = self  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None
        self._runs: dict[str, _ServeRun] = {}
        self._run_lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._started = False
        self._stopped = False
        self._retry_inflight: dict[str, asyncio.Future[dict[str, object]]] = {}

    @property
    def address(self) -> str:
        host, port = self._server.server_address[:2]
        return (
            f"http://{host}:{port}"
            if isinstance(host, str)
            else f"http://{host.decode('ascii')}:{port}"
        )

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._stopped:
                raise ServeApiError("serve_api_stopped")
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="agent-workspace-serve",
                daemon=True,
            )
            self._thread.start()
            self._started = True

    def stop(self) -> None:
        with self._lifecycle_lock:
            if self._stopped:
                return
            self._stopped = True
            started = self._started
        with self._run_lock:
            active = tuple(run for run in self._runs.values() if run.task is not None)
        for run in active:
            if (
                run.state in {"queued", "running", "waiting_approval"}
                and run.task is not None
                and not run.task.done()
            ):
                if run.state == "queued":
                    with self._run_lock:
                        # A task can be cancelled before its coroutine gets a
                        # scheduling turn. Persist the terminal transition in
                        # that case because CancelledError is never delivered
                        # inside the coroutine body.
                        if run.state == "queued":
                            run.state = "cancelled"
                            run.updated_at = monotonic()
                            self._publish_run_event(run, "run.cancelled")
                if threading.get_ident() == self._loop_thread_id:
                    run.task.cancel()
                elif not self._loop.is_closed():
                    self._loop.call_soon_threadsafe(run.task.cancel)
                else:
                    with self._run_lock:
                        if run.state not in {"succeeded", "failed", "cancelled"}:
                            run.state = "cancelled"
                            run.updated_at = monotonic()
                            self._publish_run_event(run, "run.cancelled")
        if started:
            self._server.shutdown()
        self._server.server_close()

    def _submit(self, factory: Any) -> dict[str, object]:
        """Run one lifecycle coroutine on the owning event loop.

        The HTTP server invokes this from worker threads. Direct callers on the
        loop use the async methods instead; blocking a running loop here would
        deadlock the run before it can ever start.
        """

        try:
            on_owner_loop = asyncio.get_running_loop() is self._loop
        except RuntimeError:
            on_owner_loop = False
        with self._lifecycle_lock:
            stopped = self._stopped
        if threading.get_ident() == self._loop_thread_id or on_owner_loop:
            raise ServeApiError("serve_api_sync_bridge_event_loop")
        if stopped:
            raise ServeApiError("serve_api_stopped")
        if self._loop.is_closed():
            raise ServeApiError("serve_api_loop_closed")
        future = asyncio.run_coroutine_threadsafe(factory(), self._loop)
        try:
            return cast(dict[str, object], future.result(timeout=5))
        except TimeoutError as exc:
            future.cancel()
            raise ServeApiError("serve_api_loop_timeout") from exc

    def start_run(self, session_id: str, prompt: str, model: str | None) -> dict[str, object]:
        session, resolved_model, normalized_prompt = self._validate_start(session_id, prompt, model)
        return self._submit(lambda: self._create_run(session.id, normalized_prompt, resolved_model))

    async def astart_run(
        self, session_id: str, prompt: str, model: str | None
    ) -> dict[str, object]:
        session, resolved_model, normalized_prompt = self._validate_start(session_id, prompt, model)
        return await self._create_run(session.id, normalized_prompt, resolved_model)

    def _validate_start(
        self, session_id: str, prompt: str, model: str | None
    ) -> tuple[Session, str, str]:
        session = self.runtime.service.get_session(session_id)
        resolved_model = model or self.default_model
        if resolved_model is None:
            raise ServeApiError("no model configured for the serve API")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ServeApiError("prompt is required")
        return session, resolved_model, prompt.strip()

    async def _create_run(self, session_id: str, prompt: str, model: str) -> dict[str, object]:
        with self._lifecycle_lock:
            if self._stopped:
                raise ServeApiError("serve_api_stopped")
        run = _ServeRun(uuid4().hex, session_id, prompt, model)
        with self._run_lock:
            self._runs[run.run_id] = run
            self._publish_run_event(run, "run.queued")
            run.task = asyncio.create_task(self._execute_run(run))
        return self._run_document(run)

    async def _execute_run(self, run: _ServeRun) -> None:
        with self._run_lock:
            if run.state == "cancelled":
                return
            run.state = "running"
            run.updated_at = monotonic()
            self._publish_run_event(run, "run.started")
        try:
            session = self.runtime.service.get_session(run.session_id)
            result = await self.runtime.service.run(session, run.prompt, run.model)
            with self._run_lock:
                run.text = str(result.text)
                run.state = "succeeded"
                run.updated_at = monotonic()
                self._publish_run_event(run, "run.succeeded", text=run.text)
        except asyncio.CancelledError:
            with self._run_lock:
                run.state = "cancelled"
                run.updated_at = monotonic()
                self._publish_run_event(run, "run.cancelled")
            raise
        except Exception as exc:
            with self._run_lock:
                run.state = "failed"
                run.error = " ".join(str(exc).split())[:2000]
                run.updated_at = monotonic()
                self._publish_run_event(run, "run.failed", error=run.error)

    def _run_document(self, run: _ServeRun) -> dict[str, object]:
        document: dict[str, object] = {
            "run_id": run.run_id,
            "session_id": run.session_id,
            "state": run.state,
            "status": run.state,
            "prompt": run.prompt,
            "model": run.model,
            "text": run.text,
            "error": run.error,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        }
        if run.approval is not None:
            document["approval"] = dict(run.approval)
        if run.retry_of is not None:
            document["previous_run_id"] = run.retry_of
        return document

    def run_status(self, run_id: str) -> dict[str, object]:
        with self._run_lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            return self._run_document(run)

    def run_events(self, run_id: str, *, after: int = 0) -> list[dict[str, object]]:
        with self._run_lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            filtered: list[dict[str, object]] = []
            for event in run.events:
                event_id = event.get("id")
                if isinstance(event_id, int) and event_id > after:
                    filtered.append(dict(event))
            return filtered

    def _publish_run_event(self, run: _ServeRun, event_type: str, **payload: object) -> None:
        with self._run_lock:
            event = {
                "id": len(run.events) + 1,
                "type": event_type,
                "run_id": run.run_id,
                "state": run.state,
                **payload,
            }
            run.events.append(event)

    def cancel_run(self, run_id: str) -> dict[str, object]:
        return self._submit(lambda: self._cancel_run(run_id))

    async def acancel_run(self, run_id: str) -> dict[str, object]:
        return await self._cancel_run(run_id)

    async def _cancel_run(self, run_id: str) -> dict[str, object]:
        with self._run_lock:
            run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        if run.state in {"succeeded", "failed", "cancelled"}:
            return self._run_document(run)
        if run.task is not None and not run.task.done():
            run.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await run.task
        with self._run_lock:
            if run.state not in {"succeeded", "failed", "cancelled"}:
                run.state = "cancelled"
                run.updated_at = monotonic()
                self._publish_run_event(run, "run.cancelled")
        return self._run_document(run)

    def retry_run(self, run_id: str) -> dict[str, object]:
        return self._submit(lambda: self._retry_run(run_id))

    async def aretry_run(self, run_id: str) -> dict[str, object]:
        return await self._retry_run(run_id)

    async def _retry_run(self, run_id: str) -> dict[str, object]:
        owner = False
        with self._run_lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            if run.retry_child_id is not None:
                child = self._runs.get(run.retry_child_id)
                if child is not None:
                    return self._run_document(child)
            if run.state not in {"failed", "cancelled"}:
                raise ServeApiError("run_not_retryable")
            session_id, prompt, model = run.session_id, run.prompt, run.model
            retry_waiter = self._retry_inflight.get(run_id)
            if retry_waiter is None:
                retry_waiter = asyncio.get_running_loop().create_future()
                self._retry_inflight[run_id] = retry_waiter
                owner = True
        if not owner:
            return await retry_waiter
        try:
            started = await self._create_run(session_id, prompt, model)
            child_id = str(started["run_id"])
        except BaseException as exc:
            with self._run_lock:
                waiter = self._retry_inflight.pop(run_id, None)
                if waiter is not None and not waiter.done():
                    waiter.set_exception(exc)
            raise
        with self._run_lock:
            existing = run.retry_child_id
            if existing is None:
                run.retry_child_id = child_id
                child = self._runs[child_id]
                child.retry_of = run_id
                result = self._run_document(child)
            else:
                child = self._runs.get(existing)
                result = self._run_document(child) if child is not None else started
            waiter = self._retry_inflight.pop(run_id, None)
            if waiter is not None and not waiter.done():
                waiter.set_result(result)
            return result

    def resolve_run_approval(self, run_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        return self._submit(lambda: self._resolve_run_approval(run_id, payload))

    async def aresolve_run_approval(
        self, run_id: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        return await self._resolve_run_approval(run_id, payload)

    async def _resolve_run_approval(
        self, run_id: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        with self._run_lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            if run.state in {"succeeded", "failed", "cancelled"}:
                raise ServeApiError("run_terminal")
            decision = payload.get("decision")
            if not isinstance(decision, str) or decision not in {"allow", "deny", "cancel"}:
                raise ServeApiError("invalid_approval")
            if run.approval == {"decision": decision}:
                return self._run_document(run)
            run.approval = {"decision": decision}
            self._publish_run_event(run, "run.approval.resolved", decision=decision)
            document = self._run_document(run)
        if decision == "cancel":
            return await self._cancel_run(run_id)
        return document

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "id": session.id,
                "title": session.title,
                "workspace": session.workspace,
                "mode": session.mode.value,
                "autonomy": session.autonomy.value,
                "updated_at": session.updated_at,
            }
            for session in self.runtime.store.list_sessions(limit=100)
        ]

    def create_session(self, title: str) -> dict[str, Any]:
        workspace = getattr(self.runtime.service, "_execution_workspace", None)
        if workspace is None:
            raise ValueError("runtime workspace is not configured")
        autonomy = getattr(self.runtime.service, "_execution_autonomy", None)
        if autonomy is None:
            autonomy = Autonomy.WORKSPACE
        session = self.runtime.service.create_session(
            workspace,
            autonomy=autonomy,
            title=title,
        )
        return {
            "id": session.id,
            "title": session.title,
            "workspace": session.workspace,
            "mode": session.mode.value,
            "autonomy": session.autonomy.value,
            "updated_at": session.updated_at,
        }

    def session_exists(self, session_id: str) -> bool:
        return self.runtime.store.get_session(session_id) is not None

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return [
            {
                "id": event.id,
                "type": event.type,
                "sequence": event.sequence,
                "created_at": event.created_at,
                "data": event.data,
            }
            for event in self.runtime.store.list_events(session_id)
        ]

    def list_comments(self, session_id: str) -> list[dict[str, Any]]:
        from agent_workspace.core.comments import list_comments

        return list_comments(self.runtime.store, session_id)

    def add_comment(self, session_id: str, text: str, author: str) -> str:
        from agent_workspace.core.comments import add_comment

        return add_comment(self.runtime.store, session_id, text, author)

    def run_turn(self, session_id: str, prompt: str, model: str | None) -> tuple[str, str]:
        future = asyncio.run_coroutine_threadsafe(
            self._run(session_id, prompt, model),
            self._loop,
        )
        return future.result(timeout=_RUN_TIMEOUT_SECONDS)

    async def _run(self, session_id: str, prompt: str, model: str | None) -> tuple[str, str]:
        session = self.runtime.service.get_session(session_id)
        resolved_model = model or self.default_model
        if resolved_model is None:
            raise ValueError("no model configured for the serve API")
        result = await self.runtime.service.run(session, prompt, resolved_model)
        return session.id, result.text
