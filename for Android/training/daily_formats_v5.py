"""Distinct daily artifact subtypes and independent constrained semantic checks."""

from __future__ import annotations

import ast
import csv
import html
import io
import json
import re

from training.formats_v5 import (
    _children,
    _md_text,
    _nodes,
    _text,
    checked_html,
    checked_js_names,
    checked_markdown_lines,
    json_decoder,
    strict_json,
)

SUBTYPE_KINDS = {
    "agenda": {"markdown"},
    "settings": {"json"},
    "records": {"csv"},
    "guide": {"html"},
    "text_cleanup": {"python", "javascript"},
}


def checked_daily(kind, task):
    subtype = task.get("subtype")
    if subtype not in SUBTYPE_KINDS or kind not in SUBTYPE_KINDS[subtype]:
        raise ValueError("Daily subtype is not supported by this artifact format")
    if task.get("language") not in {"zh", "en"}:
        raise ValueError("Daily task language must be zh or en")
    if subtype == "agenda":
        if not task.get("title") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", task.get("date", "")):
            raise ValueError("Agenda needs a title and complete date")
        if not 2 <= len(task.get("sections", [])) <= 6:
            raise ValueError("Agenda needs two to six meaningful sections")
        if any(
            not section.get("heading") or not 1 <= len(section.get("bullets", [])) <= 6
            for section in task["sections"]
        ):
            raise ValueError("Agenda sections need a heading and bullet notes")
    elif subtype == "settings":
        if not isinstance(task.get("data"), dict) or not task["data"]:
            raise ValueError("Settings need an explicit structured object")
        json.dumps(task["data"], allow_nan=False)
    elif subtype == "records":
        columns = task.get("columns", [])
        if not 2 <= len(columns) <= 8 or len({column["name"] for column in columns}) != len(
            columns
        ):
            raise ValueError("Record fields must be distinct")
        if any(column["type"] not in {"str", "int", "bool"} for column in columns):
            raise ValueError("Unsupported record column type")
        if not 1 <= len(task.get("rows", [])) <= 8:
            raise ValueError("Records need one to eight explicit rows")
        for row in task["rows"]:
            if len(row) != len(columns) or any(
                type(value).__name__ != column["type"]
                for value, column in zip(row, columns, strict=True)
            ):
                raise ValueError("Record field types or row width differ from the contract")
    elif subtype == "guide":
        if (
            not task.get("title")
            or not 1 <= len(task.get("paragraphs", [])) <= 4
            or not 2 <= len(task.get("steps", [])) <= 6
        ):
            raise ValueError("Guide needs a title, paragraphs and ordered steps")
        if task.get("animation") not in {None, "pulse"}:
            raise ValueError("Only the declared pulse animation contract is supported")
    elif (
        not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", task.get("function_name", ""))
        or task.get("operation") != "strip_nonempty"
        or not isinstance(task.get("samples"), list)
        or any(not isinstance(item, str) for item in task["samples"])
    ):
        raise ValueError("Text cleanup requires explicit lines and a pure strip_nonempty function")
    return task


