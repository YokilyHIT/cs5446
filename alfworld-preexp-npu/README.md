# ALFWorld Pre-Experiments (NPU build)

Reproducible implementation of the two pre-experiments from
`两个方向_预实验设计_ClaudeCode可复现版.md`:

- **Experiment A — Selective Failure Learning**: do different failure-derived
  lessons have significantly different real value for future tasks?
- **Experiment B — Prediction Confidence vs Planning Utility**: does a
  world-model's self-reported confidence actually predict whether acting on
  its foresight helps or hurts planning?

Agent: ReAct-style ALFWorld agent driven by `Qwen/Qwen3-4B-Instruct-2507`
through a local vLLM OpenAI-compatible server.

## Status

**Verified end-to-end on Ascend 910B3 / aarch64 / Python 3.11 / CANN 8.3.RC2.**
`scripts/run_smoke_test.sh` passes clean, `pytest preexperiments/tests` is
17/17, and every artifact spec section 37 requires is produced.

| | |
|---|---|
| **How to reproduce** | **[REPRODUCE.md](REPRODUCE.md)** — 11 steps from a clean machine |
| What changed and why | [CHANGES_AND_KNOWN_ISSUES.md](CHANGES_AND_KNOWN_ISSUES.md) |
| Baseline success-rate measurement | [diagnostics/stage0_baseline.md](diagnostics/stage0_baseline.md) |
| Ascend environment details | [README_NPU_SETUP.md](README_NPU_SETUP.md) |
| 中文说明 | [README_CN.md](README_CN.md) |

The full pre-experiments have **not** been run yet — only the smoke-scale
pipeline and the Stage 0 baseline measurement. Read the "已知未修" section of
[CHANGES_AND_KNOWN_ISSUES.md](CHANGES_AND_KNOWN_ISSUES.md) before trusting any
headline number from a full run.

## Layout

```
REPRODUCE.md                      # ← start here: full reproduction procedure
CHANGES_AND_KNOWN_ISSUES.md       # every change + its rationale + open issues

preexperiments/
├── configs/
│   ├── preexperiment.yaml        # single source of truth: model/sampling/seeds/splits/paths
│   └── alfworld_base_config.yaml # ALFWorld's own env config schema
├── common/                       # shared infra used by both experiments
│   ├── llm_client.py             # vLLM client; guided_choice, <think> prefill
│   ├── alfworld_runner.py        # env adapter, ReAct rollout, action-decision paths
│   ├── replay_state.py           # deterministic state restore (experiment B)
│   ├── embeddings.py             # shared sentence-transformers wrapper
│   ├── stats.py                  # bootstrap CI / Spearman / McNemar
│   ├── prompts.py                # every fixed prompt template, verbatim from the spec
│   └── logging_utils.py          # JSONL I/O, run-id, per-step log schema
├── failure_selection/            # Experiment A pipeline (run in this order)
│   ├── collect_failures.py
│   ├── extract_lessons.py
│   ├── select_related_tasks.py
│   ├── evaluate_single_lessons.py
│   ├── score_failure_proxies.py
│   ├── evaluate_topk_vs_all.py
│   └── analyze.py                # + binomial-null "luck baseline", go/no-go verdict
├── world_model_utility/          # Experiment B pipeline (run in this order)
│   ├── collect_decision_points.py
│   ├── generate_foresight.py
│   ├── build_counterfactual_pairs.py
│   ├── evaluate_planning_gain.py
│   ├── evaluate_oracle_gate.py
│   └── analyze.py                # + INCONCLUSIVE gates, go/no-go verdict
└── tests/                        # spec section 37's mandatory test list (17 tests)

scripts/
├── setup_env_npu.sh              # one-shot environment bootstrap (NPU host)
├── start_vllm_npu.sh             # start the model server on Ascend
├── inspect_alfworld_api.py       # verify ALFWorld API assumptions before running anything
├── run_smoke_test.sh             # mandatory pre-flight checks (spec section 6/38)
├── check_forced_action_rate.py   # hard gate: is the agent really choosing its actions?
├── run_experiment_A.sh / run_experiment_B.sh
├── run_all.sh                    # smoke tests -> B -> A -> report -> full test suite
├── generate_report.py            # fills reports/preliminary_results.md
└── collect_env_info.sh           # regenerate ADAMEM_COMMIT.txt / requirements_lock.txt / gpu_info.txt

tools/
└── measure_baseline.py           # Stage 0: base success rate, loop rate, forced-action rate

diagnostics/                      # Stage 0 evidence — committed, not regenerated per run
├── stage0_baseline.md            # method, results, spec-section-39 decision
└── baseline_{spec30,spec50,adamem30}.jsonl

results/ figures/ reports/        # per-run output (gitignored; see .gitkeep)
```

## Quick start

Full procedure with every prerequisite and trap: **[REPRODUCE.md](REPRODUCE.md)**.
Once the environment is up, the order that matters is:

```bash
python scripts/inspect_alfworld_api.py            # 1. ALFWorld API assumptions hold?
bash scripts/start_vllm_npu.sh &                  # 2. model server
python -m pytest preexperiments/tests -q          # 3. expect 17 passed
bash scripts/run_smoke_test.sh                    # 4. must be green before anything full-scale
python tools/measure_baseline.py --workers 16     # 5. Stage 0 — do NOT skip, see below
bash scripts/run_experiment_B.sh                  # 6. B first (slower, fails earlier)
bash scripts/run_experiment_A.sh
python scripts/generate_report.py
```

Step 5 is a gate, not a formality: whether the agent is strong enough for the
deltas these experiments measure to mean anything is an empirical question, and
spec section 39 fixes the order in which you are allowed to react to a low
success rate. `diagnostics/stage0_baseline.md` records that decision for this
host with the data behind it.

## Design notes

- Every fixed prompt, sampling parameter, seed list, and split name is copied
  verbatim from the spec into `preexperiments/configs/*.yaml` and
  `preexperiments/common/prompts.py` — no script hard-codes its own copy.
  `sampling.prompt_style` selects between the spec's section 5.1 prompt
  (default) and AdaMEM's, the remedy spec section 39 names; whichever is
  selected applies identically to every condition in both experiments, so it
  can never bias a comparison.
- `replay_state.restore_state` is the only sanctioned way to reproduce a
  specific ALFWorld state twice (spec section 19); Branch 0 / Branch W
  counterfactual rollouts in Experiment B start from exactly the same restored
  state, with exactly the same step budget.
- Action decoding is constrained to the current admissible set. This is
  load-bearing, not cosmetic: unconstrained, 51% of this model's actions were
  landing on a difflib fallback that silently substituted a different object's
  action and locked the agent into a loop.
- Every `analyze.py` rebuilds its summary purely from on-disk JSONL/CSV, so the
  headline numbers are independently reproducible from the raw logs alone (spec
  section 37, test 7) — verified by `tests/test_analysis_rebuild.py`.
- Both `analyze.py` scripts can return **INCONCLUSIVE**, deliberately outside
  the spec's GO/WEAK-GO/NO-GO trichotomy. "We measured no effect" and "this run
  produced no signal to measure" are different claims, and a floor effect or a
  spread indistinguishable from binomial noise must not be reported as evidence
  against the hypothesis.
- Go/No-Go interpretations only ever use the phrasing "supported by preliminary
  evidence" / "weakly supported" / "not supported under the current setup"
  (spec section 43) — never "hypothesis proven".
- TextWorld is not thread-safe; all env calls go through one lock in
  `alfworld_runner`. Episodes are otherwise run concurrently, which is worth
  roughly 14x (37 tok/s single-stream vs 513 tok/s at 16-way).
