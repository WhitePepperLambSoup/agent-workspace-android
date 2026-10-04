# Synthetic Android Agent tool dataset

This frozen dataset prepares Qwen3.5-0.8B for the Agent's current text and tool
protocol. It contains 320 training examples and 96 held-out examples, generated
from the actual advertised and execution tool schemas in a temporary workspace.
User conversations, user files, credentials, and fixed benchmark answers are not
data sources.

Examples cover complete Qwen XML calls, required and nullable arguments, file
paths and observed CAS hashes, tool selection, previous tool results, Todo,
authorized memory writes, Android observation/action/verification, ordinary
answers, and clarification when information is missing. The catalog contains 14
tools; 13 appear in examples. Screenshot image understanding is not covered.

## Files and model input

`train.jsonl` and `eval.jsonl` contain one example per line. Give the model only
`messages` and `tools` using its official chat template with thinking disabled.
The trainer uses `target_response` as the completion and applies completion-only
loss. During evaluation, both `target_response` and `expected` are labels and must
stay outside model input. `catalog.json` supplies schema validation information;
`manifest.json` records provenance, counts, token lengths, and file hashes.

Train and evaluation entities and scenario groups are disjoint. All 416 examples
pass an independent validator, and generated targets pass the actual Qwen output
adapter. Complete prompt-plus-completion lengths using the official tokenizer
are at most 949 training tokens and 985 evaluation tokens. No record was
truncated or excluded; all fit the trainer's 1536-token sequence window. This
training window is separate from the runtime context setting.

| File | SHA-256 |
| --- | --- |
| train.jsonl | 00d1a3d5a6c715af90cdb240f64ba12ca29cf518f677397c2bf39a23cb77ab03 |
| eval.jsonl | 80374e70f5bcebfd2f73f2910869cc3f4418d360ee941c29590885781228b91e |
| catalog.json | 0851286a885343b1c491f058f03112f64b4d6f52277aa3c89f3b0d22bd3b9b2c |

## Reproduction

From the project root, run the focused tests:

```powershell
& '.venv/Scripts/python.exe' -m pytest 'for Android/training/tests/test_dataset.py' -q
```

Use `training/build_dataset.py` with seed `20261001`, 320 training records and 96
evaluation records to regenerate candidates. Pass `--tokenizer` pointing to the
cached official Qwen3.5-0.8B tokenizer and `--max-tokens 1536` to count complete
sequences. Write candidates to a separate output directory so the frozen data
used by a training run stays identifiable. Schema changes require a new dataset
version and updated hashes.

## Evaluation limits

This is a small synthetic protocol dataset, with no vision or audio training.
Its holdout can compare base-model and trained-adapter tool-call validity and
argument accuracy under identical generation settings. It cannot establish
general Android task success, broad reasoning ability, or mainstream Agent
parity. Phone task completion, model conversion, inference integration, and
multimodal behavior require separate tests. Dataset validation alone does not
demonstrate that weight training has completed or improved the model.
