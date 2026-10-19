# Stage 3 paired-branch summary

Points: 200 sampled, 200 replayed exactly. a_base reproduced the logged action at 171/200; B0 and its exact repeat B0r produced identical trajectories at 58/200.

## Q1 utility distribution

| quantity | n | +1 | 0 | −1 | mean [95% task-cluster CI] | sign-test p |
|---|---:|---:|---:|---:|---|---:|
| U_W (foresight) | 200 | 2 (1.0%) | 98.5% | 1 (0.5%) | +0.005 [-0.010, +0.023] | 1.000 |
| U_R (rethink) | 200 | 2 (1.0%) | 97.5% | 3 (1.5%) | -0.005 [-0.028, +0.016] | 1.000 |
| U_noise (B0r − B0) | 200 | 7 (3.5%) | 95.5% | 2 (1.0%) | +0.025 [+0.005, +0.048] | — |

Visit-distribution-weighted U_W: +1 1.1%, −1 0.7%, mean +0.004.
Action changed by foresight at 30.0% of points; by rethink at 41.5%.
Given a change: U_W +1 3.3%, −1 1.7% (n=60); U_R +1 2.4%, −1 3.6% (n=83).
Changed foresight action admissible: 95.0%; changed rethink action admissible: 94.0%.
Non-zero rate: U_W 1.5%, U_R 2.5%, U_noise 4.5%.
Base branch success rate Y0: 5.5%.

## Q2 confidence vs accuracy vs utility

Prediction EM 48.5%, token-F1 0.742 (vs real next observation).

| signal → target | AUROC |
|---|---:|
| conf_for_EM | 0.900 |
| conf_for_changed | 0.661 |
| conf_for_U_nonzero | 0.668 |
| conf_for_U_pos | 0.503 |
| conf_for_U_neg | 0.995 |
| f1_for_U_pos | 0.753 |
| f1_for_U_neg | 0.751 |

Spearman(confidence, F1) = 0.645. Mean U_W when EM=1: 0.010309278350515464, EM=0: +0.000.

## Q3 by feature (see stage3_by_feature.csv for all)

| feature | value | n | changed | P(U_W=+1) | P(U_W=−1) | mean U_W | mean U_R | P(U_noise≠0) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| stratum | normal | 120 | 20.0% | 0.8% | 0.0% | +0.008 | +0.000 | 5.8% |
| stratum | stuck | 80 | 45.0% | 1.2% | 1.2% | +0.000 | -0.013 | 2.5% |
| phase | early | 108 | 17.6% | 0.9% | 0.0% | +0.009 | +0.000 | 5.6% |
| phase | late | 31 | 29.0% | 0.0% | 0.0% | +0.000 | +0.000 | 0.0% |
| phase | mid | 61 | 52.5% | 1.6% | 1.6% | +0.000 | -0.016 | 4.9% |
| action_type | close | 1 | 0.0% | 0.0% | 0.0% | +0.000 | +0.000 | 0.0% |
| action_type | cool | 1 | 0.0% | 0.0% | 0.0% | +0.000 | +0.000 | 0.0% |
| action_type | examine | 37 | 45.9% | 0.0% | 2.7% | -0.027 | -0.027 | 0.0% |
| action_type | go_to | 65 | 23.1% | 0.0% | 0.0% | +0.000 | -0.031 | 12.3% |
| action_type | inventory | 13 | 46.2% | 0.0% | 0.0% | +0.000 | +0.000 | 0.0% |
| action_type | look | 54 | 33.3% | 1.9% | 0.0% | +0.019 | +0.000 | 0.0% |
| action_type | open | 16 | 0.0% | 0.0% | 0.0% | +0.000 | +0.062 | 0.0% |
| action_type | other | 4 | 25.0% | 0.0% | 0.0% | +0.000 | +0.000 | 0.0% |
| action_type | take | 8 | 37.5% | 12.5% | 0.0% | +0.125 | +0.125 | 12.5% |
| action_type | use | 1 | 0.0% | 0.0% | 0.0% | +0.000 | +0.000 | 0.0% |
| task_type | look_at_obj_in_light | 34 | 26.5% | 0.0% | 2.9% | -0.029 | -0.029 | 0.0% |
| task_type | pick_and_place_simple | 34 | 41.2% | 2.9% | 0.0% | +0.029 | -0.059 | 14.7% |
| task_type | pick_clean_then_place_in_recep | 33 | 27.3% | 0.0% | 0.0% | +0.000 | +0.030 | 0.0% |
| task_type | pick_cool_then_place_in_recep | 33 | 36.4% | 3.0% | 0.0% | +0.030 | +0.030 | 6.1% |
| task_type | pick_heat_then_place_in_recep | 33 | 36.4% | 0.0% | 0.0% | +0.000 | +0.000 | 3.0% |
| task_type | pick_two_obj_and_place | 33 | 12.1% | 0.0% | 0.0% | +0.000 | +0.000 | 3.0% |
| repeated | no | 94 | 12.8% | 1.1% | 0.0% | +0.011 | +0.000 | 5.3% |
| repeated | yes | 106 | 45.3% | 0.9% | 0.9% | +0.000 | -0.009 | 3.8% |
| no_progress | no | 191 | 29.3% | 1.0% | 0.5% | +0.005 | -0.005 | 4.7% |
| no_progress | yes | 9 | 44.4% | 0.0% | 0.0% | +0.000 | +0.000 | 0.0% |
| orig_episode_success | False | 183 | 30.6% | 0.0% | 0.5% | -0.005 | -0.005 | 3.3% |
| orig_episode_success | True | 17 | 23.5% | 11.8% | 0.0% | +0.118 | +0.000 | 17.6% |
| conf_high(>0.9997) | no | 146 | 26.0% | 1.4% | 0.0% | +0.014 | +0.007 | 4.8% |
| conf_high(>0.9997) | yes | 54 | 40.7% | 0.0% | 1.9% | -0.019 | -0.037 | 3.7% |
| pred_em | 0 | 103 | 15.5% | 0.0% | 0.0% | +0.000 | +0.000 | 5.8% |
| pred_em | 1 | 97 | 45.4% | 2.1% | 1.0% | +0.010 | -0.010 | 3.1% |

## Q4/Q5 utility–coverage (per-decision gain = ΣU over selected / N)

Always: +0.0050. Ex-post oracle: +0.0100 at usage 1.0%. Rethink-always: -0.0050.

| selector | gain at usage 27.6% |
|---|---:|
| confidence (high first) | -0.0050 |
| confidence (low first) | +0.0000 |
| random (expected) | +0.0014 |
| stuck rule | +0.0000 |
| ex-post oracle | +0.0100 |

Oracle is a diagnostic on these fixed states only, not a deployable bound.
