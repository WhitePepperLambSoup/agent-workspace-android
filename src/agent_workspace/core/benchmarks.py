"""Weighted agent benchmark framework.

Runs benchmark cases against a real :class:`ApplicationService` (a live model
in production use, a scripted provider in tests) and scores each case against
its checklist, in the spirit of BFCL tool calling, HumanEval-style coding, and
multi-turn loop evaluation. Case weights are split evenly across the check
items, so partial credit is possible when only some checks pass.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from agent_workspace.application.service import ApplicationService
from agent_workspace.core.events import Event
from agent_workspace.policy import ProviderEgressDeniedError
from agent_workspace.tools.process_worker import ToolWorkerError, run_in_process

_CHECK_TIMEOUT_SECONDS = 60.0
_CHECK_SCRIPT_NAME = "benchmark_check.py"


class BenchmarkCategory(StrEnum):
    """The benchmark axis a case belongs to."""

    TOOL_CALLING = "tool_calling"
    CODING = "coding"
    LOOP = "loop"


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One scored scenario for the agent."""

    id: str
    category: BenchmarkCategory
    prompt: str
    weight: float = 1.0
    expected_tool_sequence: tuple[str, ...] = ()
    expected_tool_arguments: tuple[dict[str, Any], ...] = ()
    code_checks: tuple[str, ...] = ()
    expected_final_text: str | None = None
    extra_files: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkVerdict:
    """The outcome of running a single benchmark case."""

    case_id: str
    category: BenchmarkCategory
    passed: bool
    score: float
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Aggregated results across every benchmark case."""

    cases: int
    passed: int
    weighted_score: float
    by_category: dict[BenchmarkCategory, float]
    verdicts: tuple[BenchmarkVerdict, ...]

    def render(self) -> str:
        """Render a human-readable report with one line per case."""
        lines = [
            f"Benchmark: {self.cases} cases, {self.passed} passed, "
            f"weighted score {self.weighted_score:.3f}"
        ]
        for verdict in self.verdicts:
            status = "PASS" if verdict.passed else "FAIL"
            line = (
                f"[{status}] {verdict.case_id} ({verdict.category.value}) score {verdict.score:.3f}"
            )
            if verdict.failures:
                line += ": " + "; ".join(verdict.failures)
            lines.append(line)
        lines.append("Category weighted scores:")
        for category in BenchmarkCategory:
            if category in self.by_category:
                lines.append(f"  {category.value}: {self.by_category[category]:.3f}")
        lines.append(f"Overall weighted score: {self.weighted_score:.3f}")
        return "\n".join(lines)


async def run_benchmark_case(
    service: ApplicationService,
    case: BenchmarkCase,
    workspace: Path,
    provider_model: str,
    egress_ok: bool = True,
) -> BenchmarkVerdict:
    """Run one case against the service and score the result.

    ``extra_files`` are seeded into the workspace and a fresh session is
    created for the case. Tool calls are collected from the service's event
    bus: the tool sequence is matched against the tools that actually started,
    and the arguments against what was proposed for those calls. The case
    weight is split evenly across its check items (tool sequence, tool
    arguments, each code check, and the final text when one is expected).

    ``egress_ok`` only refines the failure message when the provider egress
    policy denies the run; the run still scores zero either way.
    """
    for relative_path, content in case.extra_files:
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    executions: list[tuple[str, dict[str, Any] | None]] = []
    proposed_arguments: dict[str, dict[str, Any]] = {}

    def collect(event: Event) -> None:
        if event.type == "tool.proposed":
            call_id = event.data.get("tool_call_id")
            name = event.data.get("name")
            arguments = event.data.get("arguments")
            if isinstance(call_id, str) and isinstance(name, str) and isinstance(arguments, dict):
                proposed_arguments[call_id] = arguments
        elif event.type == "tool.started":
            call_id = event.data.get("tool_call_id")
            name = event.data.get("name")
            if isinstance(call_id, str) and isinstance(name, str):
                executions.append((name, proposed_arguments.get(call_id)))

    unsubscribe = service.events.subscribe(collect)
    session = service.create_session(workspace)
    failures: list[str] = []
    final_text = ""
    try:
        result = await service.run(session, case.prompt, provider_model)
        final_text = result.text
    except ProviderEgressDeniedError as exc:
        message = "provider egress denied"
        if not egress_ok:
            message += " (the benchmark expected egress to be unavailable)"
        failures.append(f"{message}: {exc}")
    except Exception as exc:
        failures.append(f"run failed: {type(exc).__name__}: {exc}")
    finally:
        unsubscribe()
    if failures:
        return BenchmarkVerdict(case.id, case.category, False, 0.0, tuple(failures))

    actual_names = tuple(name for name, _ in executions)
    sequence_ok, sequence_failure = _check_tool_sequence(
        case.expected_tool_sequence,
        actual_names,
    )
    if sequence_failure is not None:
        failures.append(sequence_failure)
    arguments_ok, arguments_failure = _check_tool_arguments(
        case.expected_tool_arguments,
        executions,
    )
    if arguments_failure is not None:
        failures.append(arguments_failure)
    if case.code_checks:
        code = _extract_python_code(final_text)
        if code is None:
            failures.append("no python code block was found in the final text")
            code_ok = False
        else:
            code_ok, code_failure = await _run_code_checks(code, case.code_checks)
            if code_failure is not None:
                failures.append(code_failure)
    else:
        code_ok = True
    final_ok = case.expected_final_text is None or case.expected_final_text in final_text
    if case.expected_final_text is not None and not final_ok:
        failures.append(f"expected final text {case.expected_final_text!r} was not produced")

    check_count = 1 + 1 + len(case.code_checks) + (1 if case.expected_final_text is not None else 0)
    passed_items = (
        (1 if sequence_ok else 0)
        + (1 if arguments_ok else 0)
        + (len(case.code_checks) if code_ok else 0)
        + (1 if final_ok and case.expected_final_text is not None else 0)
    )
    score = case.weight * passed_items / check_count
    return BenchmarkVerdict(case.id, case.category, not failures, score, tuple(failures))


async def run_benchmark(
    service_factory: Callable[[], ApplicationService],
    cases: Sequence[BenchmarkCase],
    workspace: Path,
    provider_model: str,
) -> BenchmarkReport:
    """Run every case through a shared service and aggregate the verdicts.

    The factory is invoked once; cases share the same store and provider while
    each case gets its own session.
    """
    service = service_factory()
    verdicts: list[BenchmarkVerdict] = []
    try:
        for case in cases:
            verdicts.append(await run_benchmark_case(service, case, workspace, provider_model))
    finally:
        await service.aclose()
    return _build_report(cases, tuple(verdicts))


def build_builtin_cases() -> tuple[BenchmarkCase, ...]:
    """The built-in smoke suite: 3 tool-calling, 3 coding, and 2 loop cases."""
    return (
        BenchmarkCase(
            id="tc_read_file_summary",
            category=BenchmarkCategory.TOOL_CALLING,
            prompt="Read notes.txt and summarize its contents.",
            weight=1.0,
            expected_tool_sequence=("read_file",),
            expected_tool_arguments=({"path": "notes.txt"},),
            expected_final_text="summary",
            extra_files=(("notes.txt", "alpha\nbeta\n"),),
        ),
        BenchmarkCase(
            id="tc_create_file",
            category=BenchmarkCategory.TOOL_CALLING,
            prompt="Create a file named created.txt whose content is hello.",
            weight=1.0,
            expected_tool_sequence=("write_file",),
            expected_tool_arguments=({"path": "created.txt", "content": "hello"},),
            expected_final_text="created",
        ),
        BenchmarkCase(
            id="tc_list_then_read",
            category=BenchmarkCategory.TOOL_CALLING,
            prompt="List the workspace, then read data.txt.",
            weight=1.0,
            expected_tool_sequence=("list_files", "read_file"),
            expected_tool_arguments=({"path": "."}, {"path": "data.txt"}),
            expected_final_text="payload",
            extra_files=(("data.txt", "payload\n"),),
        ),
        BenchmarkCase(
            id="code_add",
            category=BenchmarkCategory.CODING,
            prompt="Write a Python function add(a, b) that returns a + b.",
            weight=1.2,
            code_checks=("assert add(2, 3) == 5", "assert add(-1, 1) == 0"),
            expected_final_text="def add",
        ),
        BenchmarkCase(
            id="code_sort",
            category=BenchmarkCategory.CODING,
            prompt="Write a Python function sort_list(items) that sorts a list.",
            weight=1.2,
            code_checks=("assert sort_list([3, 1, 2]) == [1, 2, 3]",),
            expected_final_text="def sort_list",
        ),
        BenchmarkCase(
            id="code_unique",
            category=BenchmarkCategory.CODING,
            prompt="Write a Python function unique(items) that removes duplicates.",
            weight=1.2,
            code_checks=("assert unique([1, 2, 2, 3]) == [1, 2, 3]",),
            expected_final_text="def unique",
        ),
        BenchmarkCase(
            id="loop_write_then_read",
            category=BenchmarkCategory.LOOP,
            prompt="Create loop.txt containing loop-data, then read it back and report its "
            "contents.",
            weight=1.5,
            expected_tool_sequence=("write_file", "read_file"),
            expected_tool_arguments=(
                {"path": "loop.txt", "content": "loop-data"},
                {"path": "loop.txt"},
            ),
            expected_final_text="loop-data",
        ),
        BenchmarkCase(
            id="loop_two_step_edit",
            category=BenchmarkCategory.LOOP,
            prompt="Write step.txt with content first, then overwrite it with content second, "
            "and report the final content.",
            weight=1.5,
            expected_tool_sequence=("write_file", "write_file"),
            expected_tool_arguments=(
                {"path": "step.txt", "content": "first"},
                {"path": "step.txt", "content": "second"},
            ),
            expected_final_text="second",
        ),
    )


def _check_tool_sequence(
    expected: tuple[str, ...],
    actual: tuple[str, ...],
) -> tuple[bool, str | None]:
    """Return (passed, failure message) for an ordered prefix match."""
    if not expected:
        return True, None
    if actual[: len(expected)] != expected:
        return (
            False,
            f"expected tool sequence {list(expected)} is not a prefix of actual {list(actual)}",
        )
    return True, None


def _check_tool_arguments(
    expected: tuple[dict[str, Any], ...],
    actual: Sequence[tuple[str, dict[str, Any] | None]],
) -> tuple[bool, str | None]:
    """Return (passed, failure message) for positional argument subset checks."""
    if not expected:
        return True, None
    if len(actual) < len(expected):
        return (
            False,
            f"expected {len(expected)} tool calls with arguments, saw {len(actual)}",
        )
    mismatches: list[str] = []
    for index, expected_arguments in enumerate(expected):
        name, actual_arguments = actual[index]
        if actual_arguments is None:
            mismatches.append(f"position {index} ({name}) has no recorded arguments")
            continue
        if not _arguments_subset(expected_arguments, actual_arguments):
            mismatches.append(
                f"position {index} ({name}) arguments {expected_arguments!r} "
                f"are not a subset of actual {actual_arguments!r}"
            )
    if mismatches:
        return False, "; ".join(mismatches)
    return True, None


def _arguments_subset(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    """Return whether every expected key/value pair exists in ``actual``."""
    try:
        return set(expected.items()) <= set(actual.items())
    except TypeError:
        # Nested dicts are unhashable; compare their values directly.
        return all(key in actual and value == actual[key] for key, value in expected.items())


def _extract_python_code(text: str) -> str | None:
    """Extract the first python code block or a plain ``def`` paragraph."""
    marker = "```python"
    start = text.find(marker)
    if start != -1:
        code_start = start + len(marker)
        end = text.find("```", code_start)
        return text[code_start:end] if end != -1 else text[code_start:]
    for paragraph in text.split("\n\n"):
        stripped = paragraph.strip()
        if stripped.startswith("def ") or stripped.startswith("async def "):
            return stripped
    return None


def _build_check_script(code: str, checks: Sequence[str]) -> str:
    return "\n".join([code.rstrip(), "", "# -- benchmark assertions --", *checks, ""])


def _run_python_check(script_path: str) -> tuple[int, str]:
    """Run a Python file in a subprocess; return (exit code, stderr tail)."""
    completed = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        timeout=_CHECK_TIMEOUT_SECONDS,
    )
    tail = "\n".join(completed.stderr.strip().splitlines()[-4:])
    return completed.returncode, tail


async def _run_code_checks(code: str, checks: Sequence[str]) -> tuple[bool, str | None]:
    """Run the extracted code plus assertions as one file; exit 0 means pass."""
    with tempfile.TemporaryDirectory() as directory:
        script_path = Path(directory) / _CHECK_SCRIPT_NAME
        script_path.write_text(_build_check_script(code, checks), encoding="utf-8")
        try:
            returncode, stderr = await run_in_process(
                _run_python_check,
                str(script_path),
                allow_children=True,
            )
        except ToolWorkerError as exc:
            return False, f"code check could not execute: {exc}"
    if returncode == 0:
        return True, None
    detail = stderr or "no output"
    return False, f"code check failed (exit {returncode}): {detail}"


def _build_report(
    cases: Sequence[BenchmarkCase],
    verdicts: Sequence[BenchmarkVerdict],
) -> BenchmarkReport:
    total_weight = sum(case.weight for case in cases)
    total_score = sum(verdict.score for verdict in verdicts)
    category_totals: dict[BenchmarkCategory, tuple[float, float]] = {}
    for case, verdict in zip(cases, verdicts, strict=True):
        score, weight = category_totals.get(case.category, (0.0, 0.0))
        category_totals[case.category] = (score + verdict.score, weight + case.weight)
    by_category = {
        category: score / weight if weight > 0 else 0.0
        for category, (score, weight) in category_totals.items()
    }
    return BenchmarkReport(
        cases=len(verdicts),
        passed=sum(1 for verdict in verdicts if verdict.passed),
        weighted_score=total_score / total_weight if total_weight > 0 else 0.0,
        by_category=by_category,
        verdicts=tuple(verdicts),
    )
