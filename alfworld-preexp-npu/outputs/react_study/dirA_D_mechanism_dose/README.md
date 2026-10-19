# Directions A + D: where does the gain from "selective intervention" come from + dose-response

Date: 2026-10-13/14. Protocol v2 (list). Evaluation set: the 460 held-out dev-pool tasks (`step3_gating/raw/eval460_games.txt`), 2 repeats per arm.
Summary table and statistics: `../dirF_final_eval/tables/round3_dev460.md` (one analysis across all round-3 arms, **Holm-corrected over 44 comparisons**).

## The confound that triggered this
In steps 3/4, the gated arms (random_pre / selective / gate_*) made one more planner call with **an identical prompt** whenever the gate was closed. At temperature 0, that call changes the action **about 12%** of the time (vLLM non-determinism), i.e. it randomly perturbs about **8% of all steps**. So "selective intervention" = information on ~30% of steps + random perturbation on ~8% of steps.

## Arms
| Arm | WM | Content |
|---|---|---|
| none_resample | no | Every step, call the planner again with the identical prompt and take its action (perturbation only, no information) |
| explore_stuck | no | When stuck (same rule as gate_stuck), resample once at temperature 0.7 (explicit exploration) |
| random_pre_nc_p{0.1,0.3,0.5,0.7} | yes | Random pre-call gate, **with no second call when closed** (information only, no perturbation); p = usage |
| Reference | | none / always (step 0), random_pre_cc_p0.3 (step 3, with the closed-gate second call) |

## Results (460 tasks × 2 reps; Δ vs none [95% CI], Holm p in parentheses)

| Arm | Steps with changed action | SR | ΔSR | PR | ΔPR | tokens/task |
|---|---:|---:|---|---:|---|---:|
| none | 0% | 11.7% | — | 32.8% | — | 40.0k |
| none_resample | 10.8% | 14.0% | **+2.3 [+1.1, +3.6] (0.011)** | 33.4% | +0.5 [−0.8, +1.9] (1.0) | 79.1k |
| explore_stuck | 19.4% | 15.2% | **+3.5 [+1.8, +5.2] (0.002)** | 34.7% | +1.8 [+0.3, +3.4] (0.48) | 64.6k |
| random_pre_nc_p0.1 | 4.0% | 14.3% | +2.6 [+1.2, +4.1] (0.011) | 33.8% | +1.0 [−0.5, +2.5] (1.0) | 45.2k |
| random_pre_nc_p0.3 | 11.6% | 13.5% | +1.7 [+0.2, +3.3] (0.77) | 33.4% | +0.6 [−1.0, +2.1] (1.0) | 56.3k |
| random_pre_nc_p0.5 | 20.0% | 14.7% | +2.9 [+1.2, +4.7] (0.029) | 34.7% | +1.9 [+0.2, +3.7] (0.74) | 67.1k |
| random_pre_nc_p0.7 | 27.9% | 13.4% | +1.6 [−0.3, +3.6] (1.0) | 35.5% | +2.7 [+0.9, +4.5] (0.088) | 78.8k |
| always (p = 1) | 40.8% | 14.6% | +2.8 [+0.7, +5.0] (0.35) | 35.7% | **+2.9 [+1.0, +4.8]** (0.095) | 95.0k |
| random_pre_cc_p0.3 | 20.0% | 14.5% | +2.7 [+0.9, +4.6] (0.11) | 35.0% | +2.2 [+0.5, +4.0] (0.35) | 84.1k |

Dose-response figure: `../dirF_final_eval/figures/dose_response_dev460.png` (paired Δ vs none).

## Conclusions
1. **SR and PR gains come from different sources.**
   - **SR (task completion)**: perturbation with no information already gets +2.3 to +3.5 (none_resample, explore_stuck, both Holm-significant), about the same as the WM arms (+1.6 to +2.9). → The SR gain is **mostly explained by escaping loops / perturbation**.
   - **PR (subgoal progress)**: pure perturbation gives only +0.5 (n.s.); with WM information, PR rises with usage: p 0.1 → 1.0 gives ΔPR +1.0 → +0.6 → +1.9 → +2.7 → +2.9. → The PR gain **needs the WM's information**, and the more information the more PR.
2. **Dose-response**: SR is flat across usage (no "less is more"). PR rises roughly monotonically with usage. The "always is worse than random" seen in step 4 (unseen) does not reproduce on these 460 tasks and should be treated as noise.
3. Explicit exploration (explore_stuck) is the cheapest SR improvement: +3.5 pp at 64.6k tokens with no WM.
4. Implication for gate research: if the target is SR, a gate has to beat "pure perturbation", not just "no intervention". If the target is PR, the gate's value is getting most of always's PR gain at low usage (see direction B).

## Directory layout
```
raw/train/{none_resample,explore_stuck,random_pre_nc_p0.1,_p0.3,_p0.5,_p0.7}_c{0,1,2}__rep{0,1}.jsonl
launch_batch1.sh (also launches direction C's fore_topk / fore_surprise), logs/
```
