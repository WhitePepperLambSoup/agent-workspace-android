from __future__ import annotations

import asyncio
import fnmatch
import glob
import importlib
import re
import time
from collections import deque
from dataclasses import dataclass, replace
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_workspace.core.models import Capability, ToolSpec

from .base import (
    ToolArgumentError,
    ToolError,
    json_result,
    optional_bool,
    optional_int,
    require_string,
)
from .filesystem import _workspace_paths
from .paths import (
    StrPath,
    WorkspacePathError,
    WorkspacePaths,
    is_sensitive_workspace_path,
    open_checked,
)
from .process_worker import run_in_process

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_FILES = 10_000
_MAX_ENTRIES = 100_000
_MAX_FILE_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_REGEX_PATTERN_CHARS = 1024
# Regex matching is bounded to the first 64 KiB of any single line so a
# pathological pattern cannot hang the worker on an enormous line.
_MAX_REGEX_LINE_CHARS = 64 * 1024
# Python's re backtracks and holds the GIL while it does: on the phone, where a tool runs on a
# thread nothing can stop, one runaway match freezes the whole engine. Patterns that can take
# exponential time are refused (_regex_line_chars); for the rest, how much of a line is matched
# shrinks with how many of the pattern's repeats can trade characters with each other (the
# degree of its worst case), so one line costs at most about a quarter of a second, and the
# search stops after _REGEX_SECONDS.
_REGEX_LINE_CHARS_BY_CHAIN = (_MAX_REGEX_LINE_CHARS, 16 * 1024, 1024, 256)
_REGEX_SECONDS = 30.0
# A repeat bounded this low adds little: \d{1,3} is not counted among the open-ended ones.
_SMALL_REPEAT = 64
# Characters that stand for the rest: ASCII, a no-break space, a Latin letter, a CJK
# character, an Arabic digit and a line separator (all of \w, \s or \d in Unicode).
_PROBE_CHARS = frozenset(
    [chr(code) for code in range(128)] + [chr(code) for code in (0xA0, 0xE9, 0x4E2D, 0x663, 0x2028)]
)
_CATEGORY_PATTERNS = {
    "CATEGORY_DIGIT": re.compile(r"\d"),
    "CATEGORY_NOT_DIGIT": re.compile(r"\D"),
    "CATEGORY_SPACE": re.compile(r"\s"),
    "CATEGORY_NOT_SPACE": re.compile(r"\S"),
    "CATEGORY_WORD": re.compile(r"\w"),
    "CATEGORY_NOT_WORD": re.compile(r"\W"),
}
# The parser re itself uses (a private module, read only to inspect a pattern's structure).
_PARSER: Any = importlib.import_module("re._parser")
_OPS: Any = importlib.import_module("re._constants")


@dataclass(frozen=True, slots=True)
class _Element:
    """One step of a pattern's sequence, as seen by the backtracking checks."""

    chars: frozenset[str]  # characters it can consume (approximated over probe characters)
    first: frozenset[str]  # characters its match can start with
    last: frozenset[str]  # characters its match can end with
    mandatory: bool  # consumes at least one character whenever its optional groups are taken
    weight: int  # open-ended repeats it stands for (0: none)
    single: bool  # matches exactly one character
    scopes: tuple[int, ...] = ()  # the optional groups it is inside


