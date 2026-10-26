# ReAct world-model study: outputs index

Code: `preexperiments/react_study/`. Each subdirectory has its own README (design / results / conclusions / layout).

## Round 1 (2026-10-12, protocol v1, 140 valid_seen tasks)
| Directory | One-line conclusion |
|---|---|
| [stage1_protocol_logging/](stage1_protocol_logging/README.md) | Original logs recovered; old +1.4 pp not significant; temperature 0 is not deterministic |
| [stage2_baselines/](stage2_baselines/README.md) | Always +3.6 pp, not significant; confidence gate ≈ random; A/A gap is about 2.6 pp |
| [stage3_paired_branching/](stage3_paired_branching/README.md) | Single-rollout utility is drowned by noise; foresight mainly breaks loops |

## Round 2 (2026-10-13, protocol v2, 600-task dev pool + 134 unseen)
| Directory | One-line conclusion |
|---|---|
| [step0_protocol_v2_measurement/](step0_protocol_v2_measurement/README.md) | Protocol v2 (AgentBoard examples + list) raises SR from 16.7% to 26.5%; Progress Rate verified against 134 labels; 600 tasks detect about 3 pp; K = 8 branching: mean single-step utility ≈ 0 but states differ by 4–10× the noise; confidence is unrelated to utility; found and fixed an outcome-selection bias |
| [step1_upper_bound_controls/](step1_upper_bound_controls/README.md) | Perfect-prediction ceiling +3.2 pp SR (significant but modest); real WM +0.6; WM-free loop hint ≈ always's PR gain; rethink is harmful |
| [step2_episodic_memory/](step2_episodic_memory/README.md) | Online EM raises WM EM from 38% to 60–62%, but SR/PR do not improve: accuracy is not the bottleneck |
| [step3_gating/](step3_gating/README.md) | On 460 held-out tasks, no gate (confidence / stuck rule / learned) significantly beats random at similar usage |
| [step4_unseen_test/](step4_unseen_test/README.md) | Test set: selective + EM +3.9 pp (b@5 39.6 vs 35.8), but post-hoc controls show random 30% gating does just as well; the gain comes from "intervening on some steps", not from confidence or memory |

## Main conclusion of round 2
1. **The WorldEvolver-style "selective > always ≈ none" reproduces on the test set**, but in our setting **the selection criterion does not matter**: random selection, confidence, a stuck rule, and even a WM-free hint all give about +3 pp.
2. **WM accuracy is not the bottleneck**: memory raises accuracy by 23 pp with no utility gain; even perfect prediction gives only +3 to +5 pp.
3. **Single-step utility does vary across states (selection room exists)**, but none of the agent-visible features or WM confidence we tried can predict it (learned gate CV ρ = 0.11).
4. Directions worth pursuing: why does sparse intervention beat dense intervention (the number of actions changed / context disturbance?), and the planner's interface for using foresight (the ceiling for 4B + perfect information is low).

Environment: 8 × 910B3, vLLM instances on ports 8001–8008 (`PREEXP_API_BASES`); `preexp_env/env.sh` sets `TMPDIR` to the data disk (avoids the container quota).
Third-party: AgentBoard code/data in `5446/third_party_dl/` (the prompt and test labels are copied into `preexperiments/react_study/assets/`).

