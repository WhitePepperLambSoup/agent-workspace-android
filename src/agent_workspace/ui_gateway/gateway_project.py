"""A folder's checks and rules (``.agent/project.json``): reading and saving them from the
Changes page, accepting a file that came with the folder, running the checks, and running
them after each turn that changed files, with failures sent back to the agent to fix."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.coding.project import (
    PROJECT_FILE,
    CheckResult,
    ProjectConfig,
    ProjectConfigError,
    config_path,
    detect_checks,
    failure_report,
    load_config,
    parse_config,
    run_checks,
    save_config,
)
from agent_workspace.core.events import Event
from agent_workspace.ui_gateway.gateway_common import _LOGGER, GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

PROJECT_COMMANDS = frozenset({"project.get", "project.set", "project.trust", "project.checks.run"})
# Running a project's tests takes minutes: off the reader thread, one at a time.
PROJECT_LONG_COMMANDS = frozenset({"project.checks.run"})
# The first line of the message that hands failed checks back to the agent; the window shows
# such a message as a notice rather than as something the user wrote.
CHECKS_MARKER = "<!-- agent-workspace:checks -->"
_MAX_REPORT_CHARS = 24_000


class ProjectCommands(GatewayState):
    def _project_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        handler = {
            "project.get": self._project_get,
            "project.set": self._project_set,
            "project.trust": self._project_trust,
            "project.checks.run": self._project_run,
        }[command.type]
        return self._reply(f"{command.type}.result", handler(command.payload), session_id=None)

    def _project_root(self) -> Path:
        return self._open_folder()

    def _project_document(self, root: Path) -> dict[str, Any]:
        error: str | None = None
        try:
            config = load_config(root)
        except ProjectConfigError as problem:
            config, error = None, str(problem)
        state = self._coding.state(root)
        return {
            "path": str(PROJECT_FILE),
            "exists": config_path(root).is_file(),
            "config": (config or ProjectConfig()).to_dict(),
            "error": error,
            "trusted": config is None or self._coding.trust.trusted(root, config),
            "suggested": [item.to_dict() for item in detect_checks(root)],
            "results": state.results,
            "finishedAt": state.finished_at,
            "running": state.running,
        }

    def _project_get(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload:
            raise GatewayError("invalid_command")
        return self._project_document(self._project_root())

    def _project_set(self, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) != {"config"}:
            raise GatewayError("invalid_command")
        root = self._project_root()
        try:
            config = parse_config(payload["config"])
        except ProjectConfigError as error:
            _LOGGER.info("project settings refused: %s", error)
            raise GatewayError("invalid_project_config") from None
        save_config(root, config)
        # The user wrote these commands here: they may run.
        self._coding.trust.trust(root, config)
        return self._project_document(root)

    def _project_trust(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload:
            raise GatewayError("invalid_command")
        root = self._project_root()
        try:
            config = load_config(root)
        except ProjectConfigError:
            raise GatewayError("invalid_project_config") from None
        if config is not None:
            self._coding.trust.trust(root, config)
        return self._project_document(root)

    def _project_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not set(payload) <= {"names"}:
            raise GatewayError("invalid_command")
        names = payload.get("names")
        if names is not None and (
            not isinstance(names, list) or not all(isinstance(name, str) for name in names)
        ):
            raise GatewayError("invalid_command")
        root = self._project_root()
        config = self._accepted_config(root)
        if config is None or not config.checks:
            raise GatewayError("project_no_checks")
        checks = [check for check in config.checks if names is None or check.name in names]
        state = self._coding.state(root)
        if state.running:
            raise GatewayError("project_checks_running")
        state.running = True
        self._announce_checks(root, None, [check.name for check in checks])
        try:
            results = run_checks(root, checks)
        finally:
            state.running = False
        self._coding.record(root, results)
        return self._project_document(root)

    def _accepted_config(self, root: Path) -> ProjectConfig | None:
        try:
            config = load_config(root)
        except ProjectConfigError:
            return None
        if config is None or not self._coding.trust.trusted(root, config):
            return None
        return config

    # -- events for the window

    def _announce_checks(self, root: Path, session_id: str | None, names: list[str]) -> None:
        """The folder's checks started; after a conversation's turn, that conversation's id."""
        with self._lock:
            self._pending_host_events.append(
                Event(
                    session_id="desktop",
                    type="checks.started",
                    data={"workspace": str(root), "checks": names, "sessionId": session_id},
                )
            )

    def _report_checks(self, root: Path, results: list[dict[str, object]]) -> None:
        """The coding desk's callback: a folder's results changed (from any conversation)."""
        with self._lock:
            self._pending_host_events.append(
                Event(
                    session_id="desktop",
                    type="checks.finished",
                    data={"workspace": str(root), "results": results},
                )
            )

    # -- after a turn

    def _note_user_turn(self, event: Event) -> None:
        """A message the user wrote starts the count of automatic fixes again."""
        text = event.data.get("text") or event.data.get("content")
        if isinstance(text, str) and text.startswith(CHECKS_MARKER):
            return
        self._check_fix_rounds.pop(event.session_id, None)

    def _after_turn_files(self, event: Event) -> None:
        """A conversation's turn changed files: run the folder's checks if it asks for that."""
        session = self._stored_session(event.session_id)
        if session is None:
            return
        root = Path(session.workspace)
        config = self._accepted_config(root)
        if config is None or not config.after_turn or not config.checks:
            return
        state = self._coding.state(root)
        if state.running:
            return
        state.running = True
        names = [check.name for check in config.checks]
        self._announce_checks(root, session.id, names)
        threading.Thread(
            target=self._run_checks_after_turn,
            args=(root, session.id, config),
            name="project-checks",
            daemon=True,
        ).start()

    def _run_checks_after_turn(self, root: Path, session_id: str, config: ProjectConfig) -> None:
        state = self._coding.state(root)
        try:
            results: list[CheckResult] = run_checks(root, config.checks)
        except Exception:
            _LOGGER.exception("project checks failed to run")
            state.running = False
            return
        state.running = False
        self._coding.record(root, results)
        if all(result.ok for result in results):
            self._check_fix_rounds.pop(session_id, None)
            return
        rounds = self._check_fix_rounds.get(session_id, 0)
        if rounds >= config.max_fix_rounds or self._closing:
            return
        self._check_fix_rounds[session_id] = rounds + 1
        session = self._stored_session(session_id)
        if session is None:
            return
        report = failure_report(results)
        if len(report) > _MAX_REPORT_CHARS:
            report = report[:_MAX_REPORT_CHARS] + "\n…"
        prompt = (
            f"{CHECKS_MARKER}\n"
            f"The project's checks failed after your changes (automatic fix {rounds + 1} of "
            f"{config.max_fix_rounds}).\n\n{report}\n\n"
            "Fix the code so these checks pass. Do not skip, weaken or delete the checks or "
            "their tests unless they are wrong; if they are, say why."
        )
        try:
            self._dispatch_prompt(f"checks-{uuid4()}", session, prompt)
        except GatewayError as error:
            _LOGGER.info("could not hand failed checks back: %s", error)


__all__ = ["CHECKS_MARKER", "PROJECT_COMMANDS", "PROJECT_LONG_COMMANDS", "ProjectCommands"]