class _PatternAnalysis:
    def __init__(self, pattern: str, flags: int) -> None:
        self.ignore_case = bool(flags & re.IGNORECASE) or "(?i" in pattern
        self.universe = set(_PROBE_CHARS)
        self._scope = 0
        self.parsed = _PARSER.parse(pattern, flags)
        self._collect_literals(self.parsed)

    def _collect_literals(self, items: Any) -> None:
        for op, value in items:
            if op in (_OPS.LITERAL, _OPS.NOT_LITERAL):
                self.universe.update(self._variants(chr(value)))
            elif op is _OPS.RANGE:
                self.universe.update((chr(value[0]), chr(value[1])))
            elif op is _OPS.IN:
                self._collect_literals(value)
            else:
                for part in _children(op, value):
                    self._collect_literals(part)

    def _variants(self, char: str) -> set[str]:
        return {char, char.lower(), char.upper()} if self.ignore_case else {char}

    def chars(self, items: Any) -> frozenset[str]:
        """Every character any step of ``items`` can consume."""
        found: set[str] = set()
        for op, value in items:
            found.update(self._node_chars(op, value))
        return frozenset(found)

    def _node_chars(self, op: Any, value: Any) -> frozenset[str]:
        if op is _OPS.LITERAL:
            return frozenset(self._variants(chr(value)))
        if op is _OPS.NOT_LITERAL:
            return frozenset(self.universe - self._variants(chr(value)))
        if op is _OPS.ANY:
            return frozenset(self.universe)
        if op is _OPS.IN:
            return frozenset(char for char in self.universe if self._in_class(value, char))
        if op is _OPS.CATEGORY:
            return frozenset(char for char in self.universe if self._in_class([(op, value)], char))
        found: set[str] = set()
        for part in _children(op, value):
            found.update(self.chars(part))
        return frozenset(found)

    def _in_class(self, items: Any, char: str) -> bool:
        negate = False
        matched = False
        candidates = self._variants(char)
        for op, value in items:
            if op is _OPS.NEGATE:
                negate = True
            elif op is _OPS.LITERAL:
                matched = matched or chr(value) in candidates
            elif op is _OPS.RANGE:
                matched = matched or any(value[0] <= ord(item) <= value[1] for item in candidates)
            elif op is _OPS.CATEGORY:
                category = _CATEGORY_PATTERNS.get(str(value))
                matched = matched or category is None or category.match(char) is not None
            else:
                matched = True
        return matched != negate

    def elements(self, items: Any) -> list[_Element]:
        """The sequence of steps, groups opened up; lookarounds and anchors consume nothing."""
        found: list[_Element] = []
        for op, value in items:
            if op is _OPS.SUBPATTERN:
                found.extend(self.elements(value[3]))
            elif op in (_OPS.MAX_REPEAT, _OPS.MIN_REPEAT):
                low, high, body = value
                if high != _OPS.MAXREPEAT and high <= 1:
                    # Optional: its steps, required only when the group is taken.
                    self._scope += 1
                    found.extend(
                        replace(item, scopes=(self._scope, *item.scopes)) if low == 0 else item
                        for item in self.elements(body)
                    )
                    continue
                open_ended = (high == _OPS.MAXREPEAT or high > _SMALL_REPEAT) and (
                    low != high or body.getwidth()[0] != body.getwidth()[1]
                )
                found.append(
                    self._compound(body, low > 0 and body.getwidth()[0] > 0, int(open_ended))
                )
            elif op is _OPS.BRANCH:
                alternatives = value[1]
                parts = [self._compound(alternative, True, 0) for alternative in alternatives]
                found.append(
                    _Element(
                        frozenset[str]().union(*(part.chars for part in parts)),
                        frozenset[str]().union(*(part.first for part in parts)),
                        frozenset[str]().union(*(part.last for part in parts)),
                        all(alternative.getwidth()[0] > 0 for alternative in alternatives),
                        max(self.chain(alternative) for alternative in alternatives),
                        False,
                    )
                )
            elif op in (_OPS.POSSESSIVE_REPEAT, _OPS.ATOMIC_GROUP):
                # Never backtracked into: one step, whatever it repeats.
                body = value[2] if op is _OPS.POSSESSIVE_REPEAT else value
                low = value[0] if op is _OPS.POSSESSIVE_REPEAT else 1
                found.append(self._compound(body, low > 0 and body.getwidth()[0] > 0, 0))
            elif op in (_OPS.ASSERT, _OPS.ASSERT_NOT, _OPS.AT):
                continue
            else:
                chars = self._node_chars(op, value)
                found.append(_Element(chars, chars, chars, True, 0, True))
        return found

    def _compound(self, body: Any, mandatory: bool, weight: int) -> _Element:
        steps = self.elements(body)
        first: set[str] = set()
        for step in steps:
            first.update(step.first)
            if step.mandatory and not step.scopes:
                break
        last: set[str] = set()
        for step in reversed(steps):
            last.update(step.last)
            if step.mandatory and not step.scopes:
                break
        return _Element(
            frozenset[str]().union(*(step.chars for step in steps)),
            frozenset(first),
            frozenset(last),
            mandatory,
            weight,
            False,
        )

    def chain(self, items: Any) -> int:
        """The most open-ended repeats of ``items`` that can trade characters in one match: each
        one multiplies the worst case by the line's length."""
        steps = self.elements(items)
        best = [0] * len(steps)
        for later, step in enumerate(steps):
            if not step.weight:
                continue
            best[later] = step.weight
            for earlier in range(later):
                if best[earlier] and self._trades(steps, earlier, later):
                    best[later] = max(best[later], best[earlier] + step.weight)
        lookarounds = sum(
            self.chain(value[1]) for op, value in items if op in (_OPS.ASSERT, _OPS.ASSERT_NOT)
        )
        return max(best, default=0) + lookarounds

    @staticmethod
    def _trades(steps: list[_Element], earlier: int, later: int) -> bool:
        # The earlier repeat can swallow what lies between and the start of the later one: where
        # one ends and the other starts is open, so both are retried against each other.
        before, after = steps[earlier], steps[later]
        taken = set(before.scopes) | set(after.scopes)
        between = [
            step
            for step in steps[earlier + 1 : later]
            if step.mandatory and set(step.scopes) <= taken
        ]
        if not all(before.chars & step.chars for step in between):
            return False
        boundary = between[0].first if between else after.first
        return bool(before.last & boundary) and bool(before.chars & after.first)

    def unsafe_repeat(self, items: Any) -> str | None:
        """Why some repeat of ``items`` can backtrack exponentially, or None."""
        for op, value in items:
            if op in (_OPS.GROUPREF, _OPS.GROUPREF_EXISTS):
                return "backreferences are not supported"
            if op in (_OPS.MAX_REPEAT, _OPS.MIN_REPEAT):
                high, body = value[1], value[2]
                if (high == _OPS.MAXREPEAT or high > 1) and not self._repeatable(body):
                    return "a repeated group that can match the same text in more than one way"
            for part in _children(op, value):
                reason = self.unsafe_repeat(part)
                if reason is not None:
                    return reason
        return None

    def _repeatable(self, body: Any) -> bool:
        steps = self.elements(body)
        low, high = body.getwidth()
        branches = [value[1] for op, value in _walk(body) if op is _OPS.BRANCH]
        if low == high and not any(step.weight for step in steps):
            # Fixed width: only alternatives that start alike leave the split open.
            return all(_disjoint_starts(self, alternatives) for alternatives in branches)
        # Otherwise one iteration must be marked off by a character nothing else in it can match.
        for edge, rest in ((0, steps[1:]), (len(steps) - 1, steps[:-1])):
            if steps and steps[edge].single and steps[edge].mandatory and not steps[edge].scopes:
                others = frozenset[str]().union(*(step.chars for step in rest))
                if not steps[edge].chars & others:
                    return True
        return False


