"""Critical operation parameters keep their influence across unequal lengths."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def helper():
    path = Path(__file__).resolve().parents[1] / "critical_parameter_loss.py"
    assert path.is_file(), "critical grouped parameter loss must be implemented"
    spec = importlib.util.spec_from_file_location("agent_critical_parameter_loss", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target(value="null", content="\nUnicode: 测试\n\n"):
    return (
        "<tool_call>\n<function=write_file>\n<parameter=path>\narchive/a.txt\n</parameter>\n"
        f"<parameter=content>\n{content}\n</parameter>\n"
        f"<parameter=expected_sha256>\n{value}\n</parameter>\n</function>\n</tool_call>"
    )


def char_encoding(text):
    return [(i, i + 1) for i in range(len(text))]


def test_exact_null_sha_function_and_content_lf_spans_exclude_wrapper_newlines():
    text = target()
    spans = helper().critical_target_spans(text)
    assert [text[s["start"] : s["end"]] for s in spans if s["kind"] == "cas"] == ["null"]
    assert [text[s["start"] : s["end"]] for s in spans if s["kind"] == "function"] == ["write_file"]
    assert [text[s["start"] : s["end"]] for s in spans if s["kind"] == "content_boundary"] == [
        "\n",
        "\n\n",
    ]
    sha = target("a" * 64)
    assert [
        sha[s["start"] : s["end"]]
        for s in helper().critical_target_spans(sha)
        if s["kind"] == "cas"
    ] == ["a" * 64]


def test_explicit_edit_span_is_exact_and_metadata_is_not_appended_to_input():
    text = target(content="状态：完成\n")  # noqa: RUF001
    begin = text.index("完成")
    extra = [{"kind": "edit_delta", "start": begin, "end": begin + 2, "expected_text": "完成"}]
    spans = helper().critical_target_spans(text, extra_spans=extra)
    assert any(
        span["kind"] == "edit_delta" and text[span["start"] : span["end"]] == "完成"
        for span in spans
    )
    extra[0]["expected_text"] = "错误"
    with pytest.raises(ValueError, match="span"):
        helper().critical_target_spans(text, extra_spans=extra)


def test_tokens_map_only_to_supervised_target_even_at_a_bpe_and_unicode_boundary():
    module = helper()
    text = target()
    prefix = "history\n"
    full = prefix + text
    offsets = char_encoding(full)
    labels = [-100] * len(prefix) + list(range(len(text)))
    mapped = module.map_critical_token_groups(
        module.critical_target_spans(text), offsets, len(prefix), labels
    )
    assert all(index >= len(prefix) for group in mapped for index in group["indices"])
    cas = next(group for group in mapped if group["kind"] == "cas")
    assert "".join(full[offsets[i][0] : offsets[i][1]] for i in cas["indices"]) == "null"
    begin = text.index("null") + len(prefix)
    merged_offsets = [*offsets[:begin], (begin, begin + 5), *offsets[begin + 5 :]]
    merged_labels = [-100] * len(prefix) + list(range(len(merged_offsets) - len(prefix)))
    groups = module.map_critical_token_groups(
        module.critical_target_spans(text), merged_offsets, len(prefix), merged_labels
    )
    assert next(group for group in groups if group["kind"] == "cas")["indices"] == [begin]


def test_offset_gaps_and_masked_critical_tokens_fail_loudly():
    module = helper()
    spans = [{"kind": "cas", "start": 0, "end": 4}]
    with pytest.raises(ValueError, match="cover"):
        module.map_critical_token_groups(spans, [(0, 1), (3, 4)], 0, [1, 4])
    with pytest.raises(ValueError, match="masked"):
        module.map_critical_token_groups(spans, [(0, 4)], 0, [-100])


def test_one_token_null_and_long_sha_get_equal_group_loss_without_prompt_gradient():
    import torch

    module = helper()
    logits = torch.zeros((1, 8, 3), requires_grad=True)
    labels = torch.tensor([[-100, 1, 2, 2, 2, 2, 2, 2]])
    loss, details = module.grouped_cross_entropy(
        logits,
        labels,
        [{"kind": "cas", "indices": [1]}, {"kind": "cas", "indices": [2, 3, 4, 5, 6, 7]}],
        weights={"cas": 0.5},
    )
    assert float(loss.detach()) == pytest.approx(1.5 * float(torch.log(torch.tensor(3.0))))
    assert details["groups"] == 2
    assert details["critical_tokens"] == 7
    loss.backward()
    assert bool((logits.grad[:, 0] == 0).all())
    short = float(logits.grad[:, 1].abs().sum()) - 4 / 3 / 7
    long = float(logits.grad[:, 2:].abs().sum()) - 4 / 3 * 6 / 7
    assert short == pytest.approx(long, abs=1e-6)


def test_unknown_groups_cannot_silently_fall_back_to_plain_loss():
    import torch

    with pytest.raises(ValueError, match="weight"):
        helper().grouped_cross_entropy(
            torch.zeros((1, 2, 3)), torch.tensor([[1, 2]]), [{"kind": "unknown", "indices": [0]}]
        )


@pytest.mark.parametrize("content", ["\r\n记录\r\n\r\n", "\r\n\n记录\r\n", "\r记录\n", "\r\n\n\r"])
def test_content_boundary_spans_preserve_crlf_mixed_cr_and_all_newline_payloads(content):
    text = target(content=content)
    spans = helper().critical_target_spans(text)
    boundaries = [
        text[span["start"] : span["end"]] for span in spans if span["kind"] == "content_boundary"
    ]
    leading = content[: len(content) - len(content.lstrip("\r\n"))]
    trailing = content[len(content.rstrip("\r\n")) :]
    assert boundaries == [
        value for value in (leading, trailing if trailing != content else "") if value
    ]
