# ALFWorld Pre-Experiments on Huawei Ascend NPU — Setup Guide

This repo implements the two pre-experiments from
`两个方向_预实验设计_ClaudeCode可复现版.md` (Selective Failure Learning /
Experiment A, and Prediction Confidence vs Planning Utility / Experiment B),
adapted so the LLM-serving side runs on a **Huawei Ascend NPU** instead of an
NVIDIA GPU. The NPU adaptation pattern (env vars, hardware-detection code,
`torch_npu` + `vllm-ascend`) follows the same approach already proven in
`OpenOneRec-Blue-Zone-main/benchmarks_green` (see
`benchmarks_green/README_NPU.md`, `benchmark/gpu_utils.py`, and
`scripts/ray-vllm/utils/generator.py` in that repo).

**This machine (the one you're reading this on) has no GPU/NPU.** It is only
used to write/edit code. Every command below that touches ALFWorld, vLLM,
torch, or an actual model must run **on the separate Ascend NPU host**. This
repo's own code only ever talks to that host over plain HTTP (the vLLM
OpenAI-compatible API), so the split is clean: edit here, run there.

> **Validated on real hardware.** The full pipeline (setup through
> `scripts/run_smoke_test.sh`) has been run end-to-end on Ascend 910B3 x2
> (aarch64, Python 3.11.13, CANN 8.3.RC2, torch/torch_npu 2.7.1,
> vllm/vllm-ascend 0.11.0, alfworld 0.4.2 / textworld 1.7.0). Every fix that
> came out of that run is already applied in this repo -- see
> `README_CN.md` section 8 for what broke and how it was fixed, and
> `diagnostics/README.md` for the measured baseline success rates that
> decided `sampling.prompt_style`'s default. If you're on a different
> ALFWorld/CANN/vLLM version, `scripts/inspect_alfworld_api.py` is still the
> first thing to run (section 6 below) -- some of the compatibility shims
> here (e.g. `_import_alfred_tw_env`) exist specifically because this API
> has already moved once.

```
┌─────────────────────────┐        HTTP (OpenAI API)        ┌──────────────────────────┐
│  This dev machine        │ ───────────────────────────────▶│  Ascend NPU host          │
│  (Windows, no GPU/NPU)   │  http://<npu-host>:8001/v1       │  CANN + torch_npu + vLLM  │
│  - edits preexperiments/ │ ◀───────────────────────────────│  serving Qwen3-4B-Instruct│
│  - never runs ALFWorld   │                                  │  ALFWorld + AdaMEM cloned │
└─────────────────────────┘                                  └──────────────────────────┘
```

If your NPU host is remote, either `rsync`/`scp` this whole directory to it,
or `git clone` the same repo there and `git pull` after edits. Everything
from here on assumes you are on the NPU host unless stated otherwise.

---

## 1. Hardware & driver prerequisites (NPU host)

- Huawei Ascend 910B (or 910A) card(s), with the **NPU driver + firmware**
  already installed by your ops/image provider (this is separate from the
  CANN toolkit below, and this repo cannot install it for you). Verify with:
  ```bash
  npu-smi info
  ```
  If this command doesn't exist, the driver isn't installed — stop and fix
  that first; nothing else in this guide will work.