def _children(op: Any, value: Any) -> list[Any]:
    """The sub-patterns a node holds."""
    if op is _OPS.SUBPATTERN:
        return [value[3]]
    if op in (_OPS.MAX_REPEAT, _OPS.MIN_REPEAT, _OPS.POSSESSIVE_REPEAT):
        return [value[2]]
    if op is _OPS.BRANCH:
        return list(value[1])
    if op in (_OPS.ASSERT, _OPS.ASSERT_NOT):
        return [value[1]]
    if op is _OPS.ATOMIC_GROUP:
        return [value]
    if op is _OPS.GROUPREF_EXISTS:
        return [part for part in value[1:] if part is not None]
    return []


def _walk(items: Any) -> list[tuple[Any, Any]]:
    found: list[tuple[Any, Any]] = []
    for op, value in items:
        found.append((op, value))
        for part in _children(op, value):
            found.extend(_walk(part))
    return found


def _disjoint_starts(analysis: _PatternAnalysis, alternatives: list[Any]) -> bool:
    starts: list[frozenset[str]] = []
    for alternative in alternatives:
        if alternative.getwidth()[0] == 0:
            return False
        starts.append(analysis._compound(alternative, True, 0).first)
    return all(
        not (first & second) for index, first in enumerate(starts) for second in starts[index + 1 :]
    )


def _regex_line_chars(pattern: str, flags: int) -> int:
    """How much of each line ``pattern`` is matched against; ToolArgumentError when it could
    backtrack exponentially or its worst case grows too fast with the line's length."""
    try:
        analysis = _PatternAnalysis(pattern, flags)
        reason = analysis.unsafe_repeat(analysis.parsed)
        chain = analysis.chain(analysis.parsed)
    except (RecursionError, ValueError, TypeError, AttributeError, IndexError) as exc:
        # A construct the check does not know is not run unchecked.
        raise ToolArgumentError(
            "'query' uses a regular expression construct the search cannot check; "
            "simplify it or search for literal text"
        ) from exc
    if reason is not None:
        raise ToolArgumentError(
            f"'query' could make the search run for hours ({reason}); simplify the pattern, "
            "for example (?:\\w+\\.)+ as [\\w.]+, or search for literal text"
        )
    if chain >= len(_REGEX_LINE_CHARS_BY_CHAIN):
        raise ToolArgumentError(
            f"'query' has {chain} open-ended repeats (+, *, {{n,}}) that can match the same "
            "characters, which makes the search very slow; use fewer, or ones separated by "
            "characters they cannot match"
        )
    return _REGEX_LINE_CHARS_BY_CHAIN[chain]


