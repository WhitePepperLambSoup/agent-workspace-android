"""Install and describe the scientific Python environment: uv (pinned, checked) installs a managed
Python and NumPy, pandas, SciPy, Matplotlib, seaborn, statsmodels, scikit-learn and the figure
helpers into the app's data folder. Nothing goes on PATH or into the system Python; removing the
folder removes it all. Package and Python downloads use a mirror when the default is unreachable.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UV_VERSION = "0.13.0"
UV_WHEEL = (
    "packages/b2/00/73abae6cafcdb868d42b2c71bf12c9c2eb06a8d229a09569760c41b7948d/"
    "uv-0.13.0-py3-none-win_amd64.whl"
)
UV_SHA256 = "0367b4e0ae4dcef32da4aa2ad2f3853b6ad81d50c187abe50d343d892b8fea21"
# The same file path is served by PyPI and its mirrors.
FILE_HOSTS = (
    "https://files.pythonhosted.org/",
    "https://pypi.tuna.tsinghua.edu.cn/",
    "https://mirrors.aliyun.com/pypi/",
)
INDEXES = (
    "https://pypi.org/simple",
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
)
PYTHON_MIRROR = "https://registry.npmmirror.com/-/binary/python-build-standalone/"
PYTHON_RELEASES = "https://github.com/astral-sh/python-build-standalone/releases"
PYTHON_VERSION = "3.12"
PACKAGES = (
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "seaborn",
    "statsmodels",
    "scikit-learn",
    "openpyxl",
    "ipykernel",
    "nbformat",
    "nbclient",
)
CHECKED_IMPORTS = ("numpy", "pandas", "scipy", "matplotlib", "seaborn", "statsmodels", "sklearn")
STEP_SECONDS = 1800.0
_CREATE_NO_WINDOW = 0x08000000
_HELPERS = Path(__file__).resolve().parent / "aw_sciplot"
# Defaults Python sets at every start (site runs the lines of a .pth file that begin with
# "import"). The agent's commands run with a clean environment in a job that allows 1 GB a
# process: OpenBLAS, once in numpy and again in scipy, sets up buffers for every core and fails
# to import there ("Memory allocation still failed"); Matplotlib finds no home folder and
# builds its font cache again in a new temporary folder each time.
STARTUP_FILE = "aw_science_defaults.pth"
STARTUP = (
    "import os, sys; "
    "os.environ.setdefault('OPENBLAS_NUM_THREADS', '4'); "
    "os.environ.setdefault('MPLCONFIGDIR', os.path.join(sys.prefix, 'mplconfig'))\n"
)


class EnvError(Exception):
    """Why the environment could not be installed: ``unsupported``, ``download``, ``checksum``,
    ``python``, ``packages``, ``check``, ``cancelled``."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Layout:
    root: Path

    @property
    def uv(self) -> Path:
        return self.root / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")

    @property
    def pythons(self) -> Path:
        return self.root / "python"

    @property
    def env(self) -> Path:
        return self.root / "env"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def state(self) -> Path:
        return self.root / "state.json"

    @property
    def python(self) -> Path:
        if sys.platform == "win32":
            return self.env / "Scripts" / "python.exe"
        return self.env / "bin" / "python"

    @property
    def site_packages(self) -> Path:
        if sys.platform == "win32":
            return self.env / "Lib" / "site-packages"
        return next(iter((self.env / "lib").glob("python3*/site-packages")), self.env / "lib")


def layout(data_dir: Path) -> Layout:
    return Layout(data_dir / "science")


def status(data_dir: Path) -> dict[str, Any]:
    """Whether the environment is installed, its Python and the main packages' versions."""
    place = layout(data_dir)
    try:
        state = json.loads(place.state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    installed = place.python.is_file() and isinstance(state, dict) and bool(state.get("installed"))
    document: dict[str, Any] = {"installed": installed, "root": str(place.root)}
    if installed:
        document.update(
            {
                "python": str(place.python),
                "pythonVersion": state.get("python_version"),
                "packages": state.get("packages", {}),
                "index": state.get("index"),
                "installedAt": state.get("installed_at"),
            }
        )
    return document


def installable() -> bool:
    """The pinned uv is the 64-bit Windows build."""
    import platform

    return sys.platform == "win32" and platform.machine().lower() in {"amd64", "x86_64"}


Progress = Callable[[str, str], None]
Opener = Callable[[urllib.request.Request, float], Any]


def _open(request: urllib.request.Request, timeout: float) -> Any:
    # The system's proxy settings apply.
    return urllib.request.urlopen(request, timeout=timeout)


def _reachable(url: str, opener: Opener, timeout: float = 6.0) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "AgentWorkspace"}, method="GET")
    try:
        with opener(request, timeout) as response:
            response.read(512)
            return True
    except OSError:
        return False


def choose_index(opener: Opener = _open) -> str:
    """The first package index that answers (PyPI, then mirrors in China)."""
    for index in INDEXES:
        if _reachable(f"{index}/pip/", opener):
            return index
    raise EnvError("download", "no package index could be reached")


def _download_uv(place: Layout, cancel: threading.Event | None, opener: Opener) -> None:
    last_error = ""
    for host in FILE_HOSTS:
        if cancel is not None and cancel.is_set():
            raise EnvError("cancelled")
        request = urllib.request.Request(host + UV_WHEEL, headers={"User-Agent": "AgentWorkspace"})
        try:
            with opener(request, 60.0) as response:
                data = response.read(80 * 1024 * 1024)
        except OSError as error:
            last_error = str(error)
            continue
        if hashlib.sha256(data).hexdigest() != UV_SHA256:
            last_error = f"checksum mismatch from {host}"
            continue
        with zipfile.ZipFile(io.BytesIO(data)) as wheel:
            names = [name for name in wheel.namelist() if Path(name).name == place.uv.name]
            if len(names) != 1:
                raise EnvError("checksum", "the uv wheel has no uv program")
            program = wheel.read(names[0])
        place.uv.parent.mkdir(parents=True, exist_ok=True)
        temporary = place.uv.with_suffix(".part")
        temporary.write_bytes(program)
        os.replace(temporary, place.uv)
        return
    raise EnvError("download", last_error)


