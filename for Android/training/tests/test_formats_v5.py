from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ANDROID_ROOT))


def formats():
    assert importlib.util.find_spec("training.formats_v5") is not None, (
        "V5 structured artifact formats and independent semantic validators are missing"
    )
    return importlib.import_module("training.formats_v5")


def task():
    return {
        "title": "合成青溪库存",
        "items": [
            {"name": "甲类", "quantity": 3, "source": "https://facts.example.test/a"},
            {"name": "乙类", "quantity": 5, "source": "https://facts.example.test/b"},
        ],
        "function_name": "total_quantity",
        "require_citations": True,
    }


def urls():
    return [item["source"] for item in task()["items"]]


@pytest.mark.parametrize("kind", ("markdown", "json", "csv", "html", "python", "javascript"))
def test_all_six_artifact_contracts_validate_semantics_and_observed_citations(kind):
    module = formats()
    content = module.render_artifact(kind, task())
    result = module.validate_artifact(kind, content, task(), observed_urls=urls())
    assert result["valid"] is True, result["errors"]
    assert result["total"] == 8
    assert result["items"] == task()["items"]
    assert result["arbitrary_code_executed"] is False


def test_json_scoring_accepts_formatting_and_key_order_without_exact_target_match():
    module = formats()
    value = {"total": 8, "items": task()["items"], "title": task()["title"]}
    content = json.dumps(value, ensure_ascii=True, indent=4)
    assert content != module.render_artifact("json", task())
    assert module.validate_artifact("json", content, task(), observed_urls=urls())["valid"]
    value["total"] = 7
    assert not module.validate_artifact("json", json.dumps(value), task(), observed_urls=urls())[
        "valid"
    ]


def test_csv_handles_quotes_unicode_commas_and_embedded_newlines():
    module = formats()
    specimen = task()
    specimen["items"][0]["name"] = '条目,引号"与\r\n换行🧬'
    content = module.render_artifact("csv", specimen)
    assert '""' in content and "\r\n" in content
    result = module.validate_artifact("csv", content, specimen, observed_urls=urls())
    assert result["valid"], result["errors"]
    wrong = content.replace(",3,", ",30,", 1)
    assert not module.validate_artifact("csv", wrong, specimen, observed_urls=urls())["valid"]


@pytest.mark.parametrize("kind", ("markdown", "json", "csv", "html", "python", "javascript"))
def test_wrong_quantity_missing_fact_and_unobserved_citation_fail(kind):
    module = formats()
    content = module.render_artifact(kind, task())
    assert not module.validate_artifact(kind, content, task(), observed_urls=urls()[:1])["valid"]
    altered = task()
    altered["items"][0]["quantity"] = 30
    wrong = module.render_artifact(kind, altered)
    assert not module.validate_artifact(kind, wrong, task(), observed_urls=urls())["valid"]
    altered = task()
    altered["items"] = altered["items"][:1]
    assert not module.validate_artifact(
        kind, module.render_artifact(kind, altered), task(), observed_urls=urls()
    )["valid"]


def test_markdown_and_html_cannot_satisfy_visible_facts_only_in_hidden_text():
    module = formats()
    for kind, wrapper in (("markdown", "```text\n{}\n```"), ("html", "<!--{}-->")):
        content = wrapper.format(module.render_artifact(kind, task()))
        assert not module.validate_artifact(kind, content, task(), observed_urls=urls())["valid"]
    html = module.render_artifact("html", task()).replace("</table>", "</span>")
    assert not module.validate_artifact("html", html, task(), observed_urls=urls())["valid"]


def test_python_validates_actual_pure_function_contract_without_running_untrusted_code():
    module = formats()
    content = module.render_artifact("python", task())
    assert module.validate_artifact("python", content, task(), observed_urls=urls())["valid"]
    assert not module.validate_artifact(
        "python",
        content.replace('sum(row["quantity"] for row in items)', "8"),
        task(),
        observed_urls=urls(),
    )["valid"]
    malicious = "import os\nos.remove('user-data')\n" + content
    result = module.validate_artifact("python", malicious, task(), observed_urls=urls())
    assert not result["valid"] and result["arbitrary_code_executed"] is False


def test_javascript_contract_requires_valid_json_export_and_quantity_sum_function():
    module = formats()
    content = module.render_artifact("javascript", task())
    assert not module.validate_artifact(
        "javascript",
        content.replace("sum + row.quantity", "sum + 1"),
        task(),
        observed_urls=urls(),
    )["valid"]
    assert not module.validate_artifact(
        "javascript", content + "\nfetch('https://example.org');", task(), observed_urls=urls()
    )["valid"]


