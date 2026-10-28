"""Read a LaTeX log: every error with the file and line it happened at, and the warnings that
matter (undefined references and citations, overfull boxes, package warnings).

Lines are located from ``file:line:`` records (``-file-line-error``), from ``l.<n>`` and
``on input line <n>``, and otherwise from the stack of files TeX had open. TeX wraps log lines at
79 columns, so wrapped lines are joined first: a long Windows path is otherwise cut in two.
"""

from __future__ import annotations

import re

from agent_workspace.latex.issues import Issue, Severity

MAX_PRINT_LINE = 79
MAX_ISSUES = 300

_FILE_LINE = re.compile(r"(?P<file>[\w.\-~/]+):(?P<line>\d+):")
_DRIVE_PATH = re.compile(r"(?:^|(?<=[ \t]))(?P<path>[A-Za-z]:/[\w.\-~/ ]*)$")
_L_LINE = re.compile(r"(?:^|\s)l\.(\d+)")
_INPUT_LINE = re.compile(r"on input line (\d+)")
_LINES_RANGE = re.compile(r"at lines? (\d+)")
_OPENED_FILE = re.compile(r"\(((?:[A-Za-z]:)?[^\s()\"{}]+\.[A-Za-z0-9]{1,8})")
_WARNING_START = re.compile(
    r"^(?:LaTeX(?: Font)? Warning|Package [\w\-.]+ Warning|Class [\w\-.]+ Warning)"
)
_PACKAGE_CONTINUATION = re.compile(r"^\([\w\-.]+\)\s+\S")
_BOX_NEEDLES = ("Overfull \\hbox", "Underfull \\hbox", "Overfull \\vbox", "Underfull \\vbox")
_UNDEFINED_REFERENCE = re.compile(r"Reference [`'](?P<key>[^']*)' on page \d+ undefined")
_UNDEFINED_CITATION = re.compile(r"Citation [`'](?P<key>[^']*)' on page \d+ undefined")
_MISSING_FILE = re.compile(r"File [`'](?P<name>[^']+)' not found")
_RERUN = re.compile(r"Rerun to get|Label\(s\) may have changed|Please rerun|Rerun LaTeX")

# Error headers, most specific first: (needle, code, English summary).
_ERRORS: tuple[tuple[str, str, str], ...] = (
    ("Undefined control sequence", "undefined_control_sequence", "Undefined control sequence"),
    ("File ended while scanning use of", "file_ended", "An argument was never closed"),
    ("Runaway argument", "runaway_argument", "Runaway argument: a brace or \\end is missing"),
    ("Missing $ inserted", "missing_dollar", "Math outside math mode ($ missing)"),
    ("Missing { inserted", "missing_lbrace", "A { is missing"),
    ("Extra }, or forgotten", "extra_rbrace", "Unbalanced braces"),
    ("Paragraph ended before", "paragraph_ended", "A blank line inside an argument"),
    ("Missing \\begin{document}", "missing_begin_document", "Missing \\begin{document}"),
    ("Emergency stop", "emergency_stop", "Emergency stop"),
    ("Fatal error", "fatal_error", "Fatal error, no PDF produced"),
)


def unwrap_lines(content: str) -> list[str]:
    """Join the lines TeX wrapped at 79 columns with their continuation."""
    lines = content.splitlines()
    out: list[str] = []
    buffer = ""
    for index, line in enumerate(lines):
        buffer += line
        wrapped = len(line) == MAX_PRINT_LINE or len(line.encode("utf-8")) == MAX_PRINT_LINE
        following = lines[index + 1] if index + 1 < len(lines) else None
        starts_record = (
            following is None
            or not following
            or following.startswith("!")
            or bool(re.match(r"l\.\d", following))
        )
        if wrapped and not starts_record:
            continue
        out.append(buffer)
        buffer = ""
    if buffer:
        out.append(buffer)
    return out


