"""Check and rewrite the Japanese and Korean UI catalogs.

Unlike Traditional Chinese these are translated by hand, so the catalogs are the source:

- web_companion/static/i18n-ja.js and i18n-ko.js map each Chinese UI string of i18n.js to its translation;
- kotlin_app/src/main/res/raw/ui_text_ja.json and ui_text_ko.json map the English wording of native text
  (every UiText.of(context, "中文", "English") pair, Kotlin templates written as {0}, {1}...).

After adding UI text, add its translations and run:

    python generate_ja_ko.py --add new.json            # web: {"中文原文": ["日本語", "한국어"], ...}
    python generate_ja_ko.py --add-native native.json  # native: {"English": ["日本語", "한국어"], ...}
    python generate_ja_ko.py                           # reorder, drop removed strings, report missing ones

The script fails while a string has no translation or a translation changes the placeholders ({0},
%s, %02d...) or the line breaks of its source.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from generate_zh_hant import CJK, STATIC, ui_texts

ROOT = Path(__file__).resolve().parent
KOTLIN = ROOT / "kotlin_app" / "src" / "main" / "kotlin"
RAW = ROOT / "kotlin_app" / "src" / "main" / "res" / "raw"
LANGUAGES = {"ja": ("MobileI18nJa", "Japanese"), "ko": ("MobileI18nKo", "Korean")}
PLACEHOLDER = re.compile(r"\{\d+\}|%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[sdfx%]")
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "$": "$", "'": "'"}


def _web_path(language: str) -> Path:
    return STATIC / f"i18n-{language}.js"


def _native_path(language: str) -> Path:
    return RAW / f"ui_text_{language}.json"


def _load_web(language: str) -> dict[str, str]:
    path = _web_path(language)
    if not path.is_file():
        return {}
    source = path.read_text(encoding="utf-8")
    return json.loads(source[source.index("{"): source.rindex("}") + 1])


def _load_native(language: str) -> dict[str, str]:
    path = _native_path(language)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _literal(source: str, start: int):
    """The Kotlin string literal (or "a" + "b" concatenation) at start: (text, end), templates as {0}..."""
    i = start
    while i < len(source) and source[i] in " \t\r\n":
        i += 1
    parts, holes = [], 0
    while True:
        if i >= len(source) or source[i] != '"' or source.startswith('"""', i):
            return None
        i += 1
        while source[i] != '"':
            if source[i] == "\n":
                return None
            if source[i] == "\\":
                parts.append(ESCAPES.get(source[i + 1], "\\" + source[i + 1]))
                i += 2
            elif source.startswith("${", i):
                depth, i = 1, i + 2
                while depth:
                    depth += {"{": 1, "}": -1}.get(source[i], 0)
                    i += 1
                parts.append("{%d}" % holes)
                holes += 1
            elif source[i] == "$" and re.match(r"[A-Za-z_]", source[i + 1]):
                name = re.match(r"[A-Za-z_]\w*", source[i + 1:]).group(0)
                parts.append("{%d}" % holes)
                holes += 1
                i += 1 + len(name)
            else:
                parts.append(source[i])
                i += 1
        i += 1
        j = i
        while j < len(source) and source[j] in " \t\r\n":
            j += 1
        if j < len(source) and source[j] == "+":
            j += 1
            while source[j] in " \t\r\n":
                j += 1
            if source[j] == '"':
                i = j
                continue
        return "".join(parts), i


def native_texts() -> dict[str, str]:
    """English wording -> Chinese wording of every adjacent ("中文", "English") literal pair in the Kotlin
    sources: what UiText.of and the helpers built on it (labels, guides, menu actions) choose between."""
    pairs: dict[str, str] = {}
    for path in sorted(KOTLIN.rglob("*.kt")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r'(?<!\\)"', source):
            try:
                first = _literal(source, match.start())
                if not first or not CJK.search(first[0]):
                    continue
                comma = first[1]
                while comma < len(source) and source[comma] in " \t\r\n":
                    comma += 1
                if comma >= len(source) or source[comma] != ",":
                    continue
                second = _literal(source, comma + 1)
            except IndexError:  # A quote that does not start a literal ran off the end of the file.
                continue
            if second and not CJK.search(second[0]) and re.search(r"[A-Za-z]", second[0]):
                pairs.setdefault(second[0], first[0])
        # Constant pairs: const val NAME = "中文" with const val NAME_EN = "English".
        constants = {match.group(1): match.end() - 1 for match in re.finditer(r'const val (\w+) = (?=")', source)}
        for name, start in constants.items():
            if name.endswith("_EN") and name[:-3] in constants:
                english, chinese = _literal(source, start), _literal(source, constants[name[:-3]])
                if english and chinese and CJK.search(chinese[0]):
                    pairs.setdefault(english[0], chinese[0])
    return pairs


def _problems(source: str, text: str) -> list[str]:
    found = []
    if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(text)):
        found.append("placeholders differ")
    if source.count("\n") != text.count("\n"):
        found.append("line breaks differ")
    if not text.strip() and source.strip():
        found.append("empty")
    return found


def _write_web(language: str, catalog: dict[str, str]) -> None:
    variable, name = LANGUAGES[language]
    body = ",\n".join(
        f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False)}"
        for key, value in catalog.items()
    )
    # Bytes, so the file keeps LF line endings on Windows too.
    _web_path(language).write_bytes((
        f"/* {name} for the web UI: every Chinese string of i18n.js, translated by hand.\n"
        f"   Checked and rewritten by generate_ja_ko.py; i18n-extra.js loads it before i18n.js when needed. */\n"
        f"window.{variable} = {{\n{body}\n}};\n"
    ).encode("utf-8"))


def _write_native(language: str, catalog: dict[str, str]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    _native_path(language).write_bytes((json.dumps(catalog, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _report(label: str, catalog: dict[str, str], missing: list[str], stale: int) -> bool:
    bad = {text: _problems(text, value) for text, value in catalog.items()}
    bad = {text: problems for text, problems in bad.items() if problems}
    print(f"{label}: {len(catalog)} strings, {len(missing)} missing, {stale} removed, {len(bad)} with problems")
    for text in missing[:20]:
        print(f"  missing: {text!r}")
    for text, problems in list(bad.items())[:20]:
        print(f"  {', '.join(problems)}: {text!r}")
    return bool(missing or bad)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--add", type=Path, help="JSON of new web translations: {chinese: [ja, ko]}")
    parser.add_argument("--add-native", type=Path, help="JSON of new native translations: {english: [ja, ko]}")
    args = parser.parse_args()
    web_additions = json.loads(args.add.read_text(encoding="utf-8")) if args.add else {}
    native_additions = json.loads(args.add_native.read_text(encoding="utf-8")) if args.add_native else {}
    web_texts = ui_texts()
    native = list(native_texts())
    failed = False
    for index, language in enumerate(LANGUAGES):
        existing = _load_web(language)
        existing.update({source: pair[index] for source, pair in web_additions.items()})
        catalog = {text: existing[text] for text in web_texts if text in existing}
        _write_web(language, catalog)
        failed |= _report(f"web {language}", catalog, [text for text in web_texts if text not in existing],
                          len(existing) - len(catalog))

        existing = _load_native(language)
        existing.update({source: pair[index] for source, pair in native_additions.items()})
        catalog = {text: existing[text] for text in native if text in existing}
        _write_native(language, catalog)
        failed |= _report(f"native {language}", catalog, [text for text in native if text not in existing],
                          len(existing) - len(catalog))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
