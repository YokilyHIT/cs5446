# Independent recheck of the 4B baseline (blind)

中文摘要：请在**不查看**我们的结果（`aim3_e/results/`、`gpu_analysis/checkpoints/`、`gpu_analysis/docs/`、`gpu_analysis/data/README.md`、`report_4b/`）的前提下，用你自己的代码从下列数据独立算出指定数值，填入 `results_template.json` 的副本后交回，由协调人运行 `compare_recheck.py` 逐项比对。

## Rules

1. **Do not open** `aim3_e/results/`, `gpu_analysis/checkpoints/`, `gpu_analysis/docs/`, `gpu_analysis/data/README.md` or `report_4b/` until you have returned your numbers. The repository is shared, so this is an honour-system blind check.
2. Write your own code. Do not import, run, copy or read this repository's analysis code before returning your numbers: `tools/`, the `sidecar/` folders under `research_progress/`, `alfworld-preexp-npu/`, and `recheck_4b/compare_recheck.py` (its output contains the reference values). For D0 rules use `ANALYSIS_SPEC.json` only.
3. Copy `results_template.json`, fill every field you computed, leave the rest `null`, and add a short note on your method. All rates, differences and interval ends are **proportions** (write 0.125, not 12.5), not percentages.
4. If something is ambiguous, write down your interpretation in `method_notes` rather than asking. Disagreements are what this check is for.
5. Some unweighted D0 counts already appear in the 2026-10-15 team handoff notes. If you have seen them, say so in `method_notes`.

## Data

| Part | File | Content |
|---|---|---|
| E (Aim 3) | `recheck_4b/data/e_episode_outcomes.jsonl` | 402 rows = 134 unseen ALFWorld games × 3 arms (`always`, `no_info`, `none`), one episode each. Row fields are listed below; `recheck_4b/data/DATA_MANIFEST.json` records the file hash and the source runs. |
| E plan | `aim3_e/plan/EVALUATION_PLAN.md`, `aim3_e/plan/shards_public.json` | Pre-registered method; shard membership. |
| D0 (Aim 1) | `gpu_analysis/data/d0_snapshot.json` | 71 selected states in 24 development games; 68 have complete D/N/P outcomes. |
| D0 rules | `research_progress/2026-10-10-d0-analysis/ANALYSIS_SPEC.json` | Frozen weighting, accuracy normalisation, ranking and tie rules. |

### E row fields

| Field | Meaning |
|---|---|
| `game` | ALFWorld game as `<task>/<trial>`; pairs the three arms |
| `arm` | `always`, `no_info` or `none` |
| `Y_study` | Primary outcome (single-attempt SR@30), 0 or 1. Policy failures and budget exhaustion count as 0 (see the plan) |
| `outcome_status` | `complete` or `policy_failed` |
| `environment_success`, `steps`, `termination_reason` | Raw episode record; `environment_success` is null for policy-failed episodes |
| `policy_failure` | null, or `step`, `decision_role`, `reason`, `raw_finish_reason`, `completion_tokens` of the failing planner call |
| `planner_calls_by_role` | Planner calls per role: `draft`, `replan`, `no_info`, `no_info_fallback` |
| `n_world_model_calls` | World-model calls in the episode |
| `cost` | `logical_calls`, `known_prompt_tokens`, `known_completion_tokens`, `sum_known_request_elapsed_s`, plus completeness counters |
| `shard_index`, `run_id`, `task_index`, `task_type` | Bookkeeping |

## What to compute

### E (use all 134 games; one row per game and arm)

- Per arm: number of games with `Y_study == 1`; number with `outcome_status == "policy_failed"`.
- For each pair `always−no_info`, `always−none`, `no_info−none`, pairing rows by `game`:
  - rescued `b` = games where the first arm has `Y_study = 1` and the second `0`; harmed `c` = the reverse;
  - difference `(b − c) / 134`;
  - interval at level L: two-sided Clopper–Pearson intervals for `b/134` and `c/134`, each at level `1 − (1 − L)/2` (Bonferroni over the two), combined as `[b_low − c_high, b_high − c_low]`. Report L = 0.975 for `always−no_info` (the pre-registered primary contrast) and L = 0.95 for all three pairs;
  - exact two-sided McNemar p from a Binomial(`b + c`, 0.5) test.
- Sensitivity: for each pair, keep only games where **both** arms have `outcome_status == "complete"`; report the number kept and the difference `(b − c) / kept`.
- Failures: for each arm and decision role, total planner calls (`planner_calls_by_role`) and the number of policy failures attributed to that role (`policy_failure.decision_role`). Also count failures whose `raw_finish_reason == "length"` and `completion_tokens == 384`, across all arms.
- Cost per arm: sums of `cost.logical_calls`, `cost.known_prompt_tokens`, `cost.known_completion_tokens`, `cost.sum_known_request_elapsed_s`.

### D0 (use `points` where all three branches D, N, P have `measurement_validity == "valid"`; there should be 68)

- Unweighted: successes `raw_Y == 1` per branch; number of states with a non-zero difference for admission `P−D`, info `P−N`, revision `N−D`; first-action changes `[changed, comparable]` for the same three pairs, counting only pairs where both first actions are present.
- Weighted, with each point's `statistical_weight` normalised over the 68 points:
  - mean `raw_Y` of D, N, P; mean observed difference for admission, info, revision;
  - mean exact match (EM) and token-F1 between `prediction.wm_prediction` and `D_reference.observation`, using the normalisation in `ANALYSIS_SPEC.json` (`accuracy`);
  - weighted Pearson correlation between the ordinary average ranks of `prediction.wm_mean_logprob` and the ranks of EM, and likewise of token-F1.
- Confidence quartiles: sort by `prediction.wm_mean_logprob` (descending) into four bins of 25 % of the normalised weight each, with the tie and boundary rules in `ANALYSIS_SPEC.json` (`scoring`). Per bin: weighted EM, token-F1 and mean observed admission, info, revision differences.
- Ranking descriptor `G = Σ w_norm × (g − 0.5) × observed difference`, where `g` is the top-half (50 % weight, same tie rule) membership by confidence; report it for admission, info and revision.

## Returning and comparing

Return your filled JSON. The coordinator runs:

```sh
python -B recheck_4b/compare_recheck.py --results <your_results.json> --out <comparison.json>
```

Counts must match exactly. E proportions and interval ends must agree within 0.0001; D0 weighted quantities within 0.000001. A mismatch is investigated on both sides; neither result is assumed correct in advance.
