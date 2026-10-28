"""What the LaTeX editor's commands keep between calls: the settings file and the running job."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from agent_workspace.latex import compile as latex_compile
from agent_workspace.latex import rules


class LatexBusy(Exception):
    """A compile or an install is already running."""


class LatexDesk:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.settings_path = data_dir / "latex.json"
        self.lock = threading.Lock()
        self.cancel: threading.Event | None = None
        self.job: str | None = None

    def settings(self) -> dict[str, Any]:
        try:
            stored = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = {}
        stored = stored if isinstance(stored, dict) else {}
        engine = stored.get("engine")
        toggles = stored.get("rules")
        toggles = toggles if isinstance(toggles, dict) else {}
        return {
            "engine": engine if engine in latex_compile.ENGINES else "auto",
            "autoCompile": stored.get("autoCompile") is True,
            "rules": {
                rule: toggles[rule] if isinstance(toggles.get(rule), bool) else info.default_enabled
                for rule, info in rules.RULES.items()
            },
        }

    def save(self, settings: dict[str, Any]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".latex-", dir=self.data_dir)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({"version": 1, **settings}, stream)
            os.replace(temporary, self.settings_path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def start(self, job: str) -> threading.Event:
        with self.lock:
            if self.job is not None:
                raise LatexBusy(self.job)
            self.job = job
            self.cancel = threading.Event()
            return self.cancel

    def finish(self) -> None:
        with self.lock:
            self.job = None
            self.cancel = None
