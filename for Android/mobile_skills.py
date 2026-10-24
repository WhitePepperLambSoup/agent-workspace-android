"""Skill packs: instructions for particular jobs, installed from GitHub or a file, phone-wide.

A skill is a folder with a ``SKILL.md`` file (the common Agent Skills format: YAML front matter
with ``name`` and ``description``, then the instructions in Markdown) and any files it refers to.
The workspace TOML skills of the core (``.agent/skills/*.toml``: id, name, description,
instructions) are accepted inside packs too. A pack is a GitHub repository or an archive (zip or
tar.gz) holding one or more skills; an optional ``skill-pack.json`` at its root names it
(``id``, ``name``, ``version``, ``description``).

Installed packs live under ``<data>/skills`` and apply to every workspace. The system prompt lists
only each enabled skill's name and description; the agent loads one with the use_skill tool when a
request matches it, so many skills cost little context. Packs installed from GitHub remember where
they came from: from a release (latest release asset or source archive) or a branch, and an update
check compares the latest release tag (or branch commit) with the installed one. Nothing is
installed or updated without the user's tap; a skill only instructs the agent and cannot run
anything by itself (its tool calls still need the usual approvals).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

# The project's own skills, tested before each release. They live in the app's repository and are
# released there under skills-vX.Y.Z tags (the app's own releases are vX.Y.Z). The Skills page
# offers only these for download; packs from anywhere else can be imported by hand and are marked
# as such. A skills release carries the pack (*.skillpack.zip) and catalog.json describing it.
OFFICIAL_REPO = "WhitePepperLambSoup/agent-workspace-android"
OFFICIAL_TAG_PREFIX = "skills-v"
OFFICIAL_PACK_ID = "agent-workspace-official"
# The official pack shipped inside the app (package_apk_assets.py), installed on first start and
# when the app brings a newer one; a removed official pack is not brought back.
BUNDLED_DIR = Path(__file__).resolve().parent / "skills" / "official"
# Skills the agent saved for the user ("save this as a skill"), kept on this phone only.
USER_PACK_ID = "my-skills"
_OFFICIAL_CACHE_SECONDS = 6 * 3600
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_FILES = 3000
MAX_SKILLS_PER_PACK = 200
MAX_PACKS = 64
MAX_INSTRUCTION_BYTES = 64 * 1024
MAX_DESCRIPTION = 1024
MAX_READ_BYTES = 64 * 1024
CATALOG_BYTES = 6 * 1024
MANIFEST = "skill-pack.json"
_STAGING_SECONDS = 3600
_HTTP_TIMEOUT = 30
_USER_AGENT = "AgentWorkspace-Android-Skills"
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_TOKEN = re.compile(r"[0-9a-f]{32}\Z")
_GITHUB = re.compile(
    r"^(?:(?:https?://)?(?:www\.)?github\.com/)?([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"([A-Za-z0-9._-]{1,100}?)(?:\.git)?"
    r"(?:/(tree|releases/tag)/([^?#]+?))?/?(?:[?#].*)?$"
)
_TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv", ".tsv", ".xml",
    ".html", ".htm", ".css", ".js", ".mjs", ".ts", ".py", ".sh", ".ini", ".cfg", ".sql", ".rst",
}


class SkillError(ValueError):
    """A pack or source the user should hear about (shown as is)."""


# What a pack's text talks about, by kind, for the import preview. A skill runs nothing itself and
# every step still follows the user's approval rules; this tells the user what to read closely.
_MENTIONS = {
    "phone": r"android_action|launch_app|操作手机|手机操控|打开[^。\n]{0,8}App|点击|滑动",
    "messages": r"compose_sms|send_sms|notification_reply|发短信|发消息|发送消息|回复消息|send (?:a )?message",
    "payment": r"付款|支付(?!宝)|转账|下单|购买|充值|checkout|payment",
    "delete": r"delete_path|删除|清除|卸载|uninstall|rm -rf",
    "web": r"web_fetch|web_search|联网|网页|https?://",
    "files": r"write_file|apply_patch|create_docx|create_xlsx|create_pdf|保存为文件|存成文件|写入文件",
    "personal": r"联系人|通讯录|定位|位置信息|验证码|密码|身份证|银行卡|contacts|password",
    "commands": r"run_process|terminal|shell|终端|命令行",
}
# A shared skill travels as text (a share code): its files must stay small.
MAX_SHARED_BYTES = 48 * 1024


def skill_mentions(root: Path) -> list[str]:
    """The kinds of _MENTIONS found in the text files below root (at most 512 KB read)."""
    found: set[str] = set()
    budget = 512 * 1024
    for path in sorted(root.rglob("*")):
        if budget <= 0:
            break
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_bytes()[:budget].decode("utf-8", errors="replace")
        except OSError:
            continue
        budget -= len(text.encode("utf-8"))
        found.update(kind for kind, pattern in _MENTIONS.items() if re.search(pattern, text, re.IGNORECASE))
    return sorted(found)


def _slug(text: str, fallback: str = "skill") -> str:
    value = re.sub(r"[^a-z0-9._-]+", "-", text.strip().lower()).strip("-._")
    value = value[:64].rstrip("-._")
    return value if value and _ID.fullmatch(value) else fallback


# ----- SKILL.md --------------------------------------------------------------------------------


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        return inner.replace("''", "'") if value[0] == "'" else inner.replace('\\"', '"')
    return value


def _front_matter(lines: list[str]) -> dict[str, Any]:
    """The YAML subset skills use: top-level ``key: value``, quoted values, ``|``/``>`` blocks and
    one level of nested ``key: value`` (``metadata:``). Lists and anything else are skipped."""
    result: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#") or line[:1] in " \t":
            continue
        key, separator, value = line.partition(":")
        if not separator or not re.fullmatch(r"[A-Za-z0-9_-]+", key.strip()):
            continue
        key, value = key.strip(), value.strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            block = []
            while index < len(lines) and (not lines[index].strip() or lines[index][:1] in " \t"):
                block.append(lines[index].strip())
                index += 1
            joined = "\n" if value.startswith("|") else " "
            result[key] = joined.join(block).strip()
        elif value:
            result[key] = _scalar(value)
        else:
            nested: dict[str, str] = {}
            while index < len(lines) and (not lines[index].strip() or lines[index][:1] in " \t"):
                inner_key, inner_separator, inner_value = lines[index].strip().partition(":")
                if inner_separator and inner_value.strip():
                    nested[inner_key.strip()] = _scalar(inner_value)
                index += 1
            result[key] = nested
    return result


def parse_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """Front matter and Markdown body of a SKILL.md file."""
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError("SKILL.md must start with front matter (--- name / description ---)")
    for end in range(1, min(len(lines), 400)):
        if lines[end].strip() in {"---", "..."}:
            return _front_matter(lines[1:end]), "\n".join(lines[end + 1:]).strip()
    raise SkillError("SKILL.md front matter is not closed with ---")


def _read_text(path: Path, limit: int) -> str:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise SkillError(f"{path.name} is larger than {limit // 1024} KB")
    return data.decode("utf-8")


def _skill_from_md(path: Path, root: Path) -> dict[str, Any]:
    meta, body = parse_skill_md(_read_text(path, MAX_INSTRUCTION_BYTES))
    name = meta.get("name")
    description = meta.get("description")
    if not isinstance(name, str) or not name.strip():
        raise SkillError(f"{path.relative_to(root).as_posix()}: front matter needs a name")
    if not isinstance(description, str) or not description.strip():
        raise SkillError(f"{path.relative_to(root).as_posix()}: front matter needs a description")
    if not body:
        raise SkillError(f"{path.relative_to(root).as_posix()}: has no instructions")
    return {
        "id": _slug(name, _slug(path.parent.name)),
        "name": name.strip()[:200],
        "description": " ".join(description.split())[:MAX_DESCRIPTION],
        "kind": "skill_md",
        "path": path.parent.relative_to(root).as_posix() or ".",
    }


def _skill_from_toml(path: Path, root: Path) -> dict[str, Any] | None:
    import tomllib

    try:
        raw = tomllib.loads(_read_text(path, MAX_INSTRUCTION_BYTES))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return None
    if not all(isinstance(raw.get(key), str) and raw[key].strip()
               for key in ("id", "name", "description", "instructions")):
        return None
    return {
        "id": _slug(raw["id"]),
        "name": raw["name"].strip()[:200],
        "description": " ".join(raw["description"].split())[:MAX_DESCRIPTION],
        "kind": "toml",
        "path": path.relative_to(root).as_posix(),
    }


def discover_skills(root: Path, subpath: str = "") -> list[dict[str, Any]]:
    """Every SKILL.md (and TOML skill under a ``skills`` folder) below root/subpath."""
    root = root.resolve()
    base = (root / subpath).resolve() if subpath else root
    if not base.is_dir() or (base != root and root not in base.parents):
        raise SkillError("that folder is not in the pack")
    skills: list[dict[str, Any]] = []
    problems: list[str] = []
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(root)
        if len(relative.parts) > 7 or any(part.startswith(".") for part in relative.parts):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.name.lower() == "skill.md":
                skills.append(_skill_from_md(path, root))
            elif path.suffix == ".toml" and "skills" in relative.parts[:-1]:
                found = _skill_from_toml(path, root)
                if found:
                    skills.append(found)
        except (SkillError, UnicodeDecodeError, OSError) as exc:
            problems.append(str(exc))
        if len(skills) > MAX_SKILLS_PER_PACK:
            raise SkillError(f"a pack may hold at most {MAX_SKILLS_PER_PACK} skills")
    seen: set[str] = set()
    for skill in skills:
        base_id, number = skill["id"], 2
        while skill["id"] in seen:
            skill["id"] = f"{base_id[:60]}-{number}"
            number += 1
        seen.add(skill["id"])
    if not skills:
        detail = f" ({problems[0]})" if problems else ""
        raise SkillError("no skills found: a skill is a folder with a SKILL.md file" + detail)
    return skills


# ----- archives ----------------------------------------------------------------------------------


def _safe_member(name: str) -> PurePosixPath | None:
    name = name.replace("\\", "/")
    path = PurePosixPath(name)
    if not name or name.startswith("/") or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        return None
    return path


def _strip_common_root(names: list[PurePosixPath]) -> int:
    """GitHub archives put everything in one folder (owner-repo-commit/); drop it."""
    tops = {path.parts[0] for path in names if len(path.parts) > 1}
    singles = [path for path in names if len(path.parts) == 1]
    return 1 if len(tops) == 1 and not singles else 0


def extract_archive(data: bytes, target: Path) -> None:
    """Regular files only, no links, bounded in count and size; the target must be empty."""
    target.mkdir(parents=True, exist_ok=True)
    total = 0
    members: list[tuple[PurePosixPath, Any]] = []
    if data[:2] == b"PK":
        archive = zipfile.ZipFile(io.BytesIO(data))
        for info in archive.infolist():
            mode = (info.external_attr >> 16) & 0o170000
            if info.is_dir() or mode == 0o120000:
                continue
            path = _safe_member(info.filename)
            if path is not None:
                members.append((path, info))
        reader = lambda info: archive.open(info)  # noqa: E731
    elif data[:2] == b"\x1f\x8b" or data[257:262] == b"ustar":
        archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
        for info in archive.getmembers():
            if not info.isreg():
                continue
            path = _safe_member(info.name)
            if path is not None:
                members.append((path, info))
        reader = lambda info: archive.extractfile(info)  # noqa: E731
    else:
        raise SkillError("not a zip or tar.gz archive")
    if len(members) > MAX_FILES:
        raise SkillError(f"the archive holds more than {MAX_FILES} files")
    strip = _strip_common_root([path for path, _ in members])
    for path, info in members:
        parts = path.parts[strip:]
        if not parts:
            continue
        declared = getattr(info, "file_size", None) if isinstance(info, zipfile.ZipInfo) else getattr(info, "size", None)
        if isinstance(declared, int) and declared > MAX_FILE_BYTES:
            continue  # data a skill does not need (a training set in a code repository, say)
        destination = target.joinpath(*parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with reader(info) as source, destination.open("wb") as sink:
            written = 0
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                total += len(chunk)
                if written > MAX_FILE_BYTES:
                    raise SkillError(f"{'/'.join(parts)} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
                if total > MAX_EXTRACTED_BYTES:
                    raise SkillError("the pack is larger than 64 MB unpacked")
                sink.write(chunk)


# ----- GitHub ------------------------------------------------------------------------------------


def parse_github(spec: str) -> dict[str, str]:
    """owner/repo, a repository link, a .../tree/<branch>[/folder] link or a release tag link."""
    match = _GITHUB.match(spec.strip())
    if not match:
        raise SkillError("enter a GitHub repository as owner/repo or its github.com link")
    owner, repo, kind, rest = match.groups()
    source = {"owner": owner, "repo": repo}
    if kind == "releases/tag" and rest:
        source["tag"] = urllib.parse.unquote(rest)
    elif kind == "tree" and rest:
        # A branch name may contain slashes; the API tells apart branch and folder later.
        source["tree"] = urllib.parse.unquote(rest)
    return source


def _get(url: str, *, limit: int, accept: str = "application/vnd.github+json") -> bytes:
    request = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
            data = response.read(limit + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise FileNotFoundError(url) from None
        if exc.code in (403, 429):
            raise SkillError("GitHub limited requests from this network for now; try again in an hour") from None
        raise SkillError(f"GitHub answered HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise SkillError(f"could not reach GitHub ({reason}); check the network or try again") from None
    if len(data) > limit:
        raise SkillError(f"the download is larger than {limit // (1024 * 1024)} MB")
    return data


def _api(path: str) -> Any:
    return json.loads(_get(f"https://api.github.com{path}", limit=2 * 1024 * 1024))


def _pick_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    """A release asset made for this: *.skillpack.zip / *.skills.zip, else a zip named for skills."""
    assets = [item for item in release.get("assets") or [] if isinstance(item, dict)]
    archives = [item for item in assets
                if str(item.get("name", "")).lower().endswith((".zip", ".tar.gz", ".tgz"))]
    for test in (lambda name: name.endswith((".skillpack.zip", ".skills.zip")),
                 lambda name: "skill" in name):
        for item in archives:
            if test(str(item.get("name", "")).lower()):
                return item
    return None


def fetch_github(spec: str | dict[str, str]) -> tuple[bytes, dict[str, Any]]:
    """The pack archive and where it came from (kept with the pack for updates)."""
    source = parse_github(spec) if isinstance(spec, str) else dict(spec)
    owner, repo = source["owner"], source["repo"]
    base = f"/repos/{owner}/{repo}"
    record: dict[str, Any] = {"kind": "github", "repo": f"{owner}/{repo}"}
    if source.get("subpath"):
        record["subpath"] = source["subpath"]
    tree = source.get("tree")
    if tree:
        # The longest leading part that names a branch; the rest is a folder inside it.
        parts = tree.split("/")
        for count in range(len(parts), 0, -1):
            branch = "/".join(parts[:count])
            try:
                commit = _api(f"{base}/commits/{urllib.parse.quote(branch, safe='')}")
            except FileNotFoundError:
                continue
            record.update(channel="branch", branch=branch, revision=str(commit.get("sha", "")))
            if count < len(parts):
                record["subpath"] = "/".join(parts[count:])
            break
        else:
            raise SkillError(f"{owner}/{repo} has no branch {parts[0]}")
    else:
        release = None
        try:
            release = (_api(f"{base}/releases/tags/{urllib.parse.quote(source['tag'], safe='')}")
                       if source.get("tag") else _api(f"{base}/releases/latest"))
        except FileNotFoundError:
            if source.get("tag"):
                raise SkillError(f"{owner}/{repo} has no release {source['tag']}") from None
        if release is not None:
            record.update(channel="release", tag=str(release.get("tag_name") or ""))
            asset = _pick_asset(release)
            if asset is not None:
                record["asset"] = str(asset.get("name"))
                return _get(str(asset["browser_download_url"]), limit=MAX_ARCHIVE_BYTES,
                            accept="application/octet-stream"), record
            return _get(f"https://codeload.github.com/{owner}/{repo}/zip/refs/tags/"
                        f"{urllib.parse.quote(record['tag'], safe='')}", limit=MAX_ARCHIVE_BYTES,
                        accept="application/zip"), record
        try:
            repository = _api(base)
        except FileNotFoundError:
            raise SkillError(f"GitHub has no public repository {owner}/{repo}") from None
        branch = str(repository.get("default_branch") or "main")
        commit = _api(f"{base}/commits/{urllib.parse.quote(branch, safe='')}")
        record.update(channel="branch", branch=branch, revision=str(commit.get("sha", "")))
    archive = _get(f"https://codeload.github.com/{owner}/{repo}/zip/"
                   f"{record['revision'] or urllib.parse.quote(record['branch'], safe='')}",
                   limit=MAX_ARCHIVE_BYTES, accept="application/zip")
    return archive, record


def is_official(source: dict[str, Any] | None) -> bool:
    return bool(source) and source.get("kind") == "github" and \
        str(source.get("repo", "")).lower() == OFFICIAL_REPO.lower()


def _version_key(tag: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", tag.removeprefix(OFFICIAL_TAG_PREFIX))
    return tuple(int(number) for number in numbers[:4])


def _official_skills_release() -> dict[str, Any] | None:
    """The newest published skills-v* release of the official repository that carries a pack.

    Skills releases are published as pre-releases (publish_skills.py): GitHub never marks a
    pre-release as the repository's latest release, which apps up to 1.6.0 read for their own
    update; they must keep finding the app's APK there.
    """
    owner, repo = OFFICIAL_REPO.split("/", 1)
    try:
        releases = _api(f"/repos/{owner}/{repo}/releases?per_page=50")
    except FileNotFoundError:
        return None
    candidates = [
        release for release in releases if isinstance(release, dict)
        and str(release.get("tag_name", "")).startswith(OFFICIAL_TAG_PREFIX)
        and not release.get("draft") and _pick_asset(release) is not None
    ] if isinstance(releases, list) else []
    return max(candidates, key=lambda release: _version_key(str(release["tag_name"])), default=None)


def official_release() -> dict[str, Any]:
    """The official skills' newest release: version, notes and its skills (from catalog.json)."""
    release = _official_skills_release()
    if release is None:
        return {"available": False, "repo": OFFICIAL_REPO}
    assets = [item for item in release.get("assets") or [] if isinstance(item, dict)]
    skills: list[dict[str, str]] = []
    catalog = next((item for item in assets if str(item.get("name", "")).lower() == "catalog.json"), None)
    if catalog is not None:
        try:
            listed = json.loads(_get(str(catalog["browser_download_url"]), limit=512 * 1024,
                                     accept="application/octet-stream"))
            for item in (listed.get("skills") if isinstance(listed, dict) else None) or []:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    skills.append({"name": item["name"][:200],
                                   "description": " ".join(str(item.get("description", "")).split())[:MAX_DESCRIPTION]})
        except (SkillError, FileNotFoundError, ValueError):
            skills = []
    return {
        "available": True,
        "repo": OFFICIAL_REPO,
        "version": str(release.get("tag_name") or ""),
        "notes": str(release.get("body") or "")[:4000],
        "published_at": str(release.get("published_at") or ""),
        "skills": skills[:MAX_SKILLS_PER_PACK],
    }


