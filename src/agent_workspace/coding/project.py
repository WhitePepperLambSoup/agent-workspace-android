"""A folder's checks and rules, kept in ``.agent/project.json`` so a team shares them.

Checks are the commands that tell whether the code is right (tests, type check, lint); they can
run after each turn that changed files, and their failures go back to the agent. Rules hold the
agent to the project: folders it must not write, formatters run on the files it writes, and no
secrets in commits.

Commands in the file run only once the user has accepted that file's contents in this app (a
cloned project cannot make the app run its commands); rules that only forbid apply always.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_FILE = PurePosixPath(".agent/project.json")
_MAX_FILE_BYTES = 256 * 1024
_MAX_CHECKS = 12
_MAX_RULES = 40
_MAX_COMMAND = 2000
_DEFAULT_TIMEOUT = 600
_MAX_TIMEOUT = 3600
_TAIL_CHARS = 6000
_CREATE_NO_WINDOW = 0x08000000


class ProjectConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    command: str
    timeout: int = _DEFAULT_TIMEOUT

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "command": self.command, "timeout": self.timeout}


@dataclass(frozen=True, slots=True)
class Formatter:
    files: str  # a glob: *.py, src/**/*.ts
    command: str  # {file} is the file's path relative to the folder

    def to_dict(self) -> dict[str, object]:
        return {"files": self.files, "command": self.command}


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    checks: tuple[Check, ...] = ()
    after_turn: bool = False
    max_fix_rounds: int = 2
    protected: tuple[str, ...] = ()
    formatters: tuple[Formatter, ...] = ()
    secret_scan: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "checks": [check.to_dict() for check in self.checks],
            "afterTurn": self.after_turn,
            "maxFixRounds": self.max_fix_rounds,
            "rules": {
                "protected": list(self.protected),
                "format": [formatter.to_dict() for formatter in self.formatters],
                "secretScan": self.secret_scan,
            },
        }

    def digest(self) -> str:
        """What the user accepts: everything that makes the app run a command."""
        runs = {
            "checks": [check.to_dict() for check in self.checks],
            "format": [formatter.to_dict() for formatter in self.formatters],
        }
        text = json.dumps(runs, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @property
    def runs_commands(self) -> bool:
        return bool(self.checks or self.formatters)


def _text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ProjectConfigError(f"{label} must be text of at most {limit} characters")
    return value.strip()


def parse_config(document: object) -> ProjectConfig:
    if not isinstance(document, dict):
        raise ProjectConfigError("the project settings must be an object")
    checks: list[Check] = []
    raw_checks = document.get("checks", [])
    if not isinstance(raw_checks, list) or len(raw_checks) > _MAX_CHECKS:
        raise ProjectConfigError(f"checks must be a list of at most {_MAX_CHECKS}")
    for raw in raw_checks:
        if not isinstance(raw, dict):
            raise ProjectConfigError("each check needs a name and a command")
        timeout = raw.get("timeout", _DEFAULT_TIMEOUT)
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or not 5 <= timeout <= _MAX_TIMEOUT
        ):
            raise ProjectConfigError(f"a check's timeout is 5 to {_MAX_TIMEOUT} seconds")
        checks.append(
            Check(
                _text(raw.get("name"), "a check's name", 60),
                _text(raw.get("command"), "a check's command", _MAX_COMMAND),
                timeout,
            )
        )
    if len({check.name for check in checks}) != len(checks):
        raise ProjectConfigError("two checks have the same name")
    rules = document.get("rules", {})
    if not isinstance(rules, dict):
        raise ProjectConfigError("rules must be an object")
    protected = rules.get("protected", [])
    if not isinstance(protected, list) or len(protected) > _MAX_RULES:
        raise ProjectConfigError(f"protected must be a list of at most {_MAX_RULES} patterns")
    formatters: list[Formatter] = []
    raw_formatters = rules.get("format", [])
    if not isinstance(raw_formatters, list) or len(raw_formatters) > _MAX_RULES:
        raise ProjectConfigError(f"format must be a list of at most {_MAX_RULES}")
    for raw in raw_formatters:
        if not isinstance(raw, dict):
            raise ProjectConfigError("each formatter needs files and a command")
        formatters.append(
            Formatter(
                _text(raw.get("files"), "a formatter's files", 200),
                _text(raw.get("command"), "a formatter's command", _MAX_COMMAND),
            )
        )
    rounds = document.get("maxFixRounds", 2)
    if not isinstance(rounds, int) or isinstance(rounds, bool) or not 0 <= rounds <= 5:
        raise ProjectConfigError("maxFixRounds is 0 to 5")
    return ProjectConfig(
        checks=tuple(checks),
        after_turn=document.get("afterTurn") is True,
        max_fix_rounds=rounds,
        protected=tuple(_text(item, "a protected pattern", 200) for item in protected),
        formatters=tuple(formatters),
        secret_scan=rules.get("secretScan", True) is not False,
    )


def config_path(root: Path) -> Path:
    return root.joinpath(*PROJECT_FILE.parts)


def load_config(root: Path) -> ProjectConfig | None:
    """The folder's settings; None when it has none. A broken file raises."""
    path = config_path(root)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ProjectConfigError(f"cannot read {PROJECT_FILE}: {error}") from None
    if len(data) > _MAX_FILE_BYTES:
        raise ProjectConfigError(f"{PROJECT_FILE} is too large")
    try:
        document = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProjectConfigError(f"{PROJECT_FILE} is not valid JSON: {error}") from None
    return parse_config(document)


