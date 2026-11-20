from __future__ import annotations

import os
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final, cast

import tomli_w

from agent_workspace.config import ProviderConfig, ProviderProtocol, default_data_dir
from agent_workspace.credentials import (
    CredentialStore,
    credential_target,
    default_credential_store,
)
from agent_workspace.storage import ProcessWriteLock

SETTINGS_VERSION: Final = 1

_PROFILE_KEYS = {"id", "name", "protocol", "base_url", "model", "credential_target"}
_SETTINGS_KEYS = {"version", "default_provider", "profiles"}


class ProviderSettingsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    id: str
    name: str
    protocol: ProviderProtocol
    base_url: str
    model: str
    credential_target: str

    def validate(self, *, check_transport: bool = True) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("provider name may not be empty")
        if not isinstance(self.protocol, ProviderProtocol):
            raise ValueError("provider protocol is invalid")
        if not isinstance(self.model, str):
            raise ValueError("provider model must be a string")
        expected_target = credential_target(
            self.id, self.base_url, check_transport=check_transport
        )
        if self.credential_target != expected_target:
            raise ValueError("credential target does not match the provider endpoint")


@dataclass(frozen=True, slots=True)
class InvalidProviderProfile:
    """A profile entry of the settings file that cannot be read, as written there.

    It is left out of the usable profiles and written back unchanged with every save, so a hand
    edit that went wrong can be put right in the file instead of being lost.
    """

    id: str
    name: str
    error: str
    document: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    version: int
    default_provider_id: str | None
    profiles: Mapping[str, ProviderProfile]
    invalid_profiles: tuple[InvalidProviderProfile, ...] = ()
    # The default the file names when that profile cannot be read: no default is used meanwhile,
    # and the file keeps naming it until another default is chosen.
    invalid_default_provider_id: str | None = None


def _builtin_profile(
    provider_id: str,
    name: str,
    protocol: ProviderProtocol,
    base_url: str,
    default_model: str = "",
) -> ProviderProfile:
    return ProviderProfile(
        id=provider_id,
        name=name,
        protocol=protocol,
        base_url=base_url,
        model=default_model,
        credential_target=credential_target(provider_id, base_url),
    )


BUILTIN_PROVIDER_PROFILES: Final = (
    _builtin_profile(
        "openai",
        "OpenAI",
        ProviderProtocol.OPENAI_COMPATIBLE,
        "https://api.openai.com/v1",
        default_model="gpt-4o",
    ),
    _builtin_profile(
        "anthropic",
        "Anthropic",
        ProviderProtocol.ANTHROPIC,
        "https://api.anthropic.com/v1",
        default_model="claude-3-7-sonnet-latest",
    ),
    _builtin_profile(
        "gemini",
        "Gemini",
        ProviderProtocol.GEMINI,
        "https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-2.5-flash",
    ),
    _builtin_profile(
        "ollama",
        "Ollama",
        ProviderProtocol.OLLAMA,
        "http://127.0.0.1:11434",
        default_model="qwen2.5-coder:7b",
    ),
    _builtin_profile(
        "deepseek",
        "DeepSeek",
        ProviderProtocol.OPENAI_COMPATIBLE,
        "https://api.deepseek.com/v1",
        default_model="deepseek-flash",
    ),
    _builtin_profile(
        "openrouter",
        "OpenRouter",
        ProviderProtocol.OPENAI_COMPATIBLE,
        "https://openrouter.ai/api/v1",
        default_model="anthropic/claude-3.7-sonnet",
    ),
)


