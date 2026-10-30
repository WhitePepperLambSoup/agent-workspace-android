"""Spec-driven work: a feature written down before it is built, in three documents the user
approves one after another (requirements, design, tasks) and then built task by task. The
documents live in the project under .agent/specs/<name>/, where the agent writes them and the
user can read and edit them like any other file."""

from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, cast

# The start of a prompt the window sends for a spec: shown as a short notice, not as the text.
SPEC_MARKER = "<!-- agent-workspace:spec -->"
SPECS_DIR = Path(".agent") / "specs"
DOCUMENTS = ("requirements", "design", "tasks")
STEPS = ("requirements", "design", "tasks", "build")
MAX_TITLE = 120
MAX_GOAL = 8000
MAX_DOCUMENT_CHARS = 200_000

_TASK = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s+(?:(\d+(?:\.\d+)*)[.)]?\s+)?(.+?)\s*$")
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")

_LANGUAGES = {
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ja-JP": "Japanese",
    "en-US": "English",
}


class SpecError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _slug(title: str) -> str:
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))[:48].strip("-")


def _approved(meta: dict[str, Any]) -> dict[str, Any]:
    value = meta.get("approved")
    return value if isinstance(value, dict) else {}


def parse_tasks(text: str) -> list[dict[str, object]]:
    """The checklist of tasks.md: `- [ ] 1. Do this` lines, numbered in order when not."""
    tasks: list[dict[str, object]] = []
    for line in text.splitlines():
        match = _TASK.match(line)
        if match is None or line.startswith((" " * 4, "\t")):
            continue
        done, number, body = match.groups()
        tasks.append(
            {
                "number": number or str(len(tasks) + 1),
                "text": body.strip(),
                "done": done.lower() == "x",
            }
        )
    return tasks


