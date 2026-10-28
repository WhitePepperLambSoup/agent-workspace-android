# ruff: noqa: RUF001 -- the rules look for full-width punctuation in Chinese sources on purpose.
"""Source rules for LaTeX documents, Chinese ones in particular: mistakes that compile without an
error but print the wrong thing, or that fail later with a confusing message.

Each rule reads one file (``check_source``) or the whole folder (``check_project``: references,
labels and the bibliography). Rules with a safe mechanical fix rewrite the text (``fix``); the
others only report, since fixing them needs a decision or information the file does not hold.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from agent_workspace.latex.issues import Issue, Severity

MAX_CHECK_CHARS = 2 * 1024 * 1024


@dataclass(frozen=True)
class RuleInfo:
    id: str
    description: str
    default_enabled: bool = True
    fixable: bool = False


RULES: dict[str, RuleInfo] = {
    rule.id: rule
    for rule in (
        RuleInfo(
            "percent", "a bare % after a number comments out the rest of the line", True, True
        ),
        RuleInfo("italic", "\\textit or \\emph around Chinese text (Chinese fonts have no italic)"),
        RuleInfo("bold", "\\textbf whose argument holds a table's &"),
        RuleInfo("float", "a figure or table placed with [ht] may drift away from its text"),
        RuleInfo("color", "mixed colours such as blue!60 without the xcolor package", True, True),
        RuleInfo("numbers", "numbers with ten or more decimals (unrounded output)", True, True),
        RuleInfo(
            "paragraph", "prose lines without a blank line between them run together", True, True
        ),
        RuleInfo("missing_end", "\\begin{document} without \\end{document}", True, True),
        RuleInfo("bom", "the file starts with a UTF-8 byte order mark", True, True),
        RuleInfo("refs", "\\ref and \\cite keys without a \\label or bibliography entry"),
        RuleInfo("cjk_spacing", "no space between Chinese and Latin letters", False, True),
        RuleInfo("bib_format", "authors not separated by 'and'; DOI fields with a URL", True, True),
        RuleInfo("bib_fields", "bibliography entries missing required (GB/T 7714) fields"),
    )
}

_REF_COMMANDS = frozenset({"ref", "pageref", "eqref", "autoref", "nameref", "cref", "Cref", "vref"})
_CITE_COMMANDS = frozenset(
    {
        "cite",
        "citep",
        "citet",
        "parencite",
        "textcite",
        "autocite",
        "footcite",
        "citealp",
        "citealt",
        "citeauthor",
        "citeyear",
        "citenum",
        "nocite",
        "supercite",
    }
)
_CJK = re.compile(
    "[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef"
    "\U00020000-\U0002a6df\U0002f800-\U0002fa1f]"
)


def contains_cjk(text: str) -> bool:
    return _CJK.search(text) is not None


def comment_start(line: str) -> int | None:
    """Where a ``%`` comment starts on a line (``\\%`` is a percent sign, ``\\\\%`` a comment)."""
    index = 0
    while index < len(line):
        character = line[index]
        if character == "\\":
            index += 2
            continue
        if character == "%":
            return index
        index += 1
    return None


def _code(line: str) -> str:
    start = comment_start(line)
    return line if start is None else line[:start]


def _issue(
    rule: str,
    code: str,
    severity: Severity,
    message: str,
    file: str,
    line: int | None = None,
    column: int | None = None,
    **params: object,
) -> Issue:
    return Issue(
        severity,
        code,
        message,
        source="rule",
        file=file,
        line=line,
        column=column,
        params=dict(params),
        rule=rule,
        fixable=RULES[rule].fixable,
    )


# -- per-file rules -------------------------------------------------------------------------------


def _percent(text: str, file: str) -> list[Issue]:
    found: list[Issue] = []
    for number, line in enumerate(text.splitlines(), 1):
        for column in _bare_percents(line):
            found.append(
                _issue(
                    "percent",
                    "percent",
                    "suggestion",
                    "a % after a number starts a comment; the rest of the line is dropped "
                    "(write \\%)",
                    file,
                    number,
                    column + 1,
                )
            )
    return found


def _bare_percents(line: str) -> list[int]:
    """Indexes of ``%`` signs that look like a percentage (``71% of``) rather than a comment."""
    positions: list[int] = []
    index = 0
    while index < len(line):
        character = line[index]
        if character == "\\":
            index += 2
            continue
        if character == "%":
            previous = line[index - 1] if index > 0 else ""
            digit_before = previous.isdigit() or (
                previous == " " and index > 1 and line[index - 2].isdigit()
            )
            following = line[index + 1] if index + 1 < len(line) else ""
            if digit_before and (
                not following
                or (following.isascii() and (following.isalnum() or following in " ("))
                or following == "（"
                or contains_cjk(following)
            ):
                positions.append(index)
            else:
                break  # a real comment: nothing after it is source
        index += 1
    return positions


def _braced_argument(line: str, brace: int) -> tuple[int, int] | None:
    """Start and end of the ``{...}`` group opening at ``brace`` on one line."""
    depth = 0
    index = brace
    while index < len(line):
        character = line[index]
        if character == "\\":
            index += 2
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return brace + 1, index
        index += 1
    return None


def _italic(text: str, file: str) -> list[Issue]:
    found: list[Issue] = []
    for number, line in enumerate(text.splitlines(), 1):
        code = _code(line)
        for match in re.finditer(r"\\(textit|emph)\s*\{", code):
            span = _braced_argument(code, match.end() - 1)
            if span is not None and contains_cjk(code[span[0] : span[1]]):
                found.append(
                    _issue(
                        "italic",
                        "italic",
                        "warning",
                        f"\\{match.group(1)} around Chinese text: Chinese fonts have no italic "
                        "face; use \\textbf or another emphasis",
                        file,
                        number,
                        match.start() + 1,
                        command=match.group(1),
                    )
                )
    return found


def _bold(text: str, file: str) -> list[Issue]:
    found: list[Issue] = []
    for number, line in enumerate(text.splitlines(), 1):
        code = _code(line)
        for match in re.finditer(r"\\textbf\{", code):
            span = _braced_argument(code, match.end() - 1)
            end = span[1] if span else len(code)
            inner = code[match.end() : end]
            ampersand = _unescaped(inner, "&")
            if ampersand is not None:
                found.append(
                    _issue(
                        "bold",
                        "bold",
                        "warning",
                        "\\textbf holds a table's &, which fails with 'File ended while "
                        "scanning use of \\textbf'; use {\\bfseries ...} in table cells",
                        file,
                        number,
                        match.end() + ampersand + 1,
                    )
                )
    return found


def _unescaped(text: str, character: str) -> int | None:
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == character:
            return index
        index += 1
    return None


def _float(text: str, file: str) -> list[Issue]:
    found: list[Issue] = []
    for number, line in enumerate(text.splitlines(), 1):
        code = _code(line)
        for match in re.finditer(r"\\begin\{(figure\*?|table\*?)\}\s*\[([^\]]*)\]", code):
            spec = match.group(2)
            if spec and "H" not in spec:
                found.append(
                    _issue(
                        "float",
                        "float",
                        "info",
                        f"\\begin{{{match.group(1)}}}[{spec}] may float away from its text; "
                        "use [H] with \\usepackage{float} to keep it here",
                        file,
                        number,
                        match.start(2) + 1,
                        env=match.group(1),
                        spec=spec,
                    )
                )
    return found


def _color(text: str, file: str) -> list[Issue]:
    has_xcolor = False
    first: tuple[int, int] | None = None
    for number, line in enumerate(text.splitlines(), 1):
        code = _code(line)
        if re.search(r"\\(?:usepackage|RequirePackage)(?:\[[^\]]*\])?\{[^}]*\bxcolor\b", code):
            has_xcolor = True
        if first is None:
            mixed = re.search(r"[A-Za-z]!\d", code)
            if mixed is not None:
                first = (number, mixed.start() + 2)
    if first is None or has_xcolor or not re.search(r"\\documentclass", text):
        return []
    return [
        _issue(
            "color",
            "color",
            "error",
            "mixed colours like blue!60 need the xcolor package, which is not loaded",
            file,
            first[0],
            first[1],
        )
    ]


_LONG_NUMBER = re.compile(r"(?<![\w.])\d+\.\d{10,}")


def _round(number: str) -> str:
    rounded = f"{round(float(number), 2):.2f}".rstrip("0").rstrip(".")
    return rounded or "0"


def _numbers(text: str, file: str) -> list[Issue]:
    found: list[Issue] = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in _LONG_NUMBER.finditer(_code(line)):
            value = match.group(0)
            decimals = len(value.split(".", 1)[1])
            found.append(
                _issue(
                    "numbers",
                    "numbers",
                    "error",
                    f"{value} has {decimals} decimals, an unrounded number from a program; "
                    f"round it (e.g. {_round(value)})",
                    file,
                    number,
                    match.start() + 1,
                    number=value,
                    rounded=_round(value),
                )
            )
    return found


def is_prose_line(line: str) -> bool:
    """A line of running text, not a command-only, table or list line."""
    if line.startswith("\\item"):
        return False
    if line.startswith("\\"):
        rest = re.sub(r"^\\[A-Za-z@]+\*?", "", line)
        while True:
            stripped = rest.lstrip()
            if stripped.startswith("["):
                end = stripped.find("]")
                if end < 0:
                    return False
                rest = stripped[end + 1 :]
            elif stripped.startswith("{"):
                end = stripped.find("}")
                if end < 0:
                    return False
                rest = stripped[end + 1 :]
            else:
                break
        remaining = rest.strip()
        if not remaining or remaining.startswith("\\") or remaining.startswith("item"):
            return False
        return contains_cjk(remaining) or any(c.isascii() and c.isalnum() for c in remaining)
    if "&" in line:
        return False
    return contains_cjk(line) or any(c.isascii() and c.isalnum() for c in line)


def _glued_runs(text: str) -> list[tuple[int, int]]:
    """Runs of adjacent prose lines (first and last line number) inside the document body."""
    runs: list[tuple[int, int]] = []
    previous: tuple[int, str] | None = None
    in_body = "\\begin{document}" not in text
    verbatim = False
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if "\\begin{document}" in stripped:
            in_body = True
        if re.match(r"\\begin\{(verbatim|lstlisting|minted|equation|align|tabular)", stripped):
            verbatim = True
        if re.match(r"\\end\{(verbatim|lstlisting|minted|equation|align|tabular)", stripped):
            verbatim = False
            previous = None
            continue
        if not stripped or stripped.startswith("%") or verbatim or not in_body:
            previous = None
            continue
        if not is_prose_line(stripped):
            previous = None
            continue
        if previous is not None and len(previous[1]) >= 4 and len(stripped) >= 4:
            if runs and runs[-1][1] == previous[0]:
                runs[-1] = (runs[-1][0], number)
            else:
                runs.append((previous[0], number))
        previous = (number, stripped)
    return runs


def _paragraph(text: str, file: str) -> list[Issue]:
    # Chinese prose written one sentence per line is joined by LaTeX into one paragraph,
    # which is often what was meant for English (lines are wrapped by the editor) but rarely
    # for Chinese, where a line break inside a paragraph is unusual.
    if not contains_cjk(text):
        return []
    return [
        _issue(
            "paragraph",
            "paragraph",
            "info",
            f"lines {start}-{end} have no blank line between them, so LaTeX joins them into "
            "one paragraph; add a blank line where a new paragraph starts",
            file,
            start,
            start=start,
            end=end,
        )
        for start, end in _glued_runs(text)
    ]


def _missing_end(text: str, file: str) -> list[Issue]:
    lines = [_code(line) for line in text.splitlines()]
    if any("\\begin{document}" in line for line in lines) and not any(
        "\\end{document}" in line for line in lines
    ):
        return [
            _issue(
                "missing_end",
                "missing_end",
                "error",
                "\\begin{document} has no \\end{document}",
                file,
                len(lines) or 1,
            )
        ]
    return []


def _bom(text: str, file: str) -> list[Issue]:
    if text.startswith("\ufeff"):
        return [
            _issue(
                "bom",
                "bom",
                "warning",
                "the file starts with a UTF-8 byte order mark",
                file,
                1,
                1,
            )
        ]
    return []


def _cjk_boundaries(line: str) -> list[int]:
    positions: list[int] = []
    dollars = 0
    for index in range(1, len(line)):
        if line[index - 1] == "$":
            dollars += 1
        if dollars % 2 == 1:
            continue
        previous, current = line[index - 1], line[index]
        latin_previous = previous.isascii() and previous.isalpha()
        latin_current = current.isascii() and current.isalpha()
        boundary = (contains_cjk(previous) and latin_current) or (
            latin_previous and contains_cjk(current)
        )
        if boundary and not _CJK_PUNCTUATION.search(previous + current):
            positions.append(index)
    return positions


_CJK_PUNCTUATION = re.compile("[\u3000-\u303f\uff00-\uffef]")


def _cjk_spacing(text: str, file: str) -> list[Issue]:
    found: list[Issue] = []
    for number, line in enumerate(text.splitlines(), 1):
        code = _code(line)
        if code.lstrip().startswith("\\") and not contains_cjk(code):
            continue
        positions = _cjk_boundaries(code)
        if positions:
            found.append(
                _issue(
                    "cjk_spacing",
                    "cjk_spacing",
                    "info",
                    "no space between Chinese and Latin letters",
                    file,
                    number,
                    positions[0] + 1,
                    count=len(positions),
                )
            )
    return found


def _refs_in_file(text: str, file: str) -> list[Issue]:
    """References to labels of this file only; the folder check settles the rest."""
    return []


_FILE_RULES: dict[str, Callable[[str, str], list[Issue]]] = {
    "percent": _percent,
    "italic": _italic,
    "bold": _bold,
    "float": _float,
    "color": _color,
    "numbers": _numbers,
    "paragraph": _paragraph,
    "missing_end": _missing_end,
    "bom": _bom,
    "cjk_spacing": _cjk_spacing,
}


def enabled_rules(settings: Mapping[str, bool] | None = None) -> set[str]:
    settings = settings or {}
    return {rule for rule, info in RULES.items() if settings.get(rule, info.default_enabled)}


def check_source(text: str, file: str, enabled: set[str] | None = None) -> list[Issue]:
    """The per-file rules' findings for one ``.tex`` file."""
    rules = enabled_rules() if enabled is None else enabled
    if len(text) > MAX_CHECK_CHARS:
        return [
            Issue(
                "info",
                "too_large",
                "the file is larger than 2 MB; the source rules skipped it",
                source="rule",
                file=file,
            )
        ]
    found: list[Issue] = []
    for rule, check in _FILE_RULES.items():
        if rule in rules:
            found.extend(check(text, file))
    return found


