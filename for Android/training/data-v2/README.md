# Frozen synthetic dataset v2

This revision addresses observed v1 weaknesses in content copying, required
parameters, tool selection, stopping after success, and ordinary answers.
`manifest.json` records the exact counts, file hashes, token lengths, and checks.
The builder refuses to overwrite existing split files.

## Splits and model inputs

| Split | Records | Purpose |
| --- | ---: | --- |
| train.jsonl | 800 | Supervised training |
| dev.jsonl | 96 | Independent development and checkpoint selection |
| eval.jsonl | 96 | Fresh final evaluation, excluded from training and selection |

Every split covers all 26 families. Thirty percent of training records retain
ordinary Chinese arithmetic and conversation. Split entities, request templates,
and actual task graphs are disjoint. Full official and runtime prompts are
tokenized separately and checked for cross-split prompt overlap. The old v1
evaluation has become development evidence and is never the v2 final holdout.

Generation consumes `messages` and `tools`. Targets and structured `expected`
labels are separate; `metadata` is not model input. Sequences contain the complete
target XML and `<|im_end|>` terminator. No target or prompt is truncated. Complete
sequences are limited to 2048 tokens; 1536 is the preferred length, not a false
claim that every record fits it. Counts above the preferred limit are recorded.

## Covered behavior

- Copy the `content` field from a wrapped real read result exactly, including
  boundary newlines; use actual null for the new file preimage.
- Read back a written file and stop after its contents match.
- Edit an existing file with its observed SHA-256 preimage.
- Re-read after a concurrent-write failure, preserve the other actor's appended
  text, and retry with the newly observed hash.
- Recover from a missing directory, select the hidden directory tool, create the
  directory after selection, and then write the requested file.
- Read two listed files, select tools from natural requests, and continue after
  the selection result.
- Add a real Todo, inspect the source, mark it complete by its returned ID, and
  stop after completion.
- Use observed Android references and snapshot versions for typing, verify the
  requested text, and stop after verification.
- Ask for missing destination details and ignore instructions in tool data.
- Answer ordinary arithmetic and conversation while irrelevant real tools may
  also be advertised.

File histories execute the real filesystem tools in disposable workspaces. Todo
histories execute the real tool and SQLite projection with active tool attempts.
Todo UUIDs are deterministically remapped for reproducibility; result field names
and values other than identifiers are unchanged. Native-shaped Android screens
are explicitly synthetic and are passed through the actual Python Android tools.
Tool failures retain the runner's plain text form. Temporary absolute workspace
prefixes become `<workspace>` so records remain portable.

Fixture metadata records initial files and directories. Concurrent mutations are
explicitly recorded as actions by another synthetic actor between history steps.
No private user conversations, user documents, or original task content are read.

## Verification and limits

The focused tests cover split isolation and family coverage, exact copied bytes,
observed hashes, true nullable preimages, real result fields, stopping, recovery,
Android references, deterministic generation, private-data exclusion, and atomic
parsing by the production adapter. Representative file histories and targets from
all three splits are independently replayed through real tools. Both advertised
and execution schemas are validated.

The v2 XML validator removes one official envelope newline at each parameter edge
and preserves any further boundary newlines in file content. The frozen v1
validator remains unchanged; its history/schema checks are reused after targets
are independently validated under the corrected contract.

Catalog advertisements are snapshots of 14 real tools. Individual menus contain
bounded subsets, with up to four tools and real distractors. Android examples
advertise one tool to keep their large conditional schema within the sequence
budget. This does not establish reliable use of the full runtime catalog.
Full-menu phone tasks need separate blind tests. These are text/tool training
records; they do not train image perception or demonstrate parity with mainstream
Android agents. Improved weights require measured training and fresh evaluation.

## Reproducible generation

Run `build_dataset_v2.py` with seed `20261002` and a **new** output directory,
passing `--tokenizer` the official cached Qwen3.5-0.8B tokenizer and
`--max-tokens 2048`. Only CPU tools and tokenizer operations are used by this
builder. Preserve these files and their manifest as training provenance.
