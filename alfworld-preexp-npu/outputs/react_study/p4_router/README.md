# Phase 4: label expansion and gate G1 re-test (2026-10-21) -> G1 FAILED, router line stopped

Plan rule (react_study_full_research_plan_20261019.md §4.4): G1 was "conditional pass" on the 127 step-0c
states (mean g_I ~ 0 but sign AUROC >= 0.60), so labels were expanded before any router training.

## Data
* 374 new 4B states from `label_pool500` (state from rep-0 `none` trajectory, group by independent rep 1:
  174 solvable + 200 unsolved; 242 tasks), `raw/p4b_label_points.jsonl`, `raw/p4_4b_label.shard*.jsonl`
  (arms base/RT/W4/W14/oracle, K=8, `launch_p4_labels_4b.sh`).
* Pooled with the 127 Phase-2 states: 501 states / 323 tasks. Analysis: `analyze_p2 --cfg p4_4b_label
  --cfg p2_4b+p4_4b_label --tag 4b_pooled` -> `p2_branch_labels/tables/p2_4b_pooled.{json,md}`.

## Result (PR, task-clustered 95% CI)
| | new 374 states | pooled 501 |
|---|---|---|
| g_R = RT - base | -0.66 pp [-1.36, -0.02] | -0.52 [-1.20, +0.13] |
| g_I4 = W4 - RT | +0.49 [-0.51, +1.53] | +0.15 [-0.93, +1.15] |
| g_I14 = W14 - RT | +0.15 [-0.93, +1.18] | +0.25 [-0.68, +1.18] |
| g_O = oracle - RT | +0.17 [-0.87, +1.21] | -0.10 [-1.12, +0.89] |
| sign AUROC of CV-predicted g_I4 / g_I14 | 0.42 / 0.43 | 0.53 / 0.46 |
| 3-way router minus matched random (q=.3, W4 / W14) | -0.01 / +0.00 | +0.36 / +0.08 |
| best-of-3 oracle (choice ceiling per decision) | +1.2 | +1.4 |

* The sign predictability seen on the first 127 states (AUROC 0.70-0.74) did not replicate on independent
  states (0.41-0.43): it was small-sample noise / overfitting.
* With identical features and penalty the incremental router equals the direct-value router exactly (ridge
  additivity error ~1e-15); the decomposition has no algorithmic content.
* Resampling alone is mildly harmful at the state level on new states (SR -1.6 pp [-2.8, -0.5]).

## Decision
G1 fails under the pre-specified rule (mean g_I not > 0 in any configuration, and offline router value not
reliably > matched random after expansion). Per plan §8 the router (Phases 5-6 as router experiments) is
not run. Next: finish Phase 3 (episode-level confirmation) and the feasibility probes
(`probe_feasibility/`), then choose between Plan C-type repair foresight and Plan D (attribution paper).