def test_artifacts_without_requested_citations_are_valid_without_web_observations():
    module = formats()
    specimen = task()
    specimen["require_citations"] = False
    specimen["items"] = [
        {"name": item["name"], "quantity": item["quantity"]} for item in specimen["items"]
    ]
    for kind in ("markdown", "json", "csv", "html", "python", "javascript"):
        result = module.validate_artifact(kind, module.render_artifact(kind, specimen), specimen)
        assert result["valid"], result["errors"]


def test_invalid_or_duplicate_structured_facts_are_rejected_before_rendering():
    module = formats()
    specimen = task()
    specimen["items"][0]["quantity"] = True
    with pytest.raises(ValueError, match="quantity"):
        module.render_artifact("json", specimen)
    specimen = task()
    specimen["items"].append(dict(specimen["items"][0]))
    with pytest.raises(ValueError, match="unique"):
        module.render_artifact("json", specimen)


def daily_tasks():
    return {
        "markdown": {
            "subtype": "agenda",
            "language": "en",
            "title": "Synthetic reading plan",
            "date": "2026-10-02",
            "sections": [
                {"heading": "Morning", "bullets": ["Read the fixture notes", "Sort project tasks"]},
                {
                    "heading": "Afternoon",
                    "bullets": ["Review unfinished actions", "Save a short summary"],
                },
            ],
        },
        "json": {
            "subtype": "settings",
            "language": "zh",
            "data": {
                "profile": {"name": "合成练习", "locale": "zh-CN"},
                "settings": {
                    "theme": "dark",
                    "notifications": {"completed": True, "failed": False},
                    "tags": ["计划", "资料"],
                },
            },
        },
        "csv": {
            "subtype": "records",
            "language": "en",
            "columns": [
                {"name": "date", "type": "str"},
                {"name": "note", "type": "str"},
                {"name": "duration", "type": "int"},
                {"name": "done", "type": "bool"},
            ],
            "rows": [
                ["2026-10-02", 'Quoted "task", line\nnext', 15, True],
                ["2026-10-03", "Second record", 30, False],
            ],
        },
        "html": {
            "subtype": "guide",
            "language": "zh",
            "title": "合成资料整理说明",
            "paragraphs": ["按主题整理本地材料。", "所有记录保存在新建说明页面中。"],
            "steps": ["收集文件", "检查标题", "整理目录"],
            "animation": "pulse",
        },
        "python": {
            "subtype": "text_cleanup",
            "language": "zh",
            "title": "资料行清理",
            "function_name": "clean_lines",
            "operation": "strip_nonempty",
            "samples": ["  青杉  ", "", "\t\n", " beta "],
        },
        "javascript": {
            "subtype": "text_cleanup",
            "language": "en",
            "title": "Tidy notes",
            "function_name": "tidy_notes",
            "operation": "strip_nonempty",
            "samples": [" alpha ", "", "\t", " second note "],
        },
    }


@pytest.mark.parametrize("kind", ("markdown", "json", "csv", "html", "python", "javascript"))
def test_daily_subtypes_are_distinct_artifacts_with_independent_semantics(kind):
    module = formats()
    specimen = daily_tasks()[kind]
    content = module.render_artifact(kind, specimen)
    result = module.validate_artifact(kind, content, specimen)
    assert result["valid"], result["errors"]
    assert result["subtype"] == specimen["subtype"]
    assert result["arbitrary_code_executed"] is False
    assert "quantity" not in content
    wrong = (
        content.replace("Morning", "Unknown")
        if kind == "markdown"
        else content + "\nmalformed extra content"
    )
    assert not module.validate_artifact(kind, wrong, specimen)["valid"]


def test_settings_preserve_nested_boolean_types_and_records_preserve_text_not_just_totals():
    module = formats()
    specimen = daily_tasks()["json"]
    wrong = json.loads(module.render_artifact("json", specimen))
    wrong["settings"]["notifications"]["failed"] = 0
    assert not module.validate_artifact("json", json.dumps(wrong), specimen)["valid"]
    specimen = daily_tasks()["csv"]
    wrong = module.render_artifact("csv", specimen).replace("Second record", "Invented note")
    assert not module.validate_artifact("csv", wrong, specimen)["valid"]


@pytest.mark.parametrize("kind", ("python", "javascript"))
def test_text_cleanup_functions_reject_hardcoded_outputs_and_unsafe_extra_code(kind):
    module = formats()
    specimen = daily_tasks()[kind]
    content = module.render_artifact(kind, specimen)
    wrong = (
        content.replace("line.strip()", "line")
        if kind == "python"
        else content.replace("line.trim()", "line")
    )
    assert not module.validate_artifact(kind, wrong, specimen)["valid"]
    extra = content + (
        "\nopen('user-file', 'w')\n" if kind == "python" else "\nfetch('https://example.org');\n"
    )
    assert not module.validate_artifact(kind, extra, specimen)["valid"]


