"""Custom request headers and backup API keys for the model provider (Android).

Some users reach their provider through a gateway or proxy that wants its own headers, or keep
several keys of one service so a rate-limited or exhausted key does not stop their work. Both are
kept per provider address in the phone's keystore (the credential store), never in plain files,
and applied by wrapping the provider's HTTP client: every request gets the headers, and on 401,
403, 429 or a server error the request goes again with the next key, which is then used first.

Takes effect for providers created after saving (an engine restart or a provider change).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import httpx

# Headers a custom setting may not replace: they carry the request itself or its credentials.
_RESERVED = frozenset({"host", "content-length", "content-type", "authorization", "x-api-key", "x-goog-api-key",
                       "transfer-encoding", "connection", "accept-encoding"})
_FAILOVER = frozenset({401, 403, 429, 500, 502, 503, 504})
MAX_KEYS = 8
MAX_HEADERS = 10


def _origin(base_url: str) -> str:
    parts = urlsplit(base_url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def _credential_name(base_url: str) -> str:
    return f"provider-extras:{_origin(base_url)}"


def load_extras(base_url: str) -> dict[str, Any]:
    try:
        from agent_workspace.credentials import get_credential

        raw = get_credential(_credential_name(base_url))
        value = json.loads(raw) if raw else {}
    except Exception:
        value = {}
    headers = value.get("headers") if isinstance(value, dict) else None
    keys = value.get("keys") if isinstance(value, dict) else None
    return {
        "headers": {str(k): str(v) for k, v in headers.items()} if isinstance(headers, dict) else {},
        "keys": [str(key) for key in keys if isinstance(key, str) and key] if isinstance(keys, list) else [],
    }


def check_extras(headers: Any, keys: Any) -> tuple[dict[str, str], list[str]]:
    if not isinstance(headers, dict) or not isinstance(keys, list):
        raise ValueError("headers must be an object and keys a list")
    if len(headers) > MAX_HEADERS or len(keys) > MAX_KEYS:
        raise ValueError(f"at most {MAX_HEADERS} headers and {MAX_KEYS} backup keys")
    cleaned: dict[str, str] = {}
    for name, value in headers.items():
        name, value = str(name).strip(), str(value).strip()
        if not name or any(ch in name for ch in " :\r\n\t") or "\n" in value or "\r" in value:
            raise ValueError(f"invalid header: {name!r}")
        if name.lower() in _RESERVED:
            raise ValueError(f"{name} cannot be set here")
        cleaned[name] = value
    clean_keys = list(dict.fromkeys(str(key).strip() for key in keys if str(key).strip()))
    if any(any(ch.isspace() for ch in key) for key in clean_keys):
        raise ValueError("an API key cannot contain spaces")
    return cleaned, clean_keys


def save_extras(base_url: str, headers: Any, keys: Any) -> dict[str, Any]:
    cleaned, clean_keys = check_extras(headers, keys)
    from agent_workspace.credentials import delete_credential, set_credential

    name = _credential_name(base_url)
    if cleaned or clean_keys:
        set_credential(name, json.dumps({"headers": cleaned, "keys": clean_keys}, ensure_ascii=False))
    else:
        delete_credential(name)
    return describe(base_url)


def describe(base_url: str) -> dict[str, Any]:
    """What is set, without the secrets: header names and how many backup keys."""
    extras = load_extras(base_url)
    return {"origin": _origin(base_url), "header_names": sorted(extras["headers"]), "backup_keys": len(extras["keys"])}


class ProviderTransport(httpx.AsyncBaseTransport):
    """Adds the custom headers to every request; with backup keys, retries a refused or failed
    request with the next key and keeps using the one that worked."""

    def __init__(self, inner: httpx.AsyncBaseTransport, headers: dict[str, str], keys: list[str]) -> None:
        self._inner = inner
        self._headers = headers
        self._keys = keys
        self._current = 0

    def _with_key(self, request: httpx.Request, key: str) -> None:
        if request.headers.get("authorization", "").lower().startswith("bearer "):
            request.headers["authorization"] = f"Bearer {key}"
        for name in ("x-api-key", "x-goog-api-key"):
            if name in request.headers:
                request.headers[name] = key

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for name, value in self._headers.items():
            request.headers[name] = value
        if len(self._keys) < 2:
            return await self._inner.handle_async_request(request)
        await request.aread()
        for attempt in range(len(self._keys)):
            index = (self._current + attempt) % len(self._keys)
            self._with_key(request, self._keys[index])
            response = await self._inner.handle_async_request(request)
            if response.status_code in _FAILOVER and attempt < len(self._keys) - 1:
                await response.aclose()
                continue
            self._current = index
            return response
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self._inner.aclose()


def client_for(base_url: str, api_key: str | None, *, trust_env: bool) -> httpx.AsyncClient | None:
    """A client with the provider's extras, or None when it has none (the provider makes its own)."""
    extras = load_extras(base_url)
    keys = ([api_key] if api_key else []) + [key for key in extras["keys"] if key != api_key]
    if not extras["headers"] and len(keys) < 2:
        return None
    transport = ProviderTransport(httpx.AsyncHTTPTransport(trust_env=trust_env), extras["headers"], keys)
    return httpx.AsyncClient(transport=transport, trust_env=trust_env)


def patch_providers() -> None:
    """Gives the OpenAI-compatible, Anthropic and Gemini providers a client with the extras."""
    from agent_workspace.providers import anthropic, gemini, openai_compatible
    from agent_workspace.config import is_loopback_endpoint

    for module, name in ((openai_compatible, "OpenAICompatibleProvider"), (anthropic, "AnthropicProvider"),
                         (gemini, "GeminiProvider")):
        cls = getattr(module, name, None)
        if cls is None or getattr(cls.__init__, "_agent_extras", False):
            continue
        original = cls.__init__

        def __init__(self, *args, _original=original, **kwargs):
            if kwargs.get("client") is None:
                base_url = kwargs.get("base_url", args[1] if len(args) > 1 else "")
                api_key = kwargs.get("api_key", args[2] if len(args) > 2 else None)
                try:
                    client = client_for(str(base_url), api_key, trust_env=not is_loopback_endpoint(str(base_url)))
                except Exception:
                    client = None
                if client is not None:
                    kwargs["client"] = client
                    _original(self, *args, **kwargs)
                    self._owns_client = True
                    return
            _original(self, *args, **kwargs)

        __init__._agent_extras = True
        cls.__init__ = __init__
