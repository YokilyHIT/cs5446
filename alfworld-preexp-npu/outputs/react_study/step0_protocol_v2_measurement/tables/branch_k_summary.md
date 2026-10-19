# Step 0c: K=8 continuation branches

200/200 points replayed; a_base reproduced log at 179.

## group: all (n=200; P_base success 0.519, PR 0.694)

A/A (half-vs-half of base rollouts): success var 0.0276, PR var 0.0091

| intervention | changed | U success [CI] | U PR [CI] | U PR@5 [CI] | PR excess-var ratio (changed) | PR +beyond 2SE | PR −beyond 2SE |
|---|---:|---|---|---|---:|---:|---:|
| wm | 32% | -0.013 [-0.037, +0.009] | -0.011 [-0.026, +0.002] | -0.010 [-0.025, +0.003] | 5.48 | 5% | 17% |
| oracle | 32% | -0.024 [-0.049, -0.001] | -0.008 [-0.019, +0.003] | -0.007 [-0.019, +0.004] | 4.1 | 3% | 17% |
| rethink | 48% | -0.007 [-0.046, +0.029] | -0.013 [-0.041, +0.011] | -0.025 [-0.050, -0.002] | 10.09 | 13% | 13% |
| loophint | 58% | -0.050 [-0.087, -0.015] | -0.020 [-0.042, +0.002] | -0.022 [-0.049, +0.004] | 10.32 | 9% | 20% |

## group: solvable (n=160; P_base success 0.636, PR 0.807)

A/A (half-vs-half of base rollouts): success var 0.0336, PR var 0.0104

| intervention | changed | U success [CI] | U PR [CI] | U PR@5 [CI] | PR excess-var ratio (changed) | PR +beyond 2SE | PR −beyond 2SE |
|---|---:|---|---|---|---:|---:|---:|
| wm | 29% | -0.016 [-0.047, +0.012] | -0.013 [-0.032, +0.004] | -0.011 [-0.030, +0.005] | 5.5 | 7% | 22% |
| oracle | 29% | -0.030 [-0.060, -0.002] | -0.011 [-0.025, +0.001] | -0.009 [-0.025, +0.004] | 4.09 | 2% | 24% |
| rethink | 44% | -0.005 [-0.050, +0.038] | -0.015 [-0.046, +0.012] | -0.028 [-0.057, -0.000] | 9.46 | 14% | 15% |
| loophint | 56% | -0.062 [-0.108, -0.017] | -0.026 [-0.054, +0.001] | -0.026 [-0.059, +0.007] | 10.61 | 10% | 24% |

## group: unsolved (n=40; P_base success 0.050, PR 0.240)

A/A (half-vs-half of base rollouts): success var 0.0030, PR var 0.0040

| intervention | changed | U success [CI] | U PR [CI] | U PR@5 [CI] | PR excess-var ratio (changed) | PR +beyond 2SE | PR −beyond 2SE |
|---|---:|---|---|---|---:|---:|---:|
| wm | 45% | +0.000 [+0.000, +0.000] | -0.002 [-0.007, +0.002] | -0.004 [-0.017, +0.005] | 2.13 | 0% | 6% |
| oracle | 45% | +0.000 [+0.000, +0.000] | +0.007 [+0.000, +0.021] | +0.002 [+0.000, +0.006] | 2.84 | 6% | 0% |
| rethink | 65% | -0.019 [-0.077, +0.018] | -0.005 [-0.067, +0.042] | -0.013 [-0.045, +0.010] | 14.96 | 12% | 8% |
| loophint | 68% | +0.000 [+0.000, +0.000] | +0.007 [-0.019, +0.031] | -0.005 [-0.016, +0.003] | 6.12 | 7% | 4% |

## Confidence vs accuracy vs utility (solvable, wm)

```
{
 "auroc_conf_for_EM": 0.862590799031477,
 "spearman_conf_f1": 0.45940485498632855,
 "spearman_conf_Uwm_pr_changed": 0.0038629625397965917,
 "auroc_conf_for_Uwm_pr_pos": 0.4111111111111111,
 "auroc_conf_for_Uwm_pr_neg": 0.48333333333333334,
 "pred_em_mean": 0.2625,
 "pred_f1_mean": 0.5650833710615455,
 "mean_Uwm_pr_when_EM1": -0.011408730158730158,
 "mean_Uwm_pr_when_EM0": -0.013594632768361583,
 "mean_Uoracle_pr": -0.011328125
}
```

## Coverage (solvable, U_PR of wm) at usage ≈ 30%

- confidence_high: -0.0033  (always: -0.0130)
- confidence_low: -0.0102  (always: -0.0130)
- stuck_rule: -0.0060  (always: -0.0130)
- random: -0.0039  (always: -0.0130)
- ex_post_oracle: +0.0100  (always: -0.0130)
