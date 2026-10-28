"""What the science commands keep between calls: the running install or correction and how far it
got (the window polls the status while it runs)."""

from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path
from typing import Any

from agent_workspace.science import env

SCIENCE_PYTHON_VARIABLE = "AGENT_WORKSPACE_SCIENCE_PYTHON"


def refresh_science_helpers(data_dir: Path) -> None:
    """After an app update, the installed environment gets this version's figure helpers."""
    # On failure the environment still works with the helpers it has.
    with contextlib.suppress(OSError):
        env.refresh_helpers(data_dir)


class ScienceBusy(Exception):
    """An install or a correction is already running."""


class ScienceDesk:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.lock = threading.Lock()
        self.job: str | None = None
        self.cancel: threading.Event | None = None
        self.stage = ""
        self.detail = ""
        self.started = 0.0
        self.error: dict[str, str] | None = None

    def start(self, job: str) -> threading.Event:
        with self.lock:
            if self.job is not None:
                raise ScienceBusy(self.job)
            self.job = job
            self.cancel = threading.Event()
            self.stage, self.detail, self.error = "", "", None
            self.started = time.monotonic()
            return self.cancel

    def progress(self, stage: str, detail: str) -> None:
        with self.lock:
            self.stage, self.detail = stage, detail

    def finish(self, error: dict[str, str] | None = None) -> None:
        with self.lock:
            self.job = None
            self.cancel = None
            self.error = error

    def running(self) -> dict[str, Any] | None:
        with self.lock:
            if self.job is None:
                return None
            return {
                "job": self.job,
                "stage": self.stage,
                "detail": self.detail,
                "seconds": round(time.monotonic() - self.started, 1),
            }

    def publish_python(self) -> str | None:
        """Tell the agent's tools where the environment's Python is (or that there is none)."""
        state = env.status(self.data_dir)
        python = state.get("python") if state.get("installed") else None
        if python:
            os.environ[SCIENCE_PYTHON_VARIABLE] = str(python)
        else:
            os.environ.pop(SCIENCE_PYTHON_VARIABLE, None)
        return str(python) if python else None
