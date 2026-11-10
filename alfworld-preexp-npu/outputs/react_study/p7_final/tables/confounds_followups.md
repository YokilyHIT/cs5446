# Confound controls and follow-ups (4B planner, 14B WM / takeover model)

## fresh600 (600 tasks x 3 reps)

| arm | SR | PR | repeated same failure / ep | repair adopted | tokens/task (of which 14B) |
|---|---:|---:|---:|---:|---:|
| none | 20.9% | 39.4% | 0.00 | - | 37.6k (0.0k) |
| inv_fail | 28.3% | 44.8% | 4.16 | - | 46.9k (0.0k) |
| inv_rules | 33.3% | 46.8% | 3.27 | - | 44.4k (0.0k) |
| wmrepair_wm14 | 36.2% | 49.0% | 3.14 | 0.50 | 47.8k (4.5k) |
| inv_repair | 36.7% | 47.5% | 2.84 | 0.68 | 42.5k (0.0k) |
| inv_takeover | 49.0% | 58.3% | 2.06 | - | 38.3k (6.7k) |
| inv_wmpred | 24.1% | 42.4% | 5.15 | - | 53.6k (4.3k) |
| inv_wmpred_info | 29.2% | 44.9% | 3.87 | - | 50.8k (4.8k) |
| inv_wmrepair_reason | 29.7% | 45.6% | 4.24 | 0.17 | 52.1k (5.4k) |
| inv_wmrepair_action | 32.2% | 47.0% | 3.76 | 0.38 | 50.0k (5.0k) |
| inv_wmrepair_exec | 36.9% | 49.2% | 2.61 | 1.00 | 41.1k (4.2k) |
| inv_wmrepair_mem | 31.8% | 47.9% | 3.06 | 0.52 | 51.6k (4.5k) |

### confounds (pre-registered primary, Holm), PR (SR exploratory)

| contrast | ΔPR | ΔSR |
|---|---|---|
| wmrepair_wm14 - inv_takeover | -9.4 [-11.7, -7.2] p=0.000 Holm=0.000 | -12.8 [-15.7, -9.9] p=0.000 |
| wmrepair_wm14 - inv_wmpred_info | +4.1 [+2.5, +5.7] p=0.000 Holm=0.000 | +7.0 [+4.8, +9.2] p=0.000 |
| inv_wmrepair_reason - inv_fail | +0.8 [-0.5, +2.1] p=0.246 Holm=0.246 | +1.4 [-0.6, +3.3] p=0.154 |

### follow-ups (pre-registered primary, Holm), PR (SR exploratory)

| contrast | ΔPR | ΔSR |
|---|---|---|
| inv_wmrepair_exec - wmrepair_wm14 | +0.2 [-1.4, +1.8] p=0.795 Holm=0.795 | +0.7 [-1.4, +2.8] p=0.547 |
| inv_wmrepair_mem - wmrepair_wm14 | -1.0 [-2.5, +0.4] p=0.166 Holm=0.331 | -4.4 [-6.5, -2.3] p=0.000 |

### Secondary (uncorrected)

| contrast | ΔPR | ΔSR |
|---|---|---|
| inv_wmrepair_action - inv_fail | +2.2 [+0.6, +3.8] p=0.004 | +3.8 [+1.8, +5.9] p=0.000 |
| wmrepair_wm14 - inv_wmrepair_action | +2.0 [+0.3, +3.6] p=0.018 | +4.1 [+1.9, +6.2] p=0.000 |
| wmrepair_wm14 - inv_wmrepair_reason | +3.4 [+1.8, +5.0] p=0.000 | +6.5 [+4.3, +8.8] p=0.000 |
| inv_wmpred_info - inv_wmpred | +2.5 [+1.1, +3.9] p=0.000 | +5.2 [+3.2, +7.2] p=0.000 |
| inv_takeover - inv_fail | +13.6 [+11.4, +15.8] p=0.000 | +20.7 [+17.7, +23.7] p=0.000 |
| wmrepair_wm14 - inv_wmpred | +6.6 [+4.9, +8.2] p=0.000 | +12.2 [+9.7, +14.7] p=0.000 |
| inv_wmrepair_exec - inv_repair | +1.7 [-0.2, +3.6] p=0.078 | +0.2 [-2.1, +2.6] p=0.846 |
| inv_wmrepair_mem - inv_rules | +1.2 [-0.8, +3.1] p=0.235 | -1.5 [-4.2, +1.3] p=0.290 |

