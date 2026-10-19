# Stage 2: Five baselines on the dev set (+ two random gates)

Date: 2026-10-12. Protocol: see `../stage1_protocol_logging/README.md` §1 (unchanged).
Data: `eval_in_distribution` 140 tasks × 6 arms × 3 repeats = 2520 episodes, all paired on the same task set.
Repeats differ only by vLLM serving nondeterminism (seed fixed at 42, temperature=0); they are not independent policy samples.

Run command (one process per arm×rep; 8 vLLM endpoints):
```bash
$PY -m preexperiments.react_study.run_episodes --stage 2 --arm <arm> --rep <0|1|2> \
    --workers 24 --tau 0.9997 --p_gate 0.276 --gate_seed 2026
$PY -m preexperiments.react_study.analyze_episodes --stage 2 \
    --raw_glob 'outputs/react_study/stage2_baselines/raw/eval_in_distribution/*.jsonl' --tag dev140_3reps
```

## 1. Main results (`tables/summary_dev140_3reps.md`, `figures/sr_vs_tokens_dev140_3reps.png`)

| Arm | SR (mean over 3 reps) | Range | ΔSR vs None [95% CI] | Tokens/task | WM calls/task | Planner calls/task | Legal action rate | Prediction usage |
|---|---:|---|---|---:|---:|---:|---:|---:|
| None | 19.0% | 18.6–19.3 | — | 22.3k | 0 | 26.5 | 93.9% | 0% |
| ReAct + rethink | 19.0% | 17.9–20.0 | −0.0 [−3.8, +4.0] | 45.6k | 0 | 52.9 | 92.3% | 0% |
| Always | **22.6%** | 20.7–23.6 | **+3.6 [−0.7, +7.9]** | 61.1k | 25.6 | 51.2 | 93.1% | 100% |
| Selective (conf > 0.9997) | 18.1% | 16.4–19.3 | −1.0 [−3.6, +1.4] | 46.0k | 26.5 | 34.1 | 92.7% | 28.9% |
| Random-post (p = 0.276) | 19.0% | 17.1–20.7 | +0.0 [−2.9, +2.9] | 44.6k | 26.4 | 33.5 | 92.4% | 27.0% |
| Random-pre (p = 0.276) | 21.7% | 20.7–22.9 | +2.6 [−0.5, +6.0] | 32.6k | 7.1 | 33.3 | 93.5% | 27.1% |

CI: per-task mean success over the 3 reps, task-level bootstrap (10k resamples). Per-rep McNemar tests are in the summary table; **no arm vs None reaches p < 0.05 in any single rep**.

Per-role tokens/task (input): planner_base ≈ 20.5–21.0k for every arm; planner_second: rethink 21.7k / always 22.2k / selective 7.4k / random 6.0–6.1k; WM: 14.5–14.7k when called every step, 3.9k for random_pre. No failed requests (failed_calls = 0).
Wall-clock and LLM latency are affected by load from the other 17 concurrent processes and are only roughly comparable; tokens are the primary cost measure.

## 2. Answers to the baseline questions in the plan

1. **Extra reasoning alone does not explain the gain.** Rethink costs as much as Selective (45.6k tokens) and changes the action at 42% of steps, but ΔSR = 0. Always vs Rethink: +3.6 [−1.4, +8.6]. The (non-significant) gain of Always comes more from the prediction content than from the second call itself.
2. **The confidence gate shows no advantage over the random gate at the same usage.** Selective (28.9% usage) 18.1% vs Random-post (27.0% usage) 19.0%; paired Selective − Random-post = −1.0 [−3.6, +1.7]. With the threshold inherited from the old run, Selective is even below None, but not significantly.
3. **Pre-call vs post-call random gating differ only in cost.** Random-pre and Random-post use the same u_t, so they use foresight at exactly the same steps: **as policies they are identical**. The only difference is that Random-post calls the WM at every step and discards most of the results. Random-pre therefore saves 27% of tokens (32.6k vs 44.6k).
4. **Built-in A/A noise check.** Because of point 3, the SR gap between Random-pre and Random-post (21.7% vs 19.0%; paired +2.6 [−0.2, +5.7]; one rep reaches McNemar p = 0.04) comes **entirely from serving nondeterminism**. On this dev set (140 tasks × 3 reps), differences of 2–3 pp are within noise, so Always's +3.6 pp cannot be counted as a stable gain.

## 3. Repeat stability
Fraction of tasks whose success outcome differs across the 3 reps: None 7.9%, Always 10.7%, Selective 10.0%, Random-post 11.4%, Random-pre 12.9%, Rethink 15.7%. Arms with a second pass are less stable (more decision points, so more chances to diverge).

## 4. By task type (mean over reps; small n per type, descriptive only)
Always is ≥ None on 5/6 types (exception: heat). Selective is below None on look/clean/cool/heat. See `tables/summary_dev140_3reps.md`.

## 5. Conclusions for Stage 3
- WM foresight probably has a small positive effect (+2–4 pp), but at 140 tasks it cannot be separated from serving noise.
- At equal usage, the confidence gate is no better than random, so prediction confidence is unlikely to be a good proxy for decision utility. Stage 3 tests this directly at the state level.
- Random-pre reaches most of Always's effect at 53% of Always's tokens. If later gates decide **before** the WM call, the cost savings are real; post-call filtering cannot save WM cost.

## 6. Directory layout
```
raw/eval_in_distribution/<arm>__rep<k>.jsonl   one row per episode (with step_log, cost)
raw/eval_in_distribution/<arm>__rep<k>.config.json, games.txt
tables/summary_dev140_3reps.{md,json}          main table (reference arm none)
tables/summary_dev140_3reps_ref_rethink.*      paired comparisons with rethink as reference
tables/summary_dev140_3reps_ref_random_post.*  paired comparisons with random_post as reference
tables/per_task_*.csv                           per-task mean success for each arm
figures/sr_vs_tokens_dev140_3reps.png           success rate vs tokens
logs/
```
