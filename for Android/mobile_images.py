"""Resolve session-owned attachment references into bounded, verified image bytes."""

from __future__ import annotations

import hashlib
import stat
from typing import Any

from mobile_protocol import MobileImageRef

from agent_workspace.core.models import ImagePart, validate_image_parts
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.filesystem import _open_identity_checked, _scan_file
from agent_workspace.tools.paths import WorkspacePaths

MAX_MOBILE_ATTACHMENT_BYTES = 4 * 1024 * 1024
_SUPPORTED_MEDIA_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
_SUPPORTED_IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp"})
_UNSUPPORTED_IMAGE_EXTENSIONS = frozenset(
    {
        "heic",
        "heif",
        "hif",
        "avif",
        "svg",
        "svgz",
        "bmp",
        "dib",
        "tif",
        "tiff",
        "ico",
        "icns",
        "psd",
        "jxl",
        "jp2",
        "j2k",
        "jpf",
        "jpm",
        "pbm",
        "pgm",
        "ppm",
    }
)
_BMFF_IMAGE_BRANDS = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"avif", b"avis"}
)


def _unsupported_image_signature(content: bytes) -> bool:
    if len(content) >= 12 and content[4:8] == b"ftyp":
        box_size = int.from_bytes(content[:4], "big")
        end = min(len(content), box_size or len(content), 1024)
        brands = {content[8:12]} | {content[offset : offset + 4] for offset in range(16, end, 4)}
        if brands & _BMFF_IMAGE_BRANDS:
            return True
    probe = content[:2048].lstrip(b"\xef\xbb\xbf \t\r\n")
    return (
        (len(content) >= 14 and content.startswith(b"BM"))
        or content.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+", b"8BPS", b"icns"))
        or content.startswith(
            (b"\xff\x0a", b"\x00\x00\x00\x0cJXL \r\n\x87\n", b"\x00\x00\x00\x0cjP  \r\n\x87\n")
        )
        or (len(content) >= 6 and content.startswith(b"\x00\x00\x01\x00"))
        or probe.startswith(b"<svg")
        or (probe.startswith((b"<?xml", b"<!--")) and b"<svg" in probe)
    )


def attachment_media_type(
    content: bytes, *, filename: str = "", declared_media_type: str | None = None
) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if declared_media_type is not None and not isinstance(declared_media_type, str):
        raise ValueError("media_type must be a MIME type string")
    declared = (declared_media_type or "").split(";", 1)[0].strip().lower()
    if (
        extension in _UNSUPPORTED_IMAGE_EXTENSIONS
        or (declared.startswith("image/") and declared not in _SUPPORTED_MEDIA_TYPES)
        or _unsupported_image_signature(content)
    ):
        raise ValueError(
            "unsupported image format; convert to PNG, JPEG, WebP, or GIF (first frame)"
        )
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if extension in _SUPPORTED_IMAGE_EXTENSIONS or declared.startswith("image/"):
        raise ValueError("invalid image file; import a valid PNG, JPEG, WebP, or GIF (first frame)")
    return "application/octet-stream"


def attachment_receipt(
    runtime: Any, session_id: str, path: str, *, retain_content: bool = True
) -> tuple[dict[str, Any], bytes]:
    """Return current verified bytes only with this session's live import proof."""
    session = runtime.service.get_session(session_id)
    # Reuse structural path validation, without requiring a client-provided hash.
    MobileImageRef(path, "0" * 64)
    paths = WorkspacePaths(session.workspace)
    execution_workspace = getattr(runtime.service, "_execution_workspace", None)
    if execution_workspace is not None and paths.root != WorkspacePaths(execution_workspace).root:
        raise KeyError(session_id)
    imported = None
    for event in runtime.store.list_events(session_id):
        if event.data.get("path") != path:
            continue
        if event.type == "mobile.attachment.imported":
            imported = event.data
        elif event.type == "mobile.attachment.deleted":
            imported = None
    if imported is None:
        raise KeyError(path)
    try:
        target = paths.resolve(path)
        if retain_content or imported.get("media_type", "").startswith("image/"):
            digest, content = _scan_file(
                target,
                max_scan_bytes=MAX_MOBILE_ATTACHMENT_BYTES,
                retain_limit=MAX_MOBILE_ATTACHMENT_BYTES,
            )
            size = len(content) if content is not None else None
        else:
            digest_state = hashlib.sha256()
            prefix = bytearray()
            with _open_identity_checked(target, "rb") as stream:
                paths.resolve(path)
                before = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), target)
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError("imported attachment is not a file")
                size = 0
                remaining = before.st_size
                while remaining:
                    chunk = stream.read(min(remaining, 64 * 1024))
                    if not chunk:
                        break
                    size += len(chunk)
                    remaining -= len(chunk)
                    digest_state.update(chunk)
                    if len(prefix) < 2048:
                        prefix.extend(chunk[: 2048 - len(prefix)])
                after = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), target)
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                ):
                    raise ValueError("imported attachment changed during verification")
            digest = digest_state.hexdigest()
            content = bytes(prefix)
    except (OSError, ToolError) as error:
        raise ValueError("imported image could not be verified inside its workspace") from error
    if content is None or size != imported.get("size") or digest != imported.get("sha256"):
        raise ValueError("imported image changed or is missing; import it again")
    media_type = attachment_media_type(
        content, filename=imported["name"], declared_media_type=imported.get("media_type")
    )
    if media_type == "application/octet-stream" and not imported.get("media_type", "").startswith(
        "image/"
    ):
        media_type = imported.get("media_type", media_type)
    if imported.get("media_type", media_type) != media_type:
        raise ValueError("imported image media type no longer matches its receipt")
    return {
        "name": imported["name"],
        "path": path,
        "size": size,
        "sha256": digest,
        "media_type": media_type,
        **({"request_id": imported["request_id"]} if imported.get("request_id") else {}),
    }, content if retain_content else b""


def resolve_mobile_images(
    runtime: Any, session_id: str, refs: tuple[MobileImageRef, ...]
) -> tuple[ImagePart, ...]:
    parts = []
    for ref in refs:
        try:
            receipt, content = attachment_receipt(runtime, session_id, ref.path)
        except KeyError as error:
            raise ValueError(
                "image attachment does not belong to this session or was deleted"
            ) from error
        if receipt["sha256"] != ref.sha256:
            raise ValueError("image attachment SHA-256 does not match its import receipt")
        if not receipt["media_type"].startswith("image/"):
            raise ValueError(
                "image reference must identify a supported PNG, JPEG, WebP, or GIF attachment"
            )
        parts.append(ImagePart(receipt["media_type"], content))
    images = tuple(parts)
    validate_image_parts(images)
    return images
