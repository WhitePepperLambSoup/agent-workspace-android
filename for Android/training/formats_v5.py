"""Synthetic daily artifact contracts with parsers, never arbitrary code execution.

Python and JavaScript have deliberately restricted pure-data/sum contracts.
Passing them does not establish correctness of arbitrary generated programs.
"""

# Chinese report labels intentionally use Chinese punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import ast
import csv
import html
import io
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

KINDS = ("markdown", "json", "csv", "html", "python", "javascript")
EXTENSIONS = dict(zip(KINDS, ("md", "json", "csv", "html", "py", "js"), strict=True))
JS_RESERVED = frozenset(
    [
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "implements",
        "import",
        "in",
        "instanceof",
        "interface",
        "let",
        "new",
        "null",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
        "eval",
        "arguments",
    ]
)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("JSON duplicate object fields are ambiguous")
        value[key] = item
    return value


def strict_json(content):
    return json.loads(content, object_pairs_hook=_unique_object)


def json_decoder():
    return json.JSONDecoder(object_pairs_hook=_unique_object)


def checked_js_names(*names):
    if any(
        name in JS_RESERVED or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in names
    ):
        raise ValueError("JavaScript function names and parameters must be legal identifiers")


def checked_markdown_lines(content):
    if (
        re.search(r"^(?: {4}|\t).*\S", content, re.MULTILINE)
        or "```" in content
        or "~~~" in content
        or re.search(r"<(?!br>)[^>]*>", content, re.IGNORECASE)
    ):
        raise ValueError("Requested Markdown must be visible, without code fences or HTML wrappers")
    return [line.strip() for line in content.splitlines() if line.strip()]


def checked_task(task):
    if not isinstance(task.get("title"), str) or not task["title"].strip():
        raise ValueError("title must be nonempty text")
    if type(task.get("require_citations")) is not bool:
        raise ValueError("require_citations must be boolean")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", task.get("function_name", "")):
        raise ValueError("function_name must be an identifier")
    items = task.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 8:
        raise ValueError("items must contain one to eight facts")
    names = set()
    required = {"name", "quantity", "source"} if task["require_citations"] else {"name", "quantity"}
    for item in items:
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError("item fields differ from the requested fact contract")
        if not isinstance(item["name"], str) or not item["name"]:
            raise ValueError("item name must be nonempty text")
        if item["name"] in names:
            raise ValueError("item names must be unique")
        names.add(item["name"])
        if type(item["quantity"]) is not int or not 0 <= item["quantity"] <= 100000:
            raise ValueError("item quantity must be a nonnegative integer")
        if task["require_citations"]:
            if not isinstance(item["source"], str):
                raise ValueError("source must be text containing an absolute HTTPS document URL")
            parsed = urlsplit(item["source"])
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.fragment
            ):
                raise ValueError("source must be an absolute HTTPS document URL")
    return task


def _md_text(text):
    return (
        html.escape(text, quote=False)
        .replace("|", r"\|")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
    )