def render_daily(kind, task):
    checked_daily(kind, task)
    subtype = task["subtype"]
    if subtype == "agenda":
        date_label = "日期" if task["language"] == "zh" else "Date"
        lines = ["# " + _md_text(task["title"]), "", f"{date_label}: {task['date']}"]
        for section in task["sections"]:
            lines.extend(["", "## " + _md_text(section["heading"])])
            lines.extend("- " + _md_text(bullet) for bullet in section["bullets"])
        return "\n".join([*lines, ""])
    if subtype == "settings":
        return json.dumps(task["data"], ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if subtype == "records":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(column["name"] for column in task["columns"])
        writer.writerows(
            [str(value).lower() if type(value) is bool else value for value in row]
            for row in task["rows"]
        )
        return stream.getvalue()
    if subtype == "guide":
        title = html.escape(task["title"])
        animation = (
            "<style>@keyframes pulse { from { opacity: 0.6; } to { opacity: 1; } } "
            ".pulse { animation: pulse 1s ease-in-out infinite alternate; }</style>"
            if task.get("animation")
            else ""
        )
        paragraphs = "\n".join("<p>" + html.escape(value) + "</p>" for value in task["paragraphs"])
        steps = "".join("<li>" + html.escape(value) + "</li>" for value in task["steps"])
        return (
            '<!DOCTYPE html>\n<html lang="'
            + ("zh-CN" if task["language"] == "zh" else "en")
            + '"><head><meta charset="utf-8"><title>'
            + title
            + "</title>"
            + animation
            + '</head><body><h1 class="pulse">'
            + title
            + "</h1>\n"
            + paragraphs
            + "\n<ol>"
            + steps
            + "</ol></body></html>\n"
        )
    if kind == "python":
        return (
            f"TITLE = {task['title']!r}\nSAMPLES = {task['samples']!r}\n\n"
            f"def {task['function_name']}(lines):\n"
            "    return [line.strip() for line in lines if line.strip()]\n"
        )
    return (
        "export const TITLE = "
        + json.dumps(task["title"], ensure_ascii=False)
        + ";\nexport const SAMPLES = "
        + json.dumps(task["samples"], ensure_ascii=False)
        + f";\n\nexport function {task['function_name']}(lines) {{\n"
        + "  return lines.map(line => line.trim()).filter(line => line.length > 0);\n}\n"
    )


def _equal(value, expected):
    if type(value) is not type(expected):
        return False
    if isinstance(value, dict):
        return value.keys() == expected.keys() and all(
            _equal(value[key], expected[key]) for key in value
        )
    if isinstance(value, list):
        return len(value) == len(expected) and all(
            _equal(first, second) for first, second in zip(value, expected, strict=True)
        )
    return value == expected


def _agenda(content, task):
    lines = checked_markdown_lines(content)
    label = "日期" if task["language"] == "zh" else "Date"
    if len(lines) < 4 or not lines[0].startswith("# ") or not lines[1].startswith(label + ": "):
        raise ValueError("Agenda title and date are missing")
    sections = []
    for line in lines[2:]:
        if line.startswith("## "):
            sections.append({"heading": html.unescape(line[3:]), "bullets": []})
        elif line.startswith("- ") and sections:
            sections[-1]["bullets"].append(html.unescape(line[2:]))
        else:
            raise ValueError("Agenda contains text outside its requested section/bullet contract")
    return {
        "title": html.unescape(lines[0][2:]),
        "date": lines[1][len(label) + 2 :],
        "sections": sections,
    }


def _records(content, task):
    rows = list(csv.reader(io.StringIO(content, newline=""), strict=True))
    columns = task["columns"]
    if not rows or rows[0] != [column["name"] for column in columns]:
        raise ValueError("Record headers differ from the requested fields")
    decoded = []
    for row in rows[1:]:
        if len(row) != len(columns):
            raise ValueError("Record row width differs from its header")
        values = []
        for value, column in zip(row, columns, strict=True):
            if column["type"] == "str":
                values.append(value)
            elif column["type"] == "int" and re.fullmatch(r"[+-]?\d+", value):
                values.append(int(value))
            elif column["type"] == "bool" and value in {"true", "false"}:
                values.append(value == "true")
            else:
                raise ValueError("Record cell violates its independent declared type")
        decoded.append(values)
    return {"columns": columns, "rows": decoded}


def _guide(content, task):
    document, body, title = checked_html(content, guide=True, animation=task.get("animation"))
    headings, bodies, lists = (_nodes(document.root, tag) for tag in ("h1", "body", "ol"))
    if len(headings) != 1 or len(bodies) != 1 or len(lists) != 1:
        raise ValueError("Guide requires one heading, body and ordered instruction list")
    if [node["tag"] for node in _children(body)] != [
        "h1",
        *(["p"] * len(task["paragraphs"])),
        "ol",
    ]:
        raise ValueError("Guide body must contain only requested heading, paragraphs and steps")
    if any(node["tag"] != "li" for node in _children(lists[0])):
        raise ValueError("Guide ordered list contains unrelated elements")
    if _text(title) != _text(headings[0]):
        raise ValueError("Guide head title differs from its visible heading")
    if task.get("animation") and "pulse" not in headings[0]["attrs"].get("class", "").split():
        raise ValueError("The requested guide animation is not declared and applied")
    return {
        "title": _text(headings[0]),
        "paragraphs": [_text(node) for node in _nodes(bodies[0], "p")],
        "steps": [_text(node) for node in _nodes(lists[0], "li")],
    }


def _text_expression(node, environment):
    if isinstance(node, ast.Name) and node.id in environment:
        return environment[node.id]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "strip"
        and not node.args
        and not node.keywords
    ):
        value = _text_expression(node.func.value, environment)
        if isinstance(value, str):
            return value.strip()
    if isinstance(node, ast.ListComp) and len(node.generators) == 1:
        generator = node.generators[0]
        if isinstance(generator.target, ast.Name) and not generator.is_async:
            result = []
            for value in _text_expression(generator.iter, environment):
                scope = {**environment, generator.target.id: value}
                if all(_text_expression(condition, scope) for condition in generator.ifs):
                    result.append(_text_expression(node.elt, scope))
            return result
    raise ValueError("Text function falls outside the declared safe comprehension contract")


