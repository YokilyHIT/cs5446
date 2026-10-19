# Direction B: gating on the planner's own uncertainty

Date: 2026-10-13/14. Code: `dirB_offline.py` (offline screen), `dirB_sign_offline.py` (sign sub-problem), `gate.py: planner_uncertain`, `protocol_v2.py: action_line_lp`.

## 1. Offline screen (`tables/offline_signal_screen.md`; 200 step-0c states, utility labels from K = 8 continuations)

Target: WM foresight utility U_PR. Unbiased subset (127 states, tasks solvable by rep1):

| Signal (higher ⇒ open the gate) | AUROC U≠0 | AUROC U>0 | AUROC U<0 | Spearman(U) |
|---|---:|---:|---:|---:|
| Low planner action logprob | 0.733 | 0.770 | 0.669 | +0.03 |
| Low planner whole-response logprob | **0.761** | **0.791** | 0.698 | +0.02 |
| Disagreement across 5 samples at T = 0.7 | 0.729 | 0.768 | 0.663 | +0.03 |
| WM predicts "Nothing happens" | 0.734 | 0.736 | 0.696 | −0.02 |
| a_base not admissible | 0.639 | 0.642 | 0.615 | −0.01 |
| Low WM confidence (WorldEvolver) | **0.433** | 0.450 | 0.430 | +0.02 |

**Finding: planner uncertainty reliably finds "high-stakes states", where intervening changes the outcome (AUROC ≈ 0.75), but it cannot tell whether the change will help or hurt** (it predicts both U > 0 and U < 0, so correlation with U ≈ 0). WM confidence carries no information at all.
→ Gating splits into two sub-problems: **where (solved by uncertainty)** and **whether it helps (unsolved)**.

## 2. Sign sub-problem (`tables/sign_offline.json`; 64 states where the WM changed the action)
For a_fore, additionally predict its outcome, then compare the two predictions with "predicted failure avoided" / "goal subgoal hit" / both:
AUROC (U>0 vs U<0) = 0.52 / 0.40 / 0.43. **Simple outcome comparison cannot tell help from harm.** "Predicted failure avoided" shows a hint on SR (adopt −0.004 vs reject −0.076), but with n = 64 and AUROC 0.52 it is not a conclusion.

## 3. Online validation (460 held-out tasks × 2 reps; threshold = 30th percentile of action logprob on the step-0c states, `tables/gate_unc_calibration.json`)

| Arm | WM usage | SR | ΔSR vs none | PR | ΔPR vs none | ΔPR vs random_pre_nc_p0.3 | tokens/task |
|---|---:|---:|---|---:|---|---|---:|
| none | 0% | 11.7% | — | 32.8% | — | — | 40.0k |
| random_pre_nc_p0.3 | 30% | 13.5% | +1.7 | 33.4% | +0.6 | — | 56.3k |
| **gate_unc** | 35% | 14.1% | +2.4 [+1.1, +3.8] (Holm 0.004) | 35.6% | **+2.8 [+1.3, +4.3] (Holm 0.004)** | **+2.2 [+0.8, +3.6]** (p 0.003, Holm 0.096) | 61.9k |
| always | 100% | 14.6% | +2.8 | 35.7% | +2.9 | +2.3 | 95.0k |

**gate_unc gets the same PR as always (+2.8 vs +2.9) at 35% usage and 65% of the tokens**; at matched usage it beats the random gate by about +2.2 PR (significant before correction, borderline after Holm). SR shows no advantage (consistent with A: SR mainly comes from perturbation).

## 4. Implications for the innovation point
- A "where to intervene" gate is feasible: it saves about 1/3 of the cost without losing PR, and should be compared against "uncertainty" rather than "confidence" baselines.
- The real open problem is the **sign / gain predictor**: at high-stakes states, will foresight help or hurt? Neither simple outcome comparison nor confidence can do it. Candidate approaches: learn a value / critic, multi-candidate comparison (direction C), or estimate the gain with multiple foresight samples.
- The unseen test set (direction F) checks H1: PR(gate_unc) > PR(random_pre_nc_p0.3).

## Directory layout
```
raw/signals.jsonl            per-state signals (with 5 samples)
raw/sign_offline.jsonl       WM predictions for a_fore
raw/train/gate_unc_c*_rep*.jsonl
tables/offline_signal_screen.{md,json}, sign_offline.json, gate_unc_calibration.json
launch_gate_unc.sh, logs/
```
