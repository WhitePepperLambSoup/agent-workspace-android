"""Plugin scaffold generator."""

from __future__ import annotations

import json
from pathlib import Path

from agent_workspace.core.plugins import PluginManifest, PluginRegistry

_PLUGIN_TEMPLATE = '''"""Generated {name} plugin."""


def tools() -> tuple:
    """Return the plugin's tool classes."""
    return ()


def register(registry) -> None:
    """Register plugin tools with a registry, if supported."""
    return None
'''


def scaffold_plugin(
    destination: str | Path,
    *,
    plugin_id: str,
    name: str,
    version: int = 1,
    tools: tuple[str, ...] = (),
    entry_point: str = "plugin.py",
    force: bool = False,
) -> tuple[Path, Path]:
    """Create a validated manifest and a minimal Python entry point."""
    manifest = PluginManifest(
        id=plugin_id,
        name=name,
        version=version,
        entry_point=entry_point,
        tools=tools,
    )
    # Validate registration semantics before touching disk.
    registry = PluginRegistry()
    registry.register(manifest)
    directory = Path(destination).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / f"{manifest.id}.json"
    plugin_path = directory / entry_point
    if not force and (manifest_path.exists() or plugin_path.exists()):
        raise FileExistsError("plugin scaffold destination already exists")
    manifest_path.write_text(
        json.dumps(manifest.to_document(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    plugin_path.write_text(
        _PLUGIN_TEMPLATE.format(name=name),
        encoding="utf-8",
    )
    return manifest_path, plugin_path


__all__ = ["scaffold_plugin"]