class ProviderSettingsStore:
    def __init__(self, path: str | Path, credential_store: CredentialStore) -> None:
        self.path = Path(path)
        self._credential_store = credential_store

    def load(self) -> ProviderSettings:
        try:
            with self.path.open("rb") as stream:
                raw_document: object = tomllib.load(stream)
        except FileNotFoundError:
            return _default_settings()
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            raise ProviderSettingsError(f"provider settings are invalid ({self.path})") from None

        try:
            if not isinstance(raw_document, dict):
                raise ValueError
            return _decode_settings(cast(dict[str, object], raw_document))
        except (TypeError, ValueError) as exc:
            detail = " ".join(str(exc).split())
            message = f"provider settings are invalid ({self.path})"
            if detail:
                message += f": {detail}"
            raise ProviderSettingsError(message) from None

    def upsert(
        self,
        profile: ProviderProfile,
        *,
        secret: str | None = None,
        make_default: bool = False,
    ) -> ProviderSettings:
        profile = _canonicalize_profile(profile)
        profile.validate()
        if secret is not None and not secret:
            raise ValueError("provider credential may not be empty")
        with self._mutation_lock():
            current = self.load()
            old_profile = current.profiles.get(profile.id)
            profiles = dict(current.profiles)
            profiles[profile.id] = profile
            default_id = profile.id if make_default else current.default_provider_id
            updated = _carried(current, default_id, profiles, replaced_id=profile.id)
            old_target = old_profile.credential_target if old_profile is not None else None
            targets = {profile.credential_target}
            if old_target is not None:
                targets.add(old_target)
            snapshots = {target: self._credential_store.get(target) for target in targets}
            mutated_targets: set[str] = set()
            settings_published = False
            try:
                if secret is not None:
                    mutated_targets.add(profile.credential_target)
                    self._credential_store.set(profile.credential_target, secret)
                self._write(updated)
                settings_published = True
                if old_target is not None and old_target != profile.credential_target:
                    mutated_targets.add(old_target)
                    self._credential_store.delete(old_target)
            except BaseException as exc:
                self._rollback(
                    current,
                    snapshots,
                    mutated_targets,
                    restore_settings=settings_published,
                    cause=exc,
                )
                raise
            return updated

    def delete(self, provider_id: str) -> ProviderSettings:
        with self._mutation_lock():
            current = self.load()
            try:
                profile = current.profiles[provider_id]
            except KeyError:
                raise KeyError(f"unknown provider profile: {provider_id}") from None

            profiles = dict(current.profiles)
            del profiles[provider_id]
            default_provider_id = (
                None if current.default_provider_id == provider_id else current.default_provider_id
            )
            updated = _carried(current, default_provider_id, profiles)
            snapshot = self._credential_store.get(profile.credential_target)
            settings_published = False
            credential_mutated = False
            try:
                self._write(updated)
                settings_published = True
                credential_mutated = True
                self._credential_store.delete(profile.credential_target)
            except BaseException as exc:
                self._rollback(
                    current,
                    {profile.credential_target: snapshot},
                    {profile.credential_target} if credential_mutated else set(),
                    restore_settings=settings_published,
                    cause=exc,
                )
                raise
            return updated

    def set_default(self, provider_id: str) -> ProviderSettings:
        with self._mutation_lock():
            current = self.load()
            if provider_id not in current.profiles:
                raise KeyError(f"unknown provider profile: {provider_id}")
            updated = _carried(current, provider_id, current.profiles)
            self._write(updated)
            return updated

    def has_credential(self, provider: str | ProviderProfile) -> bool:
        profile = self._profile(provider)
        return self._credential_store.get(profile.credential_target) is not None

    def get_credential(self, provider: str | ProviderProfile) -> str | None:
        profile = self._profile(provider)
        return self._credential_store.get(profile.credential_target)

    def set_credential(self, provider_id: str, secret: str) -> None:
        if not secret:
            raise ValueError("provider credential may not be empty")
        with self._mutation_lock():
            profile = self._profile(provider_id)
            self._credential_store.set(profile.credential_target, secret)

    def clear_credential(self, provider: str | ProviderProfile) -> None:
        with self._mutation_lock():
            profile = self._profile(provider)
            self._credential_store.delete(profile.credential_target)

    def resolve_config(self, provider_id: str | None = None) -> ProviderConfig:
        settings = self.load()
        resolved_id = (
            provider_id
            if provider_id is not None
            else settings.default_provider_id or settings.invalid_default_provider_id
        )
        if resolved_id is None:
            raise ValueError("no default provider is configured")
        try:
            profile = settings.profiles[resolved_id]
        except KeyError:
            for entry in settings.invalid_profiles:
                if entry.id == resolved_id:
                    raise ProviderSettingsError(
                        f"provider profile {resolved_id!r} in {self.path} cannot be read: "
                        f"{entry.error}"
                    ) from None
            raise KeyError(f"unknown provider profile: {resolved_id}") from None

        config = ProviderConfig(
            id=profile.id,
            base_url=profile.base_url,
            model=profile.model,
            api_key=self._credential_store.get(profile.credential_target),
            protocol=profile.protocol,
        )
        config.validate()
        return config

    def _profile(self, provider: str | ProviderProfile) -> ProviderProfile:
        if isinstance(provider, ProviderProfile):
            # Only its credential target is needed here, not whether it may be connected to.
            provider.validate(check_transport=False)
            return provider
        try:
            return self.load().profiles[provider]
        except KeyError:
            raise KeyError(f"unknown provider profile: {provider}") from None

    def _rollback(
        self,
        settings: ProviderSettings,
        snapshots: Mapping[str, str | None],
        mutated_targets: set[str],
        *,
        restore_settings: bool,
        cause: BaseException,
    ) -> None:
        rollback_failed = False
        for target in mutated_targets:
            try:
                secret = snapshots[target]
                if secret is None:
                    self._credential_store.delete(target)
                else:
                    self._credential_store.set(target, secret)
            except BaseException:
                rollback_failed = True
        if restore_settings:
            try:
                self._write(settings)
            except BaseException:
                rollback_failed = True
        if rollback_failed:
            raise ProviderSettingsError(
                "provider settings update failed and rollback was incomplete"
            ) from cause

    def _mutation_lock(self) -> ProcessWriteLock:
        return ProcessWriteLock(self.path.with_name(f"{self.path.name}.lock"))

    def _write(self, settings: ProviderSettings) -> None:
        document: dict[str, object] = {
            "version": settings.version,
            "profiles": [
                {
                    "id": profile.id,
                    "name": profile.name,
                    "protocol": profile.protocol.value,
                    "base_url": profile.base_url,
                    "model": profile.model,
                    "credential_target": profile.credential_target,
                }
                for profile in settings.profiles.values()
            ]
            # Entries the file could not read go back as they were written.
            + [dict(entry.document) for entry in settings.invalid_profiles],
        }
        default_provider = settings.default_provider_id or settings.invalid_default_provider_id
        if default_provider is not None:
            document["default_provider"] = default_provider
        payload = tomli_w.dumps(document).encode("utf-8")
        _atomic_write(self.path, payload)


