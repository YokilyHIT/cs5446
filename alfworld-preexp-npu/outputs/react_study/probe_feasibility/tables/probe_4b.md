# Feasibility probes, 4B planner, 460 dev460 tasks x 2 reps

| arm | SR | PR | legal | gate open/step | seen target | picked | tokens/task |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | 11.7% | 32.8% | 0.69 | 0.00 | 0.51 | 0.43 | 40.0k |
| always | 14.6% | 35.7% | 0.72 | 0.00 | 0.54 | 0.46 | 95.0k |
| oracle_every | 18.0% | 38.7% | 0.74 | 0.00 | 0.56 | 0.48 | 78.6k |
| inv_resample | 14.9% | 35.0% | 0.77 | 0.30 | 0.53 | 0.45 | 52.9k |
| inv_fail | 18.3% | 36.7% | 0.85 | 0.27 | 0.52 | 0.46 | 51.9k |
| inv_repair | 29.1% | 41.0% | 0.90 | 0.23 | 0.51 | 0.46 | 46.5k |
| inv_proj | 14.2% | 36.2% | 1.00 | 0.26 | 0.54 | 0.47 | 54.5k |
| wmrepair_wm4 | 23.9% | 43.5% | 0.88 | 0.26 | 0.58 | 0.53 | 56.4k |
| wmrepair_wm14 | 26.5% | 42.2% | 0.89 | 0.25 | 0.55 | 0.50 | 54.1k |

## Primary (pre-registered, Holm over 3)

| contrast | Δ pp [95% CI] |
|---|---|
| inv_repair-inv_fail:PR | +4.2 [+2.4, +6.0] p=0.000 Holm=0.000 |
| inv_repair-inv_proj:PR | +4.7 [+2.4, +7.0] p=0.000 Holm=0.000 |
| inv_proj-none:PR | +3.4 [+1.4, +5.5] p=0.001 Holm=0.001 |

## Exploratory