# -- folder rules ---------------------------------------------------------------------------------


def command_arguments(text: str, commands: frozenset[str]) -> list[tuple[str, str, int, int]]:
    """Every ``\\command[opt]{key,key}`` of the given commands outside comments, as
    (command, key, line, column)."""
    found: list[tuple[str, str, int, int]] = []
    pattern = re.compile(r"\\([A-Za-z@]+)\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]*)\}")
    for number, line in enumerate(text.splitlines(), 1):
        for match in pattern.finditer(_code(line)):
            if match.group(1) not in commands:
                continue
            for key in match.group(2).split(","):
                if key.strip():
                    found.append((match.group(1), key.strip(), number, match.start(2) + 1))
    return found


def labels(text: str) -> list[tuple[str, int]]:
    return [(key, line) for _, key, line, _ in command_arguments(text, frozenset({"label"}))]


def check_project(
    sources: Mapping[str, str],
    bibs: Mapping[str, str],
    enabled: set[str] | None = None,
    *,
    has_bibliography: bool | None = None,
) -> list[Issue]:
    """Rules over the whole folder: dangling references and citations, duplicate labels,
    unused macros, and the bibliography's entries."""
    rules = enabled_rules() if enabled is None else enabled
    found: list[Issue] = []
    if "refs" in rules:
        found.extend(_refs(sources, bibs, has_bibliography))
    records = {file: parse_bib_records(text) for file, text in bibs.items()}
    if "bib_format" in rules:
        found.extend(_bib_format(records))
    if "bib_fields" in rules:
        found.extend(_bib_fields(records, uses_gbt7714(sources)))
    return found


