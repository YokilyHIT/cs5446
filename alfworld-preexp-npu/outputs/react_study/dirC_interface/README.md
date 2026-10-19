# Direction C: change how foresight is used (the decision interface)

Date: 2026-10-13/14. 460 held-out tasks × 2 reps, protocol v2, no closed-gate second call. Statistics: `../dirF_final_eval/tables/round3_dev460.md`.

## Arms
| Arm | Content |
|---|---|
| fore_topk_p0.3 | **On the same random 30% of steps as random_pre_nc_p0.3** (same u_t): besides a_base, draw 2 more candidate actions at T = 0.7 (deduplicated), have the WM predict the outcome of each candidate, then the planner picks among "candidate → predicted outcome" (`TOPK_BLOCK`) |
| fore_surprise | Call the WM every step; show the prediction to the planner only when it says "Nothing happens" (a_base would fail) |

## Results

| Arm | WM usage | Steps with changed action | SR | ΔSR vs none [CI] (Holm) | PR | ΔPR vs none [CI] (Holm) | tokens/task |
|---|---:|---:|---:|---|---:|---|---:|
| none | 0% | 0% | 11.7% | — | 32.8% | — | 40.0k |
| random_pre_nc_p0.3 (single prediction, same steps) | 30% | 11.6% | 13.5% | +1.7 [+0.2, +3.3] (0.77) | 33.4% | +0.6 [−1.0, +2.1] (1.0) | 56.3k |
| **fore_topk_p0.3** | 30% | 12.9% | 14.9% | +3.2 [+1.5, +4.9] (0.002) | **36.1%** | **+3.3 [+1.7, +4.9] (0.002)** | 82.5k |
| **fore_surprise** | 15% | 10.3% | 15.2% | **+3.5 [+2.1, +5.1] (0.002)** | 34.9% | +2.0 [+0.5, +3.6] (0.30) | 60.1k |
| always | 100% | 40.8% | 14.6% | +2.8 | 35.7% | +2.9 | 95.0k |

fore_topk vs random_pre_nc_p0.3 (**same steps, only the interface differs**): ΔSR +1.4 [−0.7, +3.5], **ΔPR +2.7 [+0.9, +4.5]** (p 0.003, Holm 0.099).

## Conclusions
1. **The interface matters more than prediction accuracy**: on the same 30% of steps, switching from "verify one action" to "compare 3 candidates" raises PR by 2.7 pp, more than using single-action foresight on every step (always +2.9 at 100% usage). The memory experiment in step 2 raised accuracy by 23 pp with no gain.
2. **Showing only predicted failures** gives the largest SR gain (+3.5, Holm-significant) at only 15% usage; its PR gain is smaller. It acts like a cheap "precondition check".
3. Cost: fore_topk needs 2 extra samples + 3 WM calls on gated steps (82.5k tokens); the lower usage keeps it below always (95k).
4. **B + C combination `unc_topk`** (uncertainty gate decides where, candidate comparison decides how; exploratory, 460 × 2): 34% usage, SR 14.7% (+2.9 [+1.6, +4.3]), PR 36.1% (**+3.3 [+1.6, +5.0]**, Holm 0.008), 97.6k tokens/task.
   **Not additive**: no better than gate_unc (+2.8 PR) or fore_topk (+3.3 PR) alone, and it is the most expensive.
5. On the unseen test set (direction F, pre-registered H2) fore_topk shows **no gain** over the same-step random gate (PR +0.1 [−1.9, +2.0]); C's dev result does not reproduce.

## Directory layout
```
raw/train/{fore_topk_p0.3,fore_surprise,unc_topk}_c{0,1,2}__rep{0,1}.jsonl  (topk steps record candidates and predictions)
launch_unc_topk.sh, logs/
```
