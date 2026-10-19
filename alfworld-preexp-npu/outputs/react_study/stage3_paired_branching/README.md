# Stage 3: Paired branching on on-policy states: is there selection room?

Date: 2026-10-12. Protocol unchanged (see Stage 1). States come from the **train** split, disjoint from the dev/test tasks.

## 1. Procedure
1. **Collection** (`raw/train/none__rep0.jsonl`): ReAct-none run on 120 train tasks (20 per task type, seed 2026), recording the full state at every step. SR = 10.8%.
2. **Sampling** (`raw/decision_points.jsonl`, `tables/sampling_design.json`): candidates are t ≤ 25 (≥ 5 steps remaining), 2958 in total.
   - Strata: stuck (same action repeated ≥ 2 times, or ≥ 2 "Nothing happens" in the last 5 steps) vs normal. **Stuck states are 52% of candidates.** The 80 stuck / 120 normal draw (40% stuck) therefore slightly undersamples stuck states; each point carries an inverse-inclusion-probability weight.
   - At most 3 points per episode: 200 points from 101 episodes, 33–34 per task type; phase early/mid/late = 108/61/31; 17 points come from episodes that originally succeeded.
3. **Branching** (`raw/branches.shard*.jsonl`): for each point, replay the action prefix (**200/200 reproduced the logged observation exactly**). At that state, compute a_base, the WM prediction with its confidence, a_fore, and a_re. Then run 4 branches, each executing its first action and continuing with the none policy until step 30:
   B0 (a_base), **B0r (a_base again, measures the noise floor)**, BW (a_fore; shares B0 when a_fore = a_base), BR (a_re; likewise).
   U_W = Y_W − Y_0, U_R = Y_R − Y_0, U_noise = Y_0r − Y_0. The prediction is not kept in later context.

```bash
$PY -m preexperiments.react_study.run_episodes --stage 3 --arm none --split train --episodes 120 --stratify --select_seed 2026 --record_state --workers 16
$PY -m preexperiments.react_study.stage3_sample_points
for k in 0..9: $PY -m preexperiments.react_study.stage3_branch --workers 4 --shard $k --n_shards 10
$PY -m preexperiments.react_study.stage3_analyze
```

## 2. Results (`tables/stage3_summary.md`)

### Q1 Shares of positive / negative / zero utility

| Quantity | +1 | 0 | −1 | Mean [95% task-cluster CI] |
|---|---:|---:|---:|---|
| U_W (foresight) | 2 (1.0%) | 98.5% | 1 (0.5%) | +0.005 [−0.010, +0.023] |
| U_R (rethink) | 2 (1.0%) | 97.5% | 3 (1.5%) | −0.005 [−0.028, +0.016] |
| **U_noise (exact repeat)** | **7 (3.5%)** | 95.5% | **2 (1.0%)** | +0.025 [+0.005, +0.048] |

- From these states, the base branch succeeds only **5.5%** of the time (Y0 = 11/200; repeat Y0r = 16/200).
- Foresight changes the action at 30% of points and rethink at 41.5%, yet **changes in final success: foresight 3, rethink 5, while the exact repeat itself produces 9.**
- On this sample, the **effect of foresight on final success is below the serving-noise floor**. U_noise's CI excludes 0 only because of a 7 vs 2 random imbalance; the two branches are the same intervention.
- Also: a_base reproduced the logged action at only 171/200 points, and B0/B0r trajectories were identical at only 58/200. This again confirms that temperature-0 inference is not deterministic.

### Q2 Confidence vs accuracy vs utility
- Prediction quality is fairly high: EM 48.5%, token-F1 0.742 (against the real next observation).
- **Confidence predicts prediction correctness well**: AUROC(conf → EM) = 0.90, Spearman(conf, F1) = 0.645.
- Confidence vs utility: there are only 2 positive and 1 negative cases, so the AUROCs (0.50 / 0.995) are **meaningless** and not interpreted.
- High-confidence points (>0.9997) change the action more often (40.7% vs 26.0%): high confidence mostly comes from trivial "nothing new happens" predictions.

### Q3 Which states go with action changes (utility is too sparse; action change is used as a proxy)
- Stuck 45% vs normal 20%; repeated action 45% vs 13%; mid-episode 52.5% vs early 17.6%.
- Among changed actions, prediction EM is 73%, and 50% have an uninformative real next observation ("Nothing happens / nothing special / You are facing…"); among unchanged points that figure is 26%.
- Most common changes: look → go to (16), examine → go to (8), go to → go to (8).
- **Mechanism:** the WM accurately predicts that "this action will reveal nothing new", and the planner then abandons the useless action. **Foresight works mainly as a loop breaker**, not as a precondition check. The Benefit/Harm cases (`tables/stage3_cases.md`) fit this pattern as well.

### Q4/Q5 Equal-usage comparison and the ex-post oracle (`figures/utility_coverage.png`)
At 27.6% usage: confidence (high first) −0.005, confidence (low first) 0, random +0.0014, stuck rule 0, ex-post oracle +0.010 (using 1% of points). Always = +0.005. With only 3 nonzero events, these curves have **no statistical power**; they are listed only for completeness.

## 3. Conclusion: which branch of the plan's §6.2 decision table applies
Matches the row **"most predictions do not change the action or do not affect the task → examine the prediction's informativeness and the decision interface; hold off on gate training"**:
1. Final-success utility is almost always 0 on on-policy states (base success 5.5%). A 200-point sample **cannot detect** the selection room, and the effect is drowned by serving noise (noise nonzero rate 4.5% > foresight 1.5%).
2. The confidence signal measures "is the prediction correct", not "is it useful for the decision" (supported directly by Q2 + Stage 2's Selective ≈ Random).
3. Foresight does change the action substantially (30%) with a clear mechanism (breaking loops); the problem is that the outcome metric is too sparse.

## 4. Suggestions for the next round (not executed)
- **Change the utility measurement rather than adding samples**: (a) use repeated rollouts per branch (K ≥ 5) to estimate P(success), making U continuous and averaging out serving noise; (b) sample states where success is possible (e.g. tasks that succeeded in at least some repeated runs); (c) add a short-horizon proxy such as AgentBoard subgoal progress and "steps to escape the loop" as diagnostics.
- Given the "loop breaker" mechanism, add a cheap control: a no-WM loop-detection prompt (telling the agent "this action has been repeated N times with no new information"). If it matches Always's gain, the WM's distinctive value is limited.
- Gate design: pre-call (Stage 2: random_pre gets most of the effect at 53% of Always's tokens), with features from repetition / stalling / action type.

## 5. Directory layout
```
raw/train/none__rep0.jsonl          120 on-policy trajectories (with full state)
raw/decision_points.jsonl           200 sampled points (prefix, features, stratum, weight)
raw/branches.shard{0-9}.jsonl       per-point branch results (actions/success/cost per branch, prediction, thoughts)
tables/sampling_design.json
tables/stage3_summary.{md,json}     Q1–Q5
tables/stage3_by_feature.csv
tables/stage3_cases.md              benefit/harm cases
figures/utility_coverage.png
logs/
```
