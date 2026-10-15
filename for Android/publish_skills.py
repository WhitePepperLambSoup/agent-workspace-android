#!/usr/bin/env python3
"""Build and publish the official skill pack (skills/official) as a skills-vX.Y.Z release.

    python publish_skills.py build              validate every skill, write dist/skills/*
    python publish_skills.py publish            build, then create the GitHub release (needs gh)

The pack is released in the app's own repository. Apps up to 1.6.0 update themselves from the
repository's *latest* release and take its APK, so a skills release must never become the latest:
it is always created as a pre-release with --latest=false (GitHub never marks a pre-release as
latest), and publishing checks afterwards that the latest release is still an app release with an
APK. Newer apps pick the newest vX.Y.Z release with an APK themselves (UpdateChecker.pickAppRelease)
and the newest skills-v* release for skills (mobile_skills.official_release).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "skills" / "official"
DIST = ROOT / "dist" / "skills"
PACK_NAME = "agent-workspace-skills.skillpack.zip"
APP_TAG = re.compile(r"^[vV]?\d+(\.\d+){1,3}$")

sys.path.insert(0, str(ROOT))
import mobile_skills  # noqa: E402


def build() -> dict:
    manifest = json.loads((SOURCE / mobile_skills.MANIFEST).read_text(encoding="utf-8"))
    version = str(manifest.get("version") or "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("skill-pack.json needs a version such as 1.0.0")
    # The same checks the app makes when it installs the pack.
    skills = mobile_skills.discover_skills(SOURCE)
    for skill in skills:
        mobile_skills.parse_skill_md((SOURCE / skill["path"] / "SKILL.md").read_text(encoding="utf-8"))
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    archive = DIST / PACK_NAME
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as pack:
        for path in sorted(SOURCE.rglob("*")):
            relative = path.relative_to(SOURCE)
            if path.is_file() and relative.parts[0] != "tests" and not any(part.startswith(".") for part in relative.parts):
                pack.write(path, relative.as_posix())
    with tempfile.TemporaryDirectory() as scratch:  # the archive installs as it will on a phone
        store = mobile_skills.SkillStore(Path(scratch))
        preview = store.preview_file(PACK_NAME, archive.read_bytes())
        assert len(preview["skills"]) == len(skills)
    tag = f"{mobile_skills.OFFICIAL_TAG_PREFIX}{version}"
    catalog = {"version": tag, "skills": [{"name": skill["name"], "description": skill["description"]}
                                          for skill in skills]}
    (DIST / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{tag}: {len(skills)} skills, {archive.stat().st_size} bytes -> {DIST}")
    return {"tag": tag, "version": version, "name": manifest.get("name", "Agent Workspace 官方技能")}


def _gh(*arguments: str) -> str:
    return subprocess.run(["gh", *arguments], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def check_latest_is_app() -> None:
    latest = json.loads(_gh("api", f"repos/{mobile_skills.OFFICIAL_REPO}/releases/latest"))
    names = [asset.get("name", "") for asset in latest.get("assets") or []]
    if not APP_TAG.match(latest.get("tag_name", "")) or not any(name.endswith(".apk") for name in names):
        raise SystemExit(
            f"The repository's latest release is {latest.get('tag_name')!r}, not an app release with an "
            "APK; apps up to 1.6.0 would fail to update. Mark the newest app release as latest: "
            "gh release edit <vX.Y.Z> --latest"
        )
    print(f"latest release is still the app: {latest['tag_name']} ({', '.join(names)})")


def publish(notes: Path | None) -> None:
    built = build()
    check_latest_is_app()
    arguments = [
        "release", "create", built["tag"], str(DIST / PACK_NAME), str(DIST / "catalog.json"),
        "--repo", mobile_skills.OFFICIAL_REPO,
        "--title", f"{built['name']} {built['tag']}",
        "--prerelease", "--latest=false",
    ]
    arguments += ["--notes-file", str(notes)] if notes else ["--notes", f"Official skills {built['tag']}"]
    _gh(*arguments)
    check_latest_is_app()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("build", "publish"))
    parser.add_argument("--notes", type=Path, help="release notes file (Chinese first, then English)")
    arguments = parser.parse_args()
    if arguments.command == "build":
        build()
    else:
        publish(arguments.notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
