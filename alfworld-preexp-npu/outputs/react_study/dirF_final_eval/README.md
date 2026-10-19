# Direction F: evaluation method + pre-registered final test

Date: 2026-10-14. Code: `analyze_round3.py` (dev-set summary + Holm + dose-response figure), `dirF_test.py` (pre-registered test).

## Evaluation rules (fixed for this round)
1. **Main battleground for method comparison = the 460 held-out dev-pool tasks** (not used for gate training / calibration / branch sampling), 2 repeats per arm, all arms paired on the same tasks.
2. **Primary metric = PR** (much more sensitive than SR; in step 0 the PR noise floor was about half of SR's). SR is reported alongside.
3. **Multiple comparisons**: across all round-3 dev comparisons (44), Holm correction on paired-bootstrap p-values (20k task resamples).
4. **The test set (unseen 134) is used once at the end**, and hypotheses / arms / thresholds are frozen beforehand (`tables/preregistration.json`); everything else counts as exploratory.

## Dev-set summary (`tables/round3_dev460.md`, figure `figures/dose_response_dev460.png`)
See the READMEs for directions A+D / B / C. Key points:
- SR: pure perturbation already gets +2.3 to +3.5; PR: needs WM information and rises with usage.
- gate_unc: PR +2.8 (Holm 0.004) at 35% usage / 65% of always's cost; vs the random gate PR +2.2 (Holm 0.096).
- fore_topk (same steps as the random gate): PR +2.7 vs random (Holm 0.099).

## Pre-registered final test (unseen 134, 5 repeats; `tables/unseen_final.md`)

| Hypothesis | Contrast | Metric | Δ [95% CI] | p | p_holm | Dev-set Δ |
|---|---|---|---|---:|---:|---|
| H1 (B) | gate_unc − random_pre_nc_p0.3 | PR | +1.3 [−0.7, +3.4] | 0.204 | 0.611 | +2.2 |
| H2 (C) | fore_topk_p0.3 − random_pre_nc_p0.3 | PR | +0.1 [−1.9, +2.0] | 0.942 | 1.000 | +2.7 |
| H3 (A) | explore_stuck − none | SR | +0.9 [−2.1, +3.7] | 0.564 | 1.000 | +3.5 |

**None of the three pre-registered hypotheses holds on the test set.** H1 points the same way as dev but is not significant; H2 / H3 do not reproduce.

Exploratory (unseen, vs none, uncorrected), sorted by PR:

| Arm | Reps | SR | ΔSR | PR | ΔPR [CI] | tokens/task |
|---|---:|---:|---|---:|---|---:|
| none | 5 | 26.1% | — | 41.4% | — | 34.6k |
| oracle | 3 | 30.8% | +4.7 | 46.6% | +5.2 [+2.0, +8.8] | 67.4k |
| **gate_unc** | 5 | 29.1% | +3.0 | 45.4% | **+4.1 [+1.6, +6.7]** | **55.7k** |
| selective_em (step 4) | 5 | 30.0% | +3.9 | 45.4% | +4.0 [+1.6, +6.8] | 87.4k |
| selective_nomem | 3 | 28.4% | +2.2 | 44.8% | +3.5 | 81.2k |
| random_pre_cc_p0.3 | 3 | 29.4% | +3.2 | 44.2% | +2.9 | 71.7k |
| gate_stuck | 3 | 29.1% | +3.0 | 44.2% | +2.9 | 77.3k |
| fore_topk_p0.3 | 5 | 27.6% | +1.5 | 44.2% | +2.8 | 71.7k |
| random_pre_nc_p0.3 | 5 | 29.0% | +2.8 | 44.1% | +2.7 | 48.1k |
| loop_hint | 3 | 29.6% | +3.5 | 44.0% | +2.6 | 56.5k |
| always | 5 | 25.8% | −0.3 | 42.3% | +0.9 | 83.9k |
| explore_stuck | 5 | 27.0% | +0.9 | 42.3% | +0.9 | 56.4k |

## Conclusions
1. **What holds on both sets**: intervening on some steps with the WM > none; the oracle PR gain; **gate_unc is in the top tier on PR on both dev and test, and is the cheapest** (on test it matches selective_em's PR at 64% of its tokens).
2. **What does not reproduce**: candidate comparison (C) and explore-when-stuck (A) are significant on dev but give ≈ 0 on test; and the random gate (no closed-gate call) gives only +0.6 PR on dev but +2.7 on test. **Task-set heterogeneity has a large effect**, so 1–3 pp differences on 134 tasks cannot support claims about method ranking.
3. For writing up the gate innovation: the claim that holds is "an uncertainty gate gets the same progress gain as always / selective+EM at the lowest cost" (a cost-efficiency claim). A claim of "higher success rate than a random gate" cannot be supported with the current sample size.

## Directory layout
```
raw/eval_out_of_distribution/unseen_{gate_unc,fore_topk,explore_stuck,random_pre_nc}_*__rep{0-4}.jsonl
tables/preregistration.json, unseen_final.{md,json}, round3_dev460.{md,json}
figures/dose_response_dev460.png
launch_unseen.sh, logs/
```
