# D0 portable snapshot: descriptive metrics

Status: `metrics_only_development_description`. This is not the complete D0 report.

Snapshot: 24 games, 71 originally selected states.

Original weights are retained. A primary mean stays missing when its target has missing values; the available-case column describes only the observed intersection.

| Pool / metric | Primary mean | Available-case mean | Target / observed states | Observed original weight mass |
|---|---:|---:|---:|---:|
| all_planned / Y_D | — | 0.13138686131386862 | 71 / 68 | 0.9513888888888888 |
| all_planned / Y_N | — | 0.11678832116788321 | 71 / 68 | 0.9513888888888888 |
| all_planned / Y_P | — | 0.11678832116788321 | 71 / 68 | 0.9513888888888888 |
| all_planned / U_admission | — | -0.014598540145985401 | 71 / 68 | 0.9513888888888888 |
| all_planned / U_info | — | 0.0 | 71 / 68 | 0.9513888888888888 |
| all_planned / U_revision | — | -0.014598540145985401 | 71 / 68 | 0.9513888888888888 |
| all_planned / EM | — | 0.4087591240875912 | 71 / 68 | 0.9513888888888888 |
| all_planned / token_F1 | — | 0.7055986218423713 | 71 / 68 | 0.9513888888888888 |
| core_A / Y_D | 0.13138686131386862 | 0.13138686131386862 | 68 / 68 | 0.9513888888888888 |
| core_A / Y_N | 0.11678832116788321 | 0.11678832116788321 | 68 / 68 | 0.9513888888888888 |
| core_A / Y_P | 0.11678832116788321 | 0.11678832116788321 | 68 / 68 | 0.9513888888888888 |
| core_A / U_admission | -0.014598540145985401 | -0.014598540145985401 | 68 / 68 | 0.9513888888888888 |
| core_A / U_info | 0.0 | 0.0 | 68 / 68 | 0.9513888888888888 |
| core_A / U_revision | -0.014598540145985401 | -0.014598540145985401 | 68 / 68 | 0.9513888888888888 |
| core_A / EM | 0.4087591240875912 | 0.4087591240875912 | 68 / 68 | 0.9513888888888888 |
| core_A / token_F1 | 0.7055986218423713 | 0.7055986218423713 | 68 / 68 | 0.9513888888888888 |

## Fixed development cases

- `observed_admission_positive`: eligible 0; selected —; unavailable reason category_absent.
- `observed_admission_negative`: eligible 1; selected ['pick_clean_then_place_in_recep-DishSponge-None-CounterTop-427/trial_T20190909_010951_843989', '15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:16']; unavailable reason —.
- `EM1_and_same_PD_action_or_observed_admission_zero`: eligible 28; selected ['pick_heat_then_place_in_recep-Cup-None-Fridge-23/trial_T20190908_045659_449231', '40945f3e9214f2d475b3c80f62f107c7c8c9498b088581ed004454ba4abbd726:19']; unavailable reason —.
- `policy_failure_or_insufficient_evidence`: eligible 18; selected ['pick_two_obj_and_place-Pencil-None-CoffeeTable-229/trial_T20190910_231706_006365', 'e9f431271ce0c84584a2f289359ba0b8a26da49726ec93ee6fb59de0d832ca57:1']; unavailable reason —.

## Cross-job labels

These are exported labels; this command does not re-audit job/service identities or calculate the exclusion sensitivity.

| Label | States | Games | Original weight mass |
|---|---:|---:|---:|
| false | 70 | 24 | 0.986111111111111 |
| true | 1 | 1 | 0.013888888888888888 |
| unknown | 0 | 0 | 0.0 |
| not_applicable | 0 | 0 | 0.0 |

## Scope and remaining work

- This analyzes the portable snapshot; it does not regenerate the snapshot from the entire accepted evidence chain.
- D0 development description only, not a complete D0 report or D1/E inference.
- Y differences are single observations, not measured true conditional utility differences.
- Missing observations remain missing; original 1/(J*k_j) weights and exact score ties are unchanged.
- Confidence is a ranking score, not calibrated probability; EM/token-F1 are text-match proxies.
- Game deletion ranges are sensitivity descriptions, not confidence intervals.
- No confidence interval, p-value, certified C bound or automatically selected D1 size is produced.
- Cross-job exclusion sensitivity, full physical-path diagnostics, per-call costs and N/P candidates remain separate work.

The JSON contains the full metric intersections, fixed cases and game deletion sensitivity. Costs are explicitly not computed here; consult the separate accounting snapshot.
