"""Optional pinned model downloads; partial content never becomes executable weights."""

from __future__ import annotations

import asyncio
import errno
import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from mobile_model_catalog import MODEL_CATALOG, SPEECH_CATALOG, VISION_CATALOG
from mobile_trained_model import LOCAL_MODEL_CATALOG

_MANAGED_MODEL_FILES = ("installed.json", "partial.json")
# The first bytes of each weight format: GGUF's magic; an ONNX model is a protobuf whose first
# field is ir_version (field 1, varint).
_FORMAT_MAGIC = {"gguf": b"GGUF", "onnx": b"\x08"}


def _weights_name(model) -> str:
    """The weights' file name in the model's private directory."""
    return model.get("weights_file", "model.gguf")


def _managed_files(model) -> tuple[str, ...]:
    weights = _weights_name(model)
    return (weights, weights + ".part", *_MANAGED_MODEL_FILES)


_PREFIX_CACHE = "prefix-cache"
_SOURCE_IDS = ("huggingface", "modelscope")


class _SourceFailed(Exception):
    """One download source could not serve the file; another source still may."""

    def __init__(self, message, *, discard_partial=False):
        super().__init__(message)
        self.discard_partial = discard_partial


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class ModelManager:
    def __init__(self, root: Path, catalog=None, *, client_factory=None, disk_free=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog = {
            item["model_id"]: dict(item)
            for item in (
                (*MODEL_CATALOG, *LOCAL_MODEL_CATALOG, *VISION_CATALOG, *SPEECH_CATALOG)
                if catalog is None
                else catalog
            )
        }
        if catalog is None:
            for model in LOCAL_MODEL_CATALOG:
                component = self.catalog.get(model.get("vision_projector_id"))
                if component is not None:
                    component["compatible_models"] = [
                        *component.get("compatible_models", []),
                        model["model_id"],
                    ]
        for model in self.catalog.values():
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,95}", model["model_id"]):
                raise ValueError("invalid catalog model id")
            if not re.fullmatch(r"[a-f0-9]{64}", model["sha256"]) or not re.fullmatch(
                r"[a-f0-9]{40}", model["revision"]
            ):
                raise ValueError("catalog requires pinned revision and SHA256")
            if type(model["size_bytes"]) is not int or model["size_bytes"] <= 4:
                raise ValueError("invalid model size")
            if model.get("local_artifact") is True:
                if model.get("download_url") is not None:
                    raise ValueError("local training artifacts must be imported from a file")
                continue
            for source in self._sources(model):
                address = urlsplit(source["url"])
                if (
                    address.scheme != "https"
                    or not address.hostname
                    or address.username
                    or address.fragment
                ):
                    raise ValueError("model download requires an absolute HTTPS origin")
        self._client_factory = client_factory or (
            lambda: httpx.AsyncClient(
                timeout=httpx.Timeout(30, read=60),
                trust_env=False,
                follow_redirects=True,
                headers={"User-Agent": "AgentWorkspaceAndroid/0.1", "Accept-Encoding": "identity"},
            )
        )
        self._disk_free = disk_free or (lambda: shutil.disk_usage(self.root).free)
        self._lock = threading.RLock()
        self._jobs = {}
        self._verified = {}
        state_file = self.root / "downloads.json"
        try:
            self._states = (
                json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
            )
        except (ValueError, OSError) as exc:
            raise ValueError(
                "model download state is unreadable; preserve it before recovery"
            ) from exc
        if not isinstance(self._states, dict):
            raise ValueError("model download state must be an object")
        for record in self._states.values():
            if isinstance(record, dict) and record.get("state") in {
                "queued",
                "downloading",
                "verifying",
            }:
                record.update(state="paused", error="Download interrupted; resume when ready")

    def _model(self, model_id):
        if not isinstance(model_id, str) or model_id not in self.catalog:
            raise ValueError("unknown catalog model")
        return self.catalog[model_id]

    def _directory(self, model_id):
        self._model(model_id)
        directory = self.root / model_id
        if directory.is_symlink() or not directory.resolve().is_relative_to(self.root):
            raise ValueError("model path escaped private storage")
        return directory

    def _update(self, model_id, **updates):
        with self._lock:
            record = self._states.setdefault(model_id, {})
            record.update(updates, updated_at=time.time())
            _atomic_json(self.root / "downloads.json", self._states)

    @staticmethod
    def _identity(model):
        # Every source serves the same pinned bytes, so a partial file resumes from any of them.
        return {key: model[key] for key in ("sha256", "size_bytes", "revision")}

    @staticmethod
    def _sources(model):
        sources = model.get("download_sources") or [
            {
                "id": "default",
                "title": urlsplit(model["download_url"]).hostname,
                "url": model["download_url"],
            }
        ]
        return [dict(source) for source in sources]

    def _ordered_sources(self, model, source, prefer=None):
        sources = self._sources(model)
        ids = [item["id"] for item in sources]
        if source != "auto":
            if source not in ids:
                raise ValueError("unknown download source")
            return [item for item in sources if item["id"] == source]
        # The preferred source first (when this model has it); the others are fallbacks
        # tried in turn when it cannot be reached.
        return sorted(sources, key=lambda item: item["id"] != prefer)

    def _validate_file(self, path, model):
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("model integrity failed: unsafe file path")
        if not path.is_file() or path.stat().st_size != model["size_bytes"]:
            raise ValueError("model integrity failed: size mismatch")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            weight_format = model.get("format", "gguf")
            magic = _FORMAT_MAGIC[weight_format]
            if source.read(len(magic)) != magic:
                raise ValueError(f"model integrity failed: not {weight_format.upper()} weights")
            source.seek(0)
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != model["sha256"]:
            raise ValueError("model integrity failed: SHA256 mismatch")

    def installed_path(self, model_id) -> Path:
        model = self._model(model_id)
        directory = self._directory(model_id)
        path, marker = directory / _weights_name(model), directory / "installed.json"
        try:
            if path.is_symlink() or marker.is_symlink():
                raise ValueError("model integrity failed: unsafe installed path")
            metadata = json.loads(marker.read_text(encoding="utf-8"))
            if (
                any(metadata.get(key) != model[key] for key in ("sha256", "revision"))
                or metadata.get("size") != model["size_bytes"]
            ):
                raise ValueError("model integrity failed: installed metadata mismatch")
            stat = path.stat()
            stamp = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            if self._verified.get(model_id) != stamp:
                self._validate_file(path, model)
                self._verified[model_id] = stamp
            return path
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise ValueError("model is not installed with verified integrity") from exc

    def snapshot(self):
        records = {}
        for model_id, model in self.catalog.items():
            record = dict(self._states.get(model_id, {}))
            state = record.get("state", "not_installed")
            directory = self._directory(model_id)
            if (directory / "installed.json").is_file():
                try:
                    self.installed_path(model_id)
                    state = "installed"
                except ValueError:
                    state = "failed"
                    record["error"] = "Installed model failed integrity validation"
            received = record.get("downloaded_bytes", 0)
            partial = directory / (_weights_name(model) + ".part")
            if state == "paused" and partial.is_file():
                received = partial.stat().st_size
            records[model_id] = {
                **model,
                **record,
                "state": state,
                "downloaded_bytes": received,
                "progress": min(1, max(0, received / model["size_bytes"])),
                "installed": state == "installed",
                "has_local_files": any(
                    (directory / name).is_file() or (directory / name).is_symlink()
                    for name in _managed_files(model)
                ),
            }
        models, components, speech = [], [], []
        for record in records.values():
            if record.get("kind") == "vision_projection":
                components.append(record)
                continue
            # Speech recognition weights are for voice input, never a chat model to select.
            if record.get("kind") == "speech_recognition":
                speech.append(record)
                continue
            component = records.get(record.get("vision_projector_id"))
            models.append(
                {
                    **record,
                    "vision_component_installed": bool(component and component["installed"]),
                }
            )
        return {
            "models": models,
            "vision_components": components,
            "speech_models": speech,
            "storage_free_bytes": self._disk_free(),
            "weights_bundled": False,
            "downloads_resumable": True,
        }

    def installed_projection_path(self, model_id) -> Path:
        model = self._model(model_id)
        projection_id = model.get("vision_projector_id")
        component = self.catalog.get(projection_id)
        if (
            model.get("kind") == "vision_projection"
            or component is None
            or component.get("kind") != "vision_projection"
            or model_id not in component.get("compatible_models", [])
        ):
            raise ValueError("this model has no compatible vision component")
        return self.installed_path(projection_id)

    def start_download(self, model_id, source="auto", prefer=None):
        model = self._model(model_id)
        if model.get("local_artifact") is True:
            raise ValueError("Import this local training artifact from a file")
        if any(not job.done() for job in self._jobs.values()):
            raise ValueError("a model download is already active")
        self._ordered_sources(model, source, prefer)
        self._update(model_id, state="queued", error=None)
        task = asyncio.create_task(
            self.download(model_id, source, prefer), name="model-download-" + model_id
        )
        self._jobs[model_id] = task
        # Retrieve errors while preserving them in the persisted progress record.
        task.add_done_callback(lambda job: None if job.cancelled() else job.exception())
        return {"model_id": model_id, "state": "queued"}

    async def cancel_download(self, model_id):
        self._model(model_id)
        task = self._jobs.get(model_id)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._states.get(model_id, {}).get("state") in {"queued", "downloading", "verifying"}:
            self._update(model_id, state="paused", error=None)
        return self.snapshot()

    async def _fetch(self, model_id, model, source, partial):
        """Fetch the rest of the file from one source, resuming whatever is already on disk."""
        offset = partial.stat().st_size if partial.is_file() else 0
        if offset >= model["size_bytes"]:
            return
        self._update(model_id, state="downloading", downloaded_bytes=offset, source=source["id"])
        started, start_bytes, last_save = time.monotonic(), offset, time.monotonic()
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        async with (
            self._client_factory() as client,
            client.stream("GET", source["url"], headers=headers) as response,
        ):
            if any(item.url.scheme != "https" for item in [*response.history, response]):
                raise _SourceFailed("model host redirected to an insecure origin")
            if response.status_code == 206:
                match = re.fullmatch(
                    r"bytes (\d+)-(\d+)/(\d+)",
                    response.headers.get("Content-Range", ""),
                )
                if not match or tuple(map(int, match.groups())) != (
                    offset,
                    model["size_bytes"] - 1,
                    model["size_bytes"],
                ):
                    raise _SourceFailed("invalid model download range", discard_partial=True)
            elif response.status_code == 200:
                offset = 0
                start_bytes = 0
            else:
                raise _SourceFailed(f"model download returned HTTP {response.status_code}")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) != model["size_bytes"] - offset:
                raise _SourceFailed(
                    "model integrity failed: response length mismatch", discard_partial=True
                )
            with partial.open("ab" if offset else "wb") as output:
                received = offset
                async for chunk in response.aiter_bytes():
                    if received + len(chunk) > model["size_bytes"]:
                        raise _SourceFailed(
                            "model integrity failed: oversized response", discard_partial=True
                        )
                    output.write(chunk)
                    received += len(chunk)
                    now = time.monotonic()
                    if now - last_save >= 0.75 or received == model["size_bytes"]:
                        output.flush()
                        self._update(
                            model_id,
                            state="downloading",
                            downloaded_bytes=received,
                            bytes_per_second=round(
                                (received - start_bytes) / max(now - started, 0.01)
                            ),
                        )
                        last_save = now
                output.flush()
                os.fsync(output.fileno())

    async def download(self, model_id, source="auto", prefer=None):
        model = self._model(model_id)
        if model.get("local_artifact") is True:
            raise ValueError("Import this local training artifact from a file")
        sources = self._ordered_sources(model, source, prefer)
        directory = self._directory(model_id)
        directory.mkdir(parents=True, exist_ok=True)
        weights = _weights_name(model)
        partial, metadata_file = directory / (weights + ".part"), directory / "partial.json"
        identity = self._identity(model)
        try:
            old_identity = (
                json.loads(metadata_file.read_text()) if metadata_file.is_file() else None
            )
        except (OSError, ValueError):
            old_identity = None
        if partial.is_symlink():
            raise ValueError("unsafe partial model path")
        if (
            not isinstance(old_identity, dict)
            or any(old_identity.get(key) != value for key, value in identity.items())
            or (partial.is_file() and partial.stat().st_size > model["size_bytes"])
        ):
            partial.unlink(missing_ok=True)
        offset = partial.stat().st_size if partial.is_file() else 0
        try:
            if self._disk_free() < model["size_bytes"] - offset + 16 * 1024**2:
                raise ValueError("not enough storage space for this model")
            _atomic_json(metadata_file, identity)
            self._update(model_id, state="downloading", downloaded_bytes=offset, error=None)
            failures = []
            for candidate in sources:
                try:
                    await self._fetch(model_id, model, candidate, partial)
                    break
                except (_SourceFailed, httpx.HTTPError) as failure:
                    if getattr(failure, "discard_partial", False):
                        partial.unlink(missing_ok=True)
                    reason = (
                        str(failure)
                        if isinstance(failure, _SourceFailed)
                        else "model download interrupted; check connection and storage"
                    )
                    failures.append((candidate["title"], reason))
            else:
                if len(failures) == 1:
                    raise ValueError(failures[0][1])
                raise ValueError(
                    "every download source failed: "
                    + "; ".join(f"{title}: {reason}" for title, reason in failures)
                )
            self._update(model_id, state="verifying", downloaded_bytes=partial.stat().st_size)
            await asyncio.to_thread(self._validate_file, partial, model)
            final = directory / weights
            partial.replace(final)
            try:
                _atomic_json(
                    directory / "installed.json",
                    {
                        "model_id": model_id,
                        "size": model["size_bytes"],
                        "sha256": model["sha256"],
                        "revision": model["revision"],
                        "installed_at": time.time(),
                    },
                )
            except OSError:
                final.replace(partial)
                raise
            metadata_file.unlink(missing_ok=True)
            self._verified.pop(model_id, None)
            self._update(
                model_id, state="installed", downloaded_bytes=model["size_bytes"], error=None
            )
            return {"model_id": model_id, "state": "installed"}
        except asyncio.CancelledError:
            self._update(
                model_id,
                state="paused",
                downloaded_bytes=partial.stat().st_size if partial.is_file() else 0,
                error=None,
            )
            raise
        except (ValueError, OSError, httpx.HTTPError) as exc:
            message = (
                str(exc)
                if isinstance(exc, ValueError)
                else "model download interrupted; check connection and storage"
            )
            if "integrity" in message or "range" in message:
                partial.unlink(missing_ok=True)
                metadata_file.unlink(missing_ok=True)
            self._update(
                model_id,
                state="failed",
                error=message[:300],
                downloaded_bytes=partial.stat().st_size if partial.is_file() else 0,
            )
            raise ValueError(message) from None

    def remove(self, model_id):
        model = self._model(model_id)
        directory = self._directory(model_id)
        job = self._jobs.get(model_id)
        if job is not None and not job.done():
            raise ValueError("pause this download before removing it")
        for name in _managed_files(model):
            (directory / name).unlink(missing_ok=True)
        # Saved prompt states of this model (written by the native engine) go with it.
        prefix_cache = directory / _PREFIX_CACHE
        if prefix_cache.is_dir() and not prefix_cache.is_symlink():
            shutil.rmtree(prefix_cache, ignore_errors=True)
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError as exc:
            if exc.errno not in {errno.ENOTEMPTY, errno.EEXIST}:
                raise
        self._verified.pop(model_id, None)
        self._update(model_id, state="not_installed", downloaded_bytes=0, error=None)
        return {"model_id": model_id, "state": "not_installed"}

    async def aclose(self):
        for job in self._jobs.values():
            if not job.done():
                job.cancel()
        if self._jobs:
            await asyncio.gather(*self._jobs.values(), return_exceptions=True)


_MANAGERS = {}
_MANAGER_LOCK = threading.RLock()


def get_model_manager(root: Path | None = None) -> ModelManager:
    if root is None:
        data = os.getenv("AGENT_WORKSPACE_DATA_DIR")
        if not data:
            raise ValueError("private model storage is unavailable")
        root = Path(data) / "local-models"
    key = str(Path(root).resolve())
    with _MANAGER_LOCK:
        if key not in _MANAGERS:
            _MANAGERS[key] = ModelManager(Path(key))
        return _MANAGERS[key]
