"""GBNF grammars that keep a small local model's tool calls well formed.

The grammar is lazy: llama.cpp applies it only once the model starts a call with
<tool_call>, so plain answers are untouched. From there the call must name an offered tool,
use only that tool's parameters in the order they were shown (each required one present),
spell integers, booleans and fixed choices validly, and close properly; nothing but another
call may follow. Other values stay free text, and the parser still validates every call
against the tool's schema, so the grammar only removes ways to fail.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from typing import Any

_RULE_SAFE = re.compile(r"[^a-zA-Z0-9]+")
_PARAMETER_END = "</parameter>"
WHITESPACE = r"[ \t\r\n]{0,8}"


def enabled() -> bool:
    return os.getenv("AGENT_WORKSPACE_LOCAL_TOOL_GRAMMAR", "1") != "0"


def literal(text: str) -> str:
    """A GBNF string literal."""
    escaped = []
    for character in text:
        if character in '"\\':
            escaped.append("\\" + character)
        elif character == "\n":
            escaped.append("\\n")
        elif character == "\r":
            escaped.append("\\r")
        elif character == "\t":
            escaped.append("\\t")
        elif ord(character) < 0x20 or ord(character) == 0x7F:
            escaped.append(f"\\x{ord(character):02x}")
        else:
            escaped.append(character)
    return '"' + "".join(escaped) + '"'


def _class_character(character: str) -> str:
    if character in "\\]^-[":
        return "\\" + character
    if character == "\n":
        return "\\n"
    if character == "\r":
        return "\\r"
    if character == "\t":
        return "\\t"
    if ord(character) < 0x20:
        return f"\\x{ord(character):02x}"
    return character


def _char_class(characters: Iterable[str], *, negate: bool = False) -> str:
    return "[" + ("^" if negate else "") + "".join(_class_character(c) for c in characters) + "]"


class _Rules:
    def __init__(self) -> None:
        self.rules: dict[str, str] = {}

    def add(self, name: str, body: str) -> str:
        if self.rules.get(name, body) != body:
            raise ValueError(f"grammar rule {name} defined twice")
        self.rules[name] = body
        return name

    def name(self, *parts: str) -> str:
        return "-".join(_RULE_SAFE.sub("-", part).strip("-").lower() or "x" for part in parts)

    def text(self) -> str:
        return "".join(f"{name} ::= {body}\n" for name, body in self.rules.items())


def _excluding(rules: _Rules, prefix: str, delimiter: str) -> str:
    """Rules for any text that does not contain `delimiter` (a KMP automaton complement).

    Every state accepts, and the character that would complete the delimiter has no
    transition, so the delimiter can only follow the text, never occur inside it.
    """
    alphabet = sorted(set(delimiter))
    length = len(delimiter)

    def step(state: int, character: str) -> int:
        while True:
            if state < length and delimiter[state] == character:
                return state + 1
            if state == 0:
                return 0
            # longest proper border of delimiter[:state] that is also a prefix
            state = next(
                size
                for size in range(state - 1, -1, -1)
                if delimiter[:size] == delimiter[state - size : state]
            )

    def state_name(state: int) -> str:
        return prefix if state == 0 else f"{prefix}-{state}"

    for state in range(length):
        buckets: dict[int, list[str]] = {}
        specific: list[str] = []
        for character in alphabet:
            target = step(state, character)
            if target == length:
                specific.append(character)  # would complete the delimiter: no transition
            elif target != 0:
                buckets.setdefault(target, []).append(character)
                specific.append(character)
        alternatives = [""]
        alternatives += [
            f"{_char_class(chars)} {state_name(target)}" for target, chars in buckets.items()
        ]
        alternatives.append(f"{_char_class(specific, negate=True)} {state_name(0)}")
        rules.add(state_name(state), " | ".join(alternatives))
    return state_name(0)


# ---- schema helpers -----------------------------------------------------------------------


def _types(schema: Mapping[str, Any]) -> list[str]:
    value = schema.get("type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _properties(parameters: Mapping[str, Any]) -> tuple[list[tuple[str, Any]], set[str]]:
    properties = parameters.get("properties")
    if not isinstance(properties, dict):
        return [], set()
    required = {name for name in parameters.get("required") or () if name in properties}
    return list(properties.items()), required


# ---- Qwen3.5: <function=NAME><parameter=KEY>VALUE</parameter></function> ------------------


def _xml_value(rules: _Rules, schema: Any, text_rule: str) -> str:
    if not isinstance(schema, dict):
        return text_rule
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        choices = [
            literal(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
            for value in schema["enum"]
            if value is not None
        ]
        if None in schema["enum"]:
            choices += [literal("null"), literal("None")]
        return f"ws ( {' | '.join(choices)} ) ws" if choices else text_rule
    types = _types(schema)
    if not types or any(kind in {"string", "array", "object"} for kind in types):
        return text_rule
    choices = []
    for kind in types:
        if kind == "integer":
            choices.append("xml-integer")
        elif kind == "number":
            choices.append("xml-number")
        elif kind == "boolean":
            choices.append("xml-boolean")
        elif kind == "null":
            choices.append('( "null" | "None" )')
    return f"ws ( {' | '.join(choices)} ) ws" if choices else text_rule


def _qwen35(tools: list[tuple[str, Mapping[str, Any]]]) -> str:
    rules = _Rules()
    rules.add("root", "call ( ws call )* ws")
    rules.add("ws", WHITESPACE)
    functions = [rules.name("fn", str(index)) for index in range(len(tools))]
    rules.add(
        "call", f'"<tool_call>" ws "<function=" ( {" | ".join(functions)} ) ws "</tool_call>"'
    )
    text_rule = _excluding(rules, "xml-text", _PARAMETER_END)
    rules.add("xml-integer", '"-"? [0-9]{1,18}')
    rules.add("xml-number", '"-"? [0-9]{1,18} ( "." [0-9]{1,18} )? ( [eE] [-+]? [0-9]{1,4} )?')
    rules.add("xml-boolean", '"true" | "false" | "True" | "False"')
    for index, (name, parameters) in enumerate(tools):
        properties, required = _properties(parameters)
        sequence = [literal(name + ">")]
        for position, (key, schema) in enumerate(properties):
            rule = rules.name("fn", str(index), "p", str(position))
            value = _xml_value(rules, schema, text_rule)
            rules.add(rule, f"{literal(f'<parameter={key}>')} {value} {literal(_PARAMETER_END)}")
            sequence.append(f"ws {rule}" if key in required else f"( ws {rule} )?")
        sequence.append('ws "</function>"')
        rules.add(functions[index], " ".join(sequence))
    return rules.text()


# ---- Qwen3: {"name": NAME, "arguments": {...}} --------------------------------------------

_JSON_RULES = {
    "json-string": '"\\"" json-char* "\\""',
    "json-char": '[^"\\\\\\x00-\\x1f] | "\\\\" ( ["\\\\/bfnrt] | "u" [0-9a-fA-F]{4} )',
    "json-integer": '"-"? ( [0-9] | [1-9] [0-9]{1,17} )',
    "json-number": 'json-integer ( "." [0-9]{1,18} )? ( [eE] [-+]? [0-9]{1,4} )?',
    "json-boolean": '"true" | "false"',
    "json-null": '"null"',
    "json-value": (
        "json-object | json-array | json-string | json-number | json-boolean | json-null"
    ),
    "json-object": (
        '"{" ws ( json-string ws ":" ws json-value ( ws "," ws json-string ws ":" ws '
        'json-value )* )? ws "}"'
    ),
    "json-array": '"[" ws ( json-value ( ws "," ws json-value )* )? ws "]"',
}


def _json_value(rules: _Rules, schema: Any, name: str) -> str:
    if not isinstance(schema, dict):
        return "json-value"
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        choices = [literal(json.dumps(value, ensure_ascii=False)) for value in schema["enum"]]
        return f"( {' | '.join(choices)} )"
    types = _types(schema)
    if not types:
        return "json-value"
    choices = []
    for kind in types:
        if kind == "string":
            choices.append("json-string")
        elif kind == "integer":
            choices.append("json-integer")
        elif kind == "number":
            choices.append("json-number")
        elif kind == "boolean":
            choices.append("json-boolean")
        elif kind == "null":
            choices.append("json-null")
        elif kind == "array":
            item = _json_value(rules, schema.get("items"), name + "-item")
            rule = rules.add(
                rules.name(name, "array"), f'"[" ws ( {item} ( ws "," ws {item} )* )? ws "]"'
            )
            choices.append(rule)
        else:
            choices.append("json-object")
    return choices[0] if len(choices) == 1 else f"( {' | '.join(choices)} )"


def _json_arguments(rules: _Rules, name: str, parameters: Mapping[str, Any]) -> str:
    properties, required = _properties(parameters)
    pairs = []
    for position, (key, schema) in enumerate(properties):
        value = _json_value(rules, schema, rules.name(name, "v", str(position)))
        pair = rules.add(
            rules.name(name, "kv", str(position)),
            f'{literal(json.dumps(key, ensure_ascii=False))} ws ":" ws {value}',
        )
        pairs.append((pair, key in required))
    if not pairs:
        return '"{" ws "}"'
    # rest-i: the properties from i on, each after a comma, required ones present
    following = ""
    for position in range(len(pairs) - 1, -1, -1):
        pair, needed = pairs[position]
        piece = f'ws "," ws {pair}'
        body = f"{piece} {following}".strip() if needed else f"( {piece} )? {following}".strip()
        following = rules.add(rules.name(name, "rest", str(position)), body)
    # the first property written: the first required one, or any optional one before it
    starts = []
    for position, (pair, needed) in enumerate(pairs):
        rest = rules.name(name, "rest", str(position + 1)) if position + 1 < len(pairs) else ""
        starts.append(f"{pair} {rest}".strip())
        if needed:
            break
    else:
        starts.insert(0, "")  # every property is optional: none at all is fine
    first = rules.add(rules.name(name, "first"), " | ".join(starts).strip())
    return f'"{{" ws {first} ws "}}"'


def _qwen3(tools: list[tuple[str, Mapping[str, Any]]]) -> str:
    rules = _Rules()
    rules.add("root", "call ( ws call )* ws")
    rules.add("ws", WHITESPACE)
    functions = [rules.name("fn", str(index)) for index in range(len(tools))]
    rules.add(
        "call",
        '"<tool_call>" ws "{" ws "\\"name\\"" ws ":" ws ( '
        + " | ".join(functions)
        + ' ) ws "}" ws "</tool_call>"',
    )
    for name, body in _JSON_RULES.items():
        rules.add(name, body)
    for index, (name, parameters) in enumerate(tools):
        arguments = _json_arguments(rules, rules.name("fn", str(index)), parameters)
        rules.add(
            functions[index],
            f'{literal(json.dumps(name, ensure_ascii=False))} ws "," ws "\\"arguments\\"" ws ":" '
            f"ws {arguments}",
        )
    return rules.text()


def tool_call_grammar(tools: list[tuple[str, Mapping[str, Any]]], *, qwen35: bool) -> str:
    """The grammar for calls to `tools`, given as (name, parameters schema) pairs."""
    if not tools:
        return ""
    return _qwen35(tools) if qwen35 else _qwen3(tools)


__all__ = ["enabled", "literal", "tool_call_grammar"]
