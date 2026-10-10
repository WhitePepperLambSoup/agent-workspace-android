"""Secondary mobile management routes around existing task and platform adapters."""

from __future__ import annotations

import asyncio
import os
import secrets
import time
from contextlib import suppress
from pathlib import Path

import httpx
from mobile_connections import MobileConnections
from mobile_delivery import MobileOutbox
from mobile_evaluation import MobileEvaluations
from mobile_local_models import (
    get_local_engine_bridge,
    local_model_diagnostics,
    native_engine_status,
    probe_local_model,
)
from mobile_model_manager import get_model_manager
from mobile_schedules import MobileScheduleManager
from mobile_workflows import MobileWorkflows

_PROVIDER_CHANGE_TTL_SECONDS = 120


class MobileManagement:
    def __init__(self, runtime, controller):
        self.runtime, self.controller = runtime, controller
        root = Path(runtime.service._execution_workspace).resolve()
        data = Path(getattr(runtime, "database", root.parent / "agent-data" / "agent.db")).parent
        self.data, self.workspace = data, root
        self.models = get_model_manager(data / "local-models")
        path = data / "mobile-management.db"
        self.connections = MobileConnections(path)
        self.outbox = MobileOutbox(path, self.connections)
        self.workflows = MobileWorkflows(path)
        self.evaluations = MobileEvaluations(path)
        self.schedules = MobileScheduleManager(controller, data / "mobile-schedules.json")
        self._job = None
        self._maintenance_jobs = set()
        self._provider_change_lease = None
        self._provider_change_result = None
        self._provider_change_timer = None

    @staticmethod
    async def system(request):
        from android_adapter.android_system import execute_android_system_request

        return await asyncio.to_thread(execute_android_system_request, request)

    def mirror_schedules(self):
        if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy":
            import json

            from java import jclass

            jclass(
                "com.agentworkspace.mobile.embedded.MobileScheduleCoordinator"
            ).syncGlobalFromJson(json.dumps(self.schedules.snapshot()))

    def start(self):
        with suppress(Exception):
            self.knowledge()  # resumes documents whose indexing an engine stop interrupted
        self._job = asyncio.create_task(self._run(), name="mobile-management")

    async def _run(self):
        await asyncio.gather(self.schedules.run(), self.outbox.run(), self._mirror_loop())

    async def _mirror_loop(self):
        while True:
            with suppress(Exception):
                self.mirror_schedules()
            await asyncio.sleep(30)

    def stop(self):
        if self._job:
            self._job.cancel()

    async def aclose(self):
        self.stop()
        if self._provider_change_lease is not None:
            await self._finish_provider_change("aborted")
        if self._provider_change_timer is not None:
            self._provider_change_timer.cancel()
            await asyncio.gather(self._provider_change_timer, return_exceptions=True)
        if self._job:
            await asyncio.gather(self._job, return_exceptions=True)
        await self.workflows.aclose()
        await self.evaluations.aclose()
        await self.models.aclose()
        if self._maintenance_jobs:
            await asyncio.gather(*tuple(self._maintenance_jobs), return_exceptions=True)

    def require_idle(self):
        state = self.controller.status()
        if state.get("active_task_id") or state.get("queued_tasks"):
            raise ValueError(
                "stop or finish active and queued tasks before changing models or tools"
            )
        if native_engine_status().get("generating"):
            raise ValueError("wait for local generation to stop before changing models or tools")

    async def _prepare_provider_change(self, payload):
        if set(payload) - {"require_local_engine"}:
            raise ValueError("unsupported provider reservation field")
        require_local = payload.get("require_local_engine", False)
        if not isinstance(require_local, bool):
            raise ValueError("require_local_engine must be boolean")
        reservation = self.controller.maintenance()
        await reservation.__aenter__()
        try:
            self.require_idle()
            if require_local and not native_engine_status().get("available"):
                raise ValueError("the embedded local model engine is unavailable")
            lease_id = secrets.token_urlsafe(32)
            self._provider_change_lease = {
                "lease_id": lease_id,
                "deadline": time.monotonic() + _PROVIDER_CHANGE_TTL_SECONDS,
                "reservation": reservation,
            }
            self._provider_change_timer = asyncio.create_task(
                self._expire_provider_change(lease_id), name="mobile-provider-reservation"
            )
            return {"ok": True, "lease_id": lease_id, "ttl_seconds": _PROVIDER_CHANGE_TTL_SECONDS}
        except BaseException:
            await reservation.__aexit__(None, None, None)
            raise

    async def _finish_provider_change(self, state):
        lease = self._provider_change_lease
        if lease is None:
            return
        # An expired caller may still be writing preferences. Keep admission
        # closed until restart rather than letting that caller interrupt a new task.
        if state in {"committed", "expired"}:
            self.controller.prepare_provider_restart()
        self._provider_change_result = {"lease_id": lease["lease_id"], "state": state}
        self._provider_change_lease = None
        timer = self._provider_change_timer
        if timer is not None and timer is not asyncio.current_task():
            timer.cancel()
        await lease["reservation"].__aexit__(None, None, None)

    async def _expire_provider_change(self, lease_id):
        await asyncio.sleep(_PROVIDER_CHANGE_TTL_SECONDS)
        lease = self._provider_change_lease
        if lease is not None and secrets.compare_digest(lease["lease_id"], lease_id):
            await self._finish_provider_change("expired")

    async def _provider_change(self, operation, payload):
        if operation == "prepare":
            return await self._prepare_provider_change(payload)
        if operation not in {"commit", "abort", "status"}:
            raise ValueError("unknown provider reservation operation")
        lease_id = payload.get("lease_id")
        if (
            set(payload) != {"lease_id"}
            or not isinstance(lease_id, str)
            or not 1 <= len(lease_id) <= 80
        ):
            raise ValueError("invalid provider change lease")
        lease = self._provider_change_lease
        if lease is not None and secrets.compare_digest(lease["lease_id"], lease_id):
            if time.monotonic() >= lease["deadline"]:
                await self._finish_provider_change("expired")
            elif operation == "status":
                return {"ok": True, "state": "prepared", "restart_required": False}
            else:
                await self._finish_provider_change(
                    "committed" if operation == "commit" else "aborted"
                )
        result = self._provider_change_result
        if result is None or not secrets.compare_digest(result["lease_id"], lease_id):
            raise ValueError("provider change lease is unknown")
        state = result["state"]
        return {
            "ok": (state == "committed" and operation != "abort")
            or (state == "aborted" and operation != "commit"),
            "state": state,
            "restart_required": state in {"committed", "expired"},
        }

    async def _run_maintenance(self, operation):
        async with self.controller.maintenance():
            self.require_idle()
            worker = asyncio.create_task(operation())
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                # Cancelling an HTTP coroutine cannot stop its native/thread
                # worker. Retain the gate until the whole operation settles,
                # including repeated cancellation during server shutdown.
                while not worker.done():
                    try:
                        await asyncio.shield(worker)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                with suppress(Exception, asyncio.CancelledError):
                    worker.result()
                raise

    async def _start_toolchain_install(self):
        ready = asyncio.get_running_loop().create_future()
        ready.add_done_callback(lambda value: None if value.cancelled() else value.exception())

        async def install():
            manager = await self.toolchain()
            progress = await asyncio.to_thread(manager.install)
            ready.set_result(progress)
            return await asyncio.to_thread(manager.wait_for_install)

        job = asyncio.create_task(
            self._run_maintenance(install), name="mobile-toolchain-maintenance"
        )
        self._maintenance_jobs.add(job)

        def finished(completed):
            self._maintenance_jobs.discard(completed)
            error = None if completed.cancelled() else completed.exception()
            if not ready.done():
                if completed.cancelled():
                    ready.cancel()
                elif error is not None:
                    ready.set_exception(error)
                else:
                    ready.set_result(completed.result())

        job.add_done_callback(finished)
        # The response reports initial progress; the owned job keeps admission
        # blocked through extraction, replacement, and native execution probes.
        return await asyncio.shield(ready)

    async def toolchain(self):
        from mobile_toolchain import get_toolchain_manager

        manager = await asyncio.to_thread(get_toolchain_manager, self.data, self.workspace)
        if manager is None:
            raise ValueError("toolchain storage is unavailable")
        return manager

    async def _session_controller(self, session_id):
        if session_id is None:
            return self.controller
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a nonempty string")
        route = getattr(self.controller, "controller_for", None)
        if callable(route):
            return await route(session_id)
        self.runtime.service.get_session(session_id)
        return self.controller

    async def get(self, path, query):
        if path == "/mobile/capabilities":
            from android_adapter.capabilities import (
                discover_runnable_executables,
                runtime_capabilities,
            )

            runner = getattr(self.runtime.service, "runner", None)
            registry = getattr(runner, "_tools", None)
            await asyncio.to_thread(
                discover_runnable_executables, getattr(registry, "_android_workspace", None)
            )

            return 200, runtime_capabilities(self.runtime)
        if path == "/mobile/android-system/status":
            from android_adapter.android_system import get_android_system_status

            return 200, get_android_system_status()
        if path == "/mobile/extensions":
            controller = await self._session_controller(query.get("session_id", [None])[0])
            consents = getattr(controller, "extension_consents", None)
            return 200, consents.snapshot() if consents else {
                "extensions": [],
                "restart_required": False,
            }
        if path == "/mobile/schedules":
            return 200, self.schedules.snapshot()
        if path == "/mobile/connections":
            return 200, {
                "hosts": self.connections.list(),
                "data_location": "phone",
                "workspace": str(self.runtime.service._execution_workspace),
            }
        if path == "/mobile/connections/sessions":
            return 200, await self.connections.sessions(query.get("host_id", [""])[0])
        if path == "/mobile/connections/events":
            return 200, await self.connections.events(
                query.get("host_id", [""])[0], query.get("session_id", [""])[0]
            )
        if path == "/mobile/outbox":
            return 200, {"deliveries": self.outbox.list(), "data_location": "phone"}
        if path == "/mobile/workflows":
            return 200, {"workflows": self.workflows.list(), "runs": self.workflows.runs()}
        if path == "/mobile/workflows/export":
            return 200, self.workflows.export(query.get("workflow_id", [""])[0])
        if path == "/mobile/workflows/run":
            return 200, self.workflows.run(query.get("run_id", [""])[0])
        if path == "/mobile/evaluations/export":
            return 200, self.evaluations.export(limit=int(query.get("limit", ["200"])[0]))
        if path == "/mobile/evaluations":
            return 200, {
                "scenarios": self.evaluations.scenarios(),
                "runs": self.evaluations.list(),
                "summary": self.evaluations.summary(),
            }
        if path == "/mobile/local-models":
            value = await asyncio.to_thread(
                local_model_diagnostics, self.controller, model_manager=self.models
            )
            if value["route"] == "embedded_qwen" and getattr(self.runtime.service, "runner", None):
                from android_adapter.local_context import local_context_status

                value["context_profile"] = local_context_status(self.runtime)
            state = self.controller.status()
            return 200, {
                **value,
                **{
                    key: state.get(key) for key in ("active_task_id", "queued_tasks", "maintenance")
                },
            }
        if path == "/mobile/toolchain":
            return 200, (await self.toolchain()).snapshot()
        if path == "/mobile/memory":
            return 200, self.memory().snapshot()
        if path == "/mobile/knowledge":
            return 200, await asyncio.to_thread(self.knowledge().snapshot)
        if path == "/mobile/backup/status":
            from mobile_backup import backup_jobs

            return 200, backup_jobs.status(query.get("job_id", [""])[0])
        if path == "/mobile/notification-rules":
            return 200, self.notification_rules().snapshot()
        if path == "/mobile/services":
            return 200, await asyncio.to_thread(self.services().snapshot, probe=True)
        if path == "/mobile/services/logs":
            max_bytes = int(query.get("max_bytes", ["16384"])[0])
            return 200, self.services().logs(query.get("id", [""])[0], max_bytes)
        if path == "/mobile/live-output":
            from mobile_services import live_output

            output = live_output(query.get("attempt_id", [""])[0])
            return 200, output or {"active": False, "text": "", "bytes": 0}
        return None

    def notification_rules(self):
        from mobile_notification_rules import get_notification_rules

        return get_notification_rules(self.data)

    async def _submit_rule_task(self, rule, prompt):
        """A notification rule's task, submitted like a scheduled one into the rule's conversation."""
        from mobile_protocol import parse_mobile_task_request

        request = parse_mobile_task_request({
            "session_id": rule["session_id"],
            "prompt": prompt,
            "model": rule.get("model") or self.controller.default_model,
            "reasoning_effort": rule.get("reasoning_effort") or self.controller.default_reasoning_effort,
        })
        task = await self.controller.submit(request)
        return task.task_id

    async def _notification_rules_post(self, action, payload):
        rules = self.notification_rules()
        if action == "":
            return 201, rules.add(payload)
        if action == "update":
            return 200, rules.update(payload.get("id"), payload)
        if action == "delete":
            return 200, rules.delete(payload.get("id"))
        if action == "settings":
            return 200, rules.set_enabled(payload.get("enabled"))
        if action == "trigger":
            return 200, await rules.trigger(payload, self._submit_rule_task)
        if action == "run":
            return 200, await rules.run_pending(payload.get("trigger_id"), self._submit_rule_task)
        if action == "dismiss":
            return 200, rules.dismiss(payload.get("trigger_id"))
        raise KeyError(action)

    @staticmethod
    def _browser(action):
        """Device & tools: check the in-app browser on a known page, or forget its data."""
        from android_adapter.browser import BrowserSession, browser_available

        if not browser_available():
            raise ValueError("the in-app browser needs the Android app")
        session = BrowserSession()
        if action == "clear":
            session.call({"action": "clear"})
            return {"ok": True}
        if action != "test":
            raise KeyError(action)
        session.call({"action": "navigate", "url": "https://example.com/", "timeout_ms": 15000})
        page = session.snapshot(500, 5)
        shot = session.call({"action": "screenshot"}).get("screenshot") or {}
        return {
            "ok": True,
            "title": page.get("title"),
            "url": page.get("url"),
            "elements": len(page.get("elements") or []),
            "screenshot": {key: shot.get(key) for key in ("width", "height", "blank")},
        }

    def services(self):
        from mobile_services import get_service_manager

        manager = get_service_manager(self.data)
        if manager is None:
            raise ValueError("services are unavailable in this runtime")
        return manager

    def _app_file(self, raw: object) -> Path:
        """A path inside this app's cache folder (backups are written and read only there)."""
        if not isinstance(raw, str) or not raw:
            raise ValueError("a backup path is required")
        app_root = self.data.parent.parent.resolve()
        path = Path(raw).resolve()
        if not path.is_relative_to(app_root / "cache"):
            raise ValueError("backups are only read from and written to the app's own cache")
        return path

    def memory(self):
        from mobile_memory import get_memory_store

        return get_memory_store(self.data)

    def knowledge(self):
        from mobile_knowledge import get_knowledge_store

        return get_knowledge_store(self.data)

    async def _knowledge_post(self, action, payload):
        """Knowledge page: settings, removal, renaming and a test search. Uploads and workspace
        imports are gateway routes, which stream bodies and resolve workspaces."""
        store = self.knowledge()
        if action == "settings":
            return 200, await asyncio.to_thread(
                store.set_settings, enabled=payload.get("enabled"), auto=payload.get("auto")
            )
        if action == "synonyms":
            return 200, await asyncio.to_thread(store.set_synonyms, payload.get("text"))
        if action in {"delete", "rename"}:
            if action == "delete":
                await asyncio.to_thread(store.delete, payload.get("id"))
            else:
                await asyncio.to_thread(store.rename, payload.get("id"), payload.get("title"))
            return 200, await asyncio.to_thread(store.snapshot)
        if action == "search":
            query = payload.get("query")
            if not isinstance(query, str) or len(query) > 500:
                raise ValueError("query must be text of at most 500 characters")
            results = await asyncio.to_thread(store.search, query, limit=8)
            return 200, {"results": [store.public(result, excerpt=240) for result in results]}
        raise KeyError(action)

    async def post(self, path, payload):
        if path == "/mobile/backup/create":
            from mobile_backup import backup_jobs

            output = self._app_file(payload.get("output"))
            if output.suffix != ".zip":
                raise ValueError("backups are zip files")
            settings = {key: payload.get(key) for key in ("app_settings", "web_settings")
                        if isinstance(payload.get(key), dict)}
            return 202, backup_jobs.start(self.data.parent, output, **settings)
        if path == "/mobile/backup/restore":
            from mobile_backup import stage_restore

            async with self.controller.maintenance():
                self.require_idle()
                archive = self._app_file(payload.get("path"))
                staged = await asyncio.to_thread(stage_restore, self.data.parent, archive)
            return 200, {**staged, "restart_required": True}
        if path.startswith("/mobile/memory"):
            store = self.memory()
            if path == "/mobile/memory":
                store.add(payload.get("content"), source="user")
                return 201, store.snapshot()
            if path == "/mobile/memory/update":
                store.update(payload.get("id"), payload.get("content"), source="user")
                return 200, store.snapshot()
            if path == "/mobile/memory/delete":
                store.delete(payload.get("id"))
                return 200, store.snapshot()
            if path == "/mobile/memory/clear":
                store.clear()
                return 200, store.snapshot()
            if path == "/mobile/memory/settings":
                return 200, store.set_settings(
                    enabled=payload.get("enabled"), auto=payload.get("auto")
                )
        if path.startswith("/mobile/knowledge/"):
            return await self._knowledge_post(path[len("/mobile/knowledge/"):], payload)
        if path == "/mobile/notification-rules" or path.startswith("/mobile/notification-rules/"):
            return await self._notification_rules_post(path[len("/mobile/notification-rules/"):], payload)
        if path.startswith("/mobile/browser/"):
            return 200, await asyncio.to_thread(self._browser, path.rsplit("/", 1)[-1])
        if path.startswith("/mobile/services/"):
            manager = self.services()
            action = path.rsplit("/", 1)[-1]
            if action == "settings":
                return 200, manager.set_keep_awake(payload.get("keep_awake"))
            key = payload.get("id")
            if not isinstance(key, str) or not key:
                raise ValueError("a service id is required")
            if action == "stop":
                return 200, await asyncio.to_thread(manager.stop, key, "stopped by the user")
            if action == "restart":
                return 200, await asyncio.to_thread(manager.restart, key)
            if action == "autostart":
                return 200, manager.set_autostart(key, payload.get("enabled"))
            if action == "remove":
                manager.remove(key)
                return 200, manager.snapshot()
        if path.startswith("/mobile/provider-change/"):
            return 200, await self._provider_change(path.rsplit("/", 1)[-1], payload)
        if path == "/mobile/android-system":
            return 200, await self.system(payload)
        if path in {"/mobile/extensions/resolve", "/mobile/extensions/revoke"}:
            controller = await self._session_controller(payload.get("session_id"))
            consents = getattr(controller, "extension_consents", None)
            if consents is None:
                raise ValueError("extension consent store is not available")
            async with self.controller.maintenance():
                self.require_idle()
                if path.endswith("resolve"):
                    consents.decide(
                        payload.get("request_id"), payload.get("allowed"), payload.get("digest")
                    )
                else:
                    consents.revoke(payload.get("request_id"), payload.get("digest"))
                disable = getattr(consents, "disable_tools", None)
                if callable(disable):
                    registry = getattr(
                        getattr(controller.runtime.service, "runner", None), "_tools", None
                    )
                    if registry is not None:
                        disable(registry)
                return 200, consents.snapshot()
        if path == "/mobile/schedules":
            record = self.schedules.create(payload)
            self.mirror_schedules()
            return 201, record
        if path == "/mobile/schedules/update":
            record = self.schedules.update(
                payload.get("schedule_id"),
                {key: value for key, value in payload.items() if key != "schedule_id"},
            )
            self.mirror_schedules()
            return 200, record
        if path == "/mobile/schedules/delete":
            self.schedules.delete(payload.get("schedule_id"))
            self.mirror_schedules()
            return 200, self.schedules.snapshot()
        if path == "/mobile/schedules/run":
            dispatched = await self.schedules.dispatch_due()
            self.mirror_schedules()
            return 200, {**self.schedules.snapshot(), "dispatched": dispatched}
        if path == "/mobile/connections":
            return 201, await self.connections.pair(payload)
        if path == "/mobile/connections/remove":
            if any(
                job["host_id"] == payload.get("host_id")
                and job["state"] in {"pending", "sending", "submitted", "uncertain"}
                for job in self.outbox.list()
            ):
                raise ValueError("cancel or reconcile outgoing requests before removing the host")
            return 200, {"ok": self.connections.remove(payload.get("host_id"))}
        if path == "/mobile/outbox":
            return 201, self.outbox.enqueue(payload)
        if path == "/mobile/outbox/send":
            return 200, await self.outbox.send(payload.get("delivery_id"))
        if path == "/mobile/outbox/reconcile":
            return 200, await self.outbox.reconcile(payload.get("delivery_id"))
        if path == "/mobile/outbox/cancel":
            return 200, self.outbox.cancel(payload.get("delivery_id"))
        if path == "/mobile/workflows":
            return 201, self.workflows.save(payload)
        if path == "/mobile/workflows/delete":
            return 200, {"ok": self.workflows.delete(payload.get("workflow_id"))}
        if path == "/mobile/workflows/run":
            return 202, await self.workflows.start(
                payload.get("workflow_id"), payload, self.controller, self.system
            )
        if path == "/mobile/workflows/import":
            return 201, self.workflows.import_document(payload.get("document"))
        if path == "/mobile/workflows/record":
            return 201, self.workflows.record(payload)
        if path == "/mobile/workflows/resume":
            return 202, await self.workflows.resume(
                payload.get("run_id"), payload, self.controller, self.system
            )
        if path == "/mobile/evaluations/plan":
            return 200, self.evaluations.export_plan(payload)
        if path == "/mobile/evaluations":
            return 201, self.evaluations.record(payload)
        if path == "/mobile/evaluations/run":
            from android_adapter.android_system import get_android_system_status

            controller = await self._session_controller(payload.get("session_id"))
            device = get_android_system_status()
            metadata = payload.get("metadata") or {
                "device": device.get("device"),
                "app_version": device.get("app_version"),
                "model": self.controller.default_model,
                "budget_steps": 30,
                "retry_policy": "bounded provider recovery; no automatic task replay",
            }
            for field in ("device", "app_version"):
                actual = device.get(field)
                if actual and metadata.get(field) != actual:
                    raise ValueError(f"evaluation {field} does not match the actual device")
                if actual:
                    metadata[field] = actual
            return 202, await self.evaluations.start(
                payload, self.controller, self.system, controller.runtime, metadata
            )
        if path == "/mobile/local-models/probe":
            return 200, await probe_local_model(self.controller, model_manager=self.models)
        if path == "/mobile/local-models/download":
            source, prefer = payload.get("source", "auto"), payload.get("prefer")
            if not isinstance(source, str) or not (prefer is None or isinstance(prefer, str)):
                raise ValueError("invalid download source")
            return 202, self.models.start_download(payload.get("model_id"), source, prefer)
        if path == "/mobile/local-models/cancel":
            return 200, await self.models.cancel_download(payload.get("model_id"))
        if path in {"/mobile/local-models/remove", "/mobile/local-models/unload"}:

            async def change_model():
                bridge = get_local_engine_bridge()
                if bridge is not None:
                    await asyncio.to_thread(bridge.unload)
                if path.endswith("remove"):
                    await asyncio.to_thread(self.models.remove, payload.get("model_id"))
                return await asyncio.to_thread(
                    local_model_diagnostics, self.controller, model_manager=self.models
                )

            return 200, await self._run_maintenance(change_model)
        if path.startswith("/mobile/toolchain/"):
            operation = path.rsplit("/", 1)[-1]
            if operation == "install":
                return 200, await self._start_toolchain_install()
            if operation in {"remove", "probe"}:

                async def change_toolchain():
                    manager = await self.toolchain()
                    return await asyncio.to_thread(getattr(manager, operation))

                return 200, await self._run_maintenance(change_toolchain)
            if operation == "cancel":
                manager = await self.toolchain()
                return 200, await asyncio.to_thread(manager.cancel)
        return None

    async def dispatch(self, method, path, payload):
        try:
            return await (self.get(path, payload) if method == "GET" else self.post(path, payload))
        except KeyError:
            return 404, {"error": "requested management record does not exist"}
        except (ValueError, TypeError) as exc:
            return 400, {"error": " ".join(str(exc).split())[:1500]}
        except httpx.HTTPError:
            return 503, {"error": "remote host is unavailable"}
        except Exception as exc:
            from mobile_toolchain import ToolchainError

            from agent_workspace.tools.base import ToolError

            if isinstance(exc, (ToolError, ToolchainError)):
                return 409, {"error": str(exc)[:1500]}
            return 500, {"error": "management operation failed"}