def find_file_line(text: str) -> tuple[str, int] | None:
    """The first ``file:line:`` record in a line (``./main.tex:12:``, ``C:/dir/a.tex:3:``)."""
    for match in _FILE_LINE.finditer(text):
        name = match.group("file")
        drive = _DRIVE_PATH.search(text[: match.end("file")])
        if drive is not None and drive.start("path") <= match.start("file"):
            name = drive.group("path")
        if ".tex" in name or name.startswith("./"):
            return name.removeprefix("./"), int(match.group("line"))
    return None


def _strip_file_line(header: str) -> str:
    """A ``file:line: message`` record's message; other headers unchanged."""
    if find_file_line(header) is None:
        return header
    match = re.search(r":\d+:\s*(.+)$", header)
    return match.group(1) if match else header


class _Block:
    def __init__(self, header: str, context_file: str | None, kind: str) -> None:
        self.header = header
        self.body: list[str] = []
        self.context_file = context_file
        self.kind = kind  # "error", "box" or "warning"
        self.located = False

    @property
    def warning(self) -> bool:
        return self.kind != "error"

    def takes(self, line: str) -> bool:
        """Whether the line still belongs to this record."""
        if self.kind == "box":
            return bool(line.strip())
        if self.kind == "warning":
            return bool(_PACKAGE_CONTINUATION.match(line))
        if line == "?" or len(self.body) >= 12 or (self.located and not line.strip()):
            return False
        if _L_LINE.match(line):
            self.located = True
        return True


def _track_files(line: str, stack: list[str]) -> None:
    """Follow the files TeX opens ``(./chapter.tex`` and closes ``)`` on one log line."""
    position = 0
    while position < len(line):
        character = line[position]
        if character == "(":
            match = _OPENED_FILE.match(line, position)
            if match is not None:
                stack.append(match.group(1))
                position = match.end()
                continue
            stack.append("")
        elif character == ")" and stack:
            stack.pop()
        position += 1


def _record_kind(line: str) -> str | None:
    """Whether a log line starts an error, a box warning or another warning."""
    if any(needle in line for needle in _BOX_NEEDLES):
        return "box"
    if line.startswith("!") or (find_file_line(line) is not None and not line.startswith("(")):
        return "error"
    if _WARNING_START.match(line):
        return "warning"
    return None


def _current_file(stack: list[str]) -> str | None:
    for name in reversed(stack):
        if name:
            return name
    return None


def parse_log(content: str) -> list[Issue]:
    """The problems a log reports, in the order they happened."""
    blocks: list[_Block] = []
    current: _Block | None = None
    stack: list[str] = []
    for raw in unwrap_lines(content):
        line = raw.rstrip()
        kind = _record_kind(line)
        if kind is not None:
            if current is not None:
                blocks.append(current)
            current = _Block(line, _current_file(stack), kind)
            continue
        if current is not None:
            if current.takes(line):
                current.body.append(line)
                continue
            blocks.append(current)
            current = None
        _track_files(line, stack)
    if current is not None:
        blocks.append(current)
    issues: list[Issue] = []
    seen: set[tuple[str, str | None, int | None]] = set()
    for block in blocks:
        issue = _classify(block)
        if issue is None:
            continue
        if issue.code in {"emergency_stop", "fatal_error"}:
            # The stop follows the real error; it only adds where it happened.
            earlier = next((item for item in reversed(issues) if item.severity == "error"), None)
            if earlier is not None:
                if earlier.line is None and issue.line is not None:
                    earlier.file, earlier.line = issue.file or earlier.file, issue.line
                continue
        key = (issue.message, issue.file, issue.line)
        if key in seen:
            continue
        seen.add(key)
        issues.append(issue)
        if len(issues) >= MAX_ISSUES:
            break
    return issues