## dev460 (460 tasks x 2 reps)

| arm | SR | PR | repeated same failure / ep | repair adopted | tokens/task (of which 14B) |
|---|---:|---:|---:|---:|---:|
| none | 11.7% | 32.8% | 0.00 | - | 40.0k (0.0k) |
| inv_fail | 18.3% | 36.7% | 5.16 | - | 51.9k (0.0k) |
| inv_rules | 26.4% | 40.9% | 4.42 | - | 48.7k (0.0k) |
| inv_wmpred | 15.3% | 35.1% | 5.81 | - | 57.5k (4.7k) |
| wmrepair_wm14 | 26.5% | 42.2% | 4.07 | 0.44 | 54.1k (5.6k) |
| inv_repair | 29.1% | 41.0% | 3.57 | 0.63 | 46.5k (0.0k) |
| inv_takeover | 40.2% | 51.6% | 2.96 | - | 42.8k (8.6k) |
| inv_wmpred_info | 18.6% | 36.5% | 5.06 | - | 56.7k (5.7k) |
| inv_wmrepair_reason | 20.1% | 37.9% | 5.08 | 0.16 | 57.5k (6.2k) |
| inv_wmrepair_action | 20.8% | 39.3% | 5.04 | 0.34 | 57.3k (6.3k) |
| inv_wmrepair_exec | 30.9% | 44.8% | 3.44 | 1.00 | 45.2k (5.1k) |
| inv_wmrepair_mem | 24.2% | 41.7% | 3.43 | 0.47 | 56.1k (5.1k) |

### confounds (dev reference, Holm within family), PR (SR exploratory)

| contrast | ΔPR | ΔSR |
|---|---|---|
| wmrepair_wm14 - inv_takeover | -9.4 [-12.1, -6.8] p=0.000 Holm=0.000 | -13.7 [-17.3, -10.2] p=0.000 |
| wmrepair_wm14 - inv_wmpred_info | +5.6 [+3.8, +7.6] p=0.000 Holm=0.000 | +7.9 [+5.2, +10.7] p=0.000 |
| inv_wmrepair_reason - inv_fail | +1.1 [-0.6, +2.9] p=0.207 Holm=0.207 | +1.8 [-0.4, +4.1] p=0.118 |

### follow-ups (dev reference, Holm within family), PR (SR exploratory)

| contrast | ΔPR | ΔSR |
|---|---|---|
| inv_wmrepair_exec - wmrepair_wm14 | +2.6 [+0.4, +4.9] p=0.023 Holm=0.046 | +4.3 [+1.3, +7.4] p=0.005 |
| inv_wmrepair_mem - wmrepair_wm14 | -0.4 [-2.5, +1.5] p=0.665 Holm=0.665 | -2.3 [-5.1, +0.4] p=0.113 |

### Secondary (uncorrected)

| contrast | ΔPR | ΔSR |
|---|---|---|
| inv_wmrepair_action - inv_fail | +2.6 [+0.7, +4.5] p=0.007 | +2.5 [+0.1, +5.0] p=0.049 |
| wmrepair_wm14 - inv_wmrepair_action | +2.9 [+0.8, +5.0] p=0.007 | +5.8 [+2.8, +8.7] p=0.000 |
| wmrepair_wm14 - inv_wmrepair_reason | +4.3 [+2.2, +6.4] p=0.000 | +6.4 [+3.8, +9.1] p=0.000 |
| inv_wmpred_info - inv_wmpred | +1.4 [-0.2, +3.0] p=0.086 | +3.3 [+1.2, +5.4] p=0.002 |
| inv_takeover - inv_fail | +14.9 [+12.4, +17.4] p=0.000 | +22.0 [+18.5, +25.5] p=0.000 |
| wmrepair_wm14 - inv_wmpred | +7.1 [+5.1, +9.0] p=0.000 | +11.2 [+8.5, +14.0] p=0.000 |
| inv_wmrepair_exec - inv_repair | +3.8 [+1.4, +6.3] p=0.002 | +1.7 [-1.4, +4.9] p=0.289 |
| inv_wmrepair_mem - inv_rules | +0.8 [-1.3, +3.0] p=0.445 | -2.2 [-5.4, +1.0] p=0.182 |