def save_config(root: Path, config: ProjectConfig) -> None:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


class TrustBook:
    """Which folders' commands the user accepted, by the digest of what was accepted."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict[str, str]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {
            key: value
            for key, value in (document.items() if isinstance(document, dict) else ())
            if isinstance(key, str) and isinstance(value, str)
        }

    @staticmethod
    def _key(root: Path) -> str:
        text = os.path.normcase(str(root.resolve()))
        return text

    def trusted(self, root: Path, config: ProjectConfig) -> bool:
        if not config.runs_commands:
            return True
        with self._lock:
            return self._read().get(self._key(root)) == config.digest()

    def trust(self, root: Path, config: ProjectConfig) -> None:
        with self._lock:
            book = self._read()
            book[self._key(root)] = config.digest()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.tmp")
            temporary.write_text(json.dumps(book, indent=1), encoding="utf-8")
            os.replace(temporary, self.path)


# -- what a folder's own files suggest ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Suggestion:
    name: str
    command: str
    source: str

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "command": self.command, "source": self.source}


_SCRIPT_NAMES = (
    ("test", "test"),
    ("typecheck", "types"),
    ("type-check", "types"),
    ("check-types", "types"),
    ("lint", "lint"),
    ("check", "check"),
)


def _python_command(root: Path) -> str:
    for relative in (".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe"):
        if (root / relative).is_file():
            return relative.replace("/", "\\") if sys.platform == "win32" else relative
    return "python"


def detect_checks(root: Path) -> list[Suggestion]:
    found: list[Suggestion] = []

    def add(name: str, command: str, source: str) -> None:
        if all(item.command != command for item in found) and all(
            item.name != name for item in found
        ):
            found.append(Suggestion(name, command, source))

    package = root / "package.json"
    if package.is_file():
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
        except (OSError, ValueError, AttributeError):
            scripts = {}
        runner = (
            "pnpm"
            if (root / "pnpm-lock.yaml").is_file()
            else "yarn"
            if (root / "yarn.lock").is_file()
            else "npm"
        )
        for script, name in _SCRIPT_NAMES:
            if isinstance(scripts, dict) and isinstance(scripts.get(script), str):
                command = (
                    f"{runner} test"
                    if script == "test" and runner == "npm"
                    else f"{runner} run {script}"
                )
                add(name, command, "package.json")
        if (root / "tsconfig.json").is_file() and not any(item.name == "types" for item in found):
            add("types", "npx tsc --noEmit", "tsconfig.json")
    pyproject: dict[str, Any] = {}
    if (root / "pyproject.toml").is_file():
        try:
            pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            pyproject = {}
    tool = pyproject.get("tool", {}) if isinstance(pyproject.get("tool"), dict) else {}
    python = _python_command(root)
    tests = root / "tests"
    if (
        "pytest" in tool
        or (root / "pytest.ini").is_file()
        or (root / "conftest.py").is_file()
        or (tests.is_dir() and next(tests.glob("test_*.py"), None) is not None)
    ):
        add("test", f"{python} -m pytest -q", "pyproject.toml" if "pytest" in tool else "tests/")
    if "ruff" in tool or (root / "ruff.toml").is_file():
        add("lint", f"{python} -m ruff check .", "ruff")
    if "mypy" in tool or (root / "mypy.ini").is_file():
        add("types", f"{python} -m mypy .", "mypy")
    if (root / "Cargo.toml").is_file():
        add("check", "cargo check --quiet", "Cargo.toml")
        add("test", "cargo test --quiet", "Cargo.toml")
    if (root / "go.mod").is_file():
        add("vet", "go vet ./...", "go.mod")
        add("test", "go test ./...", "go.mod")
    makefile = root / "Makefile"
    if makefile.is_file():
        try:
            targets = set(
                re.findall(
                    r"^([A-Za-z][\w-]*):",
                    makefile.read_text(encoding="utf-8", errors="replace"),
                    re.M,
                )
            )
        except OSError:
            targets = set()
        for target in ("test", "lint", "check"):
            if target in targets:
                add(target, f"make {target}", "Makefile")
    return found[:_MAX_CHECKS]


# -- running checks -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    command: str
    ok: bool
    exit_code: int | None
    seconds: float
    output: str  # the end of what it printed
    timed_out: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "ok": self.ok,
            "exitCode": self.exit_code,
            "seconds": round(self.seconds, 1),
            "output": self.output,
            "timedOut": self.timed_out,
        }


def _tail(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    if len(text) <= _TAIL_CHARS:
        return text
    return "…\n" + text[-_TAIL_CHARS:]


def run_check(root: Path, check: Check, *, cancel: threading.Event | None = None) -> CheckResult:
    started = time.monotonic()
    environment = {**os.environ, "CI": "1", "FORCE_COLOR": "0", "NO_COLOR": "1"}
    try:
        process = subprocess.Popen(
            check.command,
            shell=True,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except OSError as error:
        return CheckResult(check.name, check.command, False, None, 0.0, f"could not start: {error}")
    output: list[bytes] = []
    reader = threading.Thread(
        target=lambda: output.append(process.stdout.read() if process.stdout else b""),
        daemon=True,
    )
    reader.start()
    timed_out = False
    deadline = started + check.timeout
    while process.poll() is None:
        if time.monotonic() > deadline or (cancel is not None and cancel.is_set()):
            timed_out = time.monotonic() > deadline
            _kill_tree(process)
            break
        time.sleep(0.1)
    reader.join(5)
    exit_code = process.poll()
    seconds = time.monotonic() - started
    text = _tail(b"".join(output))
    if timed_out:
        text += f"\n[stopped after {check.timeout} s]"
    return CheckResult(
        check.name,
        check.command,
        exit_code == 0 and not timed_out,
        exit_code,
        seconds,
        text,
        timed_out,
    )


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    else:
        process.kill()
    try:
        process.wait(5)
    except subprocess.TimeoutExpired:
        process.kill()


def run_checks(
    root: Path, checks: Iterable[Check], *, cancel: threading.Event | None = None
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        if cancel is not None and cancel.is_set():
            break
        results.append(run_check(root, check, cancel=cancel))
    return results


def failure_report(results: Iterable[CheckResult]) -> str:
    """What goes back to the agent when checks fail."""
    parts: list[str] = []
    for result in results:
        if result.ok:
            continue
        state = "timed out" if result.timed_out else f"exit code {result.exit_code}"
        parts.append(
            f"## {result.name}: `{result.command}` ({state})\n```\n{result.output.strip()}\n```"
        )
    return "\n\n".join(parts)


# -- rules --------------------------------------------------------------------------------------


def _relative(root: Path, value: str) -> str | None:
    try:
        path = (root / value).resolve()
        return path.relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def matches(relative: str, pattern: str) -> bool:
    """A glob against a folder-relative path. Without a slash it is any part of the path
    (``*.lock``, ``.env*``, ``migrations``); with one, the path from the folder or a folder
    above the file (``src/generated``, ``src/**/*.ts``)."""
    pattern = pattern.strip().replace("\\", "/").removeprefix("./").rstrip("/")
    if not pattern:
        return False
    path = PurePosixPath(relative)
    if "/" not in pattern:
        return any(fnmatch.fnmatchcase(part, pattern) for part in path.parts)
    pattern = pattern.removesuffix("/**")
    candidates = [relative, *(str(parent) for parent in path.parents if str(parent) != ".")]
    variants = {pattern, pattern.replace("/**/", "/")}
    return any(
        fnmatch.fnmatchcase(candidate, item) for candidate in candidates for item in variants
    )


def protected_reason(root: Path, config: ProjectConfig, values: Iterable[object]) -> str | None:
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        relative = _relative(root, value)
        if relative is None:
            continue
        for pattern in config.protected:
            if matches(relative, pattern):
                return (
                    f"{relative} is protected by the project's rules ({pattern}); leave it as it is"
                )
    return None


_SECRETS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("API key", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
)


def scan_secrets(diff: str) -> list[str]:
    """Secrets in the added lines of a diff: ``path: kind`` for each."""
    found: list[str] = []
    current = "?"
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/").strip()
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for kind, pattern in _SECRETS:
            if pattern.search(line):
                entry = f"{current}: {kind}"
                if entry not in found:
                    found.append(entry)
    return found


def staged_diff(root: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "--no-color", "--unified=0"],
        cwd=root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
        creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        check=False,
    )
    return result.stdout.decode("utf-8", errors="replace")


@dataclass(slots=True)
class FormatOutcome:
    command: str
    ok: bool
    changed: bool
    output: str = ""


def format_file(root: Path, config: ProjectConfig, relative: str) -> FormatOutcome | None:
    formatter = next((item for item in config.formatters if matches(relative, item.files)), None)
    if formatter is None:
        return None
    path = root / relative
    try:
        before = path.read_bytes()
    except OSError:
        return None
    quoted = (
        f'"{relative}"' if sys.platform == "win32" else "'" + relative.replace("'", "'\\''") + "'"
    )
    command = formatter.command.replace("{file}", quoted)
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
            creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return FormatOutcome(command, False, False, str(error))
    try:
        changed = path.read_bytes() != before
    except OSError:
        changed = False
    output = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")[-800:]
    return FormatOutcome(command, completed.returncode == 0, changed, output)


@dataclass
class ProjectState:
    """The latest check results of a folder, for the window."""

    results: list[dict[str, object]] = field(default_factory=list)
    finished_at: float | None = None
    running: bool = False


__all__ = [
    "PROJECT_FILE",
    "Check",
    "CheckResult",
    "FormatOutcome",
    "Formatter",
    "ProjectConfig",
    "ProjectConfigError",
    "ProjectState",
    "Suggestion",
    "TrustBook",
    "config_path",
    "detect_checks",
    "failure_report",
    "format_file",
    "load_config",
    "matches",
    "parse_config",
    "protected_reason",
    "run_check",
    "run_checks",
    "save_config",
    "scan_secrets",
    "staged_diff",
]
