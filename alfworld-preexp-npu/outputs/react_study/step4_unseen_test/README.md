# Step 4: Unseen test set (AgentBoard ALFWorld 134)

Date: 2026-10-13. Split `eval_out_of_distribution` = AgentBoard's 134 ALFWorld test tasks (checked 134/134). **Touched for the first time in this step.**
The configuration was frozen before any test run: `tables/frozen_config.json`. Protocol v2, max 30 steps, temp 0 / top_p 0.5 / seed 42.

## Pre-registered arms (frozen)
| Arm | Runs | Notes |
|---|---:|---|
| none | 5 | Baseline |
| always | 5 | WM every step, no memory |
| **selective_em** | 5 **sequential** attempts | Closest to WorldEvolver: confidence gate τ = 1 − 4.6e-6 (30% usage on the dev pool) + online EM, bank starts empty and is **carried across attempts** |
| oracle | 3 | Upper bound with the true next observation |
| loop_hint | 3 | WM-free loop hint |
| gate_stuck | 3 | Best gate from Step 3 (chosen on dev by ΔPR) |

**Post-hoc controls** (added after seeing the results above, to separate the sources of selective_em's gain; **not part of the frozen comparison**): selective_nomem (τ = 0.99943 from Step 3) × 3, random_pre (p = 0.3, no memory) × 3.

## Results (`tables/summary_unseen134.md`; reference random_pre: `summary_unseen134_ref_random_pre.md`; `tables/best_of_k_unseen134.json`)

| Arm | Runs | SR (single run) | ΔSR vs none [95% CI] | PR | ΔPR vs none [95% CI] | WM usage | best-of-k | tokens in/task |
|---|---:|---:|---|---:|---|---:|---|---:|
| none | 5 | 26.1% | — | 41.4% | — | 0% | b@3 32.2 / **b@5 35.8** | 33.2k |
| always | 5 | 25.8% | −0.3 [−4.8, +4.0] | 42.3% | +0.9 [−2.4, +4.2] | 100% | b@3 32.3 / **b@5 35.1** | 80.3k |
| **selective_em** | 5 | **30.0%** | **+3.9 [+0.3, +7.6]** | 45.4% | **+4.0 [+1.6, +6.8]** | 29% | b@3 37.3 / **b@5 39.6** | 84.0k |
| oracle | 3 | 30.8% | +4.7 [−0.1, +9.5] | 46.6% | +5.2 [+2.0, +8.7] | 100% | b@3 42.5 | 64.7k |
| loop_hint | 3 | 29.6% | +3.5 [+0.3, +6.9] | 44.0% | +2.6 [−0.1, +5.6] | 0% | b@3 37.3 | 54.2k |
| gate_stuck | 3 | 29.1% | +3.0 [−0.2, +6.4] | 44.2% | +2.9 [+0.5, +5.5] | 56% | b@3 37.3 | 74.1k |
| *selective_nomem (post-hoc)* | 3 | 28.4% | +2.2 [−1.9, +6.4] | 44.8% | +3.5 [+0.4, +6.7] | 37% | b@3 37.3 | 77.7k |
| *random_pre (post-hoc)* | 3 | 29.4% | +3.2 [−0.8, +7.4] | 44.2% | +2.9 [−0.0, +5.9] | 29% | b@3 37.3 | 68.7k |

Paired against random_pre: selective_em +0.6 [−2.7, +4.2]; selective_nomem −1.0; gate_stuck −0.2; loop_hint +0.2; oracle +1.5 [−3.2, +6.0]; **always −3.5 [−7.4, +0.1]**.
selective_em by attempt: 30.6 / 29.1 / 29.9 / 29.1 / 31.3% (usage 28–31%). Memory raises WM EM from 40.4% to 64–66% (F1 0.65 → 0.81–0.83).

## Comparison with WorldEvolver (Gemma-4-26B, best-of-5, 134 tasks)
| | none | always | selective (full system) | selective − none |
|---|---:|---:|---:|---:|
| WorldEvolver | 23.88% | 24.63% | 26.12% | +2.24 |
| Ours (Qwen3-4B, b@5) | 35.8% | 35.1% | 39.6% (selective_em) | +3.8 |

The direction matches the paper: selective > always ≈ none. But see the conclusions below: **on our data that gain is not explained by confidence or by memory.** (Absolute numbers are not comparable: different model, prompt details, environment version.)

## Conclusions
1. **The WorldEvolver phenomenon reproduces on the test set**: selective + memory is significantly better than none (+3.9 pp SR, +4.0 pp PR; b@5 +3.8), while always is not.
2. **But the post-hoc controls show the gain comes from intervening on only some steps, not from how steps are chosen**: random_pre (random 30%, no memory) reaches 29.4% and is statistically indistinguishable from selective_em (+0.6 [−2.7, +4.2]); confidence without memory, the stuck rule and even the WM-free loop hint all land around 29–30%. The confidence signal and Episodic Memory **add no detectable value** here (consistent with Step 0c: confidence is unrelated to utility; Step 2: memory improves accuracy but not utility).
3. **WM at every step offsets the gain**: always vs random_pre −3.5 [−7.4, +0.1] (on the dev pool's 460 held-out tasks this difference was +0.1, so this effect is not stable across task sets).
4. The upper bound (oracle) is still about +5 pp SR/PR on the test set, consistent with dev.
5. Multiple-comparison caveat: 134 tasks × 3–5 runs; many arm differences are 1–3 pp with CIs around ±4 pp. Only "intervening at some steps > none" and "oracle PR > none" are stable conclusions.

## Directory layout
```
raw/unseen134_games.txt, unseen134_chunk{0..3}
raw/eval_out_of_distribution/unseen_{none,always,loop_hint,gate_stuck}__rep*.jsonl
raw/eval_out_of_distribution/unseen_o{0..3}_oracle__rep*.jsonl
raw/eval_out_of_distribution/unseen_selective__rep{0..4}.jsonl (+ .memory.jsonl)   = selective_em attempts 1..5
raw/eval_out_of_distribution/posthoc_*                                             post-hoc controls
raw/compare/   relabeled / symlinks for analysis
tables/frozen_config.json, summary_unseen134*.{md,json}, best_of_k_unseen134.json, per_task_*.csv
figures/sr_vs_tokens_unseen134.png, best_of_k_unseen134.png
launch_step4.sh, launch_selective_em.sh, launch_posthoc.sh, logs/
```
