# Step 0: Protocol v2 + calibrating the measurement (dev pool / noise / K-continuation branching)

Date: 2026-10-13. Code: `preexperiments/react_study/` (`protocol_v2.py`, `progress.py`, `power.py`, `branch_k.py`, `sample_points_v2.py`, `analyze_branch_k.py`).

## 0-pre. Protocol v2 (frozen for all later experiments)

Source: AgentBoard (hkust-nlp/AgentBoard main + HF data.tar.gz), aligned with WorldEvolver's "ReAct + AgentBoard in-context examples".

| Item | v1 (stages 1–3) | **v2 (from now on)** |
|---|---|---|
| Planner prompt | Our own zero-shot ReAct | AgentBoard ALFWorld instruction + action templates + **1 example matching the task type** |
| Action syntax | — | AgentBoard examples/templates translated to the installed ALFWorld syntax (`put…in/on`→`move…to`, `using`→`with`, `toggle`→`use`); model outputs in the old syntax are normalised automatically |
| History | Last 50 turns, `> action` format | Full history, `Observation:/Action:` format (AgentBoard) |
| Valid actions | Listed every step | **Listed every step** (variant `list`, see the pilot) + `check valid actions` pseudo-action |
| Gate closed | Use a_base directly | **Still make a second planner call** (WorldEvolver Alg. 1: a^(1) ~ π(·\|s, F=∅)) |
| Decoding / WM prompt / foresight block | — | Unchanged |

**Pilot** (102 train tasks, disjoint from the dev pool; `tables/pilot102_protocol_comparison.json`):

| Variant | SR | PR | Legal action rate | tokens/task |
|---|---:|---:|---:|---:|
| v1 | 16.7% | 36.0% | 92.6% | 21k |
| **v2-list** | **26.5%** | **45.8%** | 67.0% | 36k |
| v2-query (AgentBoard as-is, no valid-action list) | 14.7% | 32.8% | 40.2% | 31k |

v2-list vs v1: McNemar 16 vs 6, p = 0.052; v2-list vs v2-query: p = 0.008. The 4B model almost never uses `check valid actions` on its own (0.1–0.2% of steps), so without the list it invents actions at a much higher rate. **Chosen: v2-list.**
Note: v2's legal action rate drops (67%). The most common illegal actions are `go to X` while already at X, and `examine` on a container that isn't there.

## 0a. Expanded dev pool + Progress Rate

- **Dev pool**: 600 train tasks (100 per task type, seed 2027, excluding the 120 tasks used in stage 3) → `raw/devpool600_games.txt`; pilot 102 → `raw/pilot102_games.txt`. The unseen test set is still untouched.
- **Progress Rate**: AgentBoard's 134 labels are all per-task-type regex templates. `progress.py` generates equivalent subgoals for any game file, **matching all 134 official labels exactly** (`python -m preexperiments.react_study.progress`), and translates the wording to the installed environment ("You move the X to the Y").
  Back-filled PR for stage 2 (v1): Always +5.3 [+1.8, +9.0]; the two A/A twins come out at exactly the same PR, so PR is much less noisy than SR.

## 0b. Determinism and noise
- vLLM 0.11.0 (Ascend) has **no** batch-invariant mode → noise is quantified with repeats + A/A.
- Dev pool, none rep0 vs rep1 (`tables/power_dev600_AA_none.json`): **9.7%** of tasks flip success; per-task SR difference sd 0.31; PR sd 0.24.
- Tasks needed to detect a difference at 80% power, α = .05 (single runs; with 2 repeats averaged see `power_dev600_always_vs_none.json`):

| Metric | 2 pp | 3 pp | 5 pp |
|---|---:|---:|---:|
| SR | 1900 | 845 | 304 |
| PR | 1149 | 511 | 184 |

  → 600 tasks × 2 repeats detects about **3 pp on PR and 3.5–4 pp on SR**; the old 140-task set could only detect 6–8 pp.

## Dev-pool baselines under v2 (`tables/summary_dev600_v2.md`)

| Arm | SR (2 reps) | ΔSR [95% CI] | PR | ΔPR [95% CI] | tokens in/task |
|---|---:|---|---:|---|---:|
| none | 22.2% | — | 41.2% | — | 35.8k |
| always (WM) | 22.8% | +0.6 [−1.7, +2.9] | 42.7% | +1.4 [−0.3, +3.2] | 85.6k |

**Under v2, the real WM's whole-episode gain is close to 0 (CI half-width about 2.3 pp), at 2.4× the token cost.**

## 0c. K = 8 continuation branching (`tables/branch_k_summary.md`)