def _refs(
    sources: Mapping[str, str], bibs: Mapping[str, str], has_bibliography: bool | None
) -> list[Issue]:
    found: list[Issue] = []
    defined: dict[str, tuple[str, int]] = {}
    for file, text in sources.items():
        for key, line in labels(text):
            if key in defined:
                earlier_file, earlier_line = defined[key]
                found.append(
                    _issue(
                        "refs",
                        "label_duplicate",
                        "warning",
                        f"\\label{{{key}}} is defined twice "
                        f"(also at {earlier_file}:{earlier_line})",
                        file,
                        line,
                        key=key,
                        other=f"{earlier_file}:{earlier_line}",
                    )
                )
            else:
                defined[key] = (file, line)
    keys = {record.key for text in bibs.values() for record in parse_bib_records(text)}
    inline_items = {
        key
        for text in sources.values()
        for key in re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", text)
    }
    keys |= inline_items
    check_citations = (
        bool(bibs) or bool(inline_items) if has_bibliography is None else has_bibliography
    )
    for file, text in sources.items():
        for command, key, line, column in command_arguments(text, _REF_COMMANDS):
            if key not in defined and "#" not in key:
                found.append(
                    _issue(
                        "refs",
                        "ref_undefined",
                        "error",
                        f"\\{command}{{{key}}} has no \\label{{{key}}} in the folder",
                        file,
                        line,
                        column,
                        command=command,
                        key=key,
                    )
                )
        if not check_citations:
            continue
        for command, key, line, column in command_arguments(text, _CITE_COMMANDS):
            if key not in keys and key != "*" and "#" not in key:
                found.append(
                    _issue(
                        "refs",
                        "cite_undefined",
                        "warning",
                        f"\\{command}{{{key}}} has no bibliography entry {key}",
                        file,
                        line,
                        column,
                        command=command,
                        key=key,
                    )
                )
    everything = "\n".join(sources.values())
    for file, text in sources.items():
        for number, source_line in enumerate(text.splitlines(), 1):
            match = re.match(
                r"\s*\\(?:newcommand|renewcommand|providecommand)\*?\{?\\([A-Za-z@]+)", source_line
            )
            if match is None:
                continue
            name = match.group(1)
            if len(re.findall(rf"\\{re.escape(name)}(?![A-Za-z@])", everything)) <= 1:
                found.append(
                    _issue(
                        "refs",
                        "macro_unused",
                        "info",
                        f"\\{name} is defined but never used",
                        file,
                        number,
                        name=name,
                    )
                )
    return found


