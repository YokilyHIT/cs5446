# Round 5 stage B: frozen evaluation of failure-triggered WM repair

Pre-registration (frozen before any run on these data): `tables/preregistration_round5_final.json`
(method, prompts, decoding, code sha256, test-set hash). Frozen method = `inv_wmrepair` with the Qwen3-14B WM
(thinking off), pre-execution gate (planner action not in the admissible list). Analysis: `analyze_final.py`.
Launch: `launch_fresh600.sh` (fresh_test600: 600 never-run train-split tasks, 2 chunks x 3 reps),
`launch_unseen134.sh` (eval_out_of_distribution x 5 reps, repeated evaluation).
vLLM servers had exited between the fresh600 and unseen134 runs (session teardown); fresh600 had already
finished (27000/27000 rows) and servers were restarted with the same script before unseen134.

## fresh_test600 x 3 reps (`tables/final_fresh600.md`)
| arm | 4B SR | 4B PR | 14B SR | 14B PR | 4B tokens |
|---|---:|---:|---:|---:|---:|
| none | 20.9 | 39.4 | 59.1 | 70.3 | 37.6k |
| inv_fail | 28.3 | 44.8 | 63.9 | 72.8 | 46.9k |
| inv_reflect | 28.6 | 45.9 | 64.9 | 73.5 | 47.5k |
| inv_sreflect | 23.7 | 42.8 | 65.4 | 74.0 | 50.1k |
| inv_rules (rule cards) | 33.3 | 46.8 | **68.8** | **76.0** | 44.4k |
| wmrepair, 4B WM | 29.7 | 46.6 | - | - | 53.0k |
| **wmrepair, 14B WM (frozen)** | **36.2** | **49.0** | 65.9 | 74.3 | 47.8k |
| inv_repair (oracle) | 36.7 | 47.5 | 69.5 | 76.6 | 42.5k |

Pre-registered primary (4B):
* H1 PR(frozen) - PR(inv_fail) = +4.2 [+2.6, +5.7], Holm p < 0.001 -> supported
* H3 SR(frozen) - SR(none) = +15.3 [+12.7, +17.8], Holm p < 0.001 -> supported
* H2 non-inferiority vs rule cards: PR +2.2 [+0.5, +3.9] -> non-inferior (lower bound > -2 pp); the
  two-sided difference is also positive (SR +2.9 [+0.4, +5.4], exploratory)

Secondary (uncorrected): 4B frozen vs reflect +3.0 PR / +7.6 SR, vs sreflect +6.2 / +12.6; frozen reaches the
oracle repair (SR +0.4 [-1.8, +2.7] behind oracle; PR +1.5 above). 4B WM repair (self-diagnosis) is weaker on
this set than on dev (-6.6 SR vs 14B WM). 14B planner: frozen - none +6.8 SR / +4.0 PR, frozen - fail +2.0 SR /
+1.5 PR, but rule cards beat it (-2.9 SR [-5.1, -0.8], -1.7 PR) and the oracle stays +3.6 SR ahead.

## Reading
* For the weak (4B) planner the frozen method replicates on never-run tasks: +15 SR over none, +8 SR over a
  failure notice, at the level of the oracle diagnosis and above hand-written rule cards.
* For the strong (14B) planner explicit rule cards are better than the WM's diagnosis; the WM's implicit
  knowledge adds less than the planner already has, while precise rules still help.
* Dev-to-test shifts: absolute rates are higher on fresh600 (none 20.9% vs 11.7% on dev460) -- different task
  instances; all claims are paired within a set.

## unseen134 x 5 reps (repeated evaluation, secondary; `tables/final_unseen134.md`)
| arm | 4B SR | 4B PR | 14B SR | 14B PR |
|---|---:|---:|---:|---:|
| none | 25.4 | 41.0 | 67.6 | 76.3 |
| inv_fail | 34.2 | 46.7 | 74.0 | 81.2 |
| inv_reflect | 31.3 | 46.8 | 74.8 | 82.3 |
| inv_sreflect | 29.3 | 44.8 | 73.7 | 80.9 |
| inv_rules | 34.9 | 47.6 | 75.1 | 82.8 |
| wmrepair, 4B WM | 32.4 | 46.3 | - | - |
| **wmrepair, 14B WM (frozen)** | **38.5** | **48.8** | 75.5 | 81.2 |
| inv_repair (oracle) | 38.4 | 48.3 | 79.0 | 83.6 |

4B (uncorrected): frozen - none +13.1 SR [+8.7, +17.8] / +7.8 PR; - fail +4.3 SR [+0.7, +8.2] / +2.1 PR
[-0.4, +4.6]; - rules +3.6 SR [+0.4, +6.9] / +1.1 PR (n.s.); = oracle (-0.1 SR). 4B WM self-diagnosis again
below the 14B WM (-6.1 SR). 14B: frozen - none +7.9 SR, but frozen ~ fail (+1.5 SR, 0.0 PR) and ~ rules.
Direction matches fresh600; with 134 tasks the PR contrasts against fail / rules are not significant.