class _Steps:
    """Runs the installer's commands without a console window, stoppable."""

    def __init__(self, cancel: threading.Event | None, progress: Progress | None) -> None:
        self.cancel = cancel
        self.progress = progress

    def run(self, stage: str, command: list[str], env: dict[str, str]) -> str:
        flags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        lines: list[str] = []
        reader = threading.Thread(target=self._read, args=(process, stage, lines), daemon=True)
        reader.start()
        deadline = time.monotonic() + STEP_SECONDS
        while process.poll() is None:
            if (self.cancel is not None and self.cancel.is_set()) or time.monotonic() > deadline:
                _stop(process)
                reader.join(timeout=5)
                raise EnvError("cancelled" if self.cancel and self.cancel.is_set() else stage)
            time.sleep(0.1)
        reader.join(timeout=5)
        output = "".join(lines)
        if process.returncode != 0:
            raise EnvError(stage, output[-2000:])
        return output

    def _read(self, process: subprocess.Popen[bytes], stage: str, lines: list[str]) -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.decode("utf-8", errors="replace")
            lines.append(line)
            if self.progress is not None and line.strip():
                self.progress(stage, line.strip()[:200])


def _stop(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    else:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def helpers_digest() -> str:
    """What the shipped helpers are, to tell when the environment's copy is older."""
    digest = hashlib.sha256(STARTUP.encode())
    for path in sorted(_HELPERS.rglob("*.py")):
        digest.update(path.relative_to(_HELPERS).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def install_helpers(place: Layout) -> None:
    """Copy the figure helpers and the start-up defaults into the environment (again after an
    app update)."""
    (place.site_packages / STARTUP_FILE).write_text(STARTUP, encoding="utf-8")
    target = place.site_packages / "aw_sciplot"
    staging = target.with_name("aw_sciplot.new")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(_HELPERS, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (staging / ".digest").write_text(helpers_digest(), encoding="utf-8")
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)


def install(
    data_dir: Path,
    *,
    cancel: threading.Event | None = None,
    progress: Progress | None = None,
    opener: Opener = _open,
    packages: tuple[str, ...] = PACKAGES,
) -> dict[str, Any]:
    """Install (or repair) the environment; returns its status."""
    if not installable():
        raise EnvError("unsupported")
    place = layout(data_dir)
    place.root.mkdir(parents=True, exist_ok=True)
    steps = _Steps(cancel, progress)

    def tell(stage: str, detail: str = "") -> None:
        if progress is not None:
            progress(stage, detail)

    tell("uv")
    if not place.uv.is_file():
        _download_uv(place, cancel, opener)
    tell("mirror")
    index = choose_index(opener)
    env = dict(os.environ)
    env.update(
        {
            "UV_CACHE_DIR": str(place.cache),
            "UV_PYTHON_INSTALL_DIR": str(place.pythons),
            "UV_INDEX_URL": index,
            "UV_NO_PROGRESS": "1",
            "UV_PYTHON_PREFERENCE": "only-managed",
        }
    )
    if not _reachable(PYTHON_RELEASES, opener):
        env["UV_PYTHON_INSTALL_MIRROR"] = PYTHON_MIRROR
    uv = str(place.uv)
    tell("python")
    steps.run("python", [uv, "python", "install", PYTHON_VERSION], env)
    tell("venv")
    if not place.python.is_file():
        steps.run("python", [uv, "venv", str(place.env), "--python", PYTHON_VERSION], env)
    tell("packages")
    steps.run("packages", [uv, "pip", "install", "--python", str(place.python), *packages], env)
    tell("helpers")
    install_helpers(place)
    tell("check")
    probe = (
        "import importlib, json, platform\n"
        f"names = {list(CHECKED_IMPORTS)!r}\n"
        "versions = {name: getattr(importlib.import_module(name), '__version__', '')\n"
        "            for name in names}\n"
        "import aw_sciplot\n"
        "print(json.dumps({'python': platform.python_version(), 'packages': versions}))\n"
    )
    output = steps.run("check", [str(place.python), "-c", probe], env)
    try:
        found = json.loads(output.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise EnvError("check", output[-2000:]) from None
    lock = steps.run("packages", [uv, "pip", "freeze", "--python", str(place.python)], env)
    (place.root / "requirements.lock.txt").write_text(lock, encoding="utf-8")
    state = {
        "installed": True,
        "python_version": found.get("python"),
        "packages": found.get("packages", {}),
        "index": index,
        "uv": UV_VERSION,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    place.state.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return status(data_dir)


def remove(data_dir: Path) -> None:
    """Delete the environment, the managed Python and the download cache."""
    shutil.rmtree(layout(data_dir).root, ignore_errors=True)


def refresh_helpers(data_dir: Path) -> None:
    """After an app update the environment gets the helpers this version ships."""
    place = layout(data_dir)
    if not status(data_dir)["installed"]:
        return
    try:
        current = (place.site_packages / "aw_sciplot" / ".digest").read_text(encoding="utf-8")
    except OSError:
        current = ""
    if current != helpers_digest():
        install_helpers(place)
