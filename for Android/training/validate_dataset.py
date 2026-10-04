"""Independently validate synthetic records against advertised and execution schemas."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

FUNCTION = re.compile(
    r"<tool_call>\s*<function=([A-Za-z0-9_.-]+)>(.*?)</function>\s*</tool_call>", re.DOTALL
)
PARAMETER = re.compile(r"<parameter=([A-Za-z0-9_.-]+)>(.*?)</parameter>", re.DOTALL)


def _parameters(body: str, schema: dict[str, Any]) -> dict[str, Any]:
    matches = list(PARAMETER.finditer(body))
    if PARAMETER.sub("", body).strip():
        raise ValueError("Parameter delimiters must be complete")
    arguments: dict[str, Any] = {}
    for match in matches:
        name, raw = match[1], match[2].strip("\r\n")
        if name in arguments:
            raise ValueError("Duplicate parameter")
        prop = schema.get("properties", {}).get(name, schema.get("additionalProperties", {}))
        if prop is False:
            raise ValueError("Unknown parameter")
        validator = Draft202012Validator(prop if isinstance(prop, dict) else {})
        if raw in {"None", "null"} and validator.is_valid(None):
            value = None
        elif validator.is_valid(raw):
            value = raw
        elif raw in {"True", "False"}:
            value = raw == "True"
        else:
            try:
                value = json.loads(raw)
            except ValueError as error:
                raise ValueError(
                    "Parameter is neither the required string nor strict JSON"
                ) from error
        arguments[name] = value
    return arguments


def _validate_call(item: dict[str, Any], catalog: dict[str, Any]) -> None:
    name, arguments = item["name"], item["arguments"]
    if name not in catalog or not isinstance(arguments, dict):
        raise ValueError("Unknown tool or invalid arguments")
    entry = catalog[name]
    try:
        for schema in (entry["advertisement"]["function"]["parameters"], entry["execution_schema"]):
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(arguments)
    except ValidationError as error:
        raise ValueError(f"{name}: {error.message}") from error
    for key in ("path", "source", "destination"):
        if key not in arguments:
            continue
        path = arguments[key]
        if not isinstance(path, str) or "\\" in path or ":" in path or "\x00" in path:
            raise ValueError("Tool paths must be relative workspace paths")
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts:
            raise ValueError("Tool path escapes the workspace")
    preimage = arguments.get("expected_sha256")
    if preimage is not None and (
        not isinstance(preimage, str) or not re.fullmatch("[0-9a-f]{64}", preimage)
    ):
        raise ValueError("CAS requires an observed SHA-256 hash or an actual null")
    if name == "select_local_tools" and any(choice not in catalog for choice in arguments["names"]):
        raise ValueError("The tool selector cannot invent tools")
    if name == "android_action":
        fields = {
            "ref": {"ref"},
            "type_text": {"ref", "text"},
            "tap": {"x", "y"},
            "swipe": {"x", "y", "x2", "y2"},
            "launch_app": {"package_name"},
            "back": set(),
            "home": set(),
        }
        if not fields[arguments["action"]] <= arguments.keys():
            raise ValueError("Android action is missing action-specific fields")


def parse_tool_response(text: str, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    matches = list(FUNCTION.finditer(text))
    if not matches or FUNCTION.sub("", text).strip():
        raise ValueError("Expected only complete official Qwen3.5 tool-call blocks")
    calls: list[dict[str, Any]] = []
    for match in matches:
        name = match[1]
        if name not in catalog:
            raise ValueError("Unknown tool")
        schema = catalog[name]["advertisement"]["function"]["parameters"]
        item = {"name": name, "arguments": _parameters(match[2], schema)}
        _validate_call(item, catalog)
        calls.append(item)
    return calls


def _tool_result(content: str) -> dict[str, Any]:
    return json.loads(
        content.split("\n", 1)[1] if content.startswith("[UNTRUSTED TOOL DATA:") else content
    )


def validate_example(row: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if row.get("metadata", {}).get("synthetic") is not True:
        raise ValueError("Only synthetic examples are accepted")
    if row["metadata"].get("user_data_used") is not False:
        raise ValueError("User data is excluded")
    messages = row["messages"]
    if (
        not messages
        or messages[0]["role"] != "system"
        or not any(message["role"] == "user" for message in messages)
    ):
        raise ValueError("An example needs system context and a user task")
    if messages[-1]["role"] == "assistant":
        raise ValueError("Target response must not already appear in the prompt")
    advertisements: dict[str, Any] = {}
    for tool in row["tools"]:
        name = tool["function"]["name"]
        if name not in catalog or tool != catalog[name]["advertisement"] or name in advertisements:
            raise ValueError("Advertisements must be unique copies of current real ToolSpecs")
        advertisements[name] = tool
    pending: dict[str, Any] = {}
    history: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for message in messages:
        if message["role"] == "assistant":
            for previous in message.get("tool_calls", []):
                item = {
                    "name": previous["function"]["name"],
                    "arguments": previous["function"]["arguments"],
                }
                _validate_call(item, catalog)
                if previous["id"] in pending:
                    raise ValueError("Duplicate historical call ID")
                pending[previous["id"]] = item
        if message["role"] == "tool":
            item = pending.pop(message["tool_call_id"], None)
            if item is None:
                raise ValueError("Tool result has no matching historical call")
            result = _tool_result(message["content"])
            history.append((item, result))
            if item["name"] == "read_file" and result.get("truncated") is False:
                measured = hashlib.sha256(result["content"].encode()).hexdigest()
                if result["sha256"] != measured:
                    raise ValueError("Historical CAS hash does not match synthetic file content")
    if pending:
        raise ValueError("Historical tool calls must have results")
    expected, target = row["expected"], row["target_response"]
    if expected["kind"] == "tool_call":
        calls = parse_tool_response(target, catalog)
        if calls != expected["calls"]:
            raise ValueError("Parsed target differs from independent structured label")
        if any(item["name"] not in advertisements for item in calls):
            raise ValueError("Target calls an unadvertised tool")
        for item in calls:
            if item["name"] not in {"write_file", "move_path"}:
                continue
            args = item["arguments"]
            preimage = args.get("expected_sha256")
            path = args.get("path", args.get("source"))
            if preimage is not None and not any(
                previous["name"] == "read_file"
                and previous["arguments"]["path"] == path
                and result.get("sha256") == preimage
                for previous, result in history
            ):
                raise ValueError(
                    "Existing-file writes and moves require a matching observed preimage"
                )
    elif expected["kind"] == "text":
        if not target.strip() or any(marker in target for marker in expected["forbidden"]):
            raise ValueError("Ordinary replies cannot emit a tool proposal")
        if not all(fragment in target for fragment in expected["must_contain"]):
            raise ValueError("Natural reply does not meet its independent answer criteria")
        calls = []
    else:
        raise ValueError("Unsupported expected response kind")
    return {
        "calls": len(calls) + len(history),
        "names": [item["name"] for item in calls] + [item["name"] for item, _ in history],
    }


def validate_splits(
    train: list[dict[str, Any]], evaluate: list[dict[str, Any]], catalog: dict[str, Any]
) -> dict[str, Any]:
    if not train or not evaluate:
        raise ValueError("Both training and held-out evaluation examples are required")
    for attribute in ("entity", "scenario_group"):
        if not {row["metadata"][attribute] for row in train}.isdisjoint(
            {row["metadata"][attribute] for row in evaluate}
        ):
            raise ValueError(f"Train/evaluation {attribute} overlap")
    if len({row["id"] for row in train + evaluate}) != len(train) + len(evaluate):
        raise ValueError("Duplicate example IDs")
    results = [validate_example(row, catalog) for row in train + evaluate]
    return {
        "examples": len(results),
        "train": len(train),
        "eval": len(evaluate),
        "tool_calls": sum(item["calls"] for item in results),
        "tool_names": sorted({name for item in results for name in item["names"]}),
        "advertised_and_execution_schemas_valid": True,
        "entities_and_compositions_disjoint": True,
    }