def default_provider_settings_store() -> ProviderSettingsStore:
    return ProviderSettingsStore(
        default_data_dir() / "config.toml",
        default_credential_store(),
    )


def _default_settings() -> ProviderSettings:
    return _make_settings(
        "openai",
        {profile.id: profile for profile in BUILTIN_PROVIDER_PROFILES},
    )


def _make_settings(
    default_provider_id: str | None,
    profiles: Mapping[str, ProviderProfile],
    invalid_profiles: tuple[InvalidProviderProfile, ...] = (),
    invalid_default_provider_id: str | None = None,
) -> ProviderSettings:
    copied_profiles = dict(profiles)
    return ProviderSettings(
        version=SETTINGS_VERSION,
        default_provider_id=default_provider_id,
        profiles=MappingProxyType(copied_profiles),
        invalid_profiles=invalid_profiles,
        invalid_default_provider_id=invalid_default_provider_id,
    )


def _carried(
    current: ProviderSettings,
    default_provider_id: str | None,
    profiles: Mapping[str, ProviderProfile],
    *,
    replaced_id: str | None = None,
) -> ProviderSettings:
    """Changed settings that keep the entries the file could not read.

    Only saving a profile under the same id replaces such an entry; a default it held passes to
    the saved profile, and choosing another default ends it.
    """
    invalid = tuple(entry for entry in current.invalid_profiles if entry.id != replaced_id)
    kept_default = current.invalid_default_provider_id
    if default_provider_id is None and kept_default is not None and kept_default == replaced_id:
        default_provider_id = kept_default
    if default_provider_id is not None:
        kept_default = None
    return _make_settings(default_provider_id, profiles, invalid, kept_default)


