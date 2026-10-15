"""Step replay: the small pictures the accessibility service keeps after each phone action of a
task (StepShots.kt, agent-data/step-shots/<task>/), read back for the console's viewer."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

_TASK = re.compile(r"[A-Za-z0-9-]{1,64}")


def _folder(task_id: str) -> Path | None:
    if not isinstance(task_id, str) or not _TASK.fullmatch(task_id):
        return None
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "step-shots" / task_id


def count(task_id: str) -> int:
    folder = _folder(task_id)
    return len(list(folder.glob("*.jpg"))) if folder and folder.is_dir() else 0


def steps(task_id: str) -> list[dict[str, Any]]:
    """[{"index", "label", "image": data URI}] in order; empty when there are none."""
    folder = _folder(task_id)
    if folder is None or not folder.is_dir():
        return []
    try:
        labels = {item["index"]: item.get("label", "") for item in json.loads((folder / "steps.json").read_text(encoding="utf-8"))}
    except (OSError, ValueError, KeyError, TypeError):
        labels = {}
    result = []
    for picture in sorted(folder.glob("*.jpg")):
        try:
            index = int(picture.stem)
            data = picture.read_bytes()
        except (ValueError, OSError):
            continue
        result.append({"index": index, "label": labels.get(index, ""),
                       "image": "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")})
    return result
