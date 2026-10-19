# Step 2: Online Episodic Memory (does a better WM bring more utility?)

Date: 2026-10-13. Protocol v2, always arm + online Episodic Memory (`online_memory.py`), dev pool 600 tasks.
Trigger: in Step 1, oracle beat always by +2.7 pp SR, so better predictions should have value.

## Implementation (following WorldEvolver §3.2)
- After every executed environment step, append (o_t, a_t, o_{t+1}); the `check valid actions` pseudo-action is not stored. **The bank starts empty.**
- Retrieval: top-5 by Jaccard over action tokens (k_ME = 5), ties broken by recency, rendered into the WM prompt using the existing EM block format.
- **Shared across tasks**: one bank per process. A single 600-task process is GIL-bound and too slow, so the pool was split into 3 chunks of 200 tasks, **each chunk with its own bank** (each bank still covers more tasks than WorldEvolver's 134).
- **Persistent across attempts**: attempt 2 is seeded with the same chunk's final bank from attempt 1 (`--memory_init`).
- Not implemented: Semantic Memory; WorldEvolver re-queries the WM on the executed action when a^(1) ≠ a^(0), which is only needed for SM.

## Results (`tables/summary_dev600_em.md`, `tables/attempts_bestof2.json`)

WM prediction accuracy (steps where the executed action = a_base, prediction vs true next observation; `wm_accuracy.py`):

| | EM | token-F1 | Steps with a memory hit |
|---|---:|---:|---:|
| always (no memory) | 37.7% | 0.652 | 0% |
| always + EM, attempt 1 | **60.4%** | **0.812** | 99% |
| always + EM, attempt 2 (bank inherited) | **61.9%** | **0.811** | 100% |

Whole-episode results (600 tasks; none/always come from Step 0, 2 repeats):

| Arm | SR | ΔSR vs none [95% CI] | PR | ΔPR vs none [95% CI] | tokens in/task |
|---|---:|---|---:|---|---:|
| none | 22.2% | — | 41.2% | — | 35.8k |
| always | 22.8% | +0.6 [−1.7, +2.9] | 42.7% | +1.4 [−0.3, +3.2] | 85.6k |
| always + EM (attempts 1 / 2) | 22.3% (21.3 / 23.3) | +0.2 [−2.1, +2.4] | 42.0% | +0.7 [−1.1, +2.6] | 93.7k |
| (Step 1) oracle | 25.4% | +3.2 [+0.8, +5.6] | 44.6% | +3.4 [+1.5, +5.3] | — |

Best-of-2: none 27.0%, always 27.2%, always + EM 28.2% (vs none +1.2 [−1.7, +4.0]).

## Conclusions
1. **Memory raised prediction accuracy substantially (EM +23 pp, F1 +0.16), but SR / PR did not improve at all.** The "WM accuracy ↑ → decision utility ↑" link does not hold in the 60%-accuracy range. Even 100% accuracy (oracle) gives only +3 pp.
2. The relationship between accuracy and decision value is strongly nonlinear: as long as predictions are not fully reliable, the planner gains about as much from correct predictions as it loses from wrong ones (consistent with Step 0c, where U_wm is about the same for EM = 1 and EM = 0).
3. Carrying memory across attempts gives +2.0 pp from attempt 1 to attempt 2, which is within serving noise (the A/A flip rate is 9.7%).
4. **For this project: the main lever is not making the WM more accurate, but how the planner uses foresight** (the decision interface), and that even perfect information has a low ceiling with a 4B planner.

## Directory layout
```
raw/train/dev_v2_em_c{0,1,2}_always__rep{0,1}.jsonl (+ .memory.jsonl final banks, .memory.partial.jsonl)
raw/train/discarded_*   two discarded runs (quota crash / single process too slow), not counted
raw/compare/            relabeled always_em + step0 none/always symlinks
tables/summary_dev600_em.*, attempts_bestof2.json, tau_em_calibration.json (τ for Step 4)
launch_em.sh, logs/
```
