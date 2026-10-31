"""The scientific Python environment (install, status, remove) and the figure point editor: read a
saved figure's point map, and write dragged points into a corrected copy of its data, then draw
the figure again from it."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from agent_workspace.science import env
from agent_workspace.science.remote import find_program, ssh_config_hosts
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import _LOGGER, GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope
from agent_workspace.ui_gateway.science_desk import ScienceBusy

SCIENCE_COMMANDS = frozenset(
    {
        "science.status",
        "science.install",
        "science.cancel",
        "science.remove",
        "science.servers",
        "figures.points",
        "figures.correct",
    }
)
SCIENCE_LONG_COMMANDS = frozenset({"science.install", "figures.correct"})
_MAX_POINTS_BYTES = 900 * 1024
_MAX_EDITS = 5000
_RERUN_SECONDS = 300.0
_CREATE_NO_WINDOW = 0x08000000


def points_file(image: Path) -> Path:
    if image.name.endswith(".points.json"):
        return image
    return image.with_name(f"{image.stem}.points.json")


class ScienceCommands(GatewayState):
    """The scientific environment's and the figure point editor's commands."""

    def _science_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        handler = {
            "science.status": self._science_status,
            "science.install": self._science_install,
            "science.cancel": self._science_cancel,
            "science.remove": self._science_remove,
            "science.servers": self._science_servers,
            "figures.points": self._figure_points,
            "figures.correct": self._figure_correct,
        }[command.type]
        return self._reply(f"{command.type}.result", handler(command), session_id=None)

    def _system_note(self) -> str:
        """What every turn's system prompt adds on the desktop: the skills, and the scientific
        environment when there is one."""
        sections = [self._skills.catalog_block()]
        state = env.status(self._science.data_dir)
        if state.get("installed"):
            sections.append(
                "# Scientific Python\n"
                f"A scientific Python environment is installed: {state['python']} (Python "
                f"{state.get('pythonVersion') or '3'}; numpy, pandas, scipy, matplotlib, seaborn, "
                "statsmodels, scikit-learn, nbformat, nbclient). discover_executables lists it as "
                "science_python. For analysis and figures, write the script into the folder (for "
                "example analysis/plot_growth.py) and run it with this interpreter. Its aw_sciplot "
                "module (import aw_sciplot as sp): sp.read(path) reads CSV, Excel or JSON; "
                "sp.figure(style, journal='nature') and sp.panels('2x2', journal=...) make "
                "journal-sized figures; sp.save(fig, 'figures/name') writes PNG, PDF and SVG and "
                "name.points.json, with which the user can drag points to correct the data in the "
                "app (read data with sp.read so the figure is redrawn from the corrected copy); "
                "sp.compare, sp.annotate_pairs and sp.fit_line add statistics; sp.templates has "
                "volcano, kaplan_meier, pca, clustermap, dose_response, correlation and "
                "bar_points; sp.check('figures/name', 'nature') checks a journal's rules. Link a "
                "figure in the answer as [name](figures/name.png). When the user wants a notebook, "
                "build the .ipynb with nbformat and run it with nbclient so it keeps its outputs; "
                "the app shows notebooks with their outputs."
            )
        return "\n\n".join(section for section in sections if section)

    def _science_start(self, job: str) -> threading.Event:
        try:
            return self._science.start(job)
        except ScienceBusy:
            raise GatewayError("science_busy") from None

    def stop_science(self) -> None:
        with self._science.lock:
            if self._science.cancel is not None:
                self._science.cancel.set()

    def _science_status_document(self) -> dict[str, object]:
        desk = self._science
        document: dict[str, object] = {
            **env.status(desk.data_dir),
            "installable": env.installable(),
            "packages_planned": list(env.PACKAGES),
            "running": desk.running(),
        }
        with desk.lock:
            if desk.error:
                document["error"] = desk.error
        return document

    def _science_status(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        return self._science_status_document()

    def _science_install(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        desk = self._science
        cancel = self._science_start("install")
        error: dict[str, str] | None = None
        try:
            env.install(desk.data_dir, cancel=cancel, progress=desk.progress)
        except env.EnvError as failure:
            _LOGGER.warning(
                "science environment install failed: %s %s", failure.code, failure.detail[-500:]
            )
            error = {"code": failure.code, "detail": failure.detail[-1500:]}
        except OSError as failure:
            error = {"code": "storage", "detail": str(failure)[-500:]}
        finally:
            desk.finish(error)
        desk.publish_python()
        if error is not None:
            raise GatewayError(f"science_{error['code']}")
        return self._science_status_document()

    def _science_servers(self, command: CommandEnvelope) -> dict[str, object]:
        """The servers of ~/.ssh/config, by name and address, for the server room; nothing is
        connected to."""
        self._require_payload(command, set())
        hosts = []
        for host in ssh_config_hosts(self._ssh_config):
            item = {"name": host["name"]}
            if host.get("hostname"):
                item["hostname"] = host["hostname"]
            hosts.append(item)
        return {"hosts": hosts, "ssh": bool(find_program("ssh"))}

    @property
    def _ssh_config(self) -> Path:
        return Path.home() / ".ssh" / "config"

    def _science_cancel(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        with self._science.lock:
            cancel = self._science.cancel
        if cancel is not None:
            cancel.set()
        return {"cancelled": cancel is not None}

    def _science_remove(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        cancel = self._science_start("remove")
        try:
            env.remove(self._science.data_dir)
        finally:
            self._science.finish()
            del cancel
        self._science.publish_python()
        return self._science_status_document()

    def _science_paths(self) -> WorkspacePaths:
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        return WorkspacePaths(workspace)

    def _figure_points_path(self, paths: WorkspacePaths, raw: object) -> Path:
        if not isinstance(raw, str) or not raw.strip() or len(raw) > 4096:
            raise GatewayError("invalid_path")
        try:
            target = points_file(paths.resolve(raw.strip()))
        except (OSError, ToolError, ValueError):
            raise GatewayError("invalid_path") from None
        return target

    def _figure_points(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"path"})
        paths = self._science_paths()
        target = self._figure_points_path(paths, command.payload["path"])
        if not target.is_file():
            return {"available": False}
        if target.stat().st_size > _MAX_POINTS_BYTES:
            return {"available": False, "reason": "too_large"}
        try:
            document = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"available": False, "reason": "unreadable"}
        if not isinstance(document, dict) or not isinstance(document.get("sets"), list):
            return {"available": False, "reason": "unreadable"}
        image = target.with_name(str(document.get("image") or ""))
        script = document.get("script")
        return {
            "available": True,
            "points": paths.relative(target),
            "image": paths.relative(image) if image.is_file() else None,
            "axes": document.get("axes", []),
            "sets": document["sets"],
            "data": document.get("data"),
            "script": _inside(paths, script),
            "columns": document.get("columns", []),
            "unmatched": document.get("unmatched", 0),
            "environment": bool(env.status(self._science.data_dir)["installed"]),
        }

    def _figure_correct(self, command: CommandEnvelope) -> dict[str, object]:
        """Write the dragged points into a corrected copy of the data; draw the figure again."""
        self._require_payload(command, {"path", "edits"}, optional={"note", "rerun"})
        payload = command.payload
        edits, note = payload["edits"], payload.get("note", "")
        if (
            not isinstance(edits, list)
            or not 1 <= len(edits) <= _MAX_EDITS
            or not isinstance(note, str)
        ):
            raise GatewayError("invalid_payload")
        paths = self._science_paths()
        target = self._figure_points_path(paths, payload["path"])
        if not target.is_file():
            raise GatewayError("file_not_found")
        status = env.status(self._science.data_dir)
        if not status["installed"]:
            raise GatewayError("science_missing")
        python = str(status["python"])
        cancel = self._science_start("correct")
        try:
            return self._correct(
                paths,
                target,
                python,
                edits,
                note[:300],
                payload.get("rerun", True) is not False,
                cancel,
            )
        finally:
            self._science.finish()

    def _correct(
        self,
        paths: WorkspacePaths,
        target: Path,
        python: str,
        edits: list[Any],
        note: str,
        rerun: bool,
        cancel: threading.Event,
    ) -> dict[str, object]:
        document = json.loads(target.read_text(encoding="utf-8"))
        cwd = Path(str(document.get("cwd") or paths.root))
        if _inside(paths, str(cwd)) is None:
            cwd = paths.root
        with tempfile.TemporaryDirectory(prefix="aw-edits-") as scratch:
            edits_file = Path(scratch) / "edits.json"
            edits_file.write_text(json.dumps(edits), encoding="utf-8")
            code, output = _run(
                [
                    python,
                    "-m",
                    "aw_sciplot.correct",
                    "--points",
                    str(target),
                    "--edits",
                    str(edits_file),
                    "--note",
                    note,
                ],
                cwd,
                dict(os.environ),
                60.0,
                cancel,
            )
        try:
            summary = json.loads(output.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise GatewayError("figures_correct_failed") from None
        if code != 0 or "error" in summary:
            return {"ok": False, "error": str(summary.get("error", output[-500:]))}
        for key in ("corrected", "log"):
            if _inside(paths, summary.get(key)) is None:
                raise GatewayError("figures_correct_failed")
        result: dict[str, object] = {
            "ok": True,
            "corrected": _inside(paths, summary["corrected"]),
            "log": _inside(paths, summary["log"]),
            "changed": len(summary.get("changed", [])),
        }
        script = _inside(paths, document.get("script"))
        if rerun and script is not None:
            run_env = dict(os.environ)
            run_env["AW_SCIPLOT_DATA"] = json.dumps(summary.get("override", {}))
            run_env["MPLBACKEND"] = "Agg"
            run_code, run_output = _run(
                [python, str(paths.resolve(script))], cwd, run_env, _RERUN_SECONDS, cancel
            )
            result["rerun"] = {"script": script, "ok": run_code == 0, "output": run_output[-3000:]}
        return result


def _inside(paths: WorkspacePaths, value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return paths.relative(Path(value))
    except (OSError, ToolError, ValueError):
        return None


def _run(
    command: list[str],
    cwd: Path,
    environment: dict[str, str],
    seconds: float,
    cancel: threading.Event,
) -> tuple[int, str]:
    """Run the environment's Python without a console window; stopped on cancel or timeout."""
    flags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
    environment["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        if cancel.is_set() and process.returncode is None:
            process.kill()
        output.seek(0)
        text = output.read().decode("utf-8", errors="replace")
    return process.returncode if process.returncode is not None else -1, text
