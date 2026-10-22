"""Secondary mobile management routes around existing task and platform adapters."""

from __future__ import annotations

import asyncio
import os
import secrets
import threading
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
        # The official skills shipped in this app version (first start, or newer than installed).
        threading.Thread(target=self._install_bundled_skills, name="bundled-skills", daemon=True).start()
        self._job = asyncio.create_task(self._run(), name="mobile-management")

    async def _run(self):
        await asyncio.gather(self.schedules.run(), self.outbox.run(), self._mirror_loop(), self._app_watch_loop(),
                             self._calendar_loop())

    async def _mirror_loop(self):
        while True:
            with suppress(Exception):
                self.mirror_schedules()
            await asyncio.sleep(30)

    async def _app_watch_loop(self):
        """应用体检 in the background: a newly installed app with large powers, or one that newly
        holds one, is told about with a notification (mobile_app_audit.watch_once)."""
        if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") != "chaquopy":
            return
        import mobile_app_audit

        await asyncio.sleep(90)
        while True:
            with suppress(Exception):
                await asyncio.to_thread(mobile_app_audit.watch_once)
            await asyncio.sleep(1800)

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

    async def _triggers_post(self, path, payload):
        """Automatic triggers: kept by mobile_triggers; /fire (from the Android app) starts the
        matching prompts and workflows like a schedule does (the user set them up, so their tool
        calls are allowed; deleting, memory changes and other apps still ask)."""
        import mobile_triggers

        try:
            changed = None
            if path == "/mobile/triggers":
                changed = 201, mobile_triggers.add(payload)
            elif path == "/mobile/triggers/delete":
                mobile_triggers.delete(str(payload.get("trigger_id") or ""))
                changed = 200, mobile_triggers.snapshot()
            elif path == "/mobile/triggers/enable":
                changed = 200, mobile_triggers.set_enabled(str(payload.get("trigger_id") or ""), payload.get("enabled"))
            if changed is not None:
                # The accessibility service keeps the apps to watch for a minute; read them again now.
                with suppress(Exception):
                    from java import jclass

                    jclass("com.agentworkspace.mobile.embedded.TriggerEvents").invalidate()
                return changed
        except KeyError:
            return 404, {"error": "no such trigger"}
        except ValueError as error:
            return 400, {"error": str(error)}
        if path != "/mobile/triggers/fire":
            return 404, {"error": "unknown trigger route"}
        fired = mobile_triggers.fire(str(payload.get("kind") or ""), str(payload.get("value") or ""),
                                     previous=str(payload.get("previous") or ""))
        return 200, {"started": await self._start_triggered(fired)}

    async def _start_triggered(self, items):
        from mobile_protocol import parse_mobile_task_request

        started = []
        for item in items:
            try:
                if item.get("shortcut_id"):
                    self._start_shortcut(item["shortcut_id"])
                    result = {"shortcut_id": item["shortcut_id"]}
                elif item.get("workflow_id"):
                    result = await self.workflows.start(item["workflow_id"], {"session_id": item["session_id"]}, self.controller, self.system)
                else:
                    prompt = item["prompt"]
                    if item.get("event"):
                        # Which event it is ("日程：周会，10:00–11:00，3 楼会议室"), in the phone's language.
                        prompt += "\n\n" + str(item["event"].get("line") or item["event"].get("title") or "")[:500]
                    request = parse_mobile_task_request({
                        "session_id": item["session_id"], "prompt": prompt,
                        "phone_control": bool(item.get("phone_control")),
                    })
                    result = (await self.controller.submit(request, preauthorized=True)).to_dict()
                started.append({"trigger_id": item["trigger_id"], "result": result})
            except Exception as error:  # one trigger failing must not stop the others
                started.append({"trigger_id": item["trigger_id"], "error": str(error)[:300]})
        return started

    async def _calendar_loop(self):
        """Calendar triggers: once a minute, while one is on, the events starting soon."""
        if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") != "chaquopy":
            return
        import json

        import mobile_triggers
        from java import jclass

        calendar = jclass("com.agentworkspace.mobile.capabilities.AndroidClockCalendar")
        while True:
            await asyncio.sleep(60)
            with suppress(Exception):
                lead = mobile_triggers.calendar_lead()
                if lead:
                    found = json.loads(str(await asyncio.to_thread(calendar.upcoming, lead + 1)))
                    due = mobile_triggers.calendar_due(found.get("events") or [])
                    if due:
                        await self._start_triggered(due)

    def _start_shortcut(self, shortcut_id):
        """Runs a shortcut in the background (mobile_shortcuts.run waits for every step); one at a
        time, and not while a task is running, since both would operate the phone."""
        import mobile_shortcuts

        if not isinstance(shortcut_id, str) or not shortcut_id:
            raise ValueError("shortcut id is required")
        if self.controller.status().get("active_task_id"):
            raise ValueError("wait for the current task to finish")
        if mobile_shortcuts.running():
            raise ValueError("another shortcut is running")
        job = asyncio.create_task(asyncio.to_thread(mobile_shortcuts.run, shortcut_id), name="shortcut")
        self._maintenance_jobs.add(job)
        job.add_done_callback(self._maintenance_jobs.discard)

    async def _shortcuts_post(self, path, payload):
        """Shortcuts (mobile_shortcuts): recorded phone tasks, edited here and run without the model."""
        import mobile_shortcuts

        try:
            if path == "/mobile/shortcuts":
                return 201, await asyncio.to_thread(mobile_shortcuts.save, payload)
            if path == "/mobile/shortcuts/delete":
                await asyncio.to_thread(mobile_shortcuts.delete, str(payload.get("id") or ""))
                return 200, {"ok": True}
            if path == "/mobile/shortcuts/keep":
                # A finished phone-control task's steps, saved under a name the user chose.
                name = str(payload.get("name") or "").strip()[:40]
                return 201, await asyncio.to_thread(mobile_shortcuts.keep, str(payload.get("task_id") or ""), name)
            if path == "/mobile/shortcuts/heal":
                # The AI finished a stuck shortcut: its steps replace those from the stuck one on.
                return 200, await asyncio.to_thread(
                    mobile_shortcuts.heal, str(payload.get("task_id") or ""), str(payload.get("id") or ""), payload.get("from_step")
                )
            if path == "/mobile/shortcuts/run":
                self._start_shortcut(payload.get("id"))
                return 202, {"started": True}
            if path == "/mobile/shortcuts/stop":
                await asyncio.to_thread(mobile_shortcuts.stop)
                return 200, {"ok": True}
        except KeyError:
            return 404, {"error": "no such shortcut or recorded task"}
        except ValueError as error:
            return 400, {"error": str(error)}
        return 404, {"error": "unknown shortcut route"}

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
        if path == "/mobile/session-meta":
            import mobile_session_meta

            return 200, mobile_session_meta.snapshot()
        if path == "/mobile/triggers":
            import mobile_triggers

            return 200, mobile_triggers.snapshot()
        if path == "/mobile/shortcuts":
            import mobile_shortcuts

            return 200, {
                "shortcuts": await asyncio.to_thread(mobile_shortcuts.list_shortcuts),
                "available": mobile_shortcuts.available(),
                "running": mobile_shortcuts.running(),
                "last_run": mobile_shortcuts.last_run(),
            }
        if path == "/mobile/hosted-limits":
            import mobile_hosted_limits

            return 200, mobile_hosted_limits.get()
        if path == "/mobile/notification-journal":
            import mobile_notification_journal

            return 200, mobile_notification_journal.status()
        if path == "/mobile/widget-card":
            import mobile_widget_card

            return 200, {"source": mobile_widget_card.source()}
        if path == "/mobile/step-shots":
            # Step replay: what the phone looked like after each action of a task.
            import mobile_step_shots

            return 200, {"steps": await asyncio.to_thread(mobile_step_shots.steps, query.get("task_id", [""])[0])}
        if path == "/mobile/step-shots/tutorial":
            import mobile_step_tutorial

            return 200, {"frames": await asyncio.to_thread(mobile_step_tutorial.preview, query.get("task_id", [""])[0])}
        if path == "/mobile/elder":
            import mobile_elder

            return 200, await asyncio.to_thread(mobile_elder.settings)
        if path == "/mobile/app-audit":
            import mobile_app_audit

            try:
                return 200, await asyncio.to_thread(mobile_app_audit.scan_phone)
            except Exception as error:
                return 503, {"error": f"could not check the apps: {error}"[:300]}
        if path == "/mobile/step-shots/tasks":
            import mobile_step_tutorial

            session_id = query.get("session_id", [""])[0]
            if not session_id:
                return 400, {"error": "session_id is required"}
            tasks = self.controller.list(session_id)
            return 200, {"tasks": await asyncio.to_thread(mobile_step_tutorial.tasks_with_steps, tasks)}
        if path == "/mobile/shortcuts/pending":
            import mobile_shortcuts

            return 200, {"steps": mobile_shortcuts.pending(query.get("task_id", [""])[0])}
        if path == "/mobile/speech/status":
            import json as _json

            from java import jclass

            speech = jclass("com.agentworkspace.mobile.capabilities.AndroidTextToSpeech")
            return 200, _json.loads(str(speech.getUtteranceStatus(query.get("id", [""])[0])))
        if path == "/mobile/provider/extras":
            from android_adapter.provider_transport import describe

            return 200, await asyncio.to_thread(describe, os.getenv("AGENT_WORKSPACE_BASE_URL") or "")
        if path == "/mobile/model-roles":
            from mobile_model_roles import get_roles

            return 200, {"roles": get_roles()}
        if path == "/mobile/task-limits":
            from mobile_task_limits import get_limits

            return 200, {"limits": get_limits()}
        if path == "/mobile/app-notes":
            from mobile_app_notes import listing

            return 200, await asyncio.to_thread(listing)
        if path == "/mobile/background-screen":
            from android_adapter.android_system import background_screen

            try:
                return 200, await asyncio.to_thread(background_screen)
            except Exception:
                return 200, {"supported": False, "reason": "unavailable"}
        if path == "/mobile/background-screen/picture":
            import base64

            from android_adapter.android_system import background_picture

            try:
                picture = await asyncio.to_thread(background_picture, 720)
            except Exception:
                picture = None
            return 200, {"jpeg_base64": base64.b64encode(picture).decode("ascii") if picture else None}
        if path == "/mobile/skills":
            return 200, await asyncio.to_thread(self.skills().snapshot)
        if path == "/mobile/skills/job":
            return 200, self.skills().job(query.get("id", [""])[0])
        if path == "/mobile/knowledge":
            return 200, await asyncio.to_thread(self.knowledge().snapshot)
        if path == "/mobile/knowledge/session":
            return 200, await asyncio.to_thread(
                self.knowledge().session_selection, query.get("session_id", [""])[0]
            )
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

    def skills(self):
        from mobile_skills import get_skill_store

        return get_skill_store(self.data)

    def _install_bundled_skills(self):
        try:
            self.skills().install_bundled()
        except Exception:  # a damaged copy in the app never stops the engine
            import logging

            logging.getLogger(__name__).exception("bundled skills were not installed")

    async def _skills_post(self, action, payload):
        """Skills page: fetch a pack from GitHub (a background job), install a fetched or uploaded
        pack after the user saw it, turn packs and skills on or off, remove, check and update."""
        store = self.skills()
        if action == "official":
            # What the project's skills repository offers now (cached for a few hours).
            refresh = payload.get("refresh") is True
            return 202, store.start_job("official", lambda: store.official(refresh=refresh))
        if action == "install-official":
            return 202, store.start_job("install", store.install_official)
        if action == "preview":
            spec = payload.get("github")
            if not isinstance(spec, str) or not spec.strip() or len(spec) > 300:
                raise ValueError("enter a GitHub repository as owner/repo or its link")
            return 202, store.start_job("preview", lambda: store.preview_github(spec))
        if action == "install":
            await asyncio.to_thread(store.install, payload.get("token"))
            return 200, await asyncio.to_thread(store.snapshot)
        if action == "remove":
            await asyncio.to_thread(store.remove, payload.get("pack_id"))
            return 200, await asyncio.to_thread(store.snapshot)
        if action == "enable":
            await asyncio.to_thread(
                store.set_enabled, payload.get("pack_id"), payload.get("enabled"), payload.get("skill_id")
            )
            return 200, await asyncio.to_thread(store.snapshot)
        if action == "delete-skill":
            await asyncio.to_thread(store.delete_user_skill, payload.get("skill_id"))
            return 200, await asyncio.to_thread(store.snapshot)
        if action == "check-updates":
            return 202, store.start_job("check", store.check_updates)
        if action == "update":
            pack_id = payload.get("pack_id")
            return 202, store.start_job("update", lambda: store.update(pack_id))
        raise KeyError(action)

    def knowledge(self):
        from mobile_knowledge import get_knowledge_store

        return get_knowledge_store(self.data)

    async def _knowledge_post(self, action, payload):
        """Knowledge page: settings, knowledge bases, removal, renaming and a test search, and
        the knowledge bases of a conversation. Uploads and workspace imports are gateway routes,
        which stream bodies and resolve workspaces."""
        store = self.knowledge()
        if action == "session":
            if "collections" not in payload:
                raise ValueError("collections is required (a list of ids, or null)")
            return 200, await asyncio.to_thread(
                store.set_session_selection, payload.get("session_id"), payload.get("collections")
            )
        if action.startswith("collections/") or action == "move":
            if action == "collections/create":
                await asyncio.to_thread(
                    store.create_collection,
                    payload.get("name"),
                    default_on=payload.get("default_on", True),
                )
            elif action == "collections/rename":
                await asyncio.to_thread(
                    store.rename_collection, payload.get("id"), payload.get("name")
                )
            elif action == "collections/default":
                await asyncio.to_thread(
                    store.set_collection_default, payload.get("id"), payload.get("default_on")
                )
            elif action == "collections/delete":
                await asyncio.to_thread(store.delete_collection, payload.get("id"))
            elif action == "move":
                await asyncio.to_thread(
                    store.move_document, payload.get("id"), payload.get("collection_id")
                )
            else:
                raise KeyError(action)
            return 200, await asyncio.to_thread(store.snapshot)
        if action == "settings":
            return 200, await asyncio.to_thread(
                store.set_settings, enabled=payload.get("enabled"), auto=payload.get("auto")
            )
        if action == "synonyms":
            return 200, await asyncio.to_thread(store.set_synonyms, payload.get("text"))
        if action == "url":
            # A web page the user saves: fetched now (public HTTPS addresses only).
            added = await asyncio.to_thread(
                store.add_url, payload.get("url"), collection_id=payload.get("collection")
            )
            return 200, {**(await asyncio.to_thread(store.snapshot)), "added": added}
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
            collections = payload.get("collections")
            if collections is not None and (
                not isinstance(collections, list)
                or not all(isinstance(item, str) for item in collections)
            ):
                raise ValueError("collections must be a list of knowledge base ids")
            results = await asyncio.to_thread(
                store.search, query, limit=8, collections=collections
            )
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
        if path.startswith("/mobile/triggers"):
            return await self._triggers_post(path, payload)
        if path.startswith("/mobile/shortcuts"):
            return await self._shortcuts_post(path, payload)
        if path == "/mobile/hosted-limits":
            import mobile_hosted_limits

            return 200, mobile_hosted_limits.set_limits(payload)
        if path == "/mobile/widget-card":
            # Which conversation the AI card widget follows (mobile_widget_card).
            import mobile_widget_card

            return 200, await asyncio.to_thread(mobile_widget_card.set_source, payload)
        if path.startswith("/mobile/notification-journal"):
            # Notifications kept on the phone for digests (mobile_notification_journal).
            import mobile_notification_journal as journal

            if path == "/mobile/notification-journal":
                return 200, journal.set_enabled(payload.get("enabled"))
            if path == "/mobile/notification-journal/add":
                return 200, {"kept": await asyncio.to_thread(journal.add, payload)}
            if path == "/mobile/notification-journal/clear":
                return 200, journal.clear()
            return 404, {"error": "unknown notification journal route"}
        if path in ("/mobile/speech/speak", "/mobile/speech/stop"):
            # Read a reply aloud with the phone's text-to-speech (the console's read-aloud button and
            # voice conversations); the same engine as the speak_text tool.
            import json as _json
            import uuid as _uuid

            from java import jclass

            speech = jclass("com.agentworkspace.mobile.capabilities.AndroidTextToSpeech")
            if path.endswith("/stop"):
                await asyncio.to_thread(speech.stop, str(payload.get("request_id") or ""))
                return 200, {"stopped": True}
            text = " ".join(str(payload.get("text") or "").split())[:4000]
            if not text:
                return 400, {"error": "nothing to read"}
            rate = payload.get("rate", 1)
            if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0.5 <= rate <= 1.5:
                return 400, {"error": "rate is a number from 0.5 to 1.5"}
            request_id = str(_uuid.uuid4())
            started = await asyncio.to_thread(speech.startSpeakAt, request_id, text, float(rate))
            return 200, {"request_id": request_id, **_json.loads(str(started))}
        if path == "/mobile/provider/extras":
            from android_adapter.provider_transport import save_extras

            try:
                return 200, await asyncio.to_thread(
                    save_extras, os.getenv("AGENT_WORKSPACE_BASE_URL") or "", payload.get("headers") or {}, payload.get("keys") or []
                )
            except ValueError as error:
                return 400, {"error": str(error)}
        if path == "/mobile/sessions/export":
            from mobile_conversation_export import FORMATS, export_conversation

            session_id, fmt = payload.get("session_id"), payload.get("format")
            if not isinstance(session_id, str) or fmt not in FORMATS:
                return 400, {"error": f"session_id and a format ({', '.join(FORMATS)}) are required"}
            session = self.runtime.service.get_session(session_id)
            events = await asyncio.to_thread(self.runtime.store.list_events, session_id)
            title = str(payload.get("title") or "")[:120] or "Agent Workspace"
            return 200, await export_conversation(session.workspace, title, events, fmt)
        if path == "/mobile/sessions/fork":
            from mobile_session_fork import fork_conversation

            session_id, message_id, keep_reply = payload.get("session_id"), payload.get("message_event_id"), payload.get("keep_reply")
            title = payload.get("title")
            if not isinstance(session_id, str) or not isinstance(message_id, str) or not isinstance(keep_reply, bool):
                return 400, {"error": "session_id, message_event_id and keep_reply are required"}
            source = self.runtime.service.get_session(session_id)
            title = title.strip()[:200] if isinstance(title, str) and title.strip() else source.title
            try:
                result = await asyncio.to_thread(fork_conversation, self.runtime.store, session_id, message_id,
                                                 keep_reply=keep_reply, title=title)
            except ValueError as error:
                return 400, {"error": str(error)}
            forked = result["session"]
            # The same conversation goes on: what the user let it send to the model for the rest of the
            # conversation, the fork may send too. Each conversation's tasks run under their own
            # runtime's policy, so the approval is carried over, not shared.
            with suppress(Exception):
                def egress(controller):
                    runtime = getattr(controller, "runtime", None) or self.runtime
                    return getattr(getattr(runtime.service, "runner", None), "_egress_policy", None)

                source_policy = egress(await self._session_controller(session_id))
                fork_policy = egress(await self._session_controller(forked.id))
                granted = source_policy.session_grant(forked.workspace, session_id)
                if granted:
                    fork_policy.carry_session_grant(forked.workspace, forked.id, granted)
            # The knowledge bases chosen for the conversation go along.
            with suppress(Exception):
                knowledge = self.knowledge()
                chosen = await asyncio.to_thread(knowledge.session_selection, session_id)
                if chosen.get("explicit"):
                    await asyncio.to_thread(knowledge.set_session_selection, forked.id, chosen["collections"])
            return 201, {"session": {"id": forked.id, "title": forked.title, "workspace": forked.workspace},
                         "message_event_id": result["message_event_id"], "model": result["model"]}
        if path == "/mobile/step-shots/tutorial":
            from mobile_step_tutorial import export_tutorial

            session_id = payload.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                return 400, {"error": "session_id is required"}
            session = self.runtime.service.get_session(session_id)
            try:
                return 200, await export_tutorial(session.workspace, str(payload.get("task_id") or ""), payload.get("title"),
                                                  payload.get("subtitle", ""), payload.get("frames"))
            except ValueError as error:
                return 400, {"error": str(error)}
        if path in ("/mobile/session-meta/tags", "/mobile/session-meta/pin"):
            import mobile_session_meta

            try:
                if path.endswith("/tags"):
                    return 200, mobile_session_meta.set_tags(payload.get("session_id"), payload.get("tags"))
                return 200, mobile_session_meta.set_pinned(payload.get("session_id"), payload.get("pinned"))
            except ValueError as error:
                return 400, {"error": str(error)}
        if path == "/mobile/model-roles":
            from mobile_model_roles import set_roles

            try:
                return 200, {"roles": set_roles(payload.get("roles") or {})}
            except ValueError as error:
                return 400, {"error": str(error)}
        if path == "/mobile/task-limits":
            from mobile_task_limits import set_limits

            try:
                return 200, {"limits": set_limits(payload.get("limits") or {})}
            except ValueError as error:
                return 400, {"error": str(error)}
        if path == "/mobile/background-screen":
            from android_adapter.android_system import background_screen

            from agent_workspace.tools.base import ToolArgumentError

            try:
                return 200, await asyncio.to_thread(background_screen, payload)
            except ToolArgumentError as error:
                return 400, {"error": str(error)}
            except Exception as error:
                return 503, {"error": f"background screen unavailable: {error}"[:300]}
        if path == "/mobile/elder/sos":
            # 一键求救: the Messages app opens with a text to the family member; nothing is sent by itself.
            import mobile_elder

            try:
                return 200, await asyncio.to_thread(mobile_elder.sos)
            except ValueError as error:
                return 400, {"error": str(error)}
            except Exception as error:
                return 503, {"error": f"{error}"[:300]}
        if path == "/mobile/elder":
            # 长辈模式 settings; turning it off or changing the PIN needs the PIN when one is set.
            import mobile_elder

            try:
                return 200, await asyncio.to_thread(mobile_elder.update, payload)
            except ValueError as error:
                return 400, {"error": str(error)}
        if path == "/mobile/app-audit":
            # 应用体检: the pop-up record, apps marked as fine, and the pages that undo an app's powers.
            import mobile_app_audit as audit

            action = payload.get("action")
            try:
                if action == "watch" and isinstance(payload.get("enabled"), bool):
                    return 200, {"watching": await asyncio.to_thread(audit.set_watching, payload["enabled"])}
                if action == "watch_installs" and isinstance(payload.get("enabled"), bool):
                    await asyncio.to_thread(audit.set_watching_installs, payload["enabled"])
                    return 200, {"watch_installs": payload["enabled"]}
                if action == "trust" and isinstance(payload.get("trusted"), bool):
                    await asyncio.to_thread(audit.set_trusted, payload.get("package_name"), payload["trusted"])
                    return 200, {"ok": True}
                if action == "open":
                    await asyncio.to_thread(audit.open_page, payload.get("package_name"), payload.get("page"))
                    return 200, {"ok": True}
            except ValueError as error:
                return 400, {"error": str(error)}
            except Exception as error:
                return 503, {"error": f"{error}"[:300]}
            return 400, {"error": "action must be watch, watch_installs, trust or open"}
        if path == "/mobile/app-notes":
            import mobile_app_notes as notes

            action = payload.get("action")
            try:
                if action == "delete_note":
                    await asyncio.to_thread(notes.delete_note, payload.get("package_name"), payload.get("id"))
                elif action == "forget_app":
                    await asyncio.to_thread(notes.forget_app, payload.get("package_name"))
                elif action == "set_enabled" and isinstance(payload.get("enabled"), bool):
                    await asyncio.to_thread(notes.set_enabled, payload["enabled"])
                else:
                    return 400, {"error": "action must be delete_note, forget_app or set_enabled"}
            except ValueError as error:
                return 400, {"error": str(error)}
            return 200, await asyncio.to_thread(notes.listing)
        if path.startswith("/mobile/memory"):
            store = self.memory()
            if path == "/mobile/memory":
                store.add(payload.get("content"), source="user", topic=payload.get("topic"))
                return 201, store.snapshot()
            if path == "/mobile/memory/update":
                store.update(payload.get("id"), payload.get("content"), source="user", topic=payload.get("topic"))
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
        if path.startswith("/mobile/skills/"):
            return await self._skills_post(path[len("/mobile/skills/"):], payload)
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
