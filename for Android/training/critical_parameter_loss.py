"""Assistant loss with parameter means that do not favor long copied values."""

from __future__ import annotations

import math
import re
from collections import defaultdict

DEFAULT_WEIGHTS = {
    "function": 0.25,
    "cas": 0.5,
    "selector": 0.5,
    "edit_delta": 0.5,
    "content_boundary": 0.25,
}


def critical_target_spans(target: str, *, extra_spans: list[dict] | None = None) -> list[dict]:
    """Locate exact payload spans; wrapper LF is never part of a parameter."""
    spans = []
    for match in re.finditer(r"<function=([^>]+)>", target):
        spans.append({"kind": "function", "start": match.start(1), "end": match.end(1)})
    for match in re.finditer(r"<parameter=([^>]+)>\n(.*?)\n</parameter>", target, re.DOTALL):
        name, value = match.group(1), match.group(2)
        begin, end = match.start(2), match.end(2)
        if name in {"expected_sha256", "names"}:
            if not value:
                raise ValueError("Critical parameter must have an explicit value")
            spans.append(
                {
                    "kind": "cas" if name == "expected_sha256" else "selector",
                    "start": begin,
                    "end": end,
                }
            )
        if name == "content" and value:
            leading = len(value) - len(value.lstrip("\r\n"))
            trailing = len(value) - len(value.rstrip("\r\n"))
            if leading:
                spans.append({"kind": "content_boundary", "start": begin, "end": begin + leading})
            if trailing and trailing < len(value):
                spans.append({"kind": "content_boundary", "start": end - trailing, "end": end})
    for span in extra_spans or []:
        if span.get("kind") not in {"edit_delta", "content_boundary"}:
            raise ValueError("Only verified edit/content boundary extra spans are permitted")
        start, end = span.get("start"), span.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(target):
            raise ValueError("Critical span must be a nonempty target character interval")
        if span.get("expected_text") != target[start:end]:
            raise ValueError("Critical span expected text differs from the target")
        spans.append({"kind": span["kind"], "start": start, "end": end})
    unique = {(span["kind"], span["start"], span["end"]) for span in spans}
    return [
        {"kind": kind, "start": start, "end": end}
        for kind, start, end in sorted(unique, key=lambda value: (value[1], value[2], value[0]))
    ]


def map_critical_token_groups(
    spans: list[dict], offsets: list[tuple[int, int]], target_start: int, labels: list[int]
) -> list[dict]:
    """Map BPE overlaps with complete coverage, never using masked history tokens."""
    if len(offsets) != len(labels) or target_start < 0:
        raise ValueError("Offsets must align with the complete input/label sequence")
    groups = []
    for span in spans:
        begin, end = target_start + span["start"], target_start + span["end"]
        if begin >= end or span["kind"] not in DEFAULT_WEIGHTS:
            raise ValueError("Critical span has an invalid interval or kind")
        indices = []
        coverage = []
        for index, (left, right) in enumerate(offsets):
            if left < end and right > begin:
                if labels[index] == -100:
                    raise ValueError("Critical target span overlaps a masked prompt token")
                indices.append(index)
                coverage.append((max(left, begin), min(right, end)))
        cursor = begin
        for left, right in sorted(coverage):
            if left > cursor:
                break
            cursor = max(cursor, right)
        if not indices or cursor != end:
            raise ValueError("Tokenizer offsets do not completely cover the critical target span")
        groups.append({"kind": span["kind"], "indices": indices})
    return groups


def grouped_cross_entropy(logits, labels, groups: list[dict], *, weights: dict | None = None):
    """Add one mean per critical kind, averaging short and long parameters equally."""
    import torch

    active_weights = DEFAULT_WEIGHTS if weights is None else weights
    if any(not math.isfinite(value) or value < 0 for value in active_weights.values()):
        raise ValueError("Critical group weights must be finite and nonnegative")
    if logits.ndim != 3 or labels.ndim != 2 or tuple(logits.shape[:2]) != tuple(labels.shape):
        raise ValueError("Logits and labels must already be causally aligned")
    if logits.shape[0] != 1:
        raise ValueError("Grouped parameter loss requires one full assistant example")
    flat_labels = labels.reshape(-1)
    valid = flat_labels != -100
    if not bool(valid.any()):
        raise ValueError("Assistant loss requires supervised target tokens")
    per_token = torch.nn.functional.cross_entropy(
        logits.reshape(-1, logits.shape[-1]).float(),
        flat_labels,
        reduction="none",
        ignore_index=-100,
    )
    base = per_token[valid].mean()
    by_kind = defaultdict(list)
    critical_indices = set()
    for group in groups:
        kind, indices = group["kind"], group["indices"]
        if kind not in active_weights:
            raise ValueError(f"Critical group has no explicit weight: {kind}")
        if not indices or len(set(indices)) != len(indices):
            raise ValueError("Critical group indices must be unique and nonempty")
        if any(type(index) is not int or not 0 <= index < len(flat_labels) for index in indices):
            raise ValueError("Critical group token is outside the aligned assistant labels")
        if any(int(flat_labels[index]) == -100 for index in indices):
            raise ValueError("Critical group contains a masked prompt token")
        by_kind[kind].append(per_token[indices].mean())
        critical_indices.update(indices)
    total = base
    for kind, values in by_kind.items():
        total = total + active_weights[kind] * torch.stack(values).mean()
    return total, {
        "base_loss": float(base.detach()),
        "groups": len(groups),
        "critical_tokens": len(critical_indices),
        "group_counts": {kind: len(values) for kind, values in sorted(by_kind.items())},
        "group_mean_losses": {
            kind: float(torch.stack(values).mean().detach())
            for kind, values in sorted(by_kind.items())
        },
    }