@dataclass
class BibField:
    name: str
    value: str
    start: int
    end: int
    line: int


@dataclass
class BibRecord:
    entry_type: str
    key: str
    line: int
    fields: list[BibField]

    def field(self, name: str) -> BibField | None:
        return next((f for f in self.fields if f.name == name and f.value.strip()), None)

    def has(self, *names: str) -> bool:
        return any(self.field(name) is not None for name in names)


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def parse_bib_records(text: str) -> list[BibRecord]:
    """Entries of a ``.bib`` file with the place of every field value, for checks and fixes."""
    records: list[BibRecord] = []
    position = 0
    while (at := text.find("@", position)) >= 0:
        match = re.match(r"@([A-Za-z]+)\s*([{(])", text[at:])
        if match is None:
            position = at + 1
            continue
        entry_type = match.group(1).lower()
        opening = match.group(2)
        closing = "}" if opening == "{" else ")"
        body_start = at + match.end()
        depth, index = 1, body_start
        while index < len(text) and depth:
            if text[index] == opening:
                depth += 1
            elif text[index] == closing:
                depth -= 1
            index += 1
        if depth:
            break
        body_end = index - 1
        position = index
        if entry_type in {"comment", "string", "preamble"}:
            continue
        comma = text.find(",", body_start, body_end)
        if comma < 0:
            continue
        key = text[body_start:comma].strip()
        if key:
            records.append(
                BibRecord(
                    entry_type, key, _line_of(text, at), _bib_fields_of(text, comma + 1, body_end)
                )
            )
    return records


