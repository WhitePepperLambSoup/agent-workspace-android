"""Answers commands that look for or run what a phone does not have, instead of running them.

The environment section of the system prompt already names what is missing; a model that probes
anyway (``which pdflatex``, ``pip install python-docx``, ``apt install ffmpeg``) gets the answer at
once, with what to use instead, and no time goes into a command that cannot work.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterable
from typing import Any

_PACKAGE_MANAGERS = frozenset(
    {"apt", "apt-get", "apt-cache", "aptitude", "dpkg", "pkg", "yum", "dnf", "brew", "snap", "pacman", "apk"}
)
# Program -> what to do here instead.
_INSTEAD = {
    "latex": "For a PDF, call create_pdf with format latex (or markdown): it typesets formulas.",
    "pandoc": "create_pdf turns Markdown into a PDF; read_document reads Word, Excel and PowerPoint files.",
    "office": "read_document reads Office files; create_pdf writes PDFs, create_docx and create_xlsx write Word and Excel files.",
    "image": "There is no image editing program here; android_screenshot and render_pdf only make pictures.",
    "media": "There is no audio or video converter here; transcribe_audio turns speech into text.",
    "compiler": "There is no C or C++ compiler here; use Python or Node if the developer toolchain is installed.",
}
_MISSING = {
    **{name: "latex" for name in ("pdflatex", "xelatex", "lualatex", "latex", "latexmk", "tectonic", "tex", "bibtex", "biber")},
    "pandoc": "pandoc",
    **{name: "office" for name in ("soffice", "libreoffice", "lowriter", "localc", "unoconv")},
    **{name: "image" for name in ("convert", "magick", "mogrify", "identify")},
    **{name: "media" for name in ("ffmpeg", "ffprobe", "ffplay", "sox")},
    **{name: "compiler" for name in ("gcc", "g++", "cc", "c++", "clang", "clang++", "make", "cmake")},
}
_PROBES = frozenset({"which", "whereis", "type", "hash"})
_WRAPPERS = frozenset({"sudo", "env", "exec", "nohup", "time", "command", "busybox", "toybox", "xargs", "nice"})
_SPLIT = re.compile(r"\|\||&&|[;|&\n]|\$\(|`")


def _commands(argv: list[str]) -> Iterable[list[str]]:
    """The simple commands of argv, looking inside `sh -c "..."` scripts."""
    if not argv:
        return
    shell = argv[0].rsplit("/", 1)[-1]
    if shell in ("sh", "bash", "ash", "dash", "zsh") and "-c" in argv[1:-1]:
        script = argv[argv.index("-c", 1) + 1]
        for part in _SPLIT.split(script):
            try:
                words = shlex.split(part, posix=True)
            except ValueError:
                words = part.split()
            if words:
                yield words
        return
    yield argv


def _program(words: list[str]) -> tuple[str | None, list[str]]:
    index = 0
    wrapped = False
    while index < len(words) and (
        "=" in words[index] and not words[index].startswith("-")
        or words[index] in _WRAPPERS
        # A wrapper's own options (xargs -n 1, nice -n 5) come before the program it runs.
        or (wrapped and words[index].startswith("-"))
    ):
        if words[index] == "command" and index + 1 < len(words) and words[index + 1] == "-v":
            return "which", words[index + 2 :]
        wrapped = wrapped or words[index] in _WRAPPERS
        index += 1
    if index >= len(words):
        return None, []
    return words[index].rsplit("/", 1)[-1], words[index + 1 :]


def missing_program_answer(argv: Any, available: Iterable[str] = ()) -> dict[str, Any] | None:
    """The result to give instead of running argv, or None to run it."""
    if not isinstance(argv, list) or not all(isinstance(word, str) for word in argv):
        return None
    present = {name.rsplit("/", 1)[-1] for name in available}
    for words in _commands(argv):
        program, rest = _program(words)
        if program is None:
            continue
        if program in _PACKAGE_MANAGERS:
            return _answer(program, "There is no package manager on this phone: nothing can be installed.")
        if program in ("pip", "pip3") or (program.startswith("python") and rest[:2] == ["-m", "pip"]):
            if "install" in rest:
                return _answer("pip install", "Python packages cannot be installed on this phone; use what is there.")
        if program == "npm" and rest[:1] in (["install"], ["i"]) and "-g" in rest:
            return _answer("npm install -g", "Global npm packages cannot be installed on this phone.")
        targets = rest if program in _PROBES else [program]
        for target in targets:
            name = target.rsplit("/", 1)[-1]
            if name in _MISSING and name not in present:
                return _answer(name, _INSTEAD[_MISSING[name]])
    return None


def _answer(program: str, instead: str) -> dict[str, Any]:
    return {
        "returncode": 127,
        "stdout": "",
        "stderr": f"{program} is not available on this phone (see Environment); nothing was run. {instead}",
        "not_run": True,
    }
