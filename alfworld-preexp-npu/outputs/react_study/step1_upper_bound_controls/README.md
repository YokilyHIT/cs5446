# Step 1: Upper bound (oracle foresight) and the WM-free loop hint

Date: 2026-10-13. Protocol v2 (see `../step0_protocol_v2_measurement/README.md`). Dev pool: 600 train tasks × 2 repeats; all arms paired on the same tasks.
none / always come from Step 0; oracle / loop_hint / rethink were run in this step.

## Arms
- **oracle**: at every step a shadow env executes a_base and the **true** o_{t+1} goes into the same FORESIGHT_BLOCK in place of the WM prediction (`agent.py: gt_fn_inc`, an incrementally synced shadow env, equivalent to a fresh replay; checked 22/22 against the main env).
- **loop_hint**: no WM. When the stuck rule fires (a_base already executed ≥ 2 times, or ≥ 2 "Nothing happens" in the last 5 steps), a second planner call is made with a "you have repeated this N times / Nothing happens" note (`LOOP_HINT_BLOCK`). It fired at about 46% of steps.
- **rethink**: second planner call at every step, no prediction (v1 control, re-run under v2).

## Results (`tables/summary_dev600_step1.md`; reference arm always: `summary_dev600_step1_ref_always.md`)

| Arm | SR | ΔSR vs none [95% CI] | PR | ΔPR vs none [95% CI] | Legal action rate | Δaction | tokens in/task |
|---|---:|---|---:|---|---:|---:|---:|
| none | 22.2% | — | 41.2% | — | 66.4% | — | 35.8k |
| rethink | 19.8% | **−2.4 [−4.8, −0.1]** | 40.8% | −0.5 [−2.5, +1.5] | 68.7% | 58% | 74.5k |
| loop_hint | 22.5% | +0.3 [−1.7, +2.2] | 42.7% | +1.5 [−0.1, +3.0] | 67.8% | 68% | 58.6k |
| always (real WM) | 22.8% | +0.6 [−1.7, +2.9] | 42.7% | +1.4 [−0.3, +3.2] | 70.6% | 43% | 85.6k |
| **oracle** | **25.4%** | **+3.2 [+0.8, +5.6]** | **44.6%** | **+3.4 [+1.5, +5.3]** | 72.0% | 48% | 71.2k* |

\* oracle does not call the WM (the true observation comes from the environment for free), so its tokens are not comparable with WM cost.
oracle vs always: ΔSR +2.7 [+0.2, +5.1], ΔPR +1.9 [+0.1, +3.8]. Per-rep McNemar for oracle vs none: p = 0.09 / 0.02.

## Conclusions
1. **The upper bound for perfect prediction is about +3 pp (SR and PR), significant but modest.** The real WM gets only +0.6 / +1.4, leaving about **2.5 pp** of room between the two. → The Step 2 trigger is met (better predictions have value).
2. **The 4B planner does not use perfect information well**: even with 100% correct predictions, the gain is only +3 pp. The smoke test even showed the planner ignoring the true observation "Nothing happens." and executing the action anyway. Part of the ceiling comes from the planner's ability to use the information, not from prediction quality.
3. **The WM-free loop hint** matches always's PR gain (+1.5 vs +1.4) at 68% of always's tokens; neither SR gain is significant. Part of the WM's effect is substitutable by a cheap loop hint, but neither is strong.
4. **Rethink is harmful under v2** (SR −2.4 pp, significant): a second reasoning call by itself makes things worse. The second call in always / oracle is therefore not where the gain comes from.

## Engineering notes
- The original oracle implementation (fresh env + full replay every step) was too slow and was replaced by an incrementally synced shadow env, run as 12 chunks × 2 reps, 4 threads per process. The first 14 slow episodes are in `raw/train/discarded_slow_oracle/` and are not counted.
- Partway through, the container hit its disk quota (fast_downward leaves a deleted copy of libdownward.so mapped for every env it creates). Fixed by setting `TMPDIR` to the data disk (`preexp_env/env.sh`); all runs resumed via the resume logic, with no truncated rows.

## Directory layout
```
raw/train/dev_v2_c{0,1,2}_{loop_hint,rethink}__rep{0,1}.jsonl
raw/train/dev_v2_o{00..11}_oracle__rep{0,1}.jsonl ; raw/oracle_chunk{00..11}
tables/summary_dev600_step1.{md,json}, summary_dev600_step1_ref_always.*, per_task_*.csv
figures/sr_vs_tokens_dev600_step1.png
launch_oracle.sh, logs/
```
