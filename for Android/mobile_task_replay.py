"""A task's replay film (2.8): the console replays a turn's steps in the studio, records it, and sends
the video here to keep in the conversation's workspace under exports/, where it is shared or saved
like any export (mobile_conversation_export).

Only a video the browser recorded is taken: an MP4 or a WebM, told by its first bytes, at most
MAX_REPLAY_BYTES. It is written to a hidden part file first, so a broken upload leaves nothing behind.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, BinaryIO

from mobile_conversation_export import _file_stem

FORMATS = {"mp4": "video/mp4", "webm": "video/webm"}
MAX_REPLAY_BYTES = 48 * 1024 * 1024


def _looks_like(fmt: str, head: bytes) -> bool:
    if fmt == "webm":
        return head[:4] == b"\x1a\x45\xdf\xa3"
    return head[4:8] == b"ftyp"


def save_replay(workspace: str | Path, title: Any, fmt: Any, source: BinaryIO, *, content_length: int | None) -> dict[str, Any]:
    """Streams the film into <workspace>/exports and returns its workspace-relative path."""
    if fmt not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(FORMATS)}")
    if content_length is not None and (type(content_length) is not int or content_length <= 0):
        raise ValueError("invalid Content-Length")
    too_large = f"the film is larger than {MAX_REPLAY_BYTES // (1024 * 1024)} MiB"
    if content_length is not None and content_length > MAX_REPLAY_BYTES:
        raise ValueError(too_large)
    root = Path(workspace)
    folder = root / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{_file_stem(str(title or '') or 'replay')}.{fmt}"
    partial = folder / f".replay-{secrets.token_hex(6)}.part"
    size, head = 0, b""
    try:
        with partial.open("wb") as target:
            while content_length is None or size < content_length:
                wanted = 1 << 20 if content_length is None else min(1 << 20, content_length - size)
                block = source.read(wanted)
                if not block:
                    if content_length is not None:
                        raise ValueError("incomplete upload body")
                    break
                if len(head) < 16:
                    head += block[: 16 - len(head)]
                size += len(block)
                if size > MAX_REPLAY_BYTES:
                    raise ValueError(too_large)
                target.write(block)
        if not size or not _looks_like(fmt, head):
            raise ValueError(f"this is not a {fmt} video")
        partial.replace(folder / name)
    finally:
        partial.unlink(missing_ok=True)
    return {"paths": [f"exports/{name}"], "size": size, "mime_type": FORMATS[fmt]}