def _search_files(
    paths: WorkspacePaths,
    root: Path,
    query: str,
    file_glob: str,
    case_sensitive: bool,
    include_sensitive: bool,
    regex: bool,
    maximum: int,
    max_files: int,
    max_entries: int,
    max_file_bytes: int,
    max_total_bytes: int,
    regex_line_chars: int = _MAX_REGEX_LINE_CHARS,
    regex_seconds: float = _REGEX_SECONDS,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    pending: deque[Path] = deque((root,))
    files_considered = 0
    entries_considered = 0
    files_searched = 0
    bytes_searched = 0
    binary_files = 0
    oversized_files = 0
    sensitive_files = 0
    truncated_by = {
        "max_results": False,
        "max_files": False,
        "max_entries": False,
        "max_total_bytes": False,
        "max_seconds": False,
    }
    normalized_query = query if case_sensitive else query.casefold()
    pattern: re.Pattern[str] | None = None
    if regex:
        pattern = re.compile(query, flags=0 if case_sensitive else re.IGNORECASE)
    regex_deadline = time.monotonic() + regex_seconds
    stop = False

    while pending and not stop:
        directory = pending.popleft()
        try:
            remaining_entries = max_entries - entries_considered
            children = list(islice(directory.iterdir(), remaining_entries + 1))
            entries_considered += len(children)
            if len(children) > remaining_entries:
                truncated_by["max_entries"] = True
                stop = True
                break
            children.sort(key=lambda item: (item.name.casefold(), item.name))
            for child in children:
                try:
                    checked = paths.resolve(child)
                except WorkspacePathError:
                    # Symlinks, junctions, and escaping paths are skipped per
                    # entry instead of aborting the whole tree walk.
                    continue
                relative = paths.relative(checked)
                if is_sensitive_workspace_path(relative) and not include_sensitive:
                    sensitive_files += 1
                    continue
                if checked.is_dir():
                    pending.append(checked)
                    continue
                if not fnmatch.fnmatch(relative, file_glob) and not fnmatch.fnmatch(
                    checked.name, file_glob
                ):
                    continue
                if files_considered >= max_files:
                    truncated_by["max_files"] = True
                    stop = True
                    break
                files_considered += 1

                try:
                    with open_checked(checked) as stream:
                        file_size = paths.assert_safe_file_descriptor(
                            stream.fileno(), checked
                        ).st_size
                        if file_size > max_file_bytes:
                            oversized_files += 1
                            continue
                        if file_size > max_total_bytes - bytes_searched:
                            truncated_by["max_total_bytes"] = True
                            stop = True
                            break

                        file_matches: list[dict[str, Any]] = []
                        file_hit_result_limit = False
                        is_binary = False
                        remaining = file_size
                        line_number = 0
                        while remaining:
                            raw_line = stream.readline(remaining)
                            if not raw_line:
                                break
                            remaining -= len(raw_line)
                            bytes_searched += len(raw_line)
                            if b"\x00" in raw_line:
                                is_binary = True
                                break
                            line_number += 1
                            if file_hit_result_limit:
                                continue
                            text = (
                                raw_line.removesuffix(b"\n")
                                .removesuffix(b"\r")
                                .decode("utf-8", errors="replace")
                            )
                            if pattern is not None:
                                if time.monotonic() > regex_deadline:
                                    truncated_by["max_seconds"] = True
                                    stop = True
                                    break
                                match_text = (
                                    text
                                    if len(text) <= regex_line_chars
                                    else text[:regex_line_chars]
                                )
                                hit = pattern.search(match_text) is not None
                            else:
                                searchable = text if case_sensitive else text.casefold()
                                hit = normalized_query in searchable
                            if not hit:
                                continue
                            file_matches.append(
                                {"path": relative, "line": line_number, "text": text}
                            )
                            if len(matches) + len(file_matches) >= maximum:
                                file_hit_result_limit = True
                except WorkspacePathError:
                    # A folder on the way became a link after it was checked: left out, as
                    # links are.
                    continue
                except OSError as exc:
                    raise ToolError(f"cannot read file while searching: {checked}") from exc

                if is_binary:
                    binary_files += 1
                    continue
                files_searched += 1
                matches.extend(file_matches)
                if file_hit_result_limit:
                    truncated_by["max_results"] = True
                    stop = True
                    break
                if stop:  # out of matching time partway through this file
                    break
        except OSError as exc:
            raise ToolError(f"cannot search directory: {directory}") from exc

    truncation_reasons = [name for name, reached in truncated_by.items() if reached]
    return {
        "matches": matches,
        "truncated": bool(truncation_reasons),
        "skipped": {
            "binary_files": binary_files,
            "oversized_files": oversized_files,
            "sensitive_files": sensitive_files,
        },
        "stats": {
            "entries_considered": entries_considered,
            "bytes_searched": bytes_searched,
            "files_considered": files_considered,
            "files_searched": files_searched,
            "truncated_by": truncation_reasons,
        },
    }


class SearchFilesTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="search_files",
        description=(
            "Search UTF-8 workspace files using literal text, or a regular expression with "
            "the regex flag. Regex patterns are limited to 1024 characters; patterns that can "
            "backtrack without end (nested repeats such as (a+)+, backreferences) are refused. "
            "Each line is matched on its first 64 KiB, less when several repeats of the "
            "pattern can match the same characters, and regex matching stops after 30 s."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "regex": {
                    "type": "boolean",
                    "default": False,
                    "description": "Treat the query as a regular expression.",
                },
                "case_sensitive": {"type": "boolean", "default": True},
                "include_sensitive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Requires explicit approval and includes sensitive paths.",
                },
                "file_glob": {"type": "string", "default": "*"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10000},
                "max_files": {"type": "integer", "minimum": 1, "maximum": _MAX_FILES},
                "max_entries": {"type": "integer", "minimum": 1, "maximum": _MAX_ENTRIES},
                "max_file_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_FILE_BYTES,
                },
                "max_total_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_TOTAL_BYTES,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = _workspace_paths(workspace)

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._execute_sync, arguments)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        return await run_in_process(self._execute_sync, arguments)

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        query = require_string(arguments, "query")
        raw_path = arguments.get("path", ".")
        file_glob = arguments.get("file_glob", "*")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        if not isinstance(file_glob, str) or not file_glob:
            raise ToolArgumentError("'file_glob' must be a non-empty string")
        use_regex = optional_bool(arguments, "regex", False)
        case_sensitive = optional_bool(arguments, "case_sensitive", True)
        regex_line_chars = _MAX_REGEX_LINE_CHARS
        if use_regex:
            if len(query) > _MAX_REGEX_PATTERN_CHARS:
                raise ToolArgumentError("'query' exceeds the regex pattern length limit")
            try:
                re.compile(query)
            except re.error as exc:
                raise ToolArgumentError(
                    f"'query' is not a valid regular expression: {exc}"
                ) from exc
            regex_line_chars = _regex_line_chars(query, 0 if case_sensitive else re.IGNORECASE)
        include_sensitive = optional_bool(arguments, "include_sensitive", False)
        maximum = optional_int(arguments, "max_results", 1000, minimum=1, maximum=10000)
        max_files = optional_int(arguments, "max_files", 1000, minimum=1, maximum=_MAX_FILES)
        max_entries = optional_int(
            arguments,
            "max_entries",
            20_000,
            minimum=1,
            maximum=_MAX_ENTRIES,
        )
        max_file_bytes = optional_int(
            arguments,
            "max_file_bytes",
            1024 * 1024,
            minimum=1,
            maximum=_MAX_FILE_BYTES,
        )
        max_total_bytes = optional_int(
            arguments,
            "max_total_bytes",
            16 * 1024 * 1024,
            minimum=1,
            maximum=_MAX_TOTAL_BYTES,
        )

        root = self.paths.resolve(raw_path)
        if root.is_file():
            # A file is searched alone: its folder, for just that file (models often pass one).
            file_glob = glob.escape(self.paths.relative(root))
            root = root.parent
        if not root.is_dir():
            raise ToolError(f"path is not a directory: {root}")
        result = _search_files(
            self.paths,
            root,
            query,
            file_glob,
            case_sensitive,
            include_sensitive,
            use_regex,
            maximum,
            max_files,
            max_entries,
            max_file_bytes,
            max_total_bytes,
            regex_line_chars=regex_line_chars,
        )
        return json_result(result)
