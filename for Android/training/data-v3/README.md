# Independent first-step and runtime-menu candidate

This is the current v3 candidate. The earlier `data-v3-candidate` directory is
preserved as prior evidence and lacks the added CAS read-back/completion families.
Neither directory modifies v1 or v2. No weights have been trained on this data.
The parent selects any further training after measuring the current v2 model.

| Split | Records | Purpose |
| --- | ---: | --- |
| train.jsonl | 400 | Candidate follow-up training |
| dev.jsonl | 96 | Independent checkpoint development |
| eval.jsonl | 96 | New final holdout, excluded from training/selection |

All splits cover 18 families. Thirty percent of training records retain ordinary
arithmetic and conversation while the actual file tool menu is advertised.
Natural initial copy and edit requests each have 24 training examples with no
prior tool history and a first `read_file` target. Source content is available only
in the temporary fixture, not in these first-step model inputs.

The candidate covers first reads, writes using exact observed content and nullable
new-file preimages, existing-file CAS edits, read-back, verified completion, and
tool selection followed by reading or directory creation and writing. Copy
fixtures retain leading and repeated trailing newlines, Chinese text, quotes, and
an emoji. Edit holdouts vary the transformation: replacement, append, or deletion.

Every advertised menu is produced from the actual `_ContextState.prepare` state
and a file-task tool catalog. Initial active schemas are `list_files`, `read_file`,
`write_file`, and `select_local_tools`. After selecting read/write or directory/write,
the next menu contains exactly that selection plus the persistent selector.
No distractor schemas are silently appended after selection.

This is a file task profile, where Android platform tools are absent from the
available task tools. It does not establish performance when the full native UI
tool catalog is enabled. The catalog file still records all 14 real schema
snapshots. Menus contain the exact applicable subset.

Entities and user templates are distinct across train/development/final splits,
and official/runtime tokenized prompt overlaps are zero. First-read action
prefixes necessarily recur across splits; this is intentional transfer to new
tasks and is explicitly recorded rather than described as graph isolation.
All data is procedural and uses independent temporary workspaces. No private
documents, original phone holdout entities, or HTML task answers are used.

Complete official sequences have maximum lengths 1628/1798/1689 tokens for
training/development/final evaluation; runtime maxima are 1517/1687/1578. Inputs
include complete target XML and the end token. No sequences are truncated or
excluded. `manifest.json` records hashes and family counts.

The tests check natural first-step coverage, exact runtime menus, real atomic
parsing, private label isolation, deterministic generation, preserved copy
boundaries and CAS, and independent execution replay of finished records.
`audit_replay` reconstructs the temporary fixture, replays recorded histories,
checks the active menu, and executes targets through real tools. This validates
data and executor compatibility, not model performance.

The builder is `build_dataset_v3.py`, with seed `20261003`. Supply a fresh output
directory and the official cached Qwen3.5-0.8B tokenizer to reproduce the candidate.