Design: 200 points (160 from "solvable" tasks / 40 from never-solved tasks, ≤ 2 per task, 140 tasks). At each state, compute the first action of base / wm / oracle (true next observation) / rethink / loophint (hint added unconditionally). **Each distinct first action gets K = 8 continuations under the none policy**, which are shared across interventions with the same first action. U = P̂(a_X) − P̂(a_base), plus progress and 5-step progress. 200/200 states replay exactly.

### ⚠️ Methodology finding: outcome-selection bias
"Solvable" was originally defined as succeeding in either rep0 or rep1, and points were taken from rep0 trajectories, so 70% of solvable points came from **rep0 trajectories that later succeeded**. At those states a_base continues to success with probability 0.83, and any change can only make things worse (all interventions negative). Points from trajectories that later failed (P_base = 0.18) show WM / rethink / loophint ≥ 0.
**Fix**: define solvability using the other repeat (rep1). It is independent of the rep0 trajectory, so there is no selection on that trajectory's future. All conclusions below use this subset (127 points / 81 tasks); the future Step-3 sampler will use this definition directly.

### Results on the unbiased subset (mean effect of a single intervention at one state, task-cluster CI)

| Intervention | Action changed | U success | U PR |
|---|---:|---|---|
| WM foresight | 30% | −0.009 [−0.042, +0.025] | −0.010 [−0.030, +0.009] |
| oracle foresight | 30% | −0.021 [−0.054, +0.011] | −0.010 [−0.027, +0.006] |
| rethink | 45% | −0.014 [−0.064, +0.034] | −0.020 [−0.054, +0.012] |
| loop hint (unconditional) | 58% | **−0.067 [−0.120, −0.018]** | −0.027 [−0.057, +0.001] |

### But there is clear selection room
- **Excess variance**: among changed points, the variance of U is **4–10×** what K-continuation sampling noise would produce (all points: PR ratio wm 5.5 / oracle 4.1 / rethink 10.1 / loophint 10.3). States genuinely differ in how much an intervention helps or hurts; this is not noise.
- With the 2-SE criterion: for WM on solvable states, 7% of points show a significant gain and 22% a significant loss.
- **Confidence cannot pick them out**: confidence still predicts prediction correctness (AUROC 0.86), but Spearman with U_PR is **0.004**, AUROC 0.41 / 0.48 (U > 0 / U < 0).
- Utility–coverage at 30% usage (solvable, U_PR): confidence high-first −0.003, random −0.004, stuck rule −0.006, ex-post oracle +0.010, always −0.013.

### Takeaways
1. A single foresight intervention has **zero mean effect, but large and real per-state heterogeneity**, and "help" and "hurt" cancel out. The value of a gate therefore lies in avoiding the harmful states, not in finding states where it is always useful.
2. Confidence measures whether the prediction is correct, not whether it is useful, so the WorldEvolver-style confidence gate is not a suitable selector.
3. The loop hint used without a condition is harmful (−6.7 pp). It only works when triggered conditionally (whole-episode results in Step 1).

## Per-run outcomes (added 2026-10-18)
`per_task_dev600_v2.csv` only has the per-task average over the 2 runs (0.5 cannot tell which run succeeded), so the 0c unbiased subset cannot be reconstructed from it alone. Two files were added:
- `tables/per_task_per_rep_dev600.csv`: 600 tasks × {none, always} × {rep0, rep1}, giving success / progress / steps for each (plus task_type, gamefile).
- `tables/branch_k_unbiased_points.csv`: all 200 0c points with point_id, task_id, t, group, stratum, none_rep0_success, none_rep1_success, and in_unbiased_subset.
  **Unbiased subset = in_unbiased_subset == 1 (none_rep1_success == 1 and replay_ok): 127 points / 81 tasks.**
Note: on its own the CSV only reproduces the subset definition and the U-label statistics. Retraining the learned gate in `gate.py` also needs the rep0 trajectories' step observations (from the raw JSONL, not packaged).

## Directory layout
```
raw/devpool600_games.txt, devpool600_chunk{0,1,2}, pilot102_games.txt
raw/train/pilot_{v1,v2list,v2query}_none__rep0.jsonl      protocol pilot
raw/train/dev_v2_c{0,1,2}_{none,always}__rep{0,1}.jsonl  dev-pool baselines (none records full state)
raw/branch_points.jsonl, raw/branch_k.shard*.jsonl       0c sampled points and branch results
tables/pilot102_protocol_comparison.json, summary_dev600_v2.*, power_*.json, branch_k_summary.*, branch_sampling_design.json
figures/sr_vs_tokens_dev600_v2.png, branch_k_coverage_wm_pr.png
launch_branch_k.sh, logs/
```