| contrast | Δ pp [95% CI] |
|---|---|
| always-inv_fail:PR | -1.0 [-3.0, +1.0] p=0.303 |
| always-inv_fail:SR | -3.7 [-6.3, -1.2] p=0.004 |
| always-inv_resample:PR | +0.7 [-1.1, +2.5] p=0.449 |
| always-inv_resample:SR | -0.3 [-2.5, +1.7] p=0.787 |
| always-none:PR | +2.9 [+0.9, +4.8] p=0.003 |
| always-none:SR | +2.8 [+0.7, +5.0] p=0.013 |
| always-oracle_every:PR | -3.0 [-5.0, -1.0] p=0.002 |
| always-oracle_every:SR | -3.5 [-6.0, -1.0] p=0.005 |
| inv_fail-inv_resample:PR | +1.7 [+0.3, +3.2] p=0.018 |
| inv_fail-inv_resample:SR | +3.4 [+1.4, +5.4] p=0.001 |
| inv_fail-none:PR | +3.9 [+2.3, +5.6] p=0.000 |
| inv_fail-none:SR | +6.5 [+4.3, +8.7] p=0.000 |
| inv_fail-oracle_every:PR | -1.9 [-3.8, -0.0] p=0.049 |
| inv_fail-oracle_every:SR | +0.2 [-2.2, +2.6] p=0.904 |
| inv_proj-inv_fail:PR | -0.5 [-2.4, +1.5] p=0.622 |
| inv_proj-inv_fail:SR | -4.0 [-6.6, -1.4] p=0.003 |
| inv_proj-inv_resample:PR | +1.2 [-0.6, +3.0] p=0.179 |
| inv_proj-inv_resample:SR | -0.7 [-2.9, +1.6] p=0.611 |
| inv_proj-none:PR | +3.4 [+1.4, +5.5] p=0.001 |
| inv_proj-none:SR | +2.5 [+0.2, +4.8] p=0.035 |
| inv_proj-oracle_every:PR | -2.4 [-4.6, -0.1] p=0.037 |
| inv_proj-oracle_every:SR | -3.8 [-6.6, -1.1] p=0.007 |
| inv_repair-inv_fail:PR | +4.2 [+2.4, +6.0] p=0.000 |
| inv_repair-inv_fail:SR | +10.9 [+7.8, +14.0] p=0.000 |
| inv_repair-inv_resample:PR | +6.0 [+4.2, +7.8] p=0.000 |
| inv_repair-inv_resample:SR | +14.2 [+11.2, +17.4] p=0.000 |
| inv_repair-none:PR | +8.1 [+6.0, +10.2] p=0.000 |
| inv_repair-none:SR | +17.4 [+14.2, +20.7] p=0.000 |
| inv_repair-oracle_every:PR | +2.3 [-0.0, +4.6] p=0.053 |
| inv_repair-oracle_every:SR | +11.1 [+7.6, +14.7] p=0.000 |
| inv_resample-inv_fail:PR | -1.7 [-3.2, -0.3] p=0.018 |
| inv_resample-inv_fail:SR | -3.4 [-5.4, -1.4] p=0.001 |
| inv_resample-none:PR | +2.2 [+0.7, +3.7] p=0.004 |
| inv_resample-none:SR | +3.2 [+1.4, +4.9] p=0.000 |
| inv_resample-oracle_every:PR | -3.7 [-5.5, -1.9] p=0.000 |
| inv_resample-oracle_every:SR | -3.2 [-5.4, -1.0] p=0.007 |
| none-inv_fail:PR | -3.9 [-5.6, -2.2] p=0.000 |
| none-inv_fail:SR | -6.5 [-8.8, -4.3] p=0.000 |
| none-inv_resample:PR | -2.2 [-3.7, -0.6] p=0.006 |
| none-inv_resample:SR | -3.2 [-4.9, -1.4] p=0.000 |
| none-oracle_every:PR | -5.8 [-7.8, -3.9] p=0.000 |
| none-oracle_every:SR | -6.3 [-8.7, -4.0] p=0.000 |
| oracle_every-inv_fail:PR | +1.9 [+0.0, +3.8] p=0.045 |
| oracle_every-inv_fail:SR | -0.2 [-2.6, +2.2] p=0.890 |
| oracle_every-inv_resample:PR | +3.7 [+1.9, +5.5] p=0.000 |
| oracle_every-inv_resample:SR | +3.2 [+1.0, +5.4] p=0.005 |
| oracle_every-none:PR | +5.8 [+3.9, +7.8] p=0.000 |
| oracle_every-none:SR | +6.3 [+4.0, +8.7] p=0.000 |
| wmrepair_wm14-inv_fail:PR | +5.5 [+3.5, +7.4] p=0.000 |
| wmrepair_wm14-inv_fail:SR | +8.3 [+5.5, +11.1] p=0.000 |
| wmrepair_wm14-inv_resample:PR | +7.2 [+5.3, +9.1] p=0.000 |
| wmrepair_wm14-inv_resample:SR | +11.6 [+8.8, +14.5] p=0.000 |
| wmrepair_wm14-none:PR | +9.4 [+7.5, +11.4] p=0.000 |
| wmrepair_wm14-none:SR | +14.8 [+12.0, +17.7] p=0.000 |
| wmrepair_wm14-oracle_every:PR | +3.5 [+1.3, +5.8] p=0.002 |
| wmrepair_wm14-oracle_every:SR | +8.5 [+5.4, +11.5] p=0.000 |
| wmrepair_wm4-inv_fail:PR | +6.8 [+4.6, +9.1] p=0.000 |
| wmrepair_wm4-inv_fail:SR | +5.7 [+2.7, +8.6] p=0.000 |
| wmrepair_wm4-inv_resample:PR | +8.5 [+6.5, +10.7] p=0.000 |
| wmrepair_wm4-inv_resample:SR | +9.0 [+6.4, +11.7] p=0.000 |
| wmrepair_wm4-none:PR | +10.7 [+8.5, +12.9] p=0.000 |
| wmrepair_wm4-none:SR | +12.2 [+9.5, +15.0] p=0.000 |
| wmrepair_wm4-oracle_every:PR | +4.9 [+2.4, +7.3] p=0.000 |
| wmrepair_wm4-oracle_every:SR | +5.9 [+2.8, +8.9] p=0.000 |
