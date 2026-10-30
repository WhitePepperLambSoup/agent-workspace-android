"""Office commands of the window: the speech-to-text service meeting transcription uses (the one
chosen in Settings → Voice), and documents made from templates (built-in ones and the user's own
in the templates folder)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent_workspace.config import ProviderConfig, ProviderProtocol, is_loopback_endpoint
from agent_workspace.office import templates
from agent_workspace.office.ooxml import OfficeError
from agent_workspace.office.output import safe_name
from agent_workspace.settings import ProviderSettingsError, default_provider_settings_store
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths
from agent_workspace.ui_gateway import quick_actions
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_exports import EXPORT_FOLDER, export_name, unused, write_new
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

OFFICE_COMMANDS = frozenset(
    {
        "speech.set",
        "templates.list",
        "templates.create",
        "templates.folder.open",
        "quick.run",
        "quick.table",
    }
)
TEMPLATE_FOLDER = "templates"
_MAX_VALUES = 200


class OfficeCommands(GatewayState):
    """Speech service and document template commands."""

    def _office_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        handler = {
            "speech.set": self._speech_set,
            "templates.list": self._templates_list,
            "templates.create": self._templates_create,
            "templates.folder.open": self._templates_folder_open,
            "quick.run": self._quick_run,
            "quick.table": self._quick_table,
        }[command.type]
        return self._reply(f"{command.type}.result", handler(command), session_id=None)

    # ---- quick actions ----

    def _quick_provider(self) -> ProviderConfig:
        """The conversation's model, else the default profile."""
        with self._lock:
            config = self._provider
        if config is not None:
            return config
        store = self._provider_settings_store or default_provider_settings_store()
        try:
            default = store.load().default_provider_id
            resolved = store.resolve_config(default) if default else None
        except (KeyError, OSError, ProviderSettingsError, ValueError):
            resolved = None
        # A built-in profile nobody set up has no key: asking it would only fail.
        if resolved is None or not (resolved.api_key or is_loopback_endpoint(resolved.base_url)):
            raise GatewayError("provider_unconfigured")
        return resolved

    def _quick_run(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"action", "text"})
        action, text = command.payload["action"], command.payload["text"]
        if action not in quick_actions.ACTIONS:
            raise GatewayError("invalid_payload")
        if not isinstance(text, str) or not text.strip() or len(text) > quick_actions.MAX_TEXT:
            raise GatewayError("invalid_prompt")
        config = self._quick_provider()
        try:
            answer = quick_actions.run_text_action(config, str(action), text)
        except quick_actions.QuickActionError as error:
            raise GatewayError(str(error)) from None
        return {"text": answer, "model": config.model}

    def _quick_table(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"image"})
        image = command.payload["image"]
        if not isinstance(image, str) or len(image) > quick_actions.MAX_IMAGE_BYTES * 4 // 3 + 8:
            raise GatewayError("invalid_image")
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        try:
            rows, workbook = quick_actions.table_from_image(image)
        except quick_actions.QuickActionError as error:
            raise GatewayError(str(error)) from None
        paths = WorkspacePaths(workspace)
        try:
            folder = paths.resolve(EXPORT_FOLDER)
            folder.mkdir(parents=True, exist_ok=True)
            target = unused(folder / export_name("表格", ".xlsx"))
            write_new(target, workbook)
        except (OSError, WorkspacePathError):
            raise GatewayError("storage_unavailable") from None
        return {
            "path": paths.relative(target),
            "rows": len(rows),
            "columns": max((len(row) for row in rows), default=0),
            "preview": [row[:12] for row in rows[:12]],
        }

    # ---- speech ----

    def _speech_file(self) -> Path:
        return self._database.with_name("speech.json")

    def _speech_set(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"providerId", "model"})
        provider_id, model = command.payload["providerId"], command.payload["model"]
        if provider_id is not None and (not isinstance(provider_id, str) or len(provider_id) > 200):
            raise GatewayError("invalid_provider")
        if not isinstance(model, str) or len(model) > 200:
            raise GatewayError("invalid_model")
        document: dict[str, object] = {"providerId": provider_id or None, "model": model.strip()}
        try:
            self._speech_file().parent.mkdir(parents=True, exist_ok=True)
            write_new(self._speech_file(), json.dumps(document).encode("utf-8"))
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return document

    def speech_choice(self) -> tuple[str, str, str] | None:
        """(base URL, API key, model) of the speech-to-text service, or None when none is chosen
        or it is not an OpenAI-compatible profile."""
        try:
            saved = json.loads(self._speech_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        provider_id = saved.get("providerId") if isinstance(saved, dict) else None
        model = str(saved.get("model") or "whisper-1") if isinstance(saved, dict) else ""
        if not isinstance(provider_id, str) or not provider_id:
            return None
        store = self._provider_settings_store or default_provider_settings_store()
        try:
            profile = store.load().profiles.get(provider_id)
            if profile is None or profile.protocol is not ProviderProtocol.OPENAI_COMPATIBLE:
                return None
            config: ProviderConfig = store.resolve_config(provider_id)
        except (KeyError, OSError, ProviderSettingsError, ValueError):
            return None
        return config.base_url, config.api_key or "", model

    # ---- templates ----

    def _template_folder(self) -> Path:
        return self._database.parent / TEMPLATE_FOLDER

    def _templates_list(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        folder = self._template_folder()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            listed = templates.listing(folder)
        except (OSError, OfficeError):
            raise GatewayError("storage_unavailable") from None
        return {"templates": listed, "folder": str(folder)}

    def _templates_create(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"templateId"}, optional={"values", "folder"})
        template_id = command.payload["templateId"]
        values = command.payload.get("values") or {}
        target_folder = command.payload.get("folder") or ""
        if (
            not isinstance(template_id, str)
            or len(template_id) > 500
            or not isinstance(values, dict)
            or len(values) > _MAX_VALUES
            or not isinstance(target_folder, str)
            or len(target_folder) > 1000
        ):
            raise GatewayError("invalid_payload")
        clean: dict[str, Any] = {}
        for key, value in values.items():
            if not isinstance(key, str) or not isinstance(value, str) or len(value) > 5000:
                raise GatewayError("invalid_payload")
            if value.strip():
                clean[key] = value
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        paths = WorkspacePaths(workspace)
        try:
            data, suffix, missing, name = templates.create(
                template_id, self._template_folder(), clean
            )
        except OfficeError:
            raise GatewayError("unknown_template") from None
        try:
            folder = paths.resolve(target_folder) if target_folder else paths.root
            if not folder.is_dir():
                raise GatewayError("invalid_payload")
            target = unused(folder / f"{safe_name(name, 'document')}{suffix}")
            write_new(target, data)
        except WorkspacePathError:
            raise GatewayError("invalid_payload") from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return {"path": paths.relative(target), "bytes": len(data), "emptyFields": missing}

    def _templates_folder_open(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        folder = self._template_folder()
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise GatewayError("unsupported")
        try:
            folder.mkdir(parents=True, exist_ok=True)
            startfile(folder)
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return {"folder": str(folder)}


__all__ = ["OFFICE_COMMANDS", "TEMPLATE_FOLDER", "OfficeCommands"]