def _bib_fields_of(text: str, start: int, end: int) -> list[BibField]:
    fields: list[BibField] = []
    index = start
    while index < end:
        while index < end and (text[index].isspace() or text[index] == ","):
            index += 1
        match = re.compile(r"([A-Za-z0-9_\-:.]+)\s*=\s*").match(text, index, end)
        if match is None:
            next_comma = text.find(",", index, end)
            if next_comma < 0:
                break
            index = next_comma + 1
            continue
        name = match.group(1).lower()
        line = _line_of(text, index)
        index = match.end()
        if index >= end:
            break
        if text[index] == "{":
            depth, cursor = 1, index + 1
            while cursor < end and depth:
                if text[cursor] == "{":
                    depth += 1
                elif text[cursor] == "}":
                    depth -= 1
                cursor += 1
            value_start, value_end, after = index + 1, max(cursor - 1, index + 1), cursor
        elif text[index] == '"':
            cursor, depth = index + 1, 0
            while cursor < end and not (text[cursor] == '"' and depth == 0):
                if text[cursor] == "{":
                    depth += 1
                elif text[cursor] == "}":
                    depth -= 1
                cursor += 1
            value_start, value_end, after = index + 1, cursor, min(cursor + 1, end)
        else:
            cursor = index
            while cursor < end and text[cursor] not in ",\n":
                cursor += 1
            value_start, value_end, after = index, cursor, cursor
        fields.append(BibField(name, text[value_start:value_end], value_start, value_end, line))
        index = after
        while index < end and text[index] != ",":
            index += 1
    return fields


