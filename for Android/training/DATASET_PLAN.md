# Qwen3.5 Android tool dataset plan

**Goal:** Prepare an initial synthetic LoRA training set and an independent holdout
for the existing Android Agent tool protocol, without reading user data.

**Architecture:** Extract the actual `ToolRegistry` and Android `ToolSpec` schemas
inside a disposable directory. Create structured previous messages, current tool
advertisements, and a separate target response in the official Qwen3.5 XML format.
An independent validator checks the complete XML, current advertisements, both
provider and execution schemas, path containment, nullable CAS hashes, and history.
The trainer owns model loading and completion-only loss; this task owns data only.

**Constraints:** No user conversation, secrets, original HTML task, or benchmark
answer is a data source. Train/eval entities and task compositions differ. Never
truncate a response or train on an unfinished tool call. Every example must fit the
trainer's 1536-token window after the official local tokenizer is available.
No ADB, Gradle, commit, push, environment changes, or edits to `train_lora.py`.

- [x] Write independent tests for current schemas, nullable arguments, paths,
  whole XML calls, train/eval separation, and deterministic generation; observe RED.
- [x] Implement `build_dataset.py` with isolated schema extraction and synthetic
  task generation, including tool selection and result-conditioned continuations.
- [x] Implement `validate_dataset.py`, checking metadata and labels separately
  from model-visible prompts. Invalid examples fail before dataset publication.
- [x] Generate `data/train.jsonl`, `data/eval.jsonl`, `data/catalog.json`, and
  `data/manifest.json`; verify every call against current schemas.
- [x] Count complete prompt-plus-response tokens with the cached official
  tokenizer. Keep complete samples within 1536; report any excluded samples.
- [x] Run focused schema tests and lint once; send paths, counts, hashes, and
  practical evaluation limits to the training and evaluation owners.

## Frozen dataset evidence

The final split contains 320 training records and 96 held-out records, covering
548 complete current or historical tool calls. The official Qwen3.5 tokenizer
counts the entire prompt, target, and assistant end token: the longest training
record is 949 tokens and the longest held-out record is 985. No samples were
excluded or truncated. The independent validator and actual adapter acceptance
tests passed: 9 tests in `output/qwen-tool-dataset-final.xml`.

Hashes, reproduction instructions, and evaluation limits are documented in
`data/README.md`. This completes dataset preparation only; actual weight training
and independent base-versus-adapter evaluation belong to the training owner.
