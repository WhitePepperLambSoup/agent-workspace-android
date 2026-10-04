"""End-to-end acceptance scenarios with clean restart semantics.

The regular benchmark and eval runners are useful for checking a model's
tool calls, but they intentionally keep the setup small.  This module adds a
thin acceptance layer for workflows whose result is a file (a PDF, paper
download, plot, source tree, or collaboration report).  Every retry receives
an entirely new workspace and provider instance.  A run that emits a
truncation/interruption event is never accepted, even when the agent manages
to recover and eventually emits a final answer; this makes the harness useful
for catching the "looks complete but was cut off" failure mode.

The runner is deliberately provider-agnostic at its boundary.  The built-in
adapter uses :class:`~agent_workspace.core.evals.ScriptedEvalProvider`, while
callers can construct the same :class:`AcceptanceScenario` around a live
provider by supplying a factory that returns a provider for each attempt.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from pypdf import PdfReader

from agent_workspace.core.evals import (
    EvalOutcome,
    EvalScenario,
    EvalTurn,
    ScriptedEvalProvider,
    run_scenario,
)
from agent_workspace.core.models import Autonomy
from agent_workspace.storage import SQLiteEventStore
from agent_workspace.tools.paths import StrPath


class AcceptanceCategory(StrEnum):
    """The user-visible workflow represented by an acceptance scenario."""

    FILE_GENERATION = "file_generation"
    PAPER_DOWNLOAD = "paper_download"
    NETWORK_DOWNLOAD = "network_download"
    SCIENTIFIC_PLOT = "scientific_plot"
    PROGRAMMING = "programming"
    MULTI_AGENT = "multi_agent"


class ArtifactKind(StrEnum):
    """Built-in artifact signatures understood by the acceptance checker."""

    FILE = "file"
    TEXT = "text"
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    DIRECTORY = "directory"


_SAFE_SCENARIO_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,95}\Z")
_INCOMPLETE_EVENTS = frozenset(
    {
        "turn.failed",
        "turn.cancelled",
        "model.stream.interrupted",
        "model.output.limited",
        "runtime.display_truncated",
        "tool.unknown",
    }
)
_MAX_ARTIFACT_READ_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArtifactRequirement:
    """A bounded assertion about a file or directory produced by a run."""

    path: str
    kind: ArtifactKind = ArtifactKind.FILE
    min_bytes: int = 1
    required_text: tuple[str, ...] = ()
    sha256: str | None = None
    provenance_of: str | None = None

    def __post_init__(self) -> None:
        relative = Path(self.path)
        if (
            not self.path
            or relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ValueError("artifact path must be relative to the scenario workspace")
        if type(self.min_bytes) is not int or self.min_bytes < 0:
            raise ValueError("artifact min_bytes must be a non-negative integer")
        if any(not isinstance(marker, str) or not marker for marker in self.required_text):
            raise ValueError("artifact required_text must contain non-empty strings")
        if self.sha256 is not None:
            normalized = self.sha256.casefold()
            if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
                raise ValueError("artifact sha256 must be a 64-character hexadecimal digest")
            object.__setattr__(self, "sha256", normalized)
        if self.provenance_of is not None:
            source = Path(self.provenance_of)
            if (
                not self.provenance_of
                or source.is_absolute()
                or any(part in {"", ".", ".."} for part in source.parts)
            ):
                raise ValueError("provenance source path must be relative to the workspace")


@dataclass(frozen=True, slots=True)
class AcceptanceScenario:
    """An eval scenario plus the durable artifacts it must produce."""

    id: str
    name: str
    category: AcceptanceCategory
    eval: EvalScenario
    artifacts: tuple[ArtifactRequirement, ...] = ()
    seed_files: tuple[tuple[str, str], ...] = ()
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if _SAFE_SCENARIO_ID.fullmatch(self.id) is None:
            raise ValueError("acceptance scenario id must be lowercase kebab/snake case")
        if not self.name.strip():
            raise ValueError("acceptance scenario name may not be empty")
        if self.eval.id != self.id:
            raise ValueError("acceptance scenario id must match its eval scenario id")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 20:
            raise ValueError("acceptance max_attempts must be from 1 to 20")
        for relative_path, _content in self.seed_files:
            ArtifactRequirement(relative_path, min_bytes=0)


@dataclass(frozen=True, slots=True)
class AcceptanceRepairContext:
    """Information passed to a caller's repair hook before a clean retry."""

    scenario: AcceptanceScenario
    attempt: int
    workspace: Path
    next_workspace: Path
    outcome: EvalOutcome
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcceptanceAttempt:
    """One isolated attempt, retained as evidence for debugging."""

    attempt: int
    workspace: Path
    outcome: EvalOutcome
    failures: tuple[str, ...]
    incomplete: bool


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    """Aggregated result of attempts for one acceptance scenario."""

    scenario_id: str
    passed: bool
    attempts: tuple[AcceptanceAttempt, ...]

    @property
    def final_workspace(self) -> Path | None:
        """Return the workspace of the last attempt, if any."""

        return self.attempts[-1].workspace if self.attempts else None

    @property
    def failures(self) -> tuple[str, ...]:
        """Return failures from the final attempt for concise reporting."""

        return self.attempts[-1].failures if self.attempts else ("no attempts ran",)