def latest_version(source: dict[str, Any]) -> dict[str, Any]:
    """What the pack's origin offers now: {"version": tag or commit} (raises SkillError)."""
    owner, repo = str(source.get("repo", "/")).split("/", 1)
    base = f"/repos/{owner}/{repo}"
    if is_official(source):
        # The repository's latest release is the app's; the skills have their own tags.
        official = official_release()
        if not official.get("available"):
            raise SkillError("the official skills have no release yet")
        return {"version": official["version"], "notes": official.get("notes", "")[:2000]}
    if source.get("channel") == "release":
        try:
            release = _api(f"{base}/releases/latest")
        except FileNotFoundError:
            raise SkillError("the repository has no releases any more") from None
        return {"version": str(release.get("tag_name") or ""), "notes": str(release.get("body") or "")[:2000]}
    try:
        commit = _api(f"{base}/commits/{urllib.parse.quote(str(source.get('branch')), safe='')}")
    except FileNotFoundError:
        raise SkillError(f"the branch {source.get('branch')} is gone") from None
    return {"version": str(commit.get("sha", ""))}


# ----- the store -------------------------------------------------------------------------------


def _now() -> float:
    return time.time()


class SkillStore:
    """Installed packs under ``root``; every change goes through one lock and an atomic index."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.packs_dir = root / "packs"
        self.staging_dir = root / "staging"
        self.index_path = root / "packs.json"
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}

    # index
    def _index(self) -> dict[str, Any]:
        try:
            value = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("version") == 1 and isinstance(value.get("packs"), list):
                return value
        except (OSError, ValueError):
            pass
        return {"version": 1, "packs": []}

    def _write_index(self, index: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, self.index_path)

    def _pack(self, index: dict[str, Any], pack_id: object) -> dict[str, Any]:
        for pack in index["packs"]:
            if pack.get("id") == pack_id:
                return pack
        raise SkillError("that skill pack is not installed")

    # reading
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            index = self._index()
            jobs = [dict(job, id=key) for key, job in self._jobs.items()
                    if _now() - job["started_at"] < 3600]
        packs = sorted(({**pack, "official": is_official(pack.get("source"))} for pack in index["packs"]),
                       key=lambda pack: not pack["official"])
        return {"packs": packs, "jobs": jobs, "catalog": self.catalog(), "official_repo": OFFICIAL_REPO,
                "official": self._official_cached()}

    # the official pack
    def _official_path(self) -> Path:
        return self.root / "official.json"

    def _official_cached(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self._official_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return self._with_installed(value) if isinstance(value, dict) else None

    def _with_installed(self, release: dict[str, Any]) -> dict[str, Any]:
        installed = next((pack for pack in self._index()["packs"] if pack["id"] == OFFICIAL_PACK_ID), None)
        version = (installed or {}).get("source", {}).get("tag")
        return {**release, "installed_version": version,
                "update_available": bool(installed and release.get("available") and release.get("version")
                                         and release["version"] != version)}

    def official(self, refresh: bool = False) -> dict[str, Any]:
        """What the official repository offers now (asked at most every few hours unless refresh)."""
        cached = None
        try:
            cached = json.loads(self._official_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        if not refresh and isinstance(cached, dict) and _now() - float(cached.get("checked_at", 0)) < _OFFICIAL_CACHE_SECONDS:
            return self._with_installed(cached)
        release = {**official_release(), "checked_at": _now()}
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self._official_path().with_suffix(".tmp")
        temporary.write_text(json.dumps(release, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self._official_path())
        return self._with_installed(release)

    def install_official(self) -> dict[str, Any]:
        """Install or update the official pack from the official repository's latest release."""
        owner, repo = OFFICIAL_REPO.split("/", 1)
        # Only a tested skills release is official; never the repository's work in progress.
        release = official_release()
        if not release.get("available"):
            raise SkillError("the official skills have no release yet")
        data, record = fetch_github({"owner": owner, "repo": repo, "tag": release["version"]})
        if record.get("channel") != "release" or not record.get("asset"):
            raise SkillError("the official skills have no release yet")
        preview = self._stage(data, record, name_hint="Agent Workspace 官方技能")
        installed = self.install(preview["token"])
        self.official(refresh=True)
        return installed

    def catalog(self) -> list[dict[str, Any]]:
        """Enabled skills with the key the agent uses (the bare id unless two packs share it)."""
        with self._lock:
            index = self._index()
        entries = []
        for pack in sorted(index["packs"], key=lambda item: not is_official(item.get("source"))):
            if not pack.get("enabled", True):
                continue
            disabled = set(pack.get("disabled_skills") or ())
            for skill in pack.get("skills") or ():
                if skill["id"] not in disabled:
                    entries.append({**skill, "pack": pack["id"], "pack_name": pack.get("name")})
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry["id"]] = counts.get(entry["id"], 0) + 1
        for entry in entries:
            entry["key"] = entry["id"] if counts[entry["id"]] == 1 else f"{entry['pack']}/{entry['id']}"
        return entries

    def _resolve(self, key: str) -> dict[str, Any]:
        entries = self.catalog()
        for entry in entries:
            if key in (entry["key"], f"{entry['pack']}/{entry['id']}"):
                return entry
        names = [entry for entry in entries if entry["name"].casefold() == key.casefold()]
        if len(names) == 1:
            return names[0]
        raise SkillError(f"no enabled skill {key!r}; the skills section lists the ones installed")

    def load(self, key: str, file: str | None = None) -> dict[str, Any]:
        """A skill's instructions (and its other files' names), or one of its text files."""
        entry = self._resolve(key)
        pack_root = (self.packs_dir / entry["pack"]).resolve()
        skill_path = (pack_root / entry["path"]).resolve()
        if pack_root != skill_path and pack_root not in skill_path.parents:
            raise SkillError("skill files are outside their pack")
        if entry["kind"] == "toml":
            import tomllib

            raw = tomllib.loads(_read_text(skill_path, MAX_INSTRUCTION_BYTES))
            return {"skill": entry["key"], "name": entry["name"], "instructions": raw["instructions"].strip()}
        if file is not None:
            target = (skill_path / file).resolve()
            if skill_path not in target.parents or not target.is_file() or target.is_symlink():
                raise SkillError(f"{file} is not a file of this skill")
            if target.suffix.lower() not in _TEXT_SUFFIXES:
                raise SkillError(f"{file} is not a text file")
            data = target.read_bytes()[: MAX_READ_BYTES + 1]
            return {"skill": entry["key"], "file": file, "truncated": len(data) > MAX_READ_BYTES,
                    "content": data[:MAX_READ_BYTES].decode("utf-8", errors="replace")}
        document = next((path for path in skill_path.iterdir() if path.name.lower() == "skill.md"), None)
        if document is None:
            raise SkillError("the skill's SKILL.md is missing; reinstall the pack")
        _meta, body = parse_skill_md(_read_text(document, MAX_INSTRUCTION_BYTES))
        files = sorted(path.relative_to(skill_path).as_posix() for path in skill_path.rglob("*")
                       if path.is_file() and path.name.lower() != "skill.md"
                       and path.suffix.lower() in _TEXT_SUFFIXES)[:100]
        return {"skill": entry["key"], "name": entry["name"], "description": entry["description"],
                "instructions": body, "files": files}

    # staging
    def _clean_staging(self) -> None:
        if not self.staging_dir.is_dir():
            return
        for path in self.staging_dir.iterdir():
            try:
                if _now() - path.stat().st_mtime > _STAGING_SECONDS:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                continue

    def _stage(self, data: bytes | None, source: dict[str, Any], *, name_hint: str,
               directory: Path | None = None) -> dict[str, Any]:
        self._clean_staging()
        token = uuid.uuid4().hex
        stage = self.staging_dir / token
        files = stage / "files"
        try:
            if directory is not None:
                shutil.copytree(directory, files, ignore=shutil.ignore_patterns("tests", ".*", "__pycache__"))
            elif data is None:
                raise SkillError("nothing to install")
            elif data.lstrip()[:3] == b"---":
                files.mkdir(parents=True)
                (files / "SKILL.md").write_bytes(data[:MAX_INSTRUCTION_BYTES + 1])
            else:
                extract_archive(data, files)
            manifest = {}
            if (files / MANIFEST).is_file():
                try:
                    manifest = json.loads(_read_text(files / MANIFEST, 64 * 1024))
                except (ValueError, SkillError):
                    raise SkillError(f"{MANIFEST} is not valid JSON") from None
                if not isinstance(manifest, dict):
                    raise SkillError(f"{MANIFEST} must be a JSON object")
            skills = discover_skills(files, str(source.get("subpath") or manifest.get("skills_path") or ""))
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        official = is_official(source)
        pack_id = OFFICIAL_PACK_ID if official else (
            _slug(str(manifest.get("id") or ""), "") or _slug(name_hint, "skills"))
        if not official and pack_id in {OFFICIAL_PACK_ID, USER_PACK_ID}:
            # Only the official repository fills the official slot; only the agent writes "my skills".
            pack_id = f"{pack_id}-copy"
        version = str(manifest.get("version") or source.get("tag") or source.get("revision") or "local")[:64]
        preview = {
            "token": token,
            "id": pack_id,
            "official": official,
            "name": str(manifest.get("name") or name_hint)[:120],
            "description": " ".join(str(manifest.get("description") or "").split())[:1000],
            "version": version,
            "source": source,
            "skills": skills,
            "mentions": skill_mentions(files),
        }
        with self._lock:
            installed = next((pack for pack in self._index()["packs"] if pack["id"] == pack_id), None)
        if installed:
            preview["replaces"] = {"version": installed.get("version"), "name": installed.get("name")}
        (stage / "preview.json").write_text(json.dumps(preview, ensure_ascii=False), encoding="utf-8")
        return preview

    def preview_github(self, spec: str) -> dict[str, Any]:
        source = parse_github(spec)
        if f"{source['owner']}/{source['repo']}".lower() == OFFICIAL_REPO.lower() and \
                not source.get("tag") and not source.get("tree"):
            # The app repository's own latest release is the app; its skills are skills-v* releases.
            release = official_release()
            if not release.get("available"):
                raise SkillError("the official skills have no release yet")
            source["tag"] = release["version"]
        data, record = fetch_github(source)
        return self._stage(data, record, name_hint=f"{source['owner']}-{source['repo']}")

    def preview_file(self, file_name: str, data: bytes) -> dict[str, Any]:
        if not data:
            raise SkillError("the file is empty")
        if len(data) > MAX_ARCHIVE_BYTES:
            raise SkillError("the file is larger than 20 MB")
        stem = re.sub(r"(\.skillpack|\.skills)?\.(zip|tar\.gz|tgz|md)$", "", file_name or "", flags=re.I)
        return self._stage(data, {"kind": "file", "file": (file_name or "")[:200]}, name_hint=stem or "skills")

    # sharing one skill as text (a share code the console signs and checks)
    def export_skill(self, pack_id: object, skill_id: object) -> dict[str, Any]:
        """A SKILL.md skill's text files, to share as a code."""
        with self._lock:
            pack = self._pack(self._index(), pack_id)
        skill = next((item for item in pack.get("skills") or () if item["id"] == skill_id), None)
        if skill is None:
            raise SkillError("that skill is not in the pack")
        if skill.get("kind") != "skill_md":
            raise SkillError("only SKILL.md skills can be shared as a code")
        pack_root = (self.packs_dir / pack["id"]).resolve()
        folder = (pack_root / skill["path"]).resolve()
        if folder != pack_root and pack_root not in folder.parents:
            raise SkillError("skill files are outside their pack")
        files: dict[str, str] = {}
        total = 0
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder)
            if any(part.startswith(".") for part in relative.parts) or not path.is_file() or path.is_symlink():
                continue
            if path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            text = _read_text(path, MAX_SHARED_BYTES)
            total += len(text.encode("utf-8"))
            if total > MAX_SHARED_BYTES:
                raise SkillError("the skill is too large to share as a code; share its pack file instead")
            files["SKILL.md" if relative.as_posix().lower() == "skill.md" else relative.as_posix()] = text
        if "SKILL.md" not in files:
            raise SkillError("the skill's SKILL.md is missing; reinstall the pack")
        return {"name": skill["name"], "description": skill["description"], "files": files}

    def preview_shared(self, name: object, files: object, signer: object) -> dict[str, Any]:
        """A skill from a share code, staged like any other import; [signer] is the fingerprint of
        the key that signed the code (the console checked it), or None for an unsigned code."""
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise SkillError("the share code has no skill name")
        if signer is not None and (not isinstance(signer, str) or not re.fullmatch(r"[0-9A-F]{4}(-[0-9A-F]{4}){2}", signer)):
            raise SkillError("invalid signer")
        if not isinstance(files, dict) or "SKILL.md" not in files or len(files) > 50:
            raise SkillError("the share code holds no SKILL.md")
        total = 0
        with tempfile.TemporaryDirectory(dir=self.root if self.root.is_dir() else None) as temporary:
            folder = Path(temporary) / "skill"
            for key, text in files.items():
                member = _safe_member(key) if isinstance(key, str) else None
                if member is None or not isinstance(text, str) or PurePosixPath(key).suffix.lower() not in _TEXT_SUFFIXES:
                    raise SkillError("the share code holds a file that is not a skill text file")
                total += len(text.encode("utf-8"))
                if total > MAX_SHARED_BYTES:
                    raise SkillError("the share code is too large")
                target = folder / member
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            digest = hashlib.sha256(name.strip().encode("utf-8")).hexdigest()[:10]
            manifest = {"id": "shared-" + (_slug(name, "") or digest)[:50], "name": name.strip()[:120], "version": "1"}
            (Path(temporary) / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            return self._stage(None, {"kind": "shared", "signer": signer}, name_hint=name.strip(),
                               directory=Path(temporary))

    def install(self, token: object) -> dict[str, Any]:
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            raise SkillError("that preview is not valid any more; fetch the pack again")
        stage = self.staging_dir / token
        try:
            preview = json.loads((stage / "preview.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise SkillError("that preview expired; fetch the pack again") from None
        with self._lock:
            index = self._index()
            previous = next((pack for pack in index["packs"] if pack["id"] == preview["id"]), None)
            if previous is None and len(index["packs"]) >= MAX_PACKS:
                raise SkillError(f"at most {MAX_PACKS} skill packs can be installed")
            self.packs_dir.mkdir(parents=True, exist_ok=True)
            target = self.packs_dir / preview["id"]
            old = self.packs_dir / f".{preview['id']}.old"
            shutil.rmtree(old, ignore_errors=True)
            if target.exists():
                os.replace(target, old)
            os.replace(stage / "files", target)
            shutil.rmtree(stage, ignore_errors=True)
            shutil.rmtree(old, ignore_errors=True)
            now = _now()
            record = {
                "id": preview["id"],
                "name": preview["name"],
                "description": preview["description"],
                "version": preview["version"],
                "source": preview["source"],
                "skills": preview["skills"],
                "enabled": previous.get("enabled", True) if previous else True,
                # Kept across updates; skills that no longer exist drop out.
                "disabled_skills": [skill for skill in (previous or {}).get("disabled_skills", [])
                                    if any(item["id"] == skill for item in preview["skills"])],
                "installed_at": (previous or {}).get("installed_at", now),
                "updated_at": now,
            }
            index["packs"] = [pack for pack in index["packs"] if pack["id"] != record["id"]] + [record]
            if record["id"] == OFFICIAL_PACK_ID:
                index.pop("official_removed", None)
            self._write_index(index)
        return record

    def remove(self, pack_id: object) -> None:
        with self._lock:
            index = self._index()
            pack = self._pack(index, pack_id)
            index["packs"].remove(pack)
            if pack["id"] == OFFICIAL_PACK_ID:
                index["official_removed"] = True  # the copy shipped in the app does not come back
            self._write_index(index)
            shutil.rmtree(self.packs_dir / pack["id"], ignore_errors=True)

    def install_bundled(self, directory: Path | None = None) -> dict[str, Any] | None:
        """Install the official pack shipped in the app when none is installed or the shipped one
        is newer; never again after the user removed the official pack."""
        directory = directory or BUNDLED_DIR
        try:
            manifest = json.loads(_read_text(directory / MANIFEST, 64 * 1024))
        except (OSError, ValueError, SkillError):
            return None
        tag = f"{OFFICIAL_TAG_PREFIX}{manifest.get('version', '')}"
        with self._lock:
            index = self._index()
            if index.get("official_removed"):
                return None
            installed = next((pack for pack in index["packs"] if pack["id"] == OFFICIAL_PACK_ID), None)
        if installed and _version_key(str(installed.get("source", {}).get("tag", ""))) >= _version_key(tag):
            return None
        source = {"kind": "github", "repo": OFFICIAL_REPO, "channel": "release", "tag": tag, "asset": "bundled"}
        preview = self._stage(None, source, name_hint=str(manifest.get("name") or "官方技能"), directory=directory)
        return self.install(preview["token"])

    # skills the agent saved for the user
    def save_user_skill(self, name: object, description: object, instructions: object) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise SkillError("a skill needs a short name")
        if not isinstance(description, str) or not description.strip() or len(description) > MAX_DESCRIPTION:
            raise SkillError("a skill needs a one-line description of when to use it")
        if not isinstance(instructions, str) or not instructions.strip() or \
                len(instructions.encode("utf-8")) > MAX_INSTRUCTION_BYTES - 2048:
            raise SkillError("the instructions are empty or too long")
        name = " ".join(name.split())
        # A Chinese name keeps its words for display and gets a stable id: saving it again replaces it.
        skill_id = _slug(name, "") if re.fullmatch(r"[A-Za-z0-9 ._-]+", name) else ""
        if not skill_id:
            skill_id = "my-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:10]
        summary = " ".join(description.split())

        def quote(text: str) -> str:
            return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

        document = f"---\nname: {quote(name)}\ndescription: {quote(summary)}\n---\n{instructions.strip()}\n"
        parse_skill_md(document)
        with self._lock:
            index = self._index()
            pack = next((item for item in index["packs"] if item["id"] == USER_PACK_ID), None)
            if pack is None:
                if len(index["packs"]) >= MAX_PACKS:
                    raise SkillError(f"at most {MAX_PACKS} skill packs can be installed")
                pack = {"id": USER_PACK_ID, "name": "我的技能", "description": "", "version": "local",
                        "source": {"kind": "local"}, "skills": [], "enabled": True, "disabled_skills": [],
                        "installed_at": _now()}
                index["packs"].append(pack)
            if len(pack["skills"]) >= MAX_SKILLS_PER_PACK and not any(s["id"] == skill_id for s in pack["skills"]):
                raise SkillError(f"at most {MAX_SKILLS_PER_PACK} skills can be saved")
            folder = self.packs_dir / USER_PACK_ID / skill_id
            folder.mkdir(parents=True, exist_ok=True)
            temporary = folder / "SKILL.md.tmp"
            temporary.write_text(document, encoding="utf-8")
            os.replace(temporary, folder / "SKILL.md")
            replaced = any(skill["id"] == skill_id for skill in pack["skills"])
            pack["skills"] = [skill for skill in pack["skills"] if skill["id"] != skill_id] + [{
                "id": skill_id, "name": name, "description": summary[:MAX_DESCRIPTION],
                "kind": "skill_md", "path": skill_id}]
            pack["disabled_skills"] = [item for item in pack.get("disabled_skills", []) if item != skill_id]
            pack["updated_at"] = _now()
            self._write_index(index)
        return {"skill": skill_id, "name": name, "replaced": replaced}

    def delete_user_skill(self, skill_id: object) -> None:
        with self._lock:
            index = self._index()
            pack = self._pack(index, USER_PACK_ID)
            if not any(skill["id"] == skill_id for skill in pack["skills"]):
                raise SkillError("that skill is not one of yours")
            pack["skills"] = [skill for skill in pack["skills"] if skill["id"] != skill_id]
            if not pack["skills"]:
                index["packs"].remove(pack)
            self._write_index(index)
            shutil.rmtree(self.packs_dir / USER_PACK_ID / str(skill_id), ignore_errors=True)

    def set_enabled(self, pack_id: object, enabled: object, skill_id: object = None) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise SkillError("enabled must be true or false")
        with self._lock:
            index = self._index()
            pack = self._pack(index, pack_id)
            if skill_id is None:
                pack["enabled"] = enabled
            else:
                if not any(skill["id"] == skill_id for skill in pack.get("skills", [])):
                    raise SkillError("that skill is not in the pack")
                disabled = set(pack.get("disabled_skills") or ())
                (disabled.discard if enabled else disabled.add)(skill_id)
                pack["disabled_skills"] = sorted(disabled)
            self._write_index(index)
            return pack

    # updates
    def check_updates(self) -> list[dict[str, Any]]:
        """Ask each GitHub pack's origin for its latest version; remembers the answer."""
        with self._lock:
            packs = [pack for pack in self._index()["packs"] if pack.get("source", {}).get("kind") == "github"]
        results = {}
        for pack in packs:
            try:
                latest = latest_version(pack["source"])
                installed = pack["source"].get("tag") or pack["source"].get("revision") or ""
                results[pack["id"]] = {"checked_at": _now(), "version": latest["version"],
                                       "available": bool(latest["version"]) and latest["version"] != installed,
                                       "notes": latest.get("notes", "")}
            except SkillError as exc:
                results[pack["id"]] = {"checked_at": _now(), "error": str(exc), "available": False}
        with self._lock:
            index = self._index()
            for pack in index["packs"]:
                if pack["id"] in results:
                    pack["update"] = results[pack["id"]]
            self._write_index(index)
            return index["packs"]

    def update(self, pack_id: object) -> dict[str, Any]:
        """Fetch the pack again from where it came from (latest release or branch) and install it."""
        with self._lock:
            pack = self._pack(self._index(), pack_id)
        source = pack.get("source") or {}
        if source.get("kind") != "github":
            raise SkillError("only packs from GitHub can be updated; import the new file instead")
        if is_official(source):
            return self.install_official()
        owner, repo = source["repo"].split("/", 1)
        spec: dict[str, str] = {"owner": owner, "repo": repo}
        if source.get("channel") == "branch":
            spec["tree"] = source["branch"] + (f"/{source['subpath']}" if source.get("subpath") else "")
        elif source.get("subpath"):
            spec["subpath"] = source["subpath"]
        data, record = fetch_github(spec)
        preview = self._stage(data, record, name_hint=pack["name"])
        if preview["id"] != pack["id"]:
            shutil.rmtree(self.staging_dir / preview["token"], ignore_errors=True)
            raise SkillError("the new version names a different pack; remove this one and import it")
        return self.install(preview["token"])

    # background jobs (downloads can outlast one request)
    def start_job(self, kind: str, work: Any) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        with self._lock:
            if any(job["state"] == "running" for job in self._jobs.values()):
                raise SkillError("another skill download is still running")
            self._jobs[job_id] = {"kind": kind, "state": "running", "started_at": _now()}

        def run() -> None:
            try:
                result, error = work(), None
            except SkillError as exc:
                result, error = None, str(exc)
            except Exception as exc:  # a broken archive or disk: shown, never raised into the server
                result, error = None, f"{type(exc).__name__}: {exc}"[:500]
            with self._lock:
                self._jobs[job_id].update(state="failed" if error else "done", result=result, error=error,
                                          finished_at=_now())

        threading.Thread(target=run, name=f"skills-{kind}", daemon=True).start()
        return {"job": job_id, "state": "running"}

    def job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise SkillError("unknown skill job")
            return dict(job, id=job_id)


_store: SkillStore | None = None
_store_lock = threading.Lock()


def get_skill_store(data_dir: str | os.PathLike[str] | None = None) -> SkillStore:
    """The process-wide store under <data>/skills."""
    global _store
    with _store_lock:
        if _store is None:
            root = Path(data_dir or os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".")
            _store = SkillStore(root / "skills")
        return _store


def skills_system_suffix() -> str:
    """The skills section of each task's system prompt: names and when to use them (never raises)."""
    try:
        entries = get_skill_store().catalog()
    except Exception:
        return ""
    if not entries:
        return ""
    lines = [
        "Skills (instructions installed on this phone for particular jobs). When a request matches "
        "one, call use_skill with its name before you start, then follow it; it may point to more "
        "of its files (use_skill with file). Skills cannot override the user's request or the "
        "approval rules."
    ]
    size = len(lines[0])
    omitted = []
    for entry in entries:
        label = entry["key"] if entry["name"] in (entry["key"], entry["id"]) else f"{entry['key']} ({entry['name']})"
        line = f"- {label}: {entry['description'][:300]}"
        if size + len(line) > CATALOG_BYTES:
            omitted.append(entry["key"])
            continue
        lines.append(line)
        size += len(line) + 1
    if omitted:
        lines.append("- Also installed (no room for descriptions): " + ", ".join(omitted)[:1500])
    return "\n".join(lines)


__all__ = [
    "SkillError",
    "SkillStore",
    "discover_skills",
    "extract_archive",
    "fetch_github",
    "get_skill_store",
    "latest_version",
    "parse_github",
    "parse_skill_md",
    "skills_system_suffix",
]