def render_artifact(kind, task):
    if task.get("subtype"):
        from training.daily_formats_v5 import render_daily

        return render_daily(kind, task)
    checked_task(task)
    if kind not in KINDS:
        raise ValueError("Unknown artifact format")
    items, cited = task["items"], task["require_citations"]
    total = sum(item["quantity"] for item in items)
    if kind == "json":
        return (
            json.dumps(
                {"title": task["title"], "items": items, "total": total},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
    if kind == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(["名称", "数量", *(["来源"] if cited else [])])
        writer.writerows(
            [item["name"], item["quantity"], *([item["source"]] if cited else [])] for item in items
        )
        writer.writerow(["合计", total, *([""] if cited else [])])
        return stream.getvalue()
    if kind == "markdown":
        lines = [
            "# " + _md_text(task["title"]),
            "",
            "| 名称 | 数量 |" + (" 来源 |" if cited else ""),
            "| --- | ---: |" + (" --- |" if cited else ""),
        ]
        for item in items:
            source = " [来源](" + item["source"] + ") |" if cited else ""
            lines.append(f"| {_md_text(item['name'])} | {item['quantity']} |" + source)
        return "\n".join([*lines, "", f"总数：{total}", ""])
    if kind == "html":
        heading = html.escape(task["title"])
        headers = "<th>名称</th><th>数量</th>" + ("<th>来源</th>" if cited else "")
        rows = []
        for item in items:
            cells = f"<td>{html.escape(item['name'])}</td><td>{item['quantity']}</td>"
            if cited:
                cells += f'<td><a href="{html.escape(item["source"], quote=True)}">来源</a></td>'
            rows.append("<tr>" + cells + "</tr>")
        return (
            '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f"<title>{heading}</title></head><body>\n<h1>{heading}</h1>\n"
            f"<table><thead><tr>{headers}</tr></thead><tbody>\n"
            + "\n".join(rows)
            + f"\n</tbody></table>\n<p>总数：{total}</p>\n</body></html>\n"
        )
    if kind == "python":
        return (
            f"TITLE = {task['title']!r}\nITEMS = {items!r}\n\n"
            f"def {task['function_name']}(items):\n"
            '    return sum(row["quantity"] for row in items)\n'
        )
    return (
        "export const TITLE = " + json.dumps(task["title"], ensure_ascii=False) + ";\n"
        "export const ITEMS = " + json.dumps(items, ensure_ascii=False) + ";\n\n"
        f"export function {task['function_name']}(items) {{\n"
        "  return items.reduce((sum, row) => sum + row.quantity, 0);\n}\n"
    )


def _int_text(value):
    if not re.fullmatch(r"[+-]?\d+", value.strip()):
        raise ValueError("quantity must be a complete integer cell")
    return int(value)


def _parse_csv(content, task):
    rows = list(csv.reader(io.StringIO(content, newline=""), strict=True))
    cited = task["require_citations"]
    headers = ["名称", "数量", *(["来源"] if cited else [])]
    if len(rows) < 3 or rows[0] != headers or rows[-1][0] != "合计":
        raise ValueError("CSV headers or total row are missing")
    if any(len(row) != len(headers) for row in rows[1:]):
        raise ValueError("CSV row width differs from its headers")
    if cited and rows[-1][2] != "":
        raise ValueError("CSV total row must not invent a source")
    items = [
        {"name": row[0], "quantity": _int_text(row[1]), **({"source": row[2]} if cited else {})}
        for row in rows[1:-1]
    ]
    return {"title": task["title"], "items": items, "total": _int_text(rows[-1][1])}


def _markdown_cells(line):
    if not line.startswith("|") or not line.endswith("|"):
        raise ValueError("Markdown data must be in a complete table")
    cells = re.split(r"(?<!\\)\|", line[1:-1])
    return [html.unescape(cell.strip().replace(r"\|", "|").replace("<br>", "\n")) for cell in cells]


def _parse_markdown(content, task):
    lines = checked_markdown_lines(content)
    headings = [html.unescape(line[2:]) for line in lines if line.startswith("# ")]
    table = [_markdown_cells(line) for line in lines if line.startswith("|")]
    cited = task["require_citations"]
    headers = ["名称", "数量", *(["来源"] if cited else [])]
    if len(headings) != 1 or len(table) < 3 or table[0] != headers:
        raise ValueError("Visible Markdown heading/table contract is missing")
    if any(not re.fullmatch(r":?-{3,}:?", cell) for cell in table[1]):
        raise ValueError("Markdown table separator is invalid")
    items = []
    for cells in table[2:]:
        if len(cells) != len(headers):
            raise ValueError("Markdown row width differs from headers")
        item = {"name": cells[0], "quantity": _int_text(cells[1])}
        if cited:
            citation = re.fullmatch(r"\[[^\]]+\]\((https://[^\s)]+)\)", cells[2])
            if citation is None:
                raise ValueError("Markdown fact lacks an explicit source link")
            item["source"] = citation[1]
        items.append(item)
    totals = [re.fullmatch(r"总数\s*[:：]\s*([+-]?\d+)", line) for line in lines]
    totals = [match for match in totals if match is not None]
    if len(totals) != 1:
        raise ValueError("Markdown requires one visible total")
    if len(lines) != 1 + len(table) + len(totals):
        raise ValueError("Markdown contains text outside the requested fact report")
    return {"title": headings[0], "items": items, "total": int(totals[0][1])}


class _Document(HTMLParser):
    void = frozenset(
        {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "document", "children": [], "attrs": {}}
        self.stack, self.errors = [self.root], []

    def handle_starttag(self, tag, attrs):
        if len(dict(attrs)) != len(attrs):
            self.errors.append("HTML duplicate attributes are ambiguous")
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in self.void:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if len(self.stack) == 1 or self.stack[-1]["tag"] != tag:
            self.errors.append("HTML closing tags are not balanced")
        else:
            self.stack.pop()

    def handle_data(self, data):
        self.stack[-1]["children"].append(data)


def _nodes(node, tag):
    result = []
    for child in node["children"]:
        if isinstance(child, dict) and child["tag"] not in {"head", "script", "style", "template"}:
            if child["tag"] == tag:
                result.append(child)
            result.extend(_nodes(child, tag))
    return result


def _text(node):
    return "".join(
        child if isinstance(child, str) else _text(child)
        for child in node["children"]
        if isinstance(child, str) or child["tag"] not in {"script", "style", "template"}
    )


def _children(node):
    if any(isinstance(child, str) and child.strip() for child in node["children"]):
        raise ValueError("HTML has visible text outside its requested semantic elements")
    return [child for child in node["children"] if isinstance(child, dict)]


def checked_html(content, *, guide=False, animation=None):
    document = _Document()
    document.feed(content)
    document.close()
    if (
        document.errors
        or len(document.stack) != 1
        or not re.match(r"\s*<!doctype html>", content, re.IGNORECASE)
    ):
        raise ValueError("HTML requires a complete balanced document")
    roots = _children(document.root)
    if len(roots) != 1 or roots[0]["tag"] != "html":
        raise ValueError("HTML requires exactly one complete html document root")
    root = roots[0]
    children = _children(root)
    if [child["tag"] for child in children] != ["head", "body"]:
        raise ValueError("HTML requires one head followed by one body")
    head, body = children
    allowed = {"html", "head", "body", "title", "meta", "h1", "p", "span", "strong", "em"}
    allowed |= (
        {"ol", "li", "style"} if guide else {"table", "thead", "tbody", "tr", "th", "td", "a"}
    )
    attributes = {"html": {"lang"}, "meta": {"charset"}, "h1": {"class"}, "a": {"href"}}

    def safe(node):
        if node["tag"] not in allowed or set(node["attrs"]) - attributes.get(node["tag"], set()):
            raise ValueError(
                "HTML contains hidden, active, remote or unsupported elements/attributes"
            )
        if node["tag"] == "meta" and str(node["attrs"].get("charset", "")).casefold() != "utf-8":
            raise ValueError("HTML meta contract permits only UTF-8 charset")
        if (
            node["tag"] == "h1"
            and "class" in node["attrs"]
            and (not guide or node["attrs"]["class"] != "pulse")
        ):
            raise ValueError("Only the declared pulse class is permitted")
        for child in node["children"]:
            if isinstance(child, dict):
                safe(child)

    safe(root)
    head_children = _children(head)
    titles = [node for node in head_children if node["tag"] == "title"]
    styles = [node for node in head_children if node["tag"] == "style"]
    if (
        len(titles) != 1
        or any(node["tag"] not in {"meta", "title", "style"} for node in head_children)
        or len(styles) != (1 if animation else 0)
    ):
        raise ValueError("HTML head must contain one title and only the declared style")
    if animation:
        css = _text(styles[0])
        # This complete bounded CSS contract proves changing visible opacity and positive duration;
        # it deliberately rejects arbitrary selectors, overrides, remote imports and hidden styles.
        match = re.fullmatch(
            r"\s*@keyframes\s+pulse\s*\{\s*from\s*\{\s*opacity\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*;?\s*\}"
            r"\s*to\s*\{\s*opacity\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*;?\s*\}\s*\}"
            r"\s*\.pulse\s*\{\s*animation\s*:\s*pulse\s+(\d+(?:\.\d+)?)(ms|s)\s+ease-in-out"
            r"\s+infinite\s+alternate\s*;?\s*\}\s*",
            css,
        )
        if match is None or float(match[1]) == float(match[2]) or float(match[3]) <= 0:
            raise ValueError(
                "Requested animation must visibly change opacity with positive duration"
            )
    return document, body, titles[0]


def _parse_html(content, task):
    document, body, title = checked_html(content)
    bodies, headings, tables = (_nodes(document.root, tag) for tag in ("body", "h1", "table"))
    if len(bodies) != 1 or len(headings) != 1 or len(tables) != 1:
        raise ValueError("HTML requires one visible body, heading and fact table")
    if [node["tag"] for node in _children(body)] != ["h1", "table", "p"]:
        raise ValueError("HTML body must contain only its heading, fact table and total")
    if _text(title) != _text(headings[0]):
        raise ValueError("HTML title and visible heading disagree")
    cited = task["require_citations"]
    headers = ["名称", "数量", *(["来源"] if cited else [])]
    rows = _nodes(tables[0], "tr")
    sections = _children(tables[0])
    if [node["tag"] for node in sections] != ["thead", "tbody"]:
        raise ValueError("HTML table must contain only its header and data sections")
    if len(_children(sections[0])) != 1 or any(
        node["tag"] != "tr" for section in sections for node in _children(section)
    ):
        raise ValueError("HTML fact table contains unrelated visible elements")
    if len(rows) < 2 or [_text(cell).strip() for cell in _nodes(rows[0], "th")] != headers:
        raise ValueError("HTML table headers differ from its contract")
    items = []
    for row in rows[1:]:
        cells = _nodes(row, "td")
        if [node["tag"] for node in _children(row)] != ["td"] * len(headers):
            raise ValueError("HTML data rows must contain exactly the requested cells")
        if len(cells) != len(headers):
            raise ValueError("HTML table row width differs from headers")
        item = {"name": _text(cells[0]), "quantity": _int_text(_text(cells[1]))}
        if cited:
            links = _nodes(cells[2], "a")
            if len(links) != 1 or _children(cells[2]) != links:
                raise ValueError("HTML fact requires exactly one source hyperlink")
            item["source"] = links[0]["attrs"].get("href")
        items.append(item)
    totals = [
        re.fullmatch(r"\s*总数\s*[:：]\s*([+-]?\d+)\s*", _text(node))
        for node in _nodes(bodies[0], "p")
    ]
    totals = [match for match in totals if match is not None]
    if len(totals) != 1:
        raise ValueError("HTML requires one visible total")
    return {"title": _text(headings[0]), "items": items, "total": int(totals[0][1])}


def _pure_expression(node, environment):
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)):
        return node.value
    if isinstance(node, ast.Name) and node.id in environment:
        return environment[node.id]
    if isinstance(node, ast.Subscript):
        return _pure_expression(node.value, environment)[_pure_expression(node.slice, environment)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _pure_expression(node.left, environment) + _pure_expression(node.right, environment)
    if isinstance(node, (ast.GeneratorExp, ast.ListComp)) and len(node.generators) == 1:
        generator = node.generators[0]
        if not isinstance(generator.target, ast.Name) or generator.ifs or generator.is_async:
            raise ValueError("Only an unconditional pure quantity comprehension is supported")
        return [
            _pure_expression(node.elt, {**environment, generator.target.id: item})
            for item in _pure_expression(generator.iter, environment)
        ]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sum"
        and len(node.args) == 1
        and not node.keywords
    ):
        if "sum" in environment:
            raise ValueError("Python quantity sum cannot shadow its builtin sum")
        return sum(_pure_expression(node.args[0], environment))
    raise ValueError("Expression falls outside the restricted pure Python contract")


def _parse_python(content, task):
    module = ast.parse(content)
    constants, function = {}, None
    for statement in module.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            name = statement.targets[0].id
            if name not in {"TITLE", "ITEMS"} or name in constants:
                raise ValueError("Python exports must be unique TITLE and ITEMS literals")
            constants[name] = ast.literal_eval(statement.value)
        elif isinstance(statement, ast.FunctionDef) and function is None:
            function = statement
        else:
            raise ValueError("Python contract forbids imports and unrelated executable statements")
    if (
        set(constants) != {"TITLE", "ITEMS"}
        or function is None
        or function.name != task["function_name"]
        or function.name in {"sum", "TITLE", "ITEMS"}
    ):
        raise ValueError("Python required literals or function are missing")
    arguments = function.args
    if (
        function.decorator_list
        or function.returns
        or getattr(function, "type_params", [])
        or any(argument.annotation is not None for argument in arguments.args)
        or arguments.defaults
        or arguments.kw_defaults
        or arguments.posonlyargs
        or arguments.kwonlyargs
        or arguments.vararg
        or arguments.kwarg
        or len(arguments.args) != 1
    ):
        raise ValueError("Python function must accept one plain items parameter")
    if len(function.body) != 1 or not isinstance(function.body[0], ast.Return):
        raise ValueError("Python contract requires one pure return expression")
    expression, name = function.body[0].value, arguments.args[0].arg
    for probe in ([], [{"quantity": 2}, {"quantity": 5}], constants["ITEMS"]):
        if _pure_expression(expression, {name: probe}) != sum(item["quantity"] for item in probe):
            raise ValueError("Python function does not compute quantity totals for variable input")
    return {
        "title": constants["TITLE"],
        "items": constants["ITEMS"],
        "total": _pure_expression(expression, {name: constants["ITEMS"]}),
    }


def _parse_javascript(content, task):
    decoder = json_decoder()
    remaining, exports = content.strip(), {}
    for _index in range(2):
        match = re.match(r"export\s+const\s+(TITLE|ITEMS)\s*=\s*", remaining)
        if match is None or match[1] in exports:
            raise ValueError("JavaScript must export unique JSON TITLE and ITEMS literals")
        value, end = decoder.raw_decode(remaining[match.end() :])
        exports[match[1]] = value
        remaining = remaining[match.end() + end :].lstrip()
        if not remaining.startswith(";"):
            raise ValueError("JavaScript export must end in a semicolon")
        remaining = remaining[1:].lstrip()
    match = re.fullmatch(
        r"export\s+function\s+([A-Za-z_]\w*)\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\{(.*?)\}\s*",
        remaining,
        re.DOTALL,
    )
    if match is None or match[1] != task["function_name"]:
        raise ValueError("JavaScript sum function export is missing or has extra executable code")
    summation = re.fullmatch(
        r"\s*return[ \t]+([A-Za-z_]\w*)\s*\.\s*reduce\s*\(\s*\(\s*([A-Za-z_]\w*)"
        r"\s*,\s*([A-Za-z_]\w*)"
        r"\s*\)\s*=>\s*([A-Za-z_]\w*)\s*\+\s*([A-Za-z_]\w*)\s*\.\s*quantity\s*,\s*0\s*\)\s*;\s*",
        match[3],
    )
    if summation is None or (summation[1], summation[2], summation[3]) != (
        match[2],
        summation[4],
        summation[5],
    ):
        raise ValueError("JavaScript function must reduce item.quantity using a zero sum")
    checked_js_names(match[1], match[2], *summation.groups())
    if summation[2] == summation[3]:
        raise ValueError("JavaScript reducer parameters must be distinct")
    return {
        "title": exports["TITLE"],
        "items": exports["ITEMS"],
        "total": sum(item["quantity"] for item in exports["ITEMS"]),
    }


def validate_artifact(kind, content, task, *, observed_urls=()):
    if task.get("subtype"):
        from training.daily_formats_v5 import validate_daily

        return validate_daily(kind, content, task)
    checked_task(task)
    errors, parsed = [], {}
    try:
        if kind == "json":
            parsed = strict_json(content)
        elif kind in {"markdown", "csv", "html", "python", "javascript"}:
            parser = {
                "markdown": _parse_markdown,
                "csv": _parse_csv,
                "html": _parse_html,
                "python": _parse_python,
                "javascript": _parse_javascript,
            }[kind]
            parsed = parser(content, task)
        else:
            raise ValueError("Unknown artifact format")
        if not isinstance(parsed, dict) or set(parsed) != {"title", "items", "total"}:
            raise ValueError("Artifact must contain exactly title, items and total")
        checked_task({**task, "title": parsed["title"], "items": parsed["items"]})
        if parsed["title"] != task["title"] or parsed["items"] != task["items"]:
            errors.append("Parsed title or facts differ from the independently specified task")
        if type(parsed["total"]) is not int or parsed["total"] != sum(
            item["quantity"] for item in task["items"]
        ):
            errors.append("Parsed total is not the independently recomputed quantity sum")
        if task["require_citations"] and any(
            item["source"] not in set(observed_urls) for item in task["items"]
        ):
            errors.append("A source URL was not actually observed through the current workflow")
    except (ValueError, TypeError, KeyError, IndexError, SyntaxError, csv.Error) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {
        "valid": not errors,
        "errors": errors,
        "title": parsed.get("title") if isinstance(parsed, dict) else None,
        "items": parsed.get("items") if isinstance(parsed, dict) else None,
        "total": parsed.get("total") if isinstance(parsed, dict) else None,
        "arbitrary_code_executed": False,
        "scope": "Requested inventory report and restricted pure quantity function contracts",
    }