RepairHook = Callable[[AcceptanceRepairContext], Awaitable[None] | None]
AttemptSetup = Callable[[AcceptanceScenario, int, Path], Awaitable[None] | None]
ProviderFactory = Callable[[int], ScriptedEvalProvider]


async def run_acceptance_scenario(
    scenario: AcceptanceScenario,
    provider_factory: ProviderFactory,
    workspace_root: StrPath,
    *,
    repair: RepairHook | None = None,
    setup: AttemptSetup | None = None,
) -> AcceptanceResult:
    """Run a scenario until it passes or its bounded retries are exhausted.

    A fresh child directory and a fresh SQLite store are created for every
    attempt.  The previous workspace is never reused as input to the next
    attempt.  ``repair`` runs *after* a failed attempt and before the next one;
    it is intended for restarting a sidecar, refreshing a sandbox, or fixing
    an external dependency.  It cannot turn a partial attempt into a passing
    result, because artifact checks always run against the new workspace.
    """

    root = Path(workspace_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError(f"acceptance workspace root is not a directory: {root}")

    attempts: list[AcceptanceAttempt] = []
    for attempt_number in range(1, scenario.max_attempts + 1):
        attempt_workspace = root / f"{scenario.id}.attempt-{attempt_number:02d}"
        _prepare_fresh_workspace(attempt_workspace)
        _seed_files(attempt_workspace, scenario.seed_files)
        if setup is not None:
            setup_result = setup(scenario, attempt_number, attempt_workspace)
            if asyncio.iscoroutine(setup_result) or isinstance(setup_result, Awaitable):
                await setup_result
        provider = provider_factory(attempt_number)
        database = attempt_workspace / ".agent-workspace-eval.db"
        with SQLiteEventStore(database) as store:
            outcome = await run_scenario(
                scenario.eval,
                provider,
                store,
                attempt_workspace,
                autonomy=Autonomy.YOLO,
            )
        failures = list(outcome.failures)
        failures.extend(
            _check_artifacts(
                attempt_workspace,
                scenario.artifacts,
                outcome.settled_tool_results,
            )
        )
        incomplete = outcome.incomplete or bool(failures)
        if outcome.incomplete and not any("truncat" in failure.casefold() for failure in failures):
            failures.append("task was interrupted or incomplete")
        attempt = AcceptanceAttempt(
            attempt=attempt_number,
            workspace=attempt_workspace,
            outcome=outcome,
            failures=tuple(dict.fromkeys(failures)),
            incomplete=incomplete,
        )
        attempts.append(attempt)
        if not attempt.failures and not attempt.incomplete:
            return AcceptanceResult(scenario.id, True, tuple(attempts))
        if attempt_number >= scenario.max_attempts:
            break
        if repair is not None:
            context = AcceptanceRepairContext(
                scenario=scenario,
                attempt=attempt_number,
                workspace=attempt_workspace,
                next_workspace=root / f"{scenario.id}.attempt-{attempt_number + 1:02d}",
                outcome=outcome,
                failures=attempt.failures,
            )
            repair_result = repair(context)
            if asyncio.iscoroutine(repair_result) or isinstance(repair_result, Awaitable):
                await repair_result
    return AcceptanceResult(scenario.id, False, tuple(attempts))


async def run_acceptance_suite(
    scenarios: Sequence[AcceptanceScenario],
    provider_factory: Callable[[AcceptanceScenario, int], ScriptedEvalProvider],
    workspace_root: StrPath,
    *,
    repair: RepairHook | None = None,
    setup: AttemptSetup | None = None,
) -> tuple[AcceptanceResult, ...]:
    """Run scenarios in deterministic order, preserving each attempt tree."""

    results: list[AcceptanceResult] = []
    for scenario in scenarios:

        def make_provider(
            attempt: int, current: AcceptanceScenario = scenario
        ) -> ScriptedEvalProvider:
            return provider_factory(current, attempt)

        results.append(
            await run_acceptance_scenario(
                scenario,
                make_provider,
                Path(workspace_root) / scenario.id,
                repair=repair,
                setup=setup,
            )
        )
    return tuple(results)


def validate_artifact(
    root: StrPath,
    requirement: ArtifactRequirement,
    *,
    tool_results: Iterable[dict[str, object]] = (),
) -> tuple[str, ...]:
    """Validate one artifact and return human-readable failures."""

    workspace = Path(root).resolve()
    target = (workspace / requirement.path).resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        return (f"artifact path escapes workspace: {requirement.path}",)
    if not target.exists():
        return (f"missing artifact: {requirement.path}",)
    if requirement.kind is ArtifactKind.DIRECTORY:
        return () if target.is_dir() else (f"artifact is not a directory: {requirement.path}",)
    if not target.is_file():
        return (f"artifact is not a regular file: {requirement.path}",)
    try:
        size = target.stat().st_size
    except OSError as exc:
        return (f"cannot stat artifact {requirement.path}: {exc}",)
    failures: list[str] = []
    if size < requirement.min_bytes:
        failures.append(
            f"artifact {requirement.path} is {size} bytes; expected at least "
            f"{requirement.min_bytes}"
        )
    try:
        content = target.read_bytes()
    except OSError as exc:
        return tuple([*failures, f"cannot read artifact {requirement.path}: {exc}"])
    if requirement.sha256 is not None and hashlib.sha256(content).hexdigest() != requirement.sha256:
        failures.append(f"artifact sha256 mismatch: {requirement.path}")
    if requirement.kind is ArtifactKind.PDF:
        if not content.startswith(b"%PDF-"):
            failures.append(f"artifact is not a PDF: {requirement.path}")
        else:
            try:
                reader = PdfReader(BytesIO(content), strict=True)
                if len(reader.pages) == 0:
                    failures.append(f"artifact is not a valid PDF: {requirement.path} has no pages")
            except Exception as exc:
                failures.append(
                    f"artifact is not a valid PDF: {requirement.path} ({type(exc).__name__})"
                )
    elif requirement.kind is ArtifactKind.PNG and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        failures.append(f"artifact is not a PNG: {requirement.path}")
    elif requirement.kind is ArtifactKind.JPEG and not content.startswith(b"\xff\xd8\xff"):
        failures.append(f"artifact is not a JPEG: {requirement.path}")
    if requirement.required_text:
        if len(content) > _MAX_ARTIFACT_READ_BYTES:
            failures.append(f"text artifact exceeds bounded validation size: {requirement.path}")
        else:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                failures.append(f"artifact is not UTF-8 text: {requirement.path}")
            else:
                for marker in requirement.required_text:
                    if marker not in text:
                        failures.append(
                            f"artifact {requirement.path} is missing required text {marker!r}"
                        )
    if requirement.provenance_of is not None:
        failures.extend(
            _validate_provenance_manifest(workspace, requirement, content, tool_results)
        )
    return tuple(failures)


def _validate_provenance_manifest(
    workspace: Path,
    requirement: ArtifactRequirement,
    content: bytes,
    tool_results: Iterable[dict[str, object]],
) -> list[str]:
    assert requirement.provenance_of is not None
    if len(content) > _MAX_ARTIFACT_READ_BYTES:
        return [f"provenance manifest exceeds validation size: {requirement.path}"]
    try:
        manifest = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return [f"provenance manifest is not valid JSON: {requirement.path}"]
    if not isinstance(manifest, dict):
        return [f"provenance manifest must be an object: {requirement.path}"]
    url = manifest.get("url")
    try:
        parsed = urlsplit(url) if isinstance(url, str) else None
        port = parsed.port if parsed is not None else None
    except ValueError:
        parsed = None
        port = None
    failures: list[str] = []
    literal_address = None
    if parsed is not None and parsed.hostname is not None:
        try:
            literal_address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            literal_address = None
    public_literal = literal_address is None or literal_address.is_global
    public_hostname = parsed is not None and (parsed.hostname or "").casefold() not in {
        "localhost",
        "localhost.localdomain",
    }
    if (
        parsed is None
        or parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port not in {None, 443}
        or not public_literal
        or not public_hostname
    ):
        failures.append(f"provenance URL is not public HTTPS: {requirement.path}")
    source = (workspace / requirement.provenance_of).resolve()
    try:
        source.relative_to(workspace)
    except ValueError:
        return [*failures, f"provenance source escapes workspace: {requirement.provenance_of}"]
    if not source.is_file():
        return [*failures, f"provenance source is missing: {requirement.provenance_of}"]
    try:
        if source.stat().st_size > _MAX_ARTIFACT_READ_BYTES:
            return [
                *failures,
                f"provenance source exceeds validation size: {requirement.provenance_of}",
            ]
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
    except OSError:
        return [*failures, f"cannot read provenance source: {requirement.provenance_of}"]
    if manifest.get("sha256") != digest:
        failures.append(f"provenance sha256 mismatch: {requirement.path}")
    receipt_match = False
    for tool_result in tool_results:
        if (
            tool_result.get("name") != "download_file"
            or tool_result.get("output_truncated") is True
        ):
            continue
        raw_result = tool_result.get("result")
        if not isinstance(raw_result, str):
            continue
        try:
            receipt = json.loads(raw_result)
        except json.JSONDecodeError:
            continue
        if not isinstance(receipt, dict):
            continue
        if (
            receipt.get("path") == requirement.provenance_of
            and receipt.get("url") == url
            and receipt.get("sha256") == digest
        ):
            receipt_match = True
            break
    if not receipt_match:
        failures.append(
            f"provenance manifest is not bound to a matching download receipt: {requirement.path}"
        )
    return failures


def _check_artifacts(
    root: Path,
    requirements: Iterable[ArtifactRequirement],
    tool_results: Iterable[dict[str, object]],
) -> list[str]:
    failures: list[str] = []
    for requirement in requirements:
        failures.extend(validate_artifact(root, requirement, tool_results=tool_results))
    return failures


def _prepare_fresh_workspace(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to reuse non-fresh acceptance workspace: {path}")
    path.mkdir(parents=True, exist_ok=False)


def _seed_files(root: Path, files: Iterable[tuple[str, str]]) -> None:
    for relative_path, content in files:
        requirement = ArtifactRequirement(relative_path, min_bytes=0)
        target = (root / requirement.path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def build_acceptance_scenarios() -> tuple[AcceptanceScenario, ...]:
    """Return the standard six workflow contracts used by release acceptance.

    These are contracts rather than provider scripts: a live run supplies the
    model/tool trace, while the harness verifies that the requested durable
    artifact actually exists.  The prompts name the expected deliverable and
    deliberately require a final verification step so a model cannot report
    success after only drafting an intermediate file.
    """

    def scenario(
        identifier: str,
        name: str,
        category: AcceptanceCategory,
        prompt: str,
        artifacts: tuple[ArtifactRequirement, ...],
        *,
        expected_tools: tuple[str, ...] = (),
    ) -> AcceptanceScenario:
        evaluation = EvalScenario(
            id=identifier,
            name=name,
            prompt=prompt,
            turns=(EvalTurn(deltas=(), expected_tool_calls=expected_tools),),
        )
        return AcceptanceScenario(
            id=identifier,
            name=name,
            category=category,
            eval=evaluation,
            artifacts=artifacts,
            max_attempts=3,
        )

    return (
        scenario(
            "latex-pdf",
            "Compile a LaTeX paper to PDF",
            AcceptanceCategory.FILE_GENERATION,
            "Create paper.tex, compile it with xelatex, and verify paper.pdf opens as a PDF.",
            (
                ArtifactRequirement("paper.tex", ArtifactKind.TEXT, min_bytes=32),
                ArtifactRequirement("paper.pdf", ArtifactKind.PDF, min_bytes=128),
            ),
            expected_tools=("write_file", "run_sandbox"),
        ),
        scenario(
            "paper-download",
            "Download a paper and preserve its source",
            AcceptanceCategory.PAPER_DOWNLOAD,
            (
                "Use download_file to save the requested paper as paper.pdf without changing "
                "its bytes. Use write_file to save paper.json with the final URL and the "
                "downloaded file's SHA-256 checksum. Verify the PDF and both files."
            ),
            (
                ArtifactRequirement("paper.pdf", ArtifactKind.PDF, min_bytes=128),
                ArtifactRequirement(
                    "paper.json",
                    ArtifactKind.TEXT,
                    min_bytes=16,
                    required_text=("url", "sha256"),
                    provenance_of="paper.pdf",
                ),
            ),
            expected_tools=("download_file", "write_file"),
        ),
        scenario(
            "network-resource-download",
            "Download a network resource with provenance",
            AcceptanceCategory.NETWORK_DOWNLOAD,
            (
                "Use download_file to save the requested network resource as resource.bin "
                "without changing its bytes. Use write_file to save resource.json with the "
                "final URL and downloaded file's SHA-256 checksum. Verify both files."
            ),
            (
                ArtifactRequirement("resource.bin", ArtifactKind.FILE, min_bytes=1),
                ArtifactRequirement(
                    "resource.json",
                    ArtifactKind.TEXT,
                    min_bytes=16,
                    required_text=("url", "sha256"),
                    provenance_of="resource.bin",
                ),
            ),
            expected_tools=("download_file", "write_file"),
        ),
        scenario(
            "scientific-plot",
            "Generate and validate a scientific plot",
            AcceptanceCategory.SCIENTIFIC_PLOT,
            (
                "Generate a publication-ready plot from the supplied data, save figure.png "
                "and the plotting script, then verify the image."
            ),
            (
                ArtifactRequirement("figure.png", ArtifactKind.PNG, min_bytes=128),
                ArtifactRequirement(
                    "plot.py", ArtifactKind.TEXT, min_bytes=32, required_text=("matplotlib",)
                ),
            ),
            expected_tools=("write_file", "run_sandbox"),
        ),
        scenario(
            "programming-project",
            "Implement and test a small program",
            AcceptanceCategory.PROGRAMMING,
            (
                "Implement the requested program, add a focused test, run it, and leave "
                "the source and test files in the workspace."
            ),
            (
                ArtifactRequirement("src", ArtifactKind.DIRECTORY),
                ArtifactRequirement("tests", ArtifactKind.DIRECTORY),
                ArtifactRequirement("README.md", ArtifactKind.TEXT, min_bytes=32),
            ),
            expected_tools=("make_directory", "write_file", "run_sandbox"),
        ),
        scenario(
            "multi-agent-report",
            "Coordinate subagents into a reviewed report",
            AcceptanceCategory.MULTI_AGENT,
            (
                "Delegate research, implementation, and review to isolated subagents, "
                "then synthesize a final report with their evidence."
            ),
            (
                ArtifactRequirement(
                    "report.md", ArtifactKind.TEXT, min_bytes=64, required_text=("##", "Evidence")
                ),
                ArtifactRequirement(
                    "agents.json", ArtifactKind.TEXT, min_bytes=16, required_text=("completed",)
                ),
            ),
            expected_tools=("subagent",),
        ),
    )


def render_acceptance_results(results: Sequence[AcceptanceResult]) -> str:
    """Render concise status lines suitable for CI or a desktop activity log."""

    lines: list[str] = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        line = f"[{status}] {result.scenario_id} ({len(result.attempts)} attempt(s))"
        if not result.passed and result.failures:
            line += ": " + "; ".join(result.failures)
        lines.append(line)
    return "\n".join(lines)


__all__ = [
    "AcceptanceAttempt",
    "AcceptanceCategory",
    "AcceptanceRepairContext",
    "AcceptanceResult",
    "AcceptanceScenario",
    "ArtifactKind",
    "ArtifactRequirement",
    "build_acceptance_scenarios",
    "render_acceptance_results",
    "run_acceptance_scenario",
    "run_acceptance_suite",
    "validate_artifact",
]
