# Phase 3: full-task 2x2 mechanism matrix (2026-10-19 – 21)

dev460 x 2 reps, protocol v2-list. Every intervention arm opens on the same random 30% of steps
(`gate_seed 2027`, identical to `random_pre_nc_p0.3`) and executes a_base when closed (NC). New arms:
R = `resample_pre` (same prompt, T=0.7, seeded), R0 = `resample0_pre` (same prompt and decoding, 4B only),
W14 = `random_pre --wm_role wm_alt` (Qwen3-14B WM, thinking off), oracle_r30 = `oracle_pre`.
Existing: none / always / oracle_every / W4 (4B: step0, step1, dirA_D; 14B: dirE). Pre-registration:
`tables/preregistration_p3.json`. Launch: `launch_p3.sh`. Analysis: `analyze_p3.py` -> `tables/p3_matrix.{md,json}`.
Runs were interrupted on 2026-10-19 19:01 by a full disk (TextWorld env leak, fixed in `agent.py`, see
`r4_common/README.md`) and resumed; 2 truncated rows were dropped and re-run.

## Arms
| planner | arm | SR | PR | tokens/task | changed actions/step |
|---|---|---:|---:|---:|---:|
| 4B | none | 11.7% | 32.8% | 40.0k | 0.000 |
| 4B | R | 14.5% | 33.0% | 51.2k | 0.095 |
| 4B | R0 | 13.5% | 33.0% | 51.5k | 0.032 |
| 4B | W4 | 13.5% | 33.4% | 56.3k | 0.116 |
| 4B | W14 | 14.0% | 34.5% | 56.4k | 0.115 |
| 4B | oracle_r30 | 16.8% | 36.0% | 51.1k | 0.133 |
| 4B | always (W4 every step) | 14.6% | 35.7% | 95.0k | 0.408 |
| 4B | oracle_every | 18.0% | 38.7% | 78.6k | 0.447 |
| 14B | none | 56.4% | 68.9% | 29.1k | 0.000 |
| 14B | R | 60.0% | 71.5% | 36.9k | 0.054 |
| 14B | W4 | 58.5% | 71.2% | 40.5k | 0.059 |
| 14B | W14 | 58.8% | 70.5% | 41.1k | 0.054 |
| 14B | oracle_r30 | 60.8% | 71.0% | 36.8k | 0.069 |
| 14B | always | 55.8% | 68.9% | 70.8k | 0.186 |
| 14B | oracle_every | 56.7% | 68.8% | 58.8k | 0.230 |

## Primary (Holm over 6, PR, paired task bootstrap)
| contrast | Δ pp [95% CI] | Holm p |
|---|---|---:|
| 4B: W4 - R | +0.4 [-1.2, +2.0] | 1.000 |
| 4B: W14 - R | +1.4 [-0.4, +3.2] | 0.594 |
| 4B: oracle_r30 - R | **+3.0 [+1.2, +4.8]** | **0.005** |
| 14B: W4 - R | -0.2 [-2.3, +1.9] | 1.000 |
| 14B: W14 - R | -1.0 [-3.0, +1.0] | 1.000 |
| 14B: oracle_r30 - R | -0.5 [-2.6, +1.6] | 1.000 |

## Exploratory highlights (uncorrected)
* No-information resampling carries the SR effect: 4B R - none SR +2.7 [+1.3, +4.2]; even R0 (re-query at
  T=0, serving nondeterminism only, 3% of steps change) gives SR +1.7 [+0.4, +3.0]. 14B R - none: SR +3.6,
  PR +2.6 [+0.6, +4.5] -- at least as large as any WM arm.
* A stronger WM does not add decision value: W14 - W4 = +1.1 PR [-0.6, +2.7] (4B), -0.7 [-2.5, +1.0] (14B),
  although the 14B WM predicts better (Phase 1: token F1 +8 pp [4, 12]).
* True information helps only the weak planner: oracle_r30 - R interaction (14B - 4B) = -3.5 PR [-6.4, -0.6].
* Episode vs state level: 4B oracle_r30 - R = +3.0 PR here, while a single oracle intervention is worth
  ~0 at the state level (Phase 2/4, g_O = -0.1 [-1.1, +0.9] over 501 states): the value of correct
  foresight is cumulative (repeated loop/precondition corrections), not a per-decision effect.

## Conclusion
At the episode level, too, a frozen LLM WM's single-step foresight is not distinguishable from a
no-information resample, for either planner and either WM size. Correct information (oracle) has value
only for the 4B planner and only cumulatively. Together with G1 (state level) this closes the router line.
