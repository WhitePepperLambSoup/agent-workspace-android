"""Bounded OpenAPI GET/POST operation generation.

The loader accepts a bounded subset of OpenAPI 3 documents and turns GET/POST
operations into ordinary workspace tools. GET execution delegates to the
existing ``web_fetch`` implementation; POST uses the same pinned-HTTPS
transport so DNS pinning and global-address validation remain identical.
"""

from __future__ import annotations

import http.client
import json
import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, ToolError, json_result
from .process_worker import run_in_process
from .web import (
    _MAX_FETCH_BYTES,
    _MAX_HEADER_BYTES,
    WebFetchTool,
    _normalize_public_https_url,
    _PinnedHTTPSConnection,
)

_MAX_OPERATIONS = 32
_MAX_DESCRIPTION_CHARS = 2000
_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_-]")


class OpenApiToolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OpenApiOperation:
    id: str
    summary: str
    path: str
    parameters: tuple[dict[str, Any], ...]
    server_url: str
    method: str = "get"
    request_schema: dict[str, Any] | None = None

    @property
    def tool_name(self) -> str:
        sanitized = _NAME_PATTERN.sub("_", self.id)
        if not sanitized or sanitized[0].isdigit():
            sanitized = f"op_{sanitized}"
        return f"api_{self.method}_{sanitized}"

    def build_url(self, arguments: dict[str, Any]) -> str:
        values: dict[str, Any] = {}
        for name in self.path_names:
            if name not in arguments:
                raise ToolArgumentError(
                    f"openapi operation {self.id!r} is missing a path parameter: {name}"
                )
            values[name] = arguments[name]
        try:
            path = self.path.format(**values)
        except (KeyError, ValueError) as exc:
            raise ToolArgumentError(
                f"openapi operation {self.id!r} is missing a path parameter"
            ) from exc
        query: list[str] = []
        for parameter in self.parameters:
            if parameter["in"] == "query" and parameter["name"] in arguments:
                query.append(f"{parameter['name']}={_url_encode(arguments[parameter['name']])}")
        if query:
            path += "?" + "&".join(query)
        return self.server_url.rstrip("/") + path

    @property
    def path_names(self) -> tuple[str, ...]:
        return tuple(
            parameter["name"] for parameter in self.parameters if parameter["in"] == "path"
        )


def _url_encode(value: object) -> str:
    from urllib.parse import quote

    return quote(str(value), safe="")


def _json_schema_type(parameter: dict[str, Any]) -> dict[str, Any]:
    raw_schema = parameter.get("schema", {})
    parameter_type = raw_schema.get("type") if isinstance(raw_schema, dict) else None
    if parameter_type not in {"string", "integer", "number", "boolean"}:
        return {"type": "string"}
    result: dict[str, Any] = {"type": parameter_type}
    if parameter_type == "integer":
        result["minimum"] = int(raw_schema.get("minimum", -2147483648))
    return result


def _openapi_post_sync(
    raw_url: str,
    body: dict[str, Any],
    timeout_seconds: float,
) -> str:
    normalized, parsed, addresses = _normalize_public_https_url(raw_url)
    address = addresses[0]
    connection = _PinnedHTTPSConnection(
        parsed.hostname or "",
        address,
        parsed.port or 443,
        float(timeout_seconds),
    )
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(payload) > 1024 * 1024:
        raise ToolError("openapi POST body exceeds 1 MiB")
    try:
        connection.request(
            "POST",
            path,
            body=payload,
            headers={
                "Accept": "application/json,text/plain",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "Content-Type": "application/json",
                "User-Agent": "AgentWorkspace/0.1",
            },
        )
        response = connection.getresponse()
        header_bytes = sum(
            len(name.encode("latin-1")) + len(value.encode("latin-1")) + 4
            for name, value in response.getheaders()
        )
        if header_bytes > _MAX_HEADER_BYTES:
            raise ToolError("openapi POST response headers exceed the safety limit")
        if not 200 <= response.status < 300:
            raise ToolError(f"openapi POST returned HTTP status {response.status}")
        if (response.getheader("Content-Encoding") or "identity").casefold() != "identity":
            raise ToolError("openapi POST compressed responses are unsupported")
        response_body = response.read(_MAX_FETCH_BYTES + 1)
    except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError) as exc:
        raise ToolError("openapi POST transport failed") from exc
    finally:
        connection.close()
    truncated = len(response_body) > _MAX_FETCH_BYTES
    text = response_body[:_MAX_FETCH_BYTES].decode("utf-8", errors="replace")
    return json_result(
        {
            "url": normalized,
            "status": response.status,
            "content": text,
            "truncated": truncated,
        }
    )