## Round 3 (2026-10-13 – 14, directions A–F; protocol v2, 460 held-out dev tasks × 2 + unseen 134 pre-registered)
| Directory | One-line conclusion |
|---|---|
| [dirA_D_mechanism_dose/](dirA_D_mechanism_dose/README.md) | The closed-gate identical second call randomly changes the action 12% of the time (a confound). The SR gain is mostly explained by perturbation (pure perturbation +2.3, explore-when-stuck +3.5); the PR gain needs WM information and rises with usage |
| [dirB_planner_uncertainty/](dirB_planner_uncertainty/README.md) | Planner uncertainty finds where intervention changes the outcome (AUROC ≈ 0.75) but cannot judge whether it helps; WM confidence carries no information (0.43). gate_unc matches always's PR at 65% of the cost |
| [dirC_interface/](dirC_interface/README.md) | On dev, candidate comparison is +2.7 PR over single prediction on the same steps, but it does not reproduce on unseen; showing only predicted failures gives SR +3.5 on dev; B+C are not additive |
| [dirE_larger_planner/](dirE_larger_planner/README.md) | 14B planner +44.7 pp SR; with 14B even oracle is only +0.3 (gain shrinks by 6 pp vs 4B): single-step foresight only has value for a weak planner |
| [dirF_final_eval/](dirF_final_eval/README.md) | Evaluation rules (460 dev as main battleground, PR primary, Holm, pre-registration). On unseen none of H1–H3 holds; gate_unc ΔPR +4.1 vs none is the highest at the lowest cost |

### Main conclusions of round 3
1. **Planner capability is the dominant factor** (4B → 14B: +45 pp), and a strong planner barely benefits from single-step foresight (oracle +0.3).
2. With a weak planner, the "selective intervention" SR gain mostly comes from perturbation / escaping loops; only the PR gain needs WM information.
3. Gating can be split into "where" (planner uncertainty works, AUROC ≈ 0.75) and "whether it helps" (unsolved; confidence, outcome comparison and existing features all fail). gate_unc's cost advantage holds on both sets, but its advantage over a random gate does not pass the pre-registered test.
4. 134 test tasks can only resolve differences of about 4 pp or more; dev results for C / A did not reproduce on unseen, and task-set heterogeneity is large.

## Round 4 (2026-10-19 – 21, full research plan; `/home/ma-user/work/5446/react_study_full_research_plan_20261019.md`)
| Directory | One-line conclusion |
|---|---|
| [r4_common/](r4_common/README.md) | Serving (4B NPU 0-3, 14B NPU 4-7), frozen data split (fresh_test600, label_pool, branch140), power plan; TextWorld env/disk leak fixed in `agent.py` |
| [p1_wm_capability/](p1_wm_capability/tables/wm_capability.json) | Same state-action pairs: 14B WM token F1 +8 pp [4, 12] over 4B WM, effect/progress judgement not significantly better |
| [p2_branch_labels/](p2_branch_labels/tables/p2_p2_4b.md) | Same-state 0/R/W labels (4B, 14B same states, 14B own states): g_I ~ 0 for every planner/WM, oracle included |
| [p3_mechanism_matrix/](p3_mechanism_matrix/README.md) | Episode level, random 30%: W4/W14 - R n.s. for both planners; only 4B oracle - R +3.0 PR (Holm .005) |
| [p4_router/](p4_router/README.md) | 374 new states: sign predictability did not replicate (AUROC 0.42); G1 failed, router line stopped |
| [failure_analysis/](failure_analysis/tables/failure_analysis.md) | 4B: 31% inadmissible actions, 74% of failures end in loops, success after pick 0.27 (14B 0.77) |
| [probe_feasibility/](probe_feasibility/README.md) | Failure-triggered repair: oracle diagnosis+repair 4B SR 11.7 -> 29.1; frozen-WM repair 23.9 / 26.5 (no rules) |

## Round 5 (2026-10-21 – 23; `/home/ma-user/work/5446/react_study_round5_plan_20261021.md`)
| Directory | One-line conclusion |
|---|---|
| [probe_feasibility/](probe_feasibility/README.md) (stage A) | Same WM and gate: repair interface +7 PR over next-observation prediction; not "reflect again"; separate diagnosis call beats in-context structured reflection; rule cards ~ WM repair on 4B, better on 14B. Freeze rule -> WM repair with 14B WM |
| [p7_final/](p7_final/README.md) (stage B) | Frozen, never-run fresh_test600 x 3: 4B SR 20.9 -> 36.2 (H1 +4.2 PR vs failure notice, H3 +15.3 SR vs none, H2 non-inferior to rule cards; all supported), = oracle repair. 14B: +6.8 SR vs none but rule cards better. unseen134 x 5 agrees in direction |