def _python_text(content, task):
    module = ast.parse(content)
    exports, function = {}, None
    for statement in module.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id in {"TITLE", "SAMPLES"}
            and statement.targets[0].id not in exports
        ):
            exports[statement.targets[0].id] = ast.literal_eval(statement.value)
        elif isinstance(statement, ast.FunctionDef) and function is None:
            function = statement
        else:
            raise ValueError("Text script has an unsafe or unrelated executable statement")
    if (
        set(exports) != {"TITLE", "SAMPLES"}
        or function is None
        or function.name != task["function_name"]
        or function.name in {"TITLE", "SAMPLES"}
    ):
        raise ValueError("Text script is missing the requested data or function")
    args = function.args
    if (
        function.decorator_list
        or function.returns
        or getattr(function, "type_params", [])
        or any(argument.annotation is not None for argument in args.args)
        or args.defaults
        or args.kw_defaults
        or args.posonlyargs
        or args.kwonlyargs
        or args.vararg
        or args.kwarg
        or len(args.args) != 1
        or len(function.body) != 1
        or not isinstance(function.body[0], ast.Return)
    ):
        raise ValueError("Text function must have one plain parameter and pure return")
    for probe in ([], ["  dynamic probe  ", "", " \t ", " second "], task["samples"]):
        expected = [value.strip() for value in probe if value.strip()]
        if _text_expression(function.body[0].value, {args.args[0].arg: probe}) != expected:
            raise ValueError("Text function does not trim and remove blank variable input lines")
    return exports


def _javascript_text(content, task):
    decoder, exports, remaining = json_decoder(), {}, content.strip()
    for _ in range(2):
        match = re.match(r"export\s+const\s+(TITLE|SAMPLES)\s*=\s*", remaining)
        if match is None or match[1] in exports:
            raise ValueError("Text module needs unique JSON TITLE and SAMPLES exports")
        value, end = decoder.raw_decode(remaining[match.end() :])
        exports[match[1]], remaining = value, remaining[match.end() + end :].lstrip()
        if not remaining.startswith(";"):
            raise ValueError("Text module literal export is incomplete")
        remaining = remaining[1:].lstrip()
    function = re.fullmatch(
        r"export\s+function\s+([A-Za-z_]\w*)\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\{(.*?)\}\s*",
        remaining,
        re.DOTALL,
    )
    if function is None or function[1] != task["function_name"]:
        raise ValueError("Text module requested function is missing or extra code exists")
    match = re.fullmatch(
        r"\s*return[ \t]+([A-Za-z_]\w*)\s*\.\s*map\s*\(\s*([A-Za-z_]\w*)\s*=>\s*([A-Za-z_]\w*)"
        r"\s*\.\s*trim\s*\(\s*\)\s*\)\s*\.\s*filter\s*\(\s*([A-Za-z_]\w*)\s*=>\s*([A-Za-z_]\w*)"
        r"\s*\.\s*length\s*>\s*0\s*\)\s*;\s*",
        function[3],
    )
    if match is None or match[1] != function[2] or match[2] != match[3] or match[4] != match[5]:
        raise ValueError("Text module must trim each line and filter empty strings")
    checked_js_names(function[1], function[2], *match.groups())
    return exports


def validate_daily(kind, content, task):
    checked_daily(kind, task)
    parsed, errors, subtype = None, [], task["subtype"]
    try:
        if subtype == "agenda":
            parsed, expected = (
                _agenda(content, task),
                {key: task[key] for key in ("title", "date", "sections")},
            )
        elif subtype == "settings":
            parsed, expected = strict_json(content), task["data"]
        elif subtype == "records":
            parsed, expected = (
                _records(content, task),
                {key: task[key] for key in ("columns", "rows")},
            )
        elif subtype == "guide":
            parsed, expected = (
                _guide(content, task),
                {key: task[key] for key in ("title", "paragraphs", "steps")},
            )
        else:
            parsed = (
                _python_text(content, task) if kind == "python" else _javascript_text(content, task)
            )
            expected = {"TITLE": task["title"], "SAMPLES": task["samples"]}
        if not _equal(parsed, expected):
            errors.append(
                "Parsed daily structure, typed data or text differs from the independent task"
            )
    except (ValueError, TypeError, KeyError, IndexError, SyntaxError, csv.Error) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {
        "valid": not errors,
        "errors": errors,
        "subtype": subtype,
        "parsed": parsed,
        "arbitrary_code_executed": False,
        "scope": "Requested daily document and restricted pure text processing contracts",
    }