def _classify(block: _Block) -> Issue | None:
    lines = [block.header, *block.body]
    raw = "\n".join(lines).strip()
    header = _strip_file_line(block.header).strip()
    file: str | None = None
    line: int | None = None
    for text in lines:
        found = find_file_line(text)
        if found is not None:
            file, line = found
            break
    if line is None:
        for pattern in (_L_LINE, _INPUT_LINE, _LINES_RANGE):
            match = next((pattern.search(text) for text in lines if pattern.search(text)), None)
            if match is not None:
                line = int(match.group(1))
                break
    if file is None and block.context_file:
        file = block.context_file.removeprefix("./")
    if line is not None and line <= 0:
        line = None
    if block.warning:
        return _warning(block, header, raw, file, line)
    code, message = "latex_error", header.removeprefix("! ").strip()
    params: dict[str, str] = {}
    for needle, error_code, summary in _ERRORS:
        if needle in header:
            code, message = error_code, summary
            break
    else:
        missing = _MISSING_FILE.search(header)
        if missing is not None:
            code, message = "file_not_found", f"File {missing.group('name')} not found"
            params["name"] = missing.group("name")
        elif "Environment" in header and "undefined" in header:
            code = "environment_undefined"
            environment = re.search(r"Environment (\S+) undefined", header)
            if environment:
                params["name"] = environment.group(1)
        elif "Package" in header and "Error" in header:
            code = "package_error"
        elif "Font" in header and "not" in header and "found" in header.lower():
            code = "font_not_found"
        elif "Unable to load picture" in header:
            code = "file_not_found"
    if code == "undefined_control_sequence":
        command = _undefined_command(block.body)
        if command:
            params["command"] = command
            message = f"Undefined control sequence {command}"
    if not message:
        message = header or "LaTeX error"
    return Issue(
        "error", code, message, file=file, line=line, params=params, raw=raw, source="compile"
    )


def _undefined_command(body: list[str]) -> str | None:
    """The command TeX did not know: the last control word on the ``l.<n>`` line."""
    for text in body:
        match = _L_LINE.search(text)
        if match is not None:
            words: list[str] = re.findall(r"\\[A-Za-z@]+", text[match.end() :])
            if words:
                return words[-1]
    return None


def _warning(
    block: _Block, header: str, raw: str, file: str | None, line: int | None
) -> Issue | None:
    text = " ".join(part.strip() for part in [block.header, *block.body])
    severity: Severity = "warning"
    params: dict[str, str] = {}
    if "Overfull" in header or "Underfull" in header:
        code = "overfull_box" if "Overfull" in header else "underfull_box"
        if code == "underfull_box":
            severity = "info"
        amount = re.search(r"\(([\d.]+pt) too (?:wide|high)\)", header)
        if amount:
            params["amount"] = amount.group(1)
        message = header
    elif (found := _UNDEFINED_REFERENCE.search(text)) is not None:
        code, params["key"] = "reference_undefined", found.group("key")
        message = f"Reference {found.group('key')} is undefined"
    elif (found := _UNDEFINED_CITATION.search(text)) is not None:
        code, params["key"] = "citation_undefined", found.group("key")
        message = f"Citation {found.group('key')} is undefined"
    elif "There were undefined references" in text or "Label(s) may have changed" in text:
        return None  # restated by the per-reference warnings, or settled by another pass
    elif "Font Warning" in header:
        code, severity, message = "font_warning", "info", text
    else:
        code, message = "latex_warning", text
    return Issue(severity, code, message[:500], file=file, line=line, params=params, raw=raw)


def needs_rerun(content: str) -> bool:
    """The log asks for another pass (cross-references or a bibliography changed)."""
    return bool(_RERUN.search(content))


def stderr_locations(stderr: str) -> list[tuple[str, int]]:
    """Tectonic's ``error: chapters/a.tex:12: message`` lines, as (file, line)."""
    found: list[tuple[str, int]] = []
    for text in stderr.splitlines():
        rest = text.strip().removeprefix("error: ")
        if rest == text.strip():
            continue
        parts = rest.rsplit(":", 2)
        if len(parts) == 3 and parts[1].strip().isdigit() and parts[0].strip():
            found.append((parts[0].strip(), int(parts[1].strip())))
    return found