def _decode_settings(document: dict[str, object]) -> ProviderSettings:
    if set(document) - _SETTINGS_KEYS or "version" not in document or "profiles" not in document:
        raise ValueError
    version = document["version"]
    if type(version) is not int or version != SETTINGS_VERSION:
        raise ValueError

    raw_profiles = document["profiles"]
    if not isinstance(raw_profiles, list):
        raise ValueError("'profiles' must be a list")
    profiles: dict[str, ProviderProfile] = {}
    invalid: list[InvalidProviderProfile] = []
    for raw_profile in raw_profiles:
        if not isinstance(raw_profile, dict):
            raise ValueError("every 'profiles' entry must be a table")
        entry = cast(dict[str, object], raw_profile)
        raw_id = entry.get("id")
        profile_id = raw_id if isinstance(raw_id, str) else ""
        try:
            if not profile_id:
                raise ValueError("it declares no id")
            if profile_id in profiles:
                raise ValueError("an earlier entry has the same id")
            profile = _decode_profile(entry)
        except (TypeError, ValueError) as exc:
            # One entry a hand edit broke used to make the whole file unreadable, and every
            # provider with it. The others stay usable; this one is reported and kept as written.
            raw_name = entry.get("name")
            invalid.append(
                InvalidProviderProfile(
                    id=profile_id,
                    name=raw_name if isinstance(raw_name, str) else "",
                    error=" ".join(str(exc).split()) or "it cannot be read",
                    document=MappingProxyType(dict(entry)),
                )
            )
            continue
        profiles[profile.id] = profile

    default_provider = document.get("default_provider")
    if default_provider is not None and not isinstance(default_provider, str):
        raise ValueError
    invalid_default: str | None = None
    if default_provider is not None and default_provider not in profiles:
        if all(entry.id != default_provider for entry in invalid):
            raise ValueError
        invalid_default, default_provider = default_provider, None
    return _make_settings(default_provider, profiles, tuple(invalid), invalid_default)


def _decode_profile(document: dict[str, object]) -> ProviderProfile:
    missing = sorted(_PROFILE_KEYS - set(document))
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    unknown = sorted(set(document) - _PROFILE_KEYS)
    if unknown:
        raise ValueError(f"unknown {', '.join(unknown)}")
    not_text = sorted(key for key in _PROFILE_KEYS if not isinstance(document[key], str))
    if not_text:
        raise ValueError(f"{', '.join(not_text)} must be text")
    provider_id = cast(str, document["id"])
    model = _canonical_model_name(provider_id, cast(str, document["model"]))
    profile = ProviderProfile(
        id=provider_id,
        name=cast(str, document["name"]),
        protocol=ProviderProtocol(cast(str, document["protocol"])),
        base_url=cast(str, document["base_url"]),
        model=model,
        credential_target=cast(str, document["credential_target"]),
    )
    # A LAN profile saved where AGENT_WORKSPACE_ALLOW_LAN_HTTP=1 used to make the whole file
    # unreadable, every provider with it, in a process without that variable. Whether plain HTTP
    # may be used is checked when that one provider connects (ProviderConfig.validate).
    profile.validate(check_transport=False)
    return profile


def _canonical_model_name(provider_id: str, model: str) -> str:
    """Return the current public model id for known legacy aliases."""
    if provider_id.casefold() == "deepseek" and model.casefold() in {
        "deepseek-v4-flash",
        "deepseek-v4.1-flash",
    }:
        return "deepseek-flash"
    return model


def _canonicalize_profile(profile: ProviderProfile) -> ProviderProfile:
    model = _canonical_model_name(profile.id, profile.model)
    if model == profile.model:
        return profile
    return ProviderProfile(
        id=profile.id,
        name=profile.name,
        protocol=profile.protocol,
        base_url=profile.base_url,
        model=model,
        credential_target=profile.credential_target,
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        if os.name != "nt":
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
