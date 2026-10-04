# Qwen3.5 Agent tool fine tuning

This directory contains real language-weight LoRA training for the Android
Agent. It does not train on personal conversations, screenshots or credentials.
The base checkpoint is `Qwen/Qwen3.5-0.8B`, pinned to revision
`2fc06364715b967f1860aea9cf38778875588b17`.

`data` is the frozen first experiment. `data-v2` is a separate procedural
dataset with 800 training, 96 development and 96 final evaluation examples.
The final evaluation split is never used for gradient updates or checkpoint
selection. Real isolated file, todo and selection tools generate its histories;
Android observations use a synthetic native-shaped fixture. The dataset
manifest records hashes, complete token lengths and split separation.

The v2 run uses rank 8 LoRA on language attention and MLP projections,
assistant-only loss, a learning rate of `5e-5`, up to 48 optimizer steps and
gradient accumulation of 4. It evaluates all development records every 12
steps and restores the best positive-step checkpoint. Source FP32 gates and
normalization weights are preserved. Vision and MTP weights remain frozen.
The saved report gives the actual trained examples and steps; the presence of
800 examples on disk does not mean all 800 were consumed.

`data-v3` is a separately frozen file-task follow-up with 400 training,
96 development and 96 final evaluation records. It adds natural first reads,
nullable new-file CAS, observed existing-file CAS, preserved newline boundaries,
readback, verified completion and exact menus after local tool selection.
Its `FROZEN.md` explains why the copied generation manifest retains historical
candidate flags. No final evaluation records are used for training or selection.

The v3 run trains from the official base using `--prompt-source runtime`,
100 steps with accumulation 4, and all 96 development records every 20 steps.
It consumes one complete 400-example epoch. The selected checkpoint is step 60,
so the exported weights reflect 240 unique examples, including 80 ordinary
answers. The report records this separately from the complete 100-step run.
It remains an experimental file-task adaptation and does not train every Android
tool or demonstrate mature autonomous behavior.

`data-v4` contains 600 training, 120 development and 120 fresh final records,
with 40% ordinary examples in each split. Its system and complete applicable
tool inventory come from the installed Android runtime. The two sanitized
capture files are included so generation can be reproduced without the original
`output` directory. `FROZEN.md` pins the reviewed candidate, sources and rules;
the copied manifest retains its original candidate status as historical evidence.
The captured bridge did not provide accessibility UI tools. These records train
file and selector stages, six arithmetic groups, literal field extraction and
string sorting; they do not establish general conversation or Android UI mastery.

The v4 configuration trains language LoRA weights from the verified official
base at rank 8, alpha 16 and learning rate `1e-5`, using accumulation 4 for two
complete epochs, at most 300 updates. Every consumed prefix contains at least
40% ordinary examples. Complete runtime and official-template sequences fit in
2560 tokens; no history, target or source content is truncated. Critical
function names, CAS values, selectors, edit changes and content boundaries
receive additional parameter group losses with exact token/causal alignment.

The untouched base and checkpoints at updates 150 and 300 generate all 120
development continuations with identical decoding. Selection uses independently
executed tool results and ordinary final answers. Every family must preserve
the paired base result, total tool success must increase, and the eight write
families in `v4-critical-minima.json` must each pass both development examples.
Loss does not select the checkpoint. A run without a passing checkpoint retains
its real adapter checkpoints and failure report and refuses a qualified adapter
or merged export. The final split is excluded from training and selection.
Measured outcomes belong in the dated verification report.

The measured v4 run was stopped when the user expanded the request to general
daily file generation and search. It produced 72 of 120 base development
generations and zero optimizer updates. It did not produce an adapter or a
trained checkpoint; the missing 48 generations cannot be counted as evaluated.
Both the original EOS diagnostic run and the corrected interrupted run retain
their raw outputs and termination records. The frozen v4 data remain immutable.

The new v5 implementation covers six document/code formats, production
`web_search` followed by source retrieval, file editing and recovery. Its planned
1200/200/200 stage splits contain exactly 40% ordinary tasks. Separately,
20 development and 20 final workflows begin from initial state and require the
model to choose every assistant/tool turn. Controlled search uses real TLS,
production parsers and synthetic fixture documents; it does not establish
public search quality. Natural phone tests provide separate external evidence.