class SpecBook:
    """The specs of one project folder."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.base = root / SPECS_DIR

    def _folder(self, spec_id: object) -> Path:
        if not isinstance(spec_id, str) or not _ID.match(spec_id):
            raise SpecError("spec_not_found")
        folder = self.base / spec_id
        if not (folder / "spec.json").is_file():
            raise SpecError("spec_not_found")
        return folder

    def _meta(self, folder: Path) -> dict[str, Any]:
        try:
            meta = json.loads((folder / "spec.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise SpecError("spec_unreadable") from None
        if not isinstance(meta, dict):
            raise SpecError("spec_unreadable")
        return meta

    def _save(self, folder: Path, meta: dict[str, Any]) -> None:
        meta["updated"] = time.time()
        (folder / "spec.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _document(self, folder: Path, name: str) -> str | None:
        try:
            text = (folder / f"{name}.md").read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        return text[:MAX_DOCUMENT_CHARS] if text.strip() else None

    def _summary(self, folder: Path, meta: dict[str, Any]) -> dict[str, object]:
        tasks = parse_tasks(self._document(folder, "tasks") or "")
        step = meta.get("step") if meta.get("step") in STEPS else "requirements"
        done = step == "build" and bool(tasks) and all(task["done"] for task in tasks)
        return {
            "id": folder.name,
            "title": str(meta.get("title") or folder.name),
            "step": "done" if done else step,
            "tasksDone": sum(1 for task in tasks if task["done"]),
            "tasksTotal": len(tasks),
            "updated": meta.get("updated"),
            "path": (SPECS_DIR / folder.name).as_posix(),
        }

    def list(self) -> list[dict[str, object]]:
        if not self.base.is_dir():
            return []
        found = []
        for folder in self.base.iterdir():
            if (folder / "spec.json").is_file() and _ID.match(folder.name):
                try:
                    found.append(self._summary(folder, self._meta(folder)))
                except SpecError:
                    continue
        return sorted(found, key=lambda item: float(str(item.get("updated") or 0)), reverse=True)

    def create(self, title: str, goal: str) -> dict[str, object]:
        title, goal = " ".join(title.split()), goal.strip()
        if not title or len(title) > MAX_TITLE or len(goal) > MAX_GOAL:
            raise SpecError("invalid_spec")
        base = _slug(title) or "spec"
        spec_id, counter = base, 2
        while (self.base / spec_id).exists():
            spec_id, counter = f"{base}-{counter}", counter + 1
        folder = self.base / spec_id
        folder.mkdir(parents=True)
        self._save(
            folder,
            {
                "title": title,
                "goal": goal,
                "step": "requirements",
                "approved": {},
                "created": time.time(),
            },
        )
        return self.get(spec_id)

    def get(self, spec_id: object) -> dict[str, object]:
        folder = self._folder(spec_id)
        meta = self._meta(folder)
        documents = {name: self._document(folder, name) for name in DOCUMENTS}
        tasks = parse_tasks(documents["tasks"] or "")
        next_task = next((task for task in tasks if not task["done"]), None)
        return {
            **self._summary(folder, meta),
            "goal": str(meta.get("goal") or ""),
            "approved": _approved(meta),
            "documents": documents,
            "tasks": tasks,
            "nextTask": next_task,
        }

    def approve(self, spec_id: object, step: object) -> dict[str, object]:
        """The user accepts the document of the current step: the next one comes up."""
        folder = self._folder(spec_id)
        meta = self._meta(folder)
        current = meta.get("step") if meta.get("step") in STEPS else "requirements"
        if step != current or current == "build":
            raise SpecError("spec_step_mismatch")
        if self._document(folder, str(current)) is None:
            raise SpecError("spec_document_missing")
        if current == "tasks" and not parse_tasks(self._document(folder, "tasks") or ""):
            raise SpecError("spec_tasks_missing")
        approved = _approved(meta)
        meta["approved"] = {**approved, str(current): time.time()}
        meta["step"] = STEPS[STEPS.index(str(current)) + 1]
        self._save(folder, meta)
        return self.get(spec_id)

    def reopen(self, spec_id: object, step: object) -> dict[str, object]:
        """Back to an earlier document; what came after it has to be approved again."""
        folder = self._folder(spec_id)
        if step not in DOCUMENTS:
            raise SpecError("spec_step_mismatch")
        meta = self._meta(folder)
        index = STEPS.index(str(step))
        approved = _approved(meta)
        meta["approved"] = {key: value for key, value in approved.items() if key in STEPS[:index]}
        meta["step"] = step
        self._save(folder, meta)
        return self.get(spec_id)

    def prompt(
        self, spec_id: object, step: object, language: str = "en-US", task: object = None
    ) -> str:
        """What the agent is asked to do for a step: write a document, or build."""
        spec = self.get(spec_id)
        folder = f"{spec['path']}"
        title = spec["title"]
        written_in = _LANGUAGES.get(language, "English")
        header = (
            f"{SPEC_MARKER}\n<!-- "
            + json.dumps({"spec": spec["id"], "title": title, "step": step, "task": task})
            + " -->\n"
        )
        if step == "requirements" and spec["step"] == "requirements":
            return header + (
                f'Write the requirements for "{title}" in `{folder}/requirements.md`.\n\n'
                f"What I want: {spec['goal'] or title}\n\n"
                "Look at the project first, as far as it bears on this. Then write, in "
                f"{written_in}: a short introduction (the problem, who it is for); the "
                "requirements, numbered, each as a user story (As a …, I want …, so that …) "
                "with acceptance criteria in the form WHEN … THEN the system SHALL …; and what "
                "is out of scope. End your reply with the questions you could not settle from "
                "the project and what I wrote, rather than guessing. Write only that file; do "
                "not change any code yet."
            )
        if step == "design" and spec["step"] == "design":
            return header + (
                f'Write the design for "{title}" in `{folder}/design.md`, from the approved '
                f"`{folder}/requirements.md` and the code as it is now. In {written_in}: an "
                "overview; the parts of this project it changes or adds, with their file paths; "
                "data models and interfaces; error handling; how it will be tested. A mermaid "
                "diagram where it helps. Say which requirement each part serves. Write only "
                "that file; do not change any code yet."
            )
        if step == "tasks" and spec["step"] == "tasks":
            return header + (
                f'Write the implementation plan for "{title}" in `{folder}/tasks.md`, from the '
                f"approved `{folder}/requirements.md` and `{folder}/design.md`. In {written_in}: "
                "a checklist of coding tasks in the order to do them, each small enough for one "
                "step and each leaving the project working, as lines `- [ ] 1. <task>` with "
                "indented sub-points naming the files and the requirements it serves. Every "
                "task writes or changes code or tests; tests come with the code they test. No "
                "deployment or manual-testing tasks. Write only that file."
            )
        if step == "build" and spec["step"] in {"build", "done"}:
            documents = f"`{folder}/requirements.md`, `{folder}/design.md` and `{folder}/tasks.md`"
            if task is None:
                return header + (
                    f'Build "{title}": carry out the unchecked tasks of `{folder}/tasks.md` in '
                    f"order. Read {documents} first. For each task: do it, run the project's "
                    "checks (run_checks, or its tests), mark it done in tasks.md (`- [x]`), and go "
                    "on to the next. Stop and tell me if a task turns out wrong or the design "
                    "does not hold, rather than working around it."
                )
            tasks = cast(list[dict[str, object]], spec["tasks"])
            found = next((item for item in tasks if item["number"] == task), None)
            if found is None:
                raise SpecError("spec_task_missing")
            return header + (
                f'Do task {task} of "{title}": {found["text"]}\n\nRead {documents} first. Do '
                "only this task. Run the project's checks (run_checks, or its tests); when it "
                "works, mark the task done in tasks.md (`- [x]`). Then stop and tell me what "
                "changed."
            )
        raise SpecError("spec_step_mismatch")


__all__ = ["DOCUMENTS", "SPEC_MARKER", "STEPS", "SpecBook", "SpecError", "parse_tasks"]
