"""A small evaluator for the formulas the agent writes, so a workbook carries their values when
it is first read (Excel and WPS calculate everything again when they open it).

Numbers, text, cell and range references (also on other sheets), + - * / ^ & and comparisons,
percentages, and SUM AVERAGE MIN MAX COUNT COUNTA COUNTIF SUMIF AVERAGEIF ROUND ROUNDUP
ROUNDDOWN ABS IF IFERROR AND OR NOT CONCAT TEXT LEN. A formula with anything else gets no
stored value; the office suite works it out.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Any

from agent_workspace.office.tables import column_index

_TOKEN = re.compile(
    r"\s*(?:"
    r"(?P<string>\"(?:[^\"]|\"\")*\")"
    r"|(?P<ref>(?:'[^']+'|[A-Za-z_一-鿿][\w一-鿿.]*)?!?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)"
    r"|(?P<number>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Z][A-Z0-9.]*)(?=\s*\()"
    r"|(?P<op><>|<=|>=|[-+*/^&=<>(),%:])"
    r")"
)


class Unsupported(ValueError):
    pass


Getter = Callable[[str | None, int, int], Any]


class _Parser:
    def __init__(self, text: str, sheet: str, get: Getter) -> None:
        self.tokens: list[tuple[str, str]] = []
        position = 0
        while position < len(text):
            match = _TOKEN.match(text, position)
            if not match or match.end() == position:
                if text[position:].strip() == "":
                    break
                raise Unsupported(text[position:])
            kind = match.lastgroup or ""
            self.tokens.append(
                (kind, match.group(kind).strip() if kind != "string" else match.group(kind))
            )
            position = match.end()
        self.index = 0
        self.sheet = sheet
        self.get = get

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.index] if self.index < len(self.tokens) else ("end", "")

    def take(self) -> tuple[str, str]:
        token = self.peek()
        self.index += 1
        return token

    def expect(self, value: str) -> None:
        if self.take()[1] != value:
            raise Unsupported(f"expected {value}")

    def parse(self) -> Any:
        value = self.comparison()
        if self.peek()[0] != "end":
            raise Unsupported("trailing tokens")
        return value

    def comparison(self) -> Any:
        left = self.concat()
        while self.peek()[1] in {"=", "<>", "<", ">", "<=", ">="}:
            op = self.take()[1]
            right = self.concat()
            left = _compare(left, right, op)
        return left

    def concat(self) -> Any:
        left = self.additive()
        while self.peek()[1] == "&":
            self.take()
            left = _text(left) + _text(self.additive())
        return left

    def additive(self) -> Any:
        left = self.term()
        while self.peek()[1] in {"+", "-"}:
            op = self.take()[1]
            right = self.term()
            left = _num(left) + _num(right) if op == "+" else _num(left) - _num(right)
        return left

    def term(self) -> Any:
        left = self.power()
        while self.peek()[1] in {"*", "/"}:
            op = self.take()[1]
            right = self.power()
            if op == "*":
                left = _num(left) * _num(right)
            else:
                divisor = _num(right)
                if divisor == 0:
                    raise Unsupported("#DIV/0!")
                left = _num(left) / divisor
        return left

    def power(self) -> Any:
        left = self.unary()
        while self.peek()[1] == "^":
            self.take()
            left = _num(left) ** _num(self.unary())
        return left

    def unary(self) -> Any:
        if self.peek()[1] == "-":
            self.take()
            return -_num(self.unary())
        if self.peek()[1] == "+":
            self.take()
            return _num(self.unary())
        value = self.primary()
        if self.peek()[1] == "%":
            self.take()
            value = _num(value) / 100
        return value

    def primary(self) -> Any:
        kind, value = self.take()
        if kind == "number":
            return float(value)
        if kind == "string":
            return value[1:-1].replace('""', '"')
        if kind == "ref":
            return self.reference(value)
        if kind == "name":
            return self.call(value)
        if value == "(":
            result = self.comparison()
            self.expect(")")
            return result
        raise Unsupported(value or "end")

    def reference(self, text: str) -> Any:
        sheet = None
        if "!" in text:
            sheet, text = text.rsplit("!", 1)
            sheet = sheet.strip("'")
        text = text.replace("$", "")
        if ":" in text:
            start, end = text.split(":")
            (c1, r1), (c2, r2) = _cell(start), _cell(end)
            return [
                [self.get(sheet, row, column) for column in range(min(c1, c2), max(c1, c2) + 1)]
                for row in range(min(r1, r2), max(r1, r2) + 1)
            ]
        column, row = _cell(text)
        return self.get(sheet, row, column)

    def arguments(self) -> list[Any]:
        self.expect("(")
        values: list[Any] = []
        if self.peek()[1] == ")":
            self.take()
            return values
        while True:
            values.append(self.comparison())
            token = self.take()[1]
            if token == ")":
                return values
            if token != ",":
                raise Unsupported("argument list")

    def call(self, name: str) -> Any:
        function = _FUNCTIONS.get(name.upper())
        if function is None:
            raise Unsupported(name)
        return function(self.arguments())


def _cell(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]{1,3})(\d+)", text)
    if not match:
        raise Unsupported(text)
    return column_index(match.group(1)), int(match.group(2)) - 1


def _flat(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for value in values:
        if isinstance(value, list):
            out.extend(_flat(value))
        else:
            out.append(value)
    return out


def _numbers(values: list[Any]) -> list[float]:
    return [
        float(value)
        for value in _flat(values)
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]


def _num(value: Any) -> float:
    if isinstance(value, list):
        raise Unsupported("range in arithmetic")
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        raise Unsupported("#VALUE!") from None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return f"{value:.15g}"
    return str(value)


def _compare(left: Any, right: Any, op: str) -> bool:
    if isinstance(left, int | float) and isinstance(right, int | float):
        a, b = float(left), float(right)
    else:
        a, b = _text(left).casefold(), _text(right).casefold()  # type: ignore[assignment]
    return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def _criterion(criterion: Any) -> Callable[[Any], bool]:
    if isinstance(criterion, int | float):
        return lambda value: isinstance(value, int | float) and float(value) == float(criterion)
    text = _text(criterion)
    match = re.match(r"(<>|<=|>=|=|<|>)?(.*)", text)
    op, operand = (match.group(1) or "=", match.group(2)) if match else ("=", text)
    try:
        number = float(operand)
    except ValueError:
        number = None
    if number is not None:
        return lambda value: isinstance(value, int | float) and _compare(float(value), number, op)
    if "*" in operand or "?" in operand:
        pattern = re.compile(
            "^" + re.escape(operand).replace(r"\*", ".*").replace(r"\?", ".") + "$", re.IGNORECASE
        )
        return lambda value: bool(pattern.match(_text(value))) == (op != "<>")
    return lambda value: _compare(_text(value), operand, op)


def _conditional(arguments: list[Any], kind: str) -> Any:
    if len(arguments) < 2:
        raise Unsupported(kind)
    test_range = _flat([arguments[0]])
    target = _flat([arguments[2]]) if len(arguments) > 2 else test_range
    test = _criterion(arguments[1])
    picked = [
        target[index]
        for index, value in enumerate(test_range)
        if index < len(target) and test(value)
    ]
    numbers = [
        float(value)
        for value in picked
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    if kind == "count":
        return float(sum(1 for value in test_range if test(value)))
    if kind == "sum":
        return sum(numbers)
    if not numbers:
        raise Unsupported("#DIV/0!")
    return sum(numbers) / len(numbers)


def _round(arguments: list[Any], mode: str) -> float:
    value = _num(arguments[0])
    digits = int(_num(arguments[1])) if len(arguments) > 1 else 0
    factor = 10**digits
    if mode == "up":
        return math.copysign(math.ceil(abs(value) * factor - 1e-9) / factor, value)
    if mode == "down":
        return math.copysign(math.floor(abs(value) * factor + 1e-9) / factor, value)
    return math.copysign(math.floor(abs(value) * factor + 0.5) / factor, value)


def _text_format(arguments: list[Any]) -> str:
    value, pattern = _num(arguments[0]), _text(arguments[1])
    decimals = len(pattern.split(".")[1].rstrip("%")) if "." in pattern else 0
    if pattern.endswith("%"):
        return f"{value * 100:.{decimals}f}%"
    return f"{value:,.{decimals}f}" if "," in pattern else f"{value:.{decimals}f}"


def _average(arguments: list[Any]) -> float:
    numbers = _numbers(arguments)
    if not numbers:
        raise Unsupported("#DIV/0!")
    return sum(numbers) / len(numbers)


_FUNCTIONS: dict[str, Callable[[list[Any]], Any]] = {
    "SUM": lambda a: sum(_numbers(a)),
    "AVERAGE": _average,
    "MIN": lambda a: min(_numbers(a), default=0.0),
    "MAX": lambda a: max(_numbers(a), default=0.0),
    "COUNT": lambda a: float(len(_numbers(a))),
    "COUNTA": lambda a: float(sum(1 for value in _flat(a) if value not in (None, ""))),
    "COUNTIF": lambda a: _conditional(a, "count"),
    "SUMIF": lambda a: _conditional(a, "sum"),
    "AVERAGEIF": lambda a: _conditional(a, "average"),
    "ROUND": lambda a: _round(a, "half"),
    "ROUNDUP": lambda a: _round(a, "up"),
    "ROUNDDOWN": lambda a: _round(a, "down"),
    "ABS": lambda a: abs(_num(a[0])),
    "IF": lambda a: (
        (a[1] if len(a) > 1 else True) if _truth(a[0]) else (a[2] if len(a) > 2 else False)
    ),
    "AND": lambda a: all(_truth(value) for value in _flat(a)),
    "OR": lambda a: any(_truth(value) for value in _flat(a)),
    "NOT": lambda a: not _truth(a[0]),
    "CONCAT": lambda a: "".join(_text(value) for value in _flat(a)),
    "CONCATENATE": lambda a: "".join(_text(value) for value in _flat(a)),
    "TEXT": _text_format,
    "LEN": lambda a: float(len(_text(a[0]))),
}


def _truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return bool(value)


def evaluate(formula: str, sheet: str, get: Getter) -> Any:
    """The formula's value, or raises Unsupported."""
    text = formula[1:] if formula.startswith("=") else formula
    match = re.fullmatch(r"\s*IFERROR\s*\((.*),([^,]*)\)\s*", text, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            return evaluate(match.group(1), sheet, get)
        except Unsupported as error:
            if str(error).startswith("#"):
                return evaluate(match.group(2), sheet, get)
            raise
    value = _Parser(text, sheet, get).parse()
    if isinstance(value, list):
        raise Unsupported("a range is not a value")
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return int(value)
    return value


__all__ = ["Unsupported", "evaluate"]
