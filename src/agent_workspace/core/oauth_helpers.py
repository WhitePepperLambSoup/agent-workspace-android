"""OAuth 2.0 / OIDC PKCE helpers.

These helpers prepare authorization requests and validate token responses.
Network exchange remains the provider layer's responsibility so credentials
never transit generic storage.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

_CODE_CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"


class OAuthHelperError(ValueError):
    pass


def generate_code_verifier(length: int = 96) -> str:
    if not 43 <= length <= 128:
        raise OAuthHelperError("PKCE verifier length must be from 43 to 128")
    return "".join(secrets.choice(_CODE_CHARSET) for _ in range(length))


def code_challenge(verifier: str) -> str:
    if not 43 <= len(verifier) <= 128:
        raise OAuthHelperError("PKCE verifier length must be from 43 to 128")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorization_url(
    *,
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    scopes: tuple[str, ...],
    state: str | None = None,
    code_challenge: str | None = None,
    audience: str | None = None,
) -> str:
    if not authorization_endpoint.startswith("https://"):
        raise OAuthHelperError("OAuth authorization endpoint must be HTTPS")
    if not client_id or not redirect_uri or not scopes:
        raise OAuthHelperError("client_id, redirect_uri, and scopes are required")
    if state is not None and not state:
        raise OAuthHelperError("state may not be empty")
    parameters: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "state": state or secrets.token_urlsafe(24),
    }
    if code_challenge is not None:
        parameters["code_challenge"] = code_challenge
        parameters["code_challenge_method"] = "S256"
    if audience is not None:
        parameters["audience"] = audience
    separator = "&" if "?" in authorization_endpoint else "?"
    return f"{authorization_endpoint}{separator}{urlencode(parameters)}"


@dataclass(frozen=True, slots=True)
class OAuthTokenRequest:
    token_endpoint: str
    client_id: str
    redirect_uri: str
    code: str
    code_verifier: str | None = None
    scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.token_endpoint.startswith("https://"):
            raise OAuthHelperError("OAuth token endpoint must be HTTPS")
        if not self.client_id or not self.redirect_uri or not self.code:
            raise OAuthHelperError("client_id, redirect_uri, and code are required")
        if self.code_verifier is not None and not 43 <= len(self.code_verifier) <= 128:
            raise OAuthHelperError("code_verifier length must be from 43 to 128")

    def to_form(self) -> dict[str, str]:
        form = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": self.code,
        }
        if self.code_verifier is not None:
            form["code_verifier"] = self.code_verifier
        if self.scopes:
            form["scope"] = " ".join(self.scopes)
        return form


def validate_token_response(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OAuthHelperError("OAuth token response must be an object")
    access_token = value.get("access_token")
    token_type = value.get("token_type")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthHelperError("OAuth token response is missing access_token")
    if not isinstance(token_type, str) or token_type.casefold() != "bearer":
        raise OAuthHelperError("OAuth token response must use Bearer token type")
    return dict(value)


__all__ = [
    "OAuthHelperError",
    "OAuthTokenRequest",
    "authorization_url",
    "code_challenge",
    "generate_code_verifier",
    "validate_token_response",
]
