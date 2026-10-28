"""Model provider profiles: listing, saving, testing and the default one; prompt optimization and
transcription with a saved profile.
"""

from __future__ import annotations

from dataclasses import replace

from agent_workspace.config import (
    ProviderConfig,
    ProviderProtocol,
    is_loopback_endpoint,
)
from agent_workspace.credentials import credential_target
from agent_workspace.providers.health import (
    ProviderHealthResult,
)
from agent_workspace.providers.reasoning import supported_reasoning_efforts
from agent_workspace.settings import (
    ProviderProfile,
    ProviderSettings,
    ProviderSettingsError,
    ProviderSettingsStore,
    default_provider_settings_store,
)
from agent_workspace.ui_gateway.gateway_common import (
    _LIFECYCLE_TIMEOUT_SECONDS,
    _MAX_PROMPT_CHARS,
    _MAX_PROVIDER_BASE_URL_CHARS,
    _MAX_PROVIDER_CREDENTIAL_BYTES,
    _MAX_PROVIDER_MODEL_CHARS,
    _MAX_PROVIDER_NAME_CHARS,
    _PROVIDER_TEST_TIMEOUT_SECONDS,
    GatewayError,
    GatewayReply,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)
from agent_workspace.ui_gateway.transcription import decode_recording


class ProviderCommands(GatewayState):
    """Model provider profiles: listing, saving, testing and the default one; prompt optimization
    and transcription with a saved profile.
    """

    def _list_providers(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set())
        settings = self._load_provider_settings()
        providers = [
            self._provider_document(profile, settings) for profile in settings.profiles.values()
        ]
        return self._reply(
            "provider.list.result",
            {
                "epoch": self.epoch,
                "defaultProviderId": settings.default_provider_id,
                "providers": providers,
            },
            session_id=None,
        )

    def _get_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        profile = self._saved_provider(settings, provider_id)
        return self._reply(
            "provider.get.result",
            {
                "epoch": self.epoch,
                "provider": self._provider_document(profile, settings),
            },
            session_id=None,
        )

    def _set_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"providerId", "name", "protocol", "baseUrl", "model"},
            optional={"apiKey", "makeDefault"},
        )
        provider_id = self._provider_id(command.payload.get("providerId"))
        name = self._provider_text(
            command.payload.get("name"),
            max_chars=_MAX_PROVIDER_NAME_CHARS,
            allow_empty=False,
        )
        base_url = self._provider_text(
            command.payload.get("baseUrl"),
            max_chars=_MAX_PROVIDER_BASE_URL_CHARS,
            allow_empty=False,
        )
        model = self._provider_text(
            command.payload.get("model"),
            max_chars=_MAX_PROVIDER_MODEL_CHARS,
            allow_empty=True,
        )
        raw_protocol = command.payload.get("protocol")
        if not isinstance(raw_protocol, str):
            raise GatewayError("invalid_provider")
        try:
            protocol = ProviderProtocol(raw_protocol)
            target = credential_target(provider_id, base_url)
        except (TypeError, ValueError):
            raise GatewayError("invalid_provider") from None

        raw_default = command.payload.get("makeDefault", False)
        if not isinstance(raw_default, bool):
            raise GatewayError("invalid_provider")
        raw_secret = command.payload.get("apiKey")
        secret: str | None = None
        if "apiKey" in command.payload:
            if (
                not isinstance(raw_secret, str)
                or not raw_secret.strip()
                or raw_secret != raw_secret.strip()
                or not raw_secret.isprintable()
            ):
                raise GatewayError("invalid_provider_credential")
            try:
                credential_bytes = len(raw_secret.encode("utf-8"))
            except UnicodeEncodeError:
                raise GatewayError("invalid_provider_credential") from None
            if credential_bytes > _MAX_PROVIDER_CREDENTIAL_BYTES:
                raise GatewayError("invalid_provider_credential")
            secret = raw_secret

        profile = ProviderProfile(
            id=provider_id,
            name=name,
            protocol=protocol,
            base_url=base_url,
            model=model,
            credential_target=target,
        )
        try:
            has_credential = (
                True if secret is not None else self._settings_store().has_credential(profile)
            )
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_unavailable") from None
        try:
            settings = self._settings_store().upsert(
                profile,
                secret=secret,
                make_default=raw_default,
            )
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_failed") from None
        return self._reply(
            "provider.set.result",
            {
                "epoch": self.epoch,
                "defaultProviderId": settings.default_provider_id,
                "provider": self._provider_document(
                    profile,
                    settings,
                    has_credential=has_credential,
                ),
            },
            session_id=None,
        )

    def _clear_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        profile = self._saved_provider(settings, provider_id)
        active = self._provider is not None and self._provider.id == provider_id
        if active and self._busy:
            raise GatewayError("runtime_busy")
        previous_provider = self._provider
        previous_session_id = self._selected_session_id
        if active:
            self._stop_host()
        try:
            self._settings_store().clear_credential(profile)
        except (OSError, ProviderSettingsError, ValueError):
            if active:
                assert previous_provider is not None
                credential_restored = previous_provider.api_key is None
                if previous_provider.api_key is not None:
                    try:
                        self._settings_store().set_credential(
                            provider_id,
                            previous_provider.api_key,
                        )
                        credential_restored = True
                    except (KeyError, OSError, ProviderSettingsError, ValueError):
                        credential_restored = False
                if credential_restored:
                    self._provider = previous_provider
                    self._start_host(session_id=previous_session_id)
                else:
                    self._provider = None
                    self._host = None
                    self._runtime_state = "unconfigured"
            raise GatewayError("provider_settings_failed") from None
        if active:
            self._provider = None
            self._host = None
            self._runtime_state = "unconfigured"
        return self._reply(
            "provider.clear.result",
            {
                "epoch": self.epoch,
                "provider": self._provider_document(
                    profile,
                    settings,
                    has_credential=False,
                ),
            },
            session_id=None,
        )

    def _delete_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        self._saved_provider(settings, provider_id)
        if provider_id == settings.default_provider_id or (
            self._provider is not None and provider_id == self._provider.id
        ):
            raise GatewayError("provider_in_use")
        try:
            updated = self._settings_store().delete(provider_id)
        except KeyError:
            raise GatewayError("unknown_provider") from None
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_failed") from None
        return self._reply(
            "provider.delete.result",
            {
                "epoch": self.epoch,
                "deletedProviderId": provider_id,
                "defaultProviderId": updated.default_provider_id,
            },
            session_id=None,
        )

    def _set_default_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        profile = self._saved_provider(settings, provider_id)
        try:
            provider = self._settings_store().resolve_config(provider_id)
            provider.validate()
        except KeyError:
            raise GatewayError("unknown_provider") from None
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_unavailable") from None
        if self._busy:
            raise GatewayError("runtime_busy")

        previous_default_id = settings.default_provider_id
        previous_provider = self._provider
        previous_session_id = self._selected_session_id
        try:
            updated = self._settings_store().set_default(provider_id)
        except KeyError:
            raise GatewayError("unknown_provider") from None
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_failed") from None

        applied = self._workspace is not None
        if applied:
            deadline = self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
            replacement_attempted = False
            try:
                if self._host is not None:
                    self._stop_host_for_lifecycle(deadline=deadline)
                self._provider = provider
                replacement_attempted = True
                self._start_host(session_id=previous_session_id, deadline=deadline)
            except GatewayError as error:
                failure_code = "runtime_start_failed" if replacement_attempted else str(error)
                replacement_cleanup_failed = False
                if replacement_attempted and self._host is not None:
                    try:
                        self._stop_host_for_lifecycle()
                    except GatewayError:
                        replacement_cleanup_failed = True
                rollback_settings_failed = False
                if previous_default_id is None:
                    rollback_settings_failed = True
                else:
                    try:
                        self._settings_store().set_default(previous_default_id)
                    except (KeyError, OSError, ProviderSettingsError, ValueError):
                        rollback_settings_failed = True
                if not replacement_attempted:
                    self._provider = previous_provider
                elif not replacement_cleanup_failed:
                    self._provider = previous_provider
                    if previous_provider is None:
                        self._host = None
                        self._runtime_state = "unconfigured"
                    else:
                        try:
                            self._start_host(session_id=previous_session_id)
                        except GatewayError:
                            raise GatewayError("runtime_start_failed") from None
                if rollback_settings_failed:
                    raise GatewayError("provider_settings_failed") from None
                raise GatewayError(failure_code) from None

        return self._reply(
            "provider.default.result",
            {
                "epoch": self.epoch,
                "defaultProviderId": updated.default_provider_id,
                "applied": applied,
                "provider": self._provider_document(
                    profile,
                    updated,
                    has_credential=provider.api_key is not None,
                ),
            },
            session_id=None,
        )

    def _bootstrap_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"providerId"})
        raw_provider_id = command.payload.get("providerId")
        provider_id = self._provider_id(raw_provider_id) if raw_provider_id is not None else None
        settings = self._load_provider_settings()
        selected_id = provider_id or settings.default_provider_id
        providers = [
            self._provider_document(profile, settings) for profile in settings.profiles.values()
        ]
        if selected_id is None:
            return self._reply(
                "provider.bootstrap.result",
                {
                    "epoch": self.epoch,
                    "status": "needs_setup",
                    "ready": False,
                    "nextAction": "select_provider",
                    "defaultProviderId": None,
                    "provider": None,
                    "providers": providers,
                },
                session_id=None,
            )
        profile = self._saved_provider(settings, selected_id)
        has_credential = self._settings_store().has_credential(profile)
        # Local servers (Ollama, llama.cpp, LM Studio, vLLM) on loopback need no key.
        local_endpoint = profile.protocol is ProviderProtocol.OLLAMA or is_loopback_endpoint(
            profile.base_url
        )
        status = "ready" if has_credential or local_endpoint else "needs_credential"
        next_action = None if status == "ready" else "enter_api_key"
        return self._reply(
            "provider.bootstrap.result",
            {
                "epoch": self.epoch,
                "status": status,
                "ready": status == "ready",
                "nextAction": next_action,
                "defaultProviderId": settings.default_provider_id,
                "provider": self._provider_document(
                    profile, settings, has_credential=has_credential
                ),
                "providers": providers,
            },
            session_id=None,
        )

    def _health_saved_provider(self, command: CommandEnvelope) -> GatewayReply:
        with self._lock:
            self._require_payload(command, set(), optional={"providerId"})
            raw_provider_id = command.payload.get("providerId")
            provider_id = (
                self._provider_id(raw_provider_id) if raw_provider_id is not None else None
            )
            settings = self._load_provider_settings()
            if provider_id is not None:
                self._saved_provider(settings, provider_id)
            elif settings.default_provider_id is None:
                raise GatewayError("provider_unconfigured")
            try:
                config = self._settings_store().resolve_config(provider_id)
            except KeyError:
                raise GatewayError("unknown_provider") from None
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_unconfigured") from None
        result = self._provider_health_checker(config)
        if not isinstance(result, ProviderHealthResult):
            raise GatewayError("provider_health_failed")
        return self._reply(
            "provider.health.result",
            {"epoch": self.epoch, **result.to_document()},
            session_id=None,
        )

    def _test_saved_provider(self, command: CommandEnvelope) -> GatewayReply:
        with self._lock:
            self._require_payload(command, set(), optional={"providerId"})
            raw_provider_id = command.payload.get("providerId")
            provider_id = (
                self._provider_id(raw_provider_id) if raw_provider_id is not None else None
            )
            settings = self._load_provider_settings()
            if provider_id is not None:
                self._saved_provider(settings, provider_id)
            elif settings.default_provider_id is None:
                raise GatewayError("provider_unconfigured")
            try:
                config = self._settings_store().resolve_config(provider_id)
            except KeyError:
                raise GatewayError("unknown_provider") from None
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_unconfigured") from None
        try:
            self._provider_tester(config)
        except Exception:
            raise GatewayError("provider_test_failed") from None
        with self._lock:
            return self._reply(
                "provider.test.result",
                {"epoch": self.epoch, "providerId": config.id, "ok": True},
                session_id=None,
            )

    def _transcribe_audio(self, command: CommandEnvelope) -> GatewayReply:
        """Turn a composer recording into text with a saved OpenAI-compatible profile."""
        with self._lock:
            self._require_payload(command, {"providerId", "model", "mediaType", "data"})
            provider_id = self._provider_id(command.payload.get("providerId"))
            model = command.payload.get("model")
            if not isinstance(model, str) or not model.strip() or len(model) > 200:
                raise GatewayError("invalid_model")
            settings = self._load_provider_settings()
            profile = self._saved_provider(settings, provider_id)
            if profile.protocol is not ProviderProtocol.OPENAI_COMPATIBLE:
                raise GatewayError("transcription_unsupported")
            try:
                config = self._settings_store().resolve_config(provider_id)
            except KeyError:
                raise GatewayError("unknown_provider") from None
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_unconfigured") from None
        try:
            audio, filename, media_type = decode_recording(
                command.payload.get("mediaType"), command.payload.get("data")
            )
        except ValueError:
            raise GatewayError("invalid_recording") from None
        try:
            text = self._audio_transcriber(config, model.strip(), audio, filename, media_type)
        except Exception:
            raise GatewayError("transcription_failed") from None
        with self._lock:
            return self._reply(
                "audio.transcribe.result",
                {"epoch": self.epoch, "text": text},
                session_id=None,
            )

    def _load_provider_settings(self) -> ProviderSettings:
        try:
            return self._settings_store().load()
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_unavailable") from None

    def _settings_store(self) -> ProviderSettingsStore:
        store = self._provider_settings_store
        if store is None:
            store = default_provider_settings_store()
            self._provider_settings_store = store
        return store

    @staticmethod
    def _saved_provider(settings: ProviderSettings, provider_id: str) -> ProviderProfile:
        try:
            return settings.profiles[provider_id]
        except KeyError:
            raise GatewayError("unknown_provider") from None

    def _provider_document(
        self,
        profile: ProviderProfile,
        settings: ProviderSettings,
        *,
        has_credential: bool | None = None,
    ) -> dict[str, object]:
        if has_credential is None:
            try:
                has_credential = self._settings_store().has_credential(profile)
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_settings_unavailable") from None
        return {
            "id": profile.id,
            "name": profile.name,
            "protocol": profile.protocol.value,
            "baseUrl": profile.base_url,
            "model": profile.model,
            "isDefault": profile.id == settings.default_provider_id,
            "hasCredential": has_credential,
            "supportedReasoningEfforts": list(self._supported_turn_reasoning_efforts(profile)),
        }

    @staticmethod
    def _supported_turn_reasoning_efforts(
        provider: ProviderConfig | ProviderProfile,
    ) -> tuple[str, ...]:
        if provider.protocol not in {
            ProviderProtocol.OPENAI_COMPATIBLE,
            ProviderProtocol.ANTHROPIC,
        }:
            return ()
        native = supported_reasoning_efforts(
            provider.protocol.value, provider.base_url, provider.model
        )
        supported = {"none", "low", "medium", "high", "xhigh", "max"}
        return tuple(
            "off" if effort == "none" else effort for effort in native if effort in supported
        )

    @staticmethod
    def _provider_id(value: object) -> str:
        if not isinstance(value, str):
            raise GatewayError("invalid_provider")
        try:
            credential_target(value, "https://validation.invalid")
        except ValueError:
            raise GatewayError("invalid_provider") from None
        return value

    @staticmethod
    def _provider_text(value: object, *, max_chars: int, allow_empty: bool) -> str:
        if not isinstance(value, str) or len(value) > max_chars:
            raise GatewayError("invalid_provider")
        normalized = value.strip()
        if not allow_empty and not normalized:
            raise GatewayError("invalid_provider")
        try:
            normalized.encode("utf-8")
        except UnicodeEncodeError:
            raise GatewayError("invalid_provider") from None
        return normalized

    def _optimize_prompt(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"prompt"}, optional={"providerId", "model"})
        self._require_selected_session(command.session_id, allow_unselected=True)
        prompt = command.payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > _MAX_PROMPT_CHARS:
            raise GatewayError("invalid_prompt")
        raw_provider_id = command.payload.get("providerId")
        raw_model = command.payload.get("model")
        if raw_provider_id is not None and not isinstance(raw_provider_id, str):
            raise GatewayError("invalid_provider")
        if raw_model is not None and (not isinstance(raw_model, str) or not raw_model.strip()):
            raise GatewayError("invalid_provider")
        host = self._host
        if host is None or self._runtime_state != "ready":
            raise GatewayError("runtime_unavailable")
        provider_config: ProviderConfig | None = None
        if raw_provider_id is not None:
            provider_id = self._provider_id(raw_provider_id)
            try:
                self._saved_provider(self._load_provider_settings(), provider_id)
                config = self._settings_store().resolve_config(provider_id)
            except (KeyError, OSError, ProviderSettingsError, ValueError):
                raise GatewayError("unknown_provider") from None
            if raw_model is not None:
                config = replace(config, model=raw_model.strip())
                config.validate()
            provider_config = config
        elif raw_model is not None:
            if self._provider is None:
                raise GatewayError("runtime_unavailable")
            provider_config = replace(self._provider, model=raw_model.strip())
            provider_config.validate()
        try:
            future = host.optimize_prompt(prompt, provider_config=provider_config)
            optimized = future.result(timeout=_PROVIDER_TEST_TIMEOUT_SECONDS)
        except TimeoutError:
            raise GatewayError("prompt_optimization_timeout") from None
        except GatewayError:
            raise
        except Exception as exc:
            code = str(exc).strip()
            if code == "runtime_busy":
                raise GatewayError("runtime_busy") from None
            if code in {"prompt_optimization_empty", "runtime_unavailable"}:
                raise GatewayError(code) from None
            raise GatewayError("prompt_optimization_failed") from exc
        active_provider = provider_config or host.settings.provider
        active_provider_id = active_provider.id
        active_model = active_provider.model
        return self._reply(
            "prompt.optimize.result",
            {
                "epoch": self.epoch,
                "optimizedPrompt": optimized,
                "providerId": active_provider_id,
                "model": active_model,
            },
            session_id=command.session_id,
        )
