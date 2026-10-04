# Frozen v3 inputs

The parent authorized freezing candidate 02 after the independent v2 phone copy
task failed to create its destination following repeated invalid CAS writes.
No phone task text, holdout entity, or original HTML answer was added to this data.

All six files from `data-v3-candidate-02` were copied byte for byte into `data-v3`.
The candidate remains preserved. Evidence is `output/qwen-v3-freeze-copy.json`.
The JSON/JSONL inputs and their manifest hashes are unchanged.

`candidate_only: true`, `weights_trained: false`, and candidate language in the
copied manifest/README describe the state at generation time. They are retained
as historical provenance. The new parent authorization makes this directory the
frozen v3 input location; training results belong in a separate run report.

The complete audit covered all 592 records with hidden scoring-field access
guards, unchanged official/runtime prompts after label mutation, exact runtime
menus, 554 real historical tool calls, and 344 actual target calls in temporary
workspaces. The audit is `output/qwen-v3-candidate-02-audit.json`.

An additional freeze check covered all 36 copy-write and 36 existing-edit records
across the three splits. Every new-file copy uses actual null and the exact
observed content, including its leading and repeated trailing newlines. Every
existing-file edit uses the full 64 hexadecimal characters from the latest
read result. No model inference or GPU work was performed by the data builder.

Training uses only `train.jsonl`; checkpoint selection uses the independent
`dev.jsonl`. `eval.jsonl` is the new final holdout and remains excluded from both.