- Linux host (Ascend's CANN toolkit does not support Windows/WSL).
- Enough host disk for: CANN toolkit (~10GB), ALFWorld dataset (~1-2GB),
  Qwen3-4B-Instruct-2507 weights (~8GB bf16), AdaMEM checkout.

## 2. CANN toolkit (the NPU equivalent of CUDA)

Download the toolkit + kernels `.run` installers matching your exact NPU
model/driver/firmware combination from
https://www.hiascend.com/developer/download/community/result?module=cann
(you must accept Huawei's license there — this cannot be scripted).

```bash
chmod +x Ascend-cann-toolkit_<version>_linux-<arch>.run
chmod +x Ascend-cann-kernels-910b_<version>_linux.run
./Ascend-cann-toolkit_<version>_linux-<arch>.run --install
./Ascend-cann-kernels-910b_<version>_linux.run --install

source /usr/local/Ascend/ascend-toolkit/set_env.sh
# add the line above to ~/.bashrc so every new shell has CANN on PATH
```

## 3. One-shot automated setup

`scripts/setup_env_npu.sh` runs steps 4-9 below for you (conda env, torch +
torch_npu, vLLM + vllm-ascend, this repo's requirements, AdaMEM clone,
ALFWorld install + dataset download, model download). Read it before running
it — it takes several environment-variable overrides (torch/vLLM version
pins, model source, etc.):

```bash
CANN_TOOLKIT_RUN=./Ascend-cann-toolkit_8.0.0_linux-aarch64.run \
CANN_KERNELS_RUN=./Ascend-cann-kernels-910b_8.0.0_linux.run \
bash scripts/setup_env_npu.sh
```

The rest of this section explains what it does, in case you need to debug or
redo a single step.

### 3.1 Conda environment

```bash
conda create -n alfworld-preexp-npu python=3.10 -y
conda activate alfworld-preexp-npu
python --version
```

### 3.2 torch + torch_npu

**Pin these together, and pin them to your CANN version** — an unpinned
`pip install torch_npu` can silently install a build that doesn't match your
CANN release, and then `torch_npu.npu.is_available()` returns `False` with
no useful error. Cross-check compatible versions at
https://gitee.com/ascend/pytorch (release notes list the torch / torch_npu /
CANN triple per release).

```bash
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install torch_npu==2.5.1
python -c "import torch, torch_npu; print(torch_npu.npu.is_available())"   # must print True
```

### 3.3 vLLM + vLLM-Ascend

```bash
pip install vllm==0.7.3
pip install vllm-ascend==0.7.3
```

Once `vllm-ascend` is importable, vLLM's platform plugin system auto-detects
the Ascend backend as long as `torch_npu` is importable and
`CUDA_VISIBLE_DEVICES` is **not** set — you do not pass a `--device npu`
flag. This is exactly the pattern used in
`OpenOneRec-Blue-Zone-main/benchmarks_green/scripts/ray-vllm/utils/generator.py`
(`_maybe_set_local_visible_devices`): it sets `ASCEND_RT_VISIBLE_DEVICES` /
`NPU_VISIBLE_DEVICES` and explicitly `os.environ.pop("CUDA_VISIBLE_DEVICES",
None)` before importing `vllm.LLM`.

### 3.4 This repo's Python dependencies

```bash
pip install -r requirements.txt
```

This is deliberately a short list (openai client, numpy/scipy/pandas,
matplotlib, sentence-transformers, pytest) — it does **not** duplicate
ALFWorld's or AdaMEM's own pins, which get installed separately in their own
checkouts below.

### 3.5 AdaMEM (agent code base / reference conventions)

```bash
cd ..                      # sibling of this repo, NOT inside it
git clone https://github.com/yunx-z/AdaMEM.git
cd AdaMEM
git rev-parse HEAD | tee ../alfworld-preexp-npu/ADAMEM_COMMIT.txt
pip install -e .
pip install -r requirements.txt
```

Per the original spec, **check before assuming anything about AdaMEM's
layout** — it may have moved on since this repo was written:

```bash
find . -maxdepth 3 -type f | sort | head -200
test -f examples/prompt_agent/gpt4o_alfworld.py && echo OK
test -f build_index.py && echo OK
test -f requirements.txt && echo OK
```

Note: `preexperiments/common/` in this repo does **not** import AdaMEM code
directly — it reimplements the ALFWorld+ReAct+vLLM plumbing itself (see
`preexperiments/common/alfworld_runner.py`), because AdaMEM's internal APIs
aren't guaranteed stable enough to depend on structurally. AdaMEM is cloned
here for reference/provenance (its commit hash goes in the final report,
spec section 36/37) and as the natural next step if Experiment A goes GO
(spec section 41: `No Memory → All Failure → Random-K → MNL-port →
ReasoningBank/AdaMEM → Ours`).

### 3.6 ALFWorld + dataset

```bash
pip install "alfworld[full]"
export ALFWORLD_DATA=$HOME/.cache/alfworld     # add to ~/.bashrc too
alfworld-download
python -c "import alfworld; print('ALFWorld import OK')"
```

> **aarch64 hosts**: `pip install alfworld` may fail while building TextWorld
> from source -- its `setup.py` runs a `setup.sh` that extracts
> `inform7-compilers_6M62_${ARCH}.tar.gz`, and Inform7 6M62 only ships
> i386/x86_64/ppc/armv6lhf builds, no aarch64. Those binaries are only used
> to *generate new* TextWorld games from scratch; ALFWorld ships pre-generated
> `.tw-pddl` games (executed by TextWorld's pure-Python PDDL environment), so
> missing them doesn't matter. Work around it with this repo's patched
> `setup.sh` (`third_party/textworld-1.7.0-setup.sh.orig` is the unmodified
> version, for diffing):
> ```bash
> cd /tmp && pip download --no-deps --no-binary :all: textworld==1.7.0
> tar xzf textworld-1.7.0.tar.gz && cd textworld-1.7.0
> cp /path/to/this/repo/third_party/textworld-1.7.0-setup.sh setup.sh
> pip install .
> ```
> x86_64 hosts: skip this, `pip install alfworld` builds TextWorld fine on its own.

`$ALFWORLD_DATA` must match the path baked into
`preexperiments/configs/alfworld_base_config.yaml` (it's a `{ALFWORLD_DATA}`
placeholder substituted at load time by
`preexperiments/common/alfworld_runner.py:_load_alfworld_config`).

**ALFWorld itself is pure Python/TextWorld and does not touch the NPU at
all** — only the LLM server does. `alfworld-play-tw` is an interactive
command that may not work well over SSH without a TTY; if it doesn't, the
smoke test below (`scripts/inspect_alfworld_api.py` +
`preexperiments/tests/test_alfworld_env.py`) covers the same
reset→observe→admissible-actions→step→next-observation loop non-interactively.

### 3.7 Model weights

Mainland-China NPU hosts often have faster/more reliable access to
ModelScope than HuggingFace:

```bash
pip install modelscope
python -c "
from modelscope import snapshot_download
snapshot_download('Qwen/Qwen3-4B-Instruct-2507', local_dir='$HOME/models/Qwen3-4B-Instruct-2507')
"
```

or, from HuggingFace directly:

```bash
pip install "huggingface_hub[cli]"
huggingface-cli download Qwen/Qwen3-4B-Instruct-2507 --local-dir $HOME/models/Qwen3-4B-Instruct-2507
```

### 3.8 Record the environment

```bash
python -m pip freeze > requirements_lock.txt
npu-smi info > gpu_info.txt
```

(`scripts/collect_env_info.sh` reruns just this step, e.g. after a package
upgrade, without redoing the whole setup.)

---

## 4. Dataset configuration recap

| What | Where | Notes |
|---|---|---|
| ALFWorld game files | `$ALFWORLD_DATA/json_2.1.1/{train,valid_seen,valid_unseen}` | populated by `alfworld-download`; `valid_seen` = `eval_in_distribution`, `valid_unseen` = `eval_out_of_distribution` (unused in phase 1, spec section 3) |
| ALFWorld logic files | `$ALFWORLD_DATA/logic/{alfred.pddl,alfred.twl2}` | also from `alfworld-download` |
| ALFWorld env config | `preexperiments/configs/alfworld_base_config.yaml` | ALFWorld's own config schema (`env`/`dataset`/`logic`/...), NOT this project's pipeline config; substitutes `{ALFWORLD_DATA}` at load time |
| Pipeline config (model/sampling/seeds/paths) | `preexperiments/configs/preexperiment.yaml` | single source of truth for every script; see spec sections 2-3 |
| Qwen3-4B-Instruct-2507 weights | `$HOME/models/Qwen3-4B-Instruct-2507` (or wherever you pointed `MODEL_PATH`) | passed to `scripts/start_vllm_npu.sh` |
| AdaMEM checkout | `../AdaMEM` (sibling of this repo) | reference only, not imported by this repo's code |

`splits.experience = "train"` and `splits.evaluation = "eval_in_distribution"`
in `preexperiment.yaml` map to ALFWorld's `train_eval="train"` /
`train_eval="eval_in_distribution"` arguments to `AlfredTWEnv` — this repo's
`ALFWorldEnvAdapter` and `build_single_game_adapter`
(`preexperiments/common/alfworld_runner.py`) pass these through directly.

---

## 5. Start the model server (NPU)

```bash
MODEL_PATH=$HOME/models/Qwen3-4B-Instruct-2507 \
NPU_DEVICES=0 \
bash scripts/start_vllm_npu.sh
```

This is the NPU-adapted equivalent of the spec's original
`CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server ...`
(spec section 1.4): `ASCEND_RT_VISIBLE_DEVICES` replaces
`CUDA_VISIBLE_DEVICES`, and `CUDA_VISIBLE_DEVICES` is explicitly unset so a
stale value can't leak in and confuse vLLM's platform auto-detection.

Health check (from either machine, if the NPU host's port 8001 is reachable):

```bash
curl http://<npu-host>:8001/v1/models
```

If your dev machine can't reach the NPU host directly, SSH-tunnel it:
`ssh -L 8001:localhost:8001 <npu-host>`, then everything in
`preexperiments/configs/preexperiment.yaml`'s `model.api_base:
http://127.0.0.1:8001/v1` works unmodified from either side of the tunnel.

If a single 910B's HBM is tight for a 4B model at `--max-model-len 32768`
(it normally isn't — a 4B model in bf16 is small), lower
`GPU_MEMORY_UTILIZATION` or shard with
`NPU_DEVICES=0,1 TENSOR_PARALLEL_SIZE=2 bash scripts/start_vllm_npu.sh`.

---

## 6. Verify the ALFWorld API assumptions

`preexperiments/common/alfworld_runner.py` hard-codes a small number of
assumptions about ALFWorld's public API (which `info` dict keys carry the
game file path / admissible commands / win flag; that `AlfredTWEnv` exposes
a reassignable `game_files` list and an `init_env(batch_size)` method). These
match the ALFWorld versions used by well-known text-agent baselines (ReAct,
Reflexion, ExpeL, AdaMEM's own `examples/prompt_agent/gpt4o_alfworld.py`),
but ALFWorld doesn't promise API stability. **Run this before anything else**
(spec section 38, step 1):

```bash
python scripts/inspect_alfworld_api.py
```

It prints exactly which assumption failed and which lines in
`alfworld_runner.py` to patch, if anything has drifted since this repo was
written.

---

## 7. Smoke tests (mandatory before any full run)

```bash
bash scripts/run_smoke_test.sh
```

This runs, in spec-mandated order (section 38, steps 1-8 / section 6):
1. the ALFWorld API check above,
2. `test_llm_client.py` / `test_alfworld_env.py` / `test_replay.py`,
3. a 5-train + 5-eval_in_distribution baseline episode run,
4. the deterministic-replay assertion (the single most important
   correctness gate for Experiment B — **do not proceed past a failure
   here**, spec section 39),
5. Experiment B's 10-decision-point mini smoke test (and everything
   downstream of it: `evaluate_planning_gain` / `evaluate_oracle_gate` /
   `analyze`, so a break in the analysis chain surfaces here instead of
   after the full-scale collection has been paid for),
6. Experiment A's 3-failure mini smoke test.

Step 2b (right after the baseline episodes) is a **hard gate** on the
forced-action rate (`scripts/check_forced_action_rate.py`) — if this fails,
the model's raw output isn't matching admissible actions and every
downstream success-rate number would be measuring action-formatting, not
planning (this is exactly what caught a 51.3% forced-action rate on the
validation host; see README_CN.md section 8.1).

### 7.1 Measure the real baseline success rate first (spec section 39)

Before deciding whether `max_episode_steps` or `sampling.prompt_style` need
changing, measure the actual no-memory baseline — a handful of ad-hoc
episodes is not enough signal to decide this on (spec section 39's remedies
are meant to be evidence-driven, not applied preemptively):

```bash
python scripts/measure_baseline.py --workers 16 --tag spec30
python scripts/measure_baseline.py --workers 16 --max_steps 50 --tag spec50
python scripts/measure_baseline.py --workers 16 --prompt_style adamem_think --tag adamem30
```

See `diagnostics/README.md` for the decision rule and the numbers measured
on the validation host (which is why `sampling.prompt_style` now defaults to
`"adamem_think"` in `preexperiment.yaml`). Re-run this if you change the base
model, its prompt-following behavior, or the ALFWorld dataset version.

## 8. Full experiments

```bash
bash scripts/run_experiment_B.sh     # spec sections 17-34
bash scripts/run_experiment_A.sh     # spec sections 7-16
python scripts/generate_report.py    # fills reports/preliminary_results.md
python -m pytest preexperiments/tests -q
```

or simply `bash scripts/run_all.sh` to run everything (smoke tests through
report + full test suite) in one shot.

Expect Experiment B to be the slower of the two — each of its ~150 decision
points requires two full episode rollouts from a restored state (spec
sections 24-25), on top of the ~5 LLM calls already spent per point on
base/world-model/foresight/ambiguity-sampling generation (section 21-23,31).

---

## 9. Output checklist (spec section 37)

After a full run, these must all exist under this repo's root:

```
ADAMEM_COMMIT.txt
requirements_lock.txt
gpu_info.txt

results/A_failures_raw.jsonl
results/A_failure_lessons.jsonl
results/A_failure_task_pairs.jsonl
results/A_failure_utility.csv
results/A_proxy_correlation.csv
results/A_eval_task_ids.json

results/B_decision_points.jsonl
results/B_world_model_utility.csv

figures/A_failure_utility_hist.png
figures/A_topk_vs_all.png

figures/B_confidence_vs_gain.png
figures/B_mismatch_matrix.png
figures/B_gain_by_ambiguity.png

reports/preliminary_results.md
```

plus a passing `python -m pytest preexperiments/tests -q`.

---

## 10. NPU-specific troubleshooting

- **`vllm-ascend` fails with `ModuleNotFoundError: No module named 'acl'`**:
  something overwrote `PYTHONPATH` instead of appending to it. Managed CANN
  containers typically pre-populate `PYTHONPATH` with CANN's own
  `python/site-packages` (which is where the `acl` module lives) — setting
  `export PYTHONPATH=/your/repo/path` clobbers that. Always append:
  `export PYTHONPATH=/your/repo/path${PYTHONPATH:+:$PYTHONPATH}` (see
  `scripts/env.sh.example`).
- **A HuggingFace/ModelScope download keeps dying after a few MB**: some
  network paths (proxied/mainland-China links to hf-mirror.com in
  particular) cut a single connection after ~7MB. `scripts/offline_download/`
  has a chunked, resumable downloader for exactly this (edit the hardcoded
  paths/filenames at the top before use) — only reach for it if the normal
  `modelscope`/`huggingface-cli` download in `scripts/setup_env_npu.sh`
  actually fails, most hosts don't need it.
- **`torch_npu.npu.is_available()` is `False`**: almost always a
  torch/torch_npu/CANN version mismatch, not a real hardware problem —
  re-check the compatible-version table at https://gitee.com/ascend/pytorch
  and reinstall the matching pair. Second most common cause: you forgot to
  `source /usr/local/Ascend/ascend-toolkit/set_env.sh` in this shell.
- **vLLM silently falls back to CPU / can't find any device**: check that
  `CUDA_VISIBLE_DEVICES` really is unset (`echo $CUDA_VISIBLE_DEVICES`
  should print nothing) — a leftover value from a previous GPU-based shell
  session can override the NPU auto-detection. `scripts/start_vllm_npu.sh`
  unsets it defensively, but only within its own subshell.
- **`ASCEND_RT_VISIBLE_DEVICES` vs `NPU_VISIBLE_DEVICES`**: different
  Ascend toolchain layers historically read different env vars; setting
  both (as `scripts/start_vllm_npu.sh` does) is the safe default.
- **A bf16 op is unsupported on your CANN/vllm-ascend version**: some
  Ascend kernel ops lag behind their CUDA equivalents; if the vLLM server
  crashes on a specific op, check the `vllm-ascend` issue tracker for your
  exact version pin before assuming the model/config is wrong.
- **`npu-smi info` shows the card but the process can't see it**: check
  container/cgroup device passthrough if you're inside a container — this
  is the NPU equivalent of a missing `--gpus` flag on `docker run`.
- **Everything else (ALFWorld crashes, low success rate, prompt issues,
  deterministic replay assertion failures)**: these are NOT NPU-specific;
  see spec section 39 ("失败时的处理原则") for the triage order, and
  `scripts/inspect_alfworld_api.py` for API-drift diagnosis.

---

## 11. What NOT to do (carried over from the spec, sections 38-40)

- Do not implement a full memory system before the phase-1 pre-experiments
  pass their Go/No-Go bar.
- Do not run 300+ episodes in phase 1 — the smoke tests and the fixed
  episode/decision-point caps in `preexperiment.yaml` are deliberate.
- Do not tune thresholds against the evaluation set to manufacture a
  positive result (spec section 0's hard requirement) — every threshold
  used in `preexperiments/*/analyze.py` is fixed in `preexperiment.yaml` or
  computed only from the calibration subset (Experiment B's `tau_c`, spec
  section 28).
- Do not run `eval_out_of_distribution` in phase 1 (spec section 3).