V5 was frozen on 2026-10-01 with 1200 training, 200 development and 200 final
records. Complete measured sequences fit in the 4096-token training budget
(maximum 4079); this is not the Android inference context limit. The output
budget is 384 tokens and workflows allow 12 model turns. Nothing is truncated
to fit these budgets. The fixed attention-only LoRA profile uses rank 16,
alpha 32, dropout 0.05, learning rate 2e-5, accumulation 4 and at most two full
epochs/600 updates. Checkpoints require absolute ordinary/tool thresholds,
paired preservation of every stage family and workflow group, observed CAS,
complete readback and independently correct final artifacts. Synthetic control
tests and successful instrumentation evidence collection are not model task
success. Python semantics, rendered animation and public source facts require
their own completed reviews before the corresponding phone task can pass.

The first V5 base evaluation generated all 200 development outputs, then
stopped before any optimizer update because the scorer interpreted a successful
wrong-function `web_search` response as a `web_fetch` result. The declared
scorer amendment guards stage semantics with actual function equivalence.
All original outputs and both generation-limit failures remain in the scoring
denominator: 67/120 tool stages and 38/80 ordinary answers passed. These are
untouched-base continuation results, not autonomous workflow performance.
The amended scorer's canonical 200/200 and 198 related CPU tests check the
evaluation program, not model quality.

Formal continuation uses a separately hashed source snapshot and explicitly
fixed synthetic fixture paths. Live Android context/settings changes are
therefore independent of the paired training evaluation. Early isolated
launches that stopped before model loading are preserved with their diagnostics;
the final training report must state actual optimizer updates. No V5 weights
are qualified or registered until the original development gates pass.

Use the compatible PyTorch, Transformers and PEFT versions in the environment
report for reproduction. The measured run reuses a local CUDA Python runtime;
it does not require or use a paid training service.

```powershell
python train_lora.py --help
python build_dataset_v2.py --help
python evaluate_tools.py --help
python export_gguf.py --help
```

From this directory, using a compatible CUDA Python environment and the verified
cached official model, the v3 training settings can be reproduced with a fresh
output directory:

```powershell
python train_lora.py --model models/qwen3.5-0.8b --train data-v3/train.jsonl --eval data-v3/dev.jsonl --output runs/new-v3-reproduction --prompt-source runtime --max-length 2048 --steps 100 --gradient-accumulation 4 --learning-rate 5e-5 --rank 8 --seed 20261001 --eval-limit 0 --checkpoint-every 20 --early-stopping-patience 0 --device cuda --export-merged
```

The fixed v4 experiment uses a fresh output directory and these settings:

```powershell
python train_lora.py --model models/qwen3.5-0.8b --train data-v4/train.jsonl --eval data-v4/dev.jsonl --output runs/new-v4-reproduction --prompt-source runtime --max-length 2560 --steps 300 --gradient-accumulation 4 --learning-rate 1e-5 --rank 8 --seed 20261001 --eval-limit 0 --checkpoint-every 150 --early-stopping-patience 0 --device cuda --critical-parameter-loss --minimum-ordinary-fraction .4 --behavioral-dev-catalog data-v4/catalog.json --behavioral-critical-minima v4-critical-minima.json --behavioral-max-new-tokens 512 --export-merged
```

The normal comparison uses identical runtime prompts, greedy decoding and a
512-token output limit for both base and trained weights. Hidden answer labels
are excluded from prompts. `evaluate_tools.py` preserves raw generations and
reports strict answer equality separately from protocol validity.
`evaluate_replay_v2.py` provides additional isolated execution measurements;
they do not replace complete real-phone task tests.
`evaluate_replay_v3.py` scores v3 file stages with real filesystem, CAS and
selection execution and labels restored historical progress separately.
`evaluate_replay_v4.py` preserves raw continuations, accepts only framing EOS
tokens, and independently scores actual file states and visible ordinary tasks.
Historical prerequisites are restored explicitly; continuation-stage success
does not count as a model completing the task autonomously from the beginning.
Ordinary math needs a final-answer audit: legacy substring scoring can accept
a correct intermediate number followed by an incorrect final answer.

Exports require genuine gradient-update evidence, adapter integrity, verified
merged language/vision/tokenizer weights, all official MTP tensors and the
pinned llama.cpp source archive. Each training version has its own model ID.
GGUF imports verify size, SHA-256 and file headers before publishing a new
private model directory. Experimental trained models remain separate from the
original model.

Development loss, synthetic continuation accuracy, quantized inference and
end-to-end phone success are different measurements. Consult the dated report
under `for Android/docs/reviews` for actual results and remaining failures.
