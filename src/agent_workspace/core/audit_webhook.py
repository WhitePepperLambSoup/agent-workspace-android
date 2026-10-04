"""Bounded audit webhook delivery with signature headers."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable
from typing import Any

_MAX_PAYLOAD_BYTES = 1024 * 1024


def sign_audit_payload(payload: dict[str, Any], secret: bytes) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret, encoded, hashlib.sha256).hexdigest()


class AuditWebhook:
    def __init__(
        self,
        url: str,
        secret: bytes,
        *,
        send: Callable[[str, bytes, dict[str, str]], Awaitable[tuple[int, bytes]]],
    ) -> None:
        if not url.startswith("https://"):
            raise ValueError("audit webhook URL must be HTTPS")
        if not secret:
            raise ValueError("audit webhook secret may not be empty")
        self.url = url
        self.secret = secret
        self._send = send

    async def deliver(self, event: dict[str, Any]) -> int:
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > _MAX_PAYLOAD_BYTES:
            raise ValueError("audit webhook payload exceeds 1 MiB")
        signature = sign_audit_payload(event, self.secret)
        status, _body = await self._send(
            self.url,
            encoded,
            {
                "Content-Type": "application/json",
                "X-AgentWorkspace-Signature": signature,
            },
        )
        return status


__all__ = ["AuditWebhook", "sign_audit_payload"]
