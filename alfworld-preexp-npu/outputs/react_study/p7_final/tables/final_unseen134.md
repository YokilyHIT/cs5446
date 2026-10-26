# Round 5 final evaluation: unseen134

## 4B planner (134 tasks x 5 reps)

| arm | SR | PR | legal | tokens/task |
|---|---:|---:|---:|---:|
| none | 25.4% | 41.0% | 0.76 | 34.9k |
| inv_fail | 34.2% | 46.7% | 0.90 | 41.3k |
| inv_reflect | 31.3% | 46.8% | 0.90 | 43.1k |
| inv_sreflect | 29.3% | 44.8% | 0.85 | 45.8k |
| inv_rules | 34.9% | 47.6% | 0.91 | 41.7k |
| wmrepair_wm4 | 32.4% | 46.3% | 0.92 | 48.1k |
| wmrepair_wm14 (frozen) | 38.5% | 48.8% | 0.93 | 43.0k |
| inv_repair | 38.4% | 48.3% | 0.93 | 38.6k |

### Secondary contrasts (4B, uncorrected)

| contrast | ΔSR | ΔPR |
|---|---|---|
| wmrepair_wm14 - none | +13.1 [+8.7, +17.8] p=0.000 | +7.8 [+5.2, +10.5] p=0.000 |
| wmrepair_wm14 - inv_fail | +4.3 [+0.7, +8.2] p=0.020 | +2.1 [-0.4, +4.6] p=0.115 |
| wmrepair_wm14 - inv_reflect | +7.2 [+3.4, +11.0] p=0.000 | +2.0 [-0.2, +4.1] p=0.077 |
| wmrepair_wm14 - inv_sreflect | +9.3 [+4.8, +13.9] p=0.000 | +4.0 [+1.3, +6.7] p=0.004 |
| wmrepair_wm14 - inv_rules | +3.6 [+0.4, +6.9] p=0.023 | +1.1 [-1.2, +3.5] p=0.342 |
| wmrepair_wm4 - inv_fail | -1.8 [-5.8, +2.2] p=0.390 | -0.4 [-3.2, +2.3] p=0.760 |
| wmrepair_wm4 - wmrepair_wm14 | -6.1 [-10.7, -1.8] p=0.004 | -2.5 [-5.5, +0.5] p=0.105 |
| inv_rules - inv_fail | +0.7 [-2.7, +4.2] p=0.684 | +0.9 [-1.3, +3.3] p=0.411 |
| inv_repair - wmrepair_wm14 | -0.1 [-4.0, +3.6] p=0.914 | -0.5 [-3.1, +2.0] p=0.709 |
| inv_fail - none | +8.8 [+5.2, +12.8] p=0.000 | +5.7 [+3.2, +8.4] p=0.000 |
| inv_reflect - inv_fail | -2.8 [-5.2, -0.6] p=0.013 | +0.1 [-1.7, +1.9] p=0.921 |
| inv_sreflect - inv_fail | -4.9 [-8.5, -1.5] p=0.004 | -1.9 [-4.4, +0.4] p=0.113 |

## 14B planner (134 tasks x 5 reps)

| arm | SR | PR | legal | tokens/task |
|---|---:|---:|---:|---:|
| none | 67.6% | 76.3% | 0.85 | 24.9k |
| inv_fail | 74.0% | 81.2% | 0.93 | 28.5k |
| inv_reflect | 74.8% | 82.3% | 0.94 | 29.0k |
| inv_sreflect | 73.7% | 80.9% | 0.92 | 29.6k |
| inv_rules | 75.1% | 82.8% | 0.94 | 28.5k |
| wmrepair_wm14 (frozen) | 75.5% | 81.2% | 0.96 | 30.1k |
| inv_repair | 79.0% | 83.6% | 0.96 | 26.8k |

### Secondary contrasts (14B, uncorrected)

| contrast | ΔSR | ΔPR |
|---|---|---|
| wmrepair_wm14 - none | +7.9 [+3.3, +12.5] p=0.001 | +4.9 [+1.5, +8.3] p=0.005 |
| wmrepair_wm14 - inv_fail | +1.5 [-2.2, +5.4] p=0.427 | -0.0 [-2.6, +2.5] p=0.985 |
| wmrepair_wm14 - inv_reflect | +0.7 [-3.4, +4.9] p=0.719 | -1.1 [-4.1, +1.8] p=0.468 |
| wmrepair_wm14 - inv_sreflect | +1.8 [-1.6, +5.4] p=0.308 | +0.3 [-2.3, +2.9] p=0.817 |
| wmrepair_wm14 - inv_rules | +0.4 [-4.0, +5.1] p=0.871 | -1.6 [-5.0, +1.5] p=0.322 |
| inv_rules - inv_fail | +1.0 [-3.3, +5.2] p=0.624 | +1.6 [-1.8, +5.1] p=0.354 |
| inv_repair - wmrepair_wm14 | +3.4 [-0.7, +7.8] p=0.110 | +2.4 [-0.3, +5.5] p=0.092 |
| inv_fail - none | +6.4 [+2.4, +10.9] p=0.002 | +4.9 [+2.4, +7.5] p=0.000 |
| inv_reflect - inv_fail | +0.7 [-3.4, +4.9] p=0.726 | +1.1 [-1.7, +4.0] p=0.450 |
| inv_sreflect - inv_fail | -0.3 [-4.3, +3.6] p=0.887 | -0.3 [-2.7, +2.1] p=0.837 |

