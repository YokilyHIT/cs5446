# Step 3: Gating comparison (held-out dev tasks)

Date: 2026-10-13. Protocol v2, WM without memory (matching the Step 0c labels). Evaluation set: **the 460 dev-pool tasks not used in Step 0c** (`raw/eval460_games.txt`), so the gate's training data, τ calibration and evaluation tasks are fully disjoint.
none / always are reused from Step 0 (same tasks, same protocol); all arms × 2 repeats.

## Gates (all target ≈ 30% WM usage; when the gate is closed the protocol-v2 second planner call is still made)
| Arm | Type | Rule | Calibration |
|---|---|---|---|
| random_pre | pre-call | u_t < 0.3 | — |
| selective | post-call (WorldEvolver) | C_logprob > τ | τ = 0.99943 = 70th percentile of confidence on the 140 Step-0c tasks (`tables/gate_calibration.json`) |
| gate_stuck | pre-call | a_base already repeated ≥ 2 times, or ≥ 2 "Nothing happens" in the last 5 steps | none (hand-written rule) |
| gate_learned | pre-call | ridge regression predicting U_PR(wm) from 20 agent-visible features > threshold | Trained on the 127 unbiased Step-0c points; leave-task-out CV Spearman = **0.11** (`tables/learned_gate.json`) |

## Results (`tables/summary_eval460.md`; reference arm random_pre: `summary_eval460_ref_random_pre.md`)

| Arm | WM usage | SR | ΔSR vs none [95% CI] | PR | ΔPR vs none [95% CI] | ΔSR vs random_pre | ΔPR vs random_pre | tokens in/task |
|---|---:|---:|---|---:|---|---|---|---:|
| none | 0% | 11.7% | — | 32.8% | — | −2.7 [−4.7, −1.0] | −2.2 [−4.1, −0.5] | 38.4k |
| always | 100% | 14.6% | +2.8 [+0.7, +5.0] | 35.7% | +2.9 [+1.0, +4.8] | +0.1 [−2.0, +2.2] | +0.6 [−1.2, +2.5] | 91.1k |
| selective | 36.8% | 15.7% | +3.9 [+2.4, +5.5] | 35.5% | +2.6 [+1.2, +4.2] | +1.2 [−0.8, +3.0] | +0.4 [−1.4, +2.2] | 89.5k |
| random_pre | 29.7% | 14.5% | +2.7 [+1.0, +4.7] | 35.0% | +2.2 [+0.5, +4.1] | — | — | 80.7k |
| **gate_stuck** | 56.2% | 15.5% | +3.8 [+2.2, +5.5] | **36.7%** | **+3.9 [+2.3, +5.5]** | +1.1 [−0.9, +3.0] | +1.7 [−0.1, +3.4] | 85.2k |
| gate_learned | 41.2% | 14.3% | +2.6 [+0.7, +4.6] | 34.4% | +1.6 [−0.1, +3.3] | −0.1 [−2.1, +1.8] | −0.6 [−2.5, +1.2] | 82.9k |

## Conclusions
1. **On these 460 (harder) tasks, every arm that uses foresight is significantly better than none** (+2.6 to +3.9 pp SR). Over all 600 dev-pool tasks, always was only +0.6 (Step 0), so on the 140 easier tasks it was actually negative. The WM's effect varies a lot across tasks and is mostly positive on hard ones. (Even with tasks disjoint, the gating conclusion is unaffected, but note that this task set is harder.)
2. **No gate significantly beats the random gate at similar usage**: confidence +1.2, stuck rule +1.1 (PR +1.7, near the significance line), learned gate −0.1. Given the 0c result (confidence is unrelated to utility; the learned gate's CV is only 0.11), this is expected.
3. **Usage was not matched exactly**: gate_stuck's stuck states are more frequent on hard tasks (usage 56% vs the 30% target), so its slight edge may partly come from simply using the WM more. With always at 100% usage giving only +2.8, the marginal value of extra usage is small.
4. **Cost**: protocol v2 still makes a second planner call when the gate is closed, and the planner dominates cost, so gating saves at most about 11% of tokens (80.7k vs 91.1k). Real savings would require dropping that "second call when closed" (a deviation from WorldEvolver) or saving on planner input.
5. **The best gate for Step 4 is fixed as gate_stuck** (preset rule: largest ΔPR vs none on the held-out set; ΔSR is about the same as selective's). It is a simple stuck rule, not a learned model.

## Directory layout
```
raw/eval460_games.txt, eval460_chunk{0,1,2}
raw/train/eval_v2_c{0,1,2}_{random_pre,selective,gate_stuck,gate_learned}__rep{0,1}.jsonl
raw/compare/   symlinks (with step 0 none/always) for paired analysis
tables/gate_calibration.json, learned_gate.json, summary_eval460*.{md,json}, per_task_*.csv
figures/sr_vs_tokens_eval460*.png
launch_gates.sh, logs/
```