_REQUIRED: dict[str, tuple[tuple[str, ...], ...]] = {
    "article": (("author",), ("title",), ("journal", "journaltitle"), ("year", "date")),
    "book": (("author", "editor"), ("title",), ("publisher",), ("year", "date")),
    "inbook": (("author", "editor"), ("title",), ("publisher",), ("year", "date")),
    "incollection": (("author",), ("title",), ("booktitle",), ("publisher",), ("year", "date")),
    "inproceedings": (("author",), ("title",), ("booktitle",), ("year", "date")),
    "conference": (("author",), ("title",), ("booktitle",), ("year", "date")),
    "proceedings": (("title",), ("year", "date")),
    "phdthesis": (("author",), ("title",), ("school", "institution"), ("year", "date")),
    "mastersthesis": (("author",), ("title",), ("school", "institution"), ("year", "date")),
    "thesis": (("author",), ("title",), ("school", "institution"), ("year", "date")),
    "techreport": (("author",), ("title",), ("institution",), ("year", "date")),
    "report": (("author",), ("title",), ("institution",), ("year", "date")),
    "patent": (("author",), ("title",), ("number",), ("year", "date")),
    "standard": (("title",), ("year", "date")),
    "online": (("title",), ("url",)),
    "electronic": (("title",), ("url",)),
    "webpage": (("title",), ("url",)),
    "misc": (("title",),),
    "manual": (("title",),),
    "unpublished": (("author",), ("title",)),
}
_DOI_PREFIX = re.compile(r"^\s*(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def uses_gbt7714(sources: Mapping[str, str]) -> bool:
    return any(re.search(r"gbt7714|gb7714-2015", text, re.IGNORECASE) for text in sources.values())


def _author_problem(value: str) -> tuple[bool, bool]:
    """(separators that can be rewritten as 'and', a comma list that cannot be split safely)."""
    if re.search(r"\sand\s", value):
        return False, False
    fixable = bool(re.search("[，、;；]", value)) or (contains_cjk(value) and "," in value)
    return fixable, not fixable and value.count(",") > 1


def _split_authors(value: str) -> str:
    separators = "[，、;；,]" if contains_cjk(value) else "[，、;；]"
    return " and ".join(part.strip() for part in re.split(separators, value) if part.strip())


def _bib_format(records: Mapping[str, list[BibRecord]]) -> list[Issue]:
    found: list[Issue] = []
    for file, entries in records.items():
        for record in entries:
            for field in record.fields:
                if field.name in {"author", "editor"} and _author_problem(field.value)[0]:
                    found.append(
                        _issue(
                            "bib_format",
                            "bib_authors",
                            "warning",
                            f"{record.key}: the {field.name} list is not separated by 'and', so "
                            "BibTeX reads it as one person",
                            file,
                            field.line,
                            key=record.key,
                            field=field.name,
                            suggestion=_split_authors(field.value),
                        )
                    )
                if field.name == "doi" and _DOI_PREFIX.match(field.value):
                    found.append(
                        _issue(
                            "bib_format",
                            "bib_doi_url",
                            "suggestion",
                            f"{record.key}: the doi field holds a URL; keep only 10.xxxx/...",
                            file,
                            field.line,
                            key=record.key,
                        )
                    )
    return found


def _bib_fields(records: Mapping[str, list[BibRecord]], gbt: bool) -> list[Issue]:
    found: list[Issue] = []
    seen: dict[str, tuple[str, int]] = {}
    for file, entries in records.items():
        for record in entries:
            if record.key in seen:
                other = seen[record.key]
                found.append(
                    _issue(
                        "bib_fields",
                        "bib_duplicate_key",
                        "warning",
                        f"the key {record.key} is used twice (also at {other[0]}:{other[1]})",
                        file,
                        record.line,
                        key=record.key,
                        other=f"{other[0]}:{other[1]}",
                    )
                )
            else:
                seen[record.key] = (file, record.line)
            missing = [
                alternatives[0]
                for alternatives in _REQUIRED.get(record.entry_type, ())
                if not record.has(*alternatives)
            ]
            if missing:
                found.append(
                    _issue(
                        "bib_fields",
                        "bib_missing_fields",
                        "warning",
                        f"{record.key} (@{record.entry_type}) lacks {', '.join(missing)}",
                        file,
                        record.line,
                        key=record.key,
                        type=record.entry_type,
                        fields=missing,
                    )
                )
            for field in record.fields:
                if field.name in {"author", "editor"} and _author_problem(field.value)[1]:
                    found.append(
                        _issue(
                            "bib_fields",
                            "bib_authors_ambiguous",
                            "warning",
                            f"{record.key}: separate the authors with 'and' "
                            "(Smith, John and Doe, Jane)",
                            file,
                            field.line,
                            key=record.key,
                        )
                    )
            year = record.field("year")
            if year is not None and not re.fullmatch(r"\d{4}[a-z]*", year.value.strip()):
                found.append(
                    _issue(
                        "bib_fields",
                        "bib_year",
                        "warning",
                        f"{record.key}: the year {year.value.strip()} is not a four-digit year",
                        file,
                        year.line,
                        key=record.key,
                        year=year.value.strip(),
                    )
                )
            if gbt:
                found.extend(_gbt_checks(record, file))
    return found


def _gbt_checks(record: BibRecord, file: str) -> list[Issue]:
    found: list[Issue] = []
    kind = record.entry_type

    def add(code: str, severity: Severity, message: str) -> None:
        found.append(
            _issue("bib_fields", code, severity, message, file, record.line, key=record.key)
        )

    if kind == "article" and not record.has("volume", "number"):
        add("gbt_volume", "suggestion", f"GB/T 7714: {record.key} lacks a volume or issue")
    if kind in {"article", "inproceedings", "incollection", "inbook"} and not record.has("pages"):
        add("gbt_pages", "suggestion", f"GB/T 7714: {record.key} lacks page numbers")
    if kind in {
        "book",
        "inbook",
        "incollection",
        "phdthesis",
        "mastersthesis",
        "thesis",
        "proceedings",
    } and not record.has("address", "location"):
        add("gbt_place", "warning", f"GB/T 7714: {record.key} lacks the place of publication")
    if record.has("url") and not record.has("urldate"):
        add("gbt_urldate", "warning", f"GB/T 7714: {record.key} lacks the access date (urldate)")
    return found


# -- fixes ----------------------------------------------------------------------------------------


def fix(text: str, rule: str) -> str | None:
    """The text with every finding of one rule fixed, or None when there is nothing to fix."""
    fixer = _FIXES.get(rule)
    if fixer is None:
        return None
    fixed = fixer(text)
    return fixed if fixed != text else None


def _fix_lines(text: str, change: Callable[[str], str]) -> str:
    lines = text.split("\n")
    return "\n".join(change(line) for line in lines)


def _fix_percent(text: str) -> str:
    def change(line: str) -> str:
        for index in reversed(_bare_percents(line)):
            line = line[:index] + "\\%" + line[index + 1 :]
        return line

    return _fix_lines(text, change)


def _fix_numbers(text: str) -> str:
    def change(line: str) -> str:
        start = comment_start(line)
        code, comment = (line, "") if start is None else (line[:start], line[start:])
        return _LONG_NUMBER.sub(lambda match: _round(match.group(0)), code) + comment

    return _fix_lines(text, change)


def _fix_paragraph(text: str) -> str:
    lines = text.split("\n")
    breaks = {number for start, end in _glued_runs(text) for number in range(start, end)}
    out: list[str] = []
    for number, line in enumerate(lines, 1):
        out.append(line)
        if number in breaks:
            out.append("")
    return "\n".join(out)


def _fix_missing_end(text: str) -> str:
    if not _missing_end(text, ""):
        return text
    return text.rstrip("\n") + "\n\\end{document}\n"


def _fix_bom(text: str) -> str:
    return text.removeprefix("\ufeff")


def _fix_color(text: str) -> str:
    if not _color(text, ""):
        return text
    return re.sub(
        r"(\\documentclass(?:\[[^\]]*\])?\{[^}]*\}[^\n]*\n)",
        lambda match: match.group(1) + "\\usepackage{xcolor}\n",
        text,
        count=1,
    )


def _fix_cjk_spacing(text: str) -> str:
    def change(line: str) -> str:
        start = comment_start(line)
        code, comment = (line, "") if start is None else (line[:start], line[start:])
        for index in reversed(_cjk_boundaries(code)):
            code = code[:index] + " " + code[index:]
        return code + comment

    return _fix_lines(text, change)


def _fix_bib_format(text: str) -> str:
    edits: list[tuple[int, int, str]] = []
    for record in parse_bib_records(text):
        for field in record.fields:
            if field.name in {"author", "editor"} and _author_problem(field.value)[0]:
                edits.append((field.start, field.end, _split_authors(field.value)))
            if field.name == "doi" and _DOI_PREFIX.match(field.value):
                edits.append((field.start, field.end, _DOI_PREFIX.sub("", field.value).strip()))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


_FIXES: dict[str, Callable[[str], str]] = {
    "percent": _fix_percent,
    "numbers": _fix_numbers,
    "paragraph": _fix_paragraph,
    "missing_end": _fix_missing_end,
    "bom": _fix_bom,
    "color": _fix_color,
    "cjk_spacing": _fix_cjk_spacing,
    "bib_format": _fix_bib_format,
}