@pytest.mark.parametrize("daily", [False, True])
@pytest.mark.parametrize(
    "kind, mutation",
    [
        ("python", "annotation"),
        ("python", "return_annotation"),
        ("javascript", "return_glued"),
        ("javascript", "return_newline"),
        ("javascript", "reserved_argument"),
        ("html", "hidden"),
        ("html", "display_none"),
        ("html", "script"),
        ("html", "onload"),
        ("html", "iframe"),
        ("html", "contradiction"),
        ("markdown", "indented_code"),
        ("markdown", "hidden_wrapper"),
        ("json", "duplicate_key"),
    ],
)
def test_independent_visibility_syntax_and_side_effect_regressions(daily, kind, mutation):
    module = formats()
    specimen = daily_tasks()[kind] if daily else task()
    content = module.render_artifact(kind, specimen)
    if mutation in {"annotation", "return_annotation"}:
        parameter = "lines" if daily else "items"
        code = '__import__("os").remove("unrequested")'
        replacement = (
            f"({parameter}: {code}):" if mutation == "annotation" else (f"({parameter}) -> {code}:")
        )
        content = content.replace(f"({parameter}):", replacement)
    elif mutation == "return_glued":
        content = content.replace("return ", "return")
    elif mutation == "return_newline":
        content = content.replace("return ", "return\n")
    elif mutation == "reserved_argument":
        parameter = "lines" if daily else "items"
        content = content.replace(f"({parameter})", "(for)").replace(parameter + ".", "for.")
    elif mutation == "hidden":
        content = content.replace("<body>", "<body hidden>")
    elif mutation == "display_none":
        content = content.replace("<body>", '<body style="display:none">')
    elif mutation == "script":
        content = content.replace("</body>", '<script>fetch("unrequested")</script></body>')
    elif mutation == "onload":
        content = content.replace("<body>", '<body onload="fetch(1)">')
    elif mutation == "iframe":
        content = content.replace(
            "</body>", '<iframe src="https://unrequested.test"></iframe></body>'
        )
    elif mutation == "contradiction":
        content = content.replace("</body>", "<p>Actual total is 999.</p></body>")
    elif mutation == "indented_code":
        content = "\n".join("    " + line for line in content.splitlines())
    elif mutation == "hidden_wrapper":
        content = "<div hidden>\n" + content + "\n</div>"
    elif mutation == "duplicate_key":
        key = next(iter(specimen["data"])) if daily else "total"
        content = content.replace('"' + key + '":', '"' + key + '": null, "' + key + '":', 1)
    result = module.validate_artifact(kind, content, specimen, observed_urls=urls())
    assert not result["valid"], f"Accepted {kind} {mutation} daily={daily}"


@pytest.mark.parametrize(
    "mutation", ["comment_only", "hidden", "static", "zero", "disabled", "import"]
)
def test_guide_animation_requires_safe_visible_changing_nonzero_css(mutation):
    module = formats()
    specimen = daily_tasks()["html"]
    content = module.render_artifact("html", specimen)
    content = {
        "comment_only": content.replace("<style>", "<!--").replace("</style>", "-->"),
        "hidden": content.replace(".pulse { animation:", ".pulse { display:none; animation:"),
        "static": content.replace("opacity: 0.6", "opacity: 1"),
        "zero": content.replace("pulse 1s", "pulse 0s"),
        "disabled": content.replace("alternate;", "alternate; animation:none;"),
        "import": content.replace("<style>", '<style>@import url("https://unrequested.test");'),
    }[mutation]
    assert not module.validate_artifact("html", content, specimen)["valid"]


def test_inventory_rejects_shadowed_sum_duplicate_js_arguments_and_extra_markdown():
    module = formats()
    py = (
        module.render_artifact("python", task())
        .replace("(items):", "(sum):")
        .replace("for row in items", "for row in sum")
    )
    js = (
        module.render_artifact("javascript", task())
        .replace("sum, row", "x, x")
        .replace("sum + row.quantity", "x + x.quantity")
    )
    md = module.render_artifact("markdown", task()) + "\nActual total: 999.\n"
    for kind, content in (("python", py), ("javascript", js), ("markdown", md)):
        assert not module.validate_artifact(kind, content, task(), observed_urls=urls())["valid"]


def test_equivalent_html_labels_accept_pretty_whitespace():
    module = formats()
    content = module.render_artifact("html", task()).replace("<th>名称</th>", "<th>\n 名称\n</th>")
    assert module.validate_artifact("html", content, task(), observed_urls=urls())["valid"]
