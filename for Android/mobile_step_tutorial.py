"""A picture tutorial made from a task's step pictures (step replay), to send to someone who wants to
do the same thing on their own phone.

Each step says what was done. A step that touched one spot shows the screen it was done on, the
picture kept after the step before, with that spot circled; that picture only counts when it was
taken before the step was done (steps of one batch follow each other faster than pictures are
taken). Other steps show the screen they led to, when no later step shows it already. Small
floating windows on a picture (this app's bubble, a floating assist button) are painted out. The
user edits the words and drops steps in the console; StepTutorial.kt draws the long picture.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mobile_step_shots import _folder

MAX_FRAMES = 80
_MAX_CAPTION = 300
_MAX_TITLE = 200


def tasks_with_steps(tasks: list[Any]) -> list[dict[str, Any]]:
    """Of a conversation's tasks, those whose step pictures are still kept, newest first."""
    from mobile_step_shots import count

    found = []
    for task in tasks:
        steps = count(task.task_id)
        if steps:
            found.append({"task_id": task.task_id, "prompt": task.prompt_preview, "created_at": task.created_at, "steps": steps})
    return sorted(found, key=lambda item: str(item["created_at"] or ""), reverse=True)


def _entries(task_id: str) -> list[dict[str, Any]]:
    """Each step of the task in order: index, label, when it was done, the spot, its picture."""
    folder = _folder(task_id)
    if folder is None or not folder.is_dir():
        return []
    try:
        listed = json.loads((folder / "steps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        listed = []
    steps: dict[int, dict[str, Any]] = {}
    for item in listed if isinstance(listed, list) else []:
        if isinstance(item, dict) and isinstance(item.get("index"), int):
            steps[item["index"]] = item
    # A picture whose words were lost is still a step.
    for picture in folder.glob("*.jpg"):
        if picture.stem.isdigit():
            steps.setdefault(int(picture.stem), {"index": int(picture.stem)})
    result = []
    for index in sorted(steps):
        item = steps[index]
        picture = folder / f"{index:02d}.jpg"
        x, y = item.get("x"), item.get("y")
        spot = [float(x), float(y)] if all(_fraction(v) for v in (x, y)) else None
        covers = item.get("covers")
        result.append({
            "index": index,
            "label": str(item.get("label") or ""),
            "acted": item.get("acted") if isinstance(item.get("acted"), (int, float)) else None,
            "at": item.get("at") if isinstance(item.get("at"), (int, float)) else None,
            "spot": spot,
            "picture": picture if picture.is_file() else None,
            # Small floating windows on the picture (this app's bubble, a floating assist button).
            "covers": [[float(v) for v in box] for box in covers[:6]
                       if isinstance(box, list) and len(box) == 4 and all(_fraction(v) for v in box)]
            if isinstance(covers, list) else [],
        })
    return result


def _fraction(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def plan(task_id: str) -> list[dict[str, Any]]:
    """[{kind: step|done, index, caption, picture: Path|None, covers, ring: [x, y]|None}] in order."""
    entries = _entries(task_id)
    frames: list[dict[str, Any]] = []
    used: set[int] = set()
    for position, entry in enumerate(entries):
        frame = {"kind": "step", "index": entry["index"], "caption": entry["label"], "picture": None, "covers": [], "ring": None}
        before = entries[position - 1] if position else None
        if (
            entry["spot"] is not None
            and before is not None
            and before["index"] == entry["index"] - 1
            and before["picture"] is not None
            and before["at"] is not None
            and entry["acted"] is not None
            and before["at"] <= entry["acted"]
        ):
            frame.update(picture=before["picture"], covers=before["covers"], ring=entry["spot"])
            used.add(before["index"])
        frames.append(frame)
    # Where a step shows nothing, the screen it led to, unless the next step shows that one.
    for frame, entry in zip(frames, entries):
        if frame["picture"] is None and entry["picture"] is not None and entry["index"] not in used:
            frame.update(picture=entry["picture"], covers=entry["covers"])
            used.add(entry["index"])
    if entries and entries[-1]["picture"] is not None and entries[-1]["index"] not in used:
        last = entries[-1]
        frames.append({"kind": "done", "index": None, "caption": "", "picture": last["picture"], "covers": last["covers"], "ring": None})
    return frames


def preview(task_id: str) -> list[dict[str, Any]]:
    """The plan for the console: pictures as data URIs."""
    shown = []
    for frame in plan(task_id):
        image = None
        if frame["picture"] is not None:
            try:
                image = "data:image/jpeg;base64," + base64.b64encode(frame["picture"].read_bytes()).decode("ascii")
            except OSError:
                pass
        shown.append({**{key: value for key, value in frame.items() if key != "picture"}, "image": image})
    return shown


def _chosen(task_id: str, frames: Any) -> list[dict[str, Any]]:
    """The frames the user kept, in their order and with their words, checked against the plan."""
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"a tutorial has 1 to {MAX_FRAMES} steps")
    planned = {(frame["kind"], frame["index"]): frame for frame in plan(task_id)}
    chosen, seen, number = [], set(), 0
    for item in frames:
        key = (item.get("kind"), item.get("index")) if isinstance(item, dict) else None
        if key not in planned or key in seen:
            raise ValueError("unknown or repeated tutorial step")
        seen.add(key)
        caption = item.get("caption")
        if not isinstance(caption, str) or len(caption) > _MAX_CAPTION:
            raise ValueError(f"each step's words are text of at most {_MAX_CAPTION} characters")
        frame = planned[key]
        done = frame["kind"] == "done"
        number += 0 if done else 1
        chosen.append({
            "number": "" if done else str(number),
            "caption": " ".join(caption.split()),
            "picture": str(frame["picture"]) if frame["picture"] is not None else "",
            "covers": frame["covers"],
            "ring": frame["ring"],
            "done": done,
        })
    return chosen


def _render_native(spec: dict[str, Any]) -> dict[str, Any]:
    from java import jclass

    return json.loads(str(jclass("com.agentworkspace.mobile.documents.StepTutorial").render(json.dumps(spec, ensure_ascii=False))))


async def export_tutorial(
    workspace: str | Path,
    task_id: str,
    title: Any,
    subtitle: Any,
    frames: Any,
    render: Callable[[dict[str, Any]], dict[str, Any]] = _render_native,
) -> dict[str, Any]:
    """Draws the tutorial and writes it to <workspace>/exports; returns the workspace-relative paths."""
    from mobile_conversation_export import _file_stem

    if not isinstance(title, str) or not title.strip() or len(title) > _MAX_TITLE:
        raise ValueError(f"title is text of 1 to {_MAX_TITLE} characters")
    if not isinstance(subtitle, str) or len(subtitle) > _MAX_TITLE:
        raise ValueError(f"subtitle is text of at most {_MAX_TITLE} characters")
    chosen = _chosen(task_id, frames)
    root = Path(workspace)
    folder = root / "exports"

    def draw() -> list[str]:
        folder.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="tutorial-", dir=os.getenv("AGENT_WORKSPACE_DATA_DIR") or None))
        try:
            result = render({"title": " ".join(title.split()), "subtitle": " ".join(subtitle.split()),
                             "output_dir": str(scratch), "frames": chosen})
            outputs = result.get("outputs")
            if result.get("error") or not isinstance(outputs, list) or not outputs:
                raise RuntimeError(str(result.get("error") or "the tutorial picture was not drawn"))
            stem = _file_stem(title)
            paths = []
            for number, output in enumerate(outputs, start=1):
                source = Path(str(output.get("path") if isinstance(output, dict) else ""))
                if source.parent != scratch or not source.is_file():
                    raise RuntimeError("the tutorial picture is missing")
                name = f"{stem}.jpg" if len(outputs) == 1 else f"{stem}-{number}.jpg"
                shutil.copyfile(source, folder / name)
                paths.append(f"exports/{name}")
            return paths
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    return {"paths": await asyncio.to_thread(draw)}