class OpenApiHttpTool:
    def __init__(self, operation: OpenApiOperation) -> None:
        self.operation = operation
        properties: dict[str, Any] = {}
        required: list[str] = []
        for parameter in operation.parameters:
            if parameter.get("in") not in {"path", "query"}:
                continue
            name = parameter["name"]
            properties[name] = _json_schema_type(parameter)
            if parameter.get("required") is True:
                required.append(name)
        if operation.method == "post":
            properties["body"] = operation.request_schema or {"type": "object"}
            required.append("body")
        self._spec = ToolSpec(
            name=operation.tool_name,
            description=operation.summary[:_MAX_DESCRIPTION_CHARS],
            input_schema={
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            side_effect="network",
            capability=Capability.NETWORK_READ,
        )
        self._web = WebFetchTool()

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        url = self.operation.build_url(arguments)
        if self.operation.method == "post":
            body = arguments.get("body")
            if not isinstance(body, dict):
                raise ToolArgumentError("openapi POST requires a JSON object body")
            return await run_in_process(_openapi_post_sync, url, body, 30.0)
        return await self._web.execute({"url": url})


OpenApiGetTool = OpenApiHttpTool


def _request_schema(raw_request_body: object) -> dict[str, Any] | None:
    if not isinstance(raw_request_body, dict):
        return None
    content = raw_request_body.get("content")
    if not isinstance(content, dict):
        return None
    json_content = content.get("application/json")
    if not isinstance(json_content, dict):
        return None
    schema = json_content.get("schema")
    return dict(schema) if isinstance(schema, dict) else None


def load_openapi_operations(
    document: object,
    *,
    max_operations: int = _MAX_OPERATIONS,
) -> tuple[OpenApiOperation, ...]:
    if not isinstance(document, dict) or document.get("openapi", "").startswith("3.") is False:
        raise OpenApiToolError("OpenAPI document must declare an openapi 3.x version")
    servers = document.get("servers")
    if not isinstance(servers, list) or not servers:
        raise OpenApiToolError("OpenAPI document must declare at least one server")
    first_server = servers[0]
    server_url = first_server.get("url") if isinstance(first_server, dict) else None
    if not isinstance(server_url, str) or not server_url.startswith("https://"):
        raise OpenApiToolError("OpenAPI operations require an HTTPS server url")
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise OpenApiToolError("OpenAPI document must declare paths")
    operations: list[OpenApiOperation] = []
    for raw_path, raw_item in paths.items():
        if not isinstance(raw_path, str) or not isinstance(raw_item, dict):
            continue
        shared_parameters = [
            parameter
            for parameter in raw_item.get("parameters", ())
            if isinstance(parameter, dict) and parameter.get("in") in {"path", "query"}
        ]
        for method, raw_operation in raw_item.items():
            if method not in {"get", "post"} or not isinstance(raw_operation, dict):
                continue
            request_schema: dict[str, Any] | None = None
            if method == "post":
                request_schema = _request_schema(raw_operation.get("requestBody"))
                if request_schema is None:
                    continue
            operation_id = raw_operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                operation_id = f"{method}_{_NAME_PATTERN.sub('_', raw_path.strip('/'))}"
            summary = (
                raw_operation.get("summary") or raw_operation.get("description") or operation_id
            )
            if not isinstance(summary, str) or not summary:
                summary = operation_id
            parameters = list(shared_parameters)
            parameters.extend(
                parameter
                for parameter in raw_operation.get("parameters", ())
                if isinstance(parameter, dict)
                and parameter.get("in") in {"path", "query"}
                and isinstance(parameter.get("name"), str)
            )
            operations.append(
                OpenApiOperation(
                    id=operation_id,
                    summary=summary,
                    path=raw_path,
                    parameters=tuple(dict(parameter) for parameter in parameters),
                    server_url=server_url,
                    method=method,
                    request_schema=request_schema,
                )
            )
            if len(operations) >= max_operations:
                return tuple(operations)
    return tuple(operations)


def load_openapi_file(path: str | Path) -> tuple[OpenApiOperation, ...]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpenApiToolError(f"cannot read OpenAPI document {path}: {exc}") from exc
    return load_openapi_operations(document)


__all__ = [
    "OpenApiGetTool",
    "OpenApiHttpTool",
    "OpenApiOperation",
    "OpenApiToolError",
    "load_openapi_file",
    "load_openapi_operations",
]
