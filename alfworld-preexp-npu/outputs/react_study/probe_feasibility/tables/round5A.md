# Round 5 stage A: method matrix (dev460 x 2 reps)

## 4B planner (460 tasks)

| arm | SR | PR | legal | gate open/step | tokens/task |
|---|---:|---:|---:|---:|---:|
| none | 11.7% | 32.8% | 0.69 | 0.00 | 40.0k |
| inv_resample | 14.9% | 35.0% | 0.77 | 0.30 | 52.9k |
| inv_proj | 14.2% | 36.2% | 1.00 | 0.26 | 54.5k |
| inv_fail | 18.3% | 36.7% | 0.85 | 0.27 | 51.9k |
| inv_reflect | 18.7% | 37.8% | 0.86 | 0.27 | 52.0k |
| inv_sreflect | 17.3% | 37.1% | 0.84 | 0.29 | 53.4k |
| inv_rules | 26.4% | 40.9% | 0.88 | 0.25 | 48.7k |
| inv_state | 21.0% | 38.2% | 0.88 | 0.26 | 50.9k |
| inv_wmpred_wm4 | 15.4% | 35.9% | 0.81 | 0.29 | 58.6k |
| inv_wmpred_wm14 | 15.3% | 35.1% | 0.80 | 0.29 | 57.5k |
| wmrepair_wm4 | 23.9% | 43.5% | 0.88 | 0.26 | 56.4k |
| wmrepair_wm14 | 26.5% | 42.2% | 0.89 | 0.25 | 54.1k |
| post_wmrepair_wm4 | 19.5% | 39.7% | 0.77 | 0.22 | 44.5k |
| inv_repair | 29.1% | 41.0% | 0.90 | 0.23 | 46.5k |

## 14B planner (460 tasks)

| arm | SR | PR | legal | gate open/step | tokens/task |
|---|---:|---:|---:|---:|---:|
| none | 56.4% | 68.9% | 0.83 | 0.00 | 29.1k |
| inv_fail | 63.9% | 73.3% | 0.90 | 0.16 | 34.3k |
| inv_reflect | 62.4% | 71.9% | 0.91 | 0.15 | 34.4k |
| inv_sreflect | 61.4% | 72.0% | 0.90 | 0.16 | 34.6k |
| inv_rules | 67.0% | 75.0% | 0.93 | 0.13 | 31.9k |
| inv_state | 65.2% | 73.5% | 0.93 | 0.13 | 32.9k |
| inv_wmpred_wm14 | 61.2% | 72.7% | 0.89 | 0.15 | 36.7k |
| wmrepair_wm14 | 64.9% | 74.1% | 0.93 | 0.14 | 36.3k |
| inv_repair | 69.5% | 76.7% | 0.95 | 0.12 | 31.0k |

## 4B primary (Holm over 4), PR

| contrast | Δ pp [95% CI] | SR Δ (exploratory) |
|---|---|---|
| wmrepair_wm14 - inv_reflect | +4.4 [+2.3, +6.4] p=0.000 Holm=0.000 | +7.8 [+5.1, +10.7] p=0.000 |
| wmrepair_wm14 - inv_sreflect | +5.1 [+2.9, +7.3] p=0.000 Holm=0.000 | +9.2 [+6.3, +12.2] p=0.000 |
| wmrepair_wm14 - inv_rules | +1.3 [-0.9, +3.5] p=0.251 Holm=0.251 | +0.1 [-3.0, +3.3] p=0.966 |
| wmrepair_wm14 - inv_wmpred_wm14 | +7.1 [+5.1, +9.1] p=0.000 Holm=0.000 | +11.2 [+8.5, +14.0] p=0.000 |

## 4B secondary (Holm over 4), PR

| contrast | Δ pp [95% CI] | SR Δ (exploratory) |
|---|---|---|
| wmrepair_wm4 - inv_sreflect | +6.4 [+4.2, +8.7] p=0.000 Holm=0.000 | +6.6 [+3.8, +9.5] p=0.000 |
| wmrepair_wm4 - inv_wmpred_wm4 | +7.6 [+5.4, +9.9] p=0.000 Holm=0.000 | +8.5 [+5.8, +11.3] p=0.000 |
| post_wmrepair_wm4 - inv_fail | +3.0 [+0.8, +5.2] p=0.006 Holm=0.006 | +1.2 [-1.3, +3.8] p=0.381 |
| post_wmrepair_wm4 - wmrepair_wm4 | -3.8 [-5.8, -1.9] p=0.000 Holm=0.000 | -4.5 [-7.1, -2.0] p=0.001 |

## 14B secondary (Holm over 3), PR

| contrast | Δ pp [95% CI] | SR Δ (exploratory) |
|---|---|---|
| inv_state - inv_fail | +0.3 [-1.6, +2.1] p=0.779 Holm=0.779 | +1.3 [-1.4, +4.0] p=0.369 |
| inv_repair - inv_state | +3.1 [+1.3, +5.0] p=0.001 Holm=0.004 | +4.2 [+1.6, +7.0] p=0.002 |
| inv_sreflect - inv_fail | -1.3 [-3.0, +0.5] p=0.156 Holm=0.312 | -2.5 [-5.2, +0.2] p=0.079 |

**Freeze-rule verdict:** freeze inv_wmrepair (14B WM)

## Diagnosis quality at gate steps (proposed first repair vs environment-derived diagnosis)

| planner | arm | gate steps sampled | repair given | oracle repair exists | agree when it exists |
|---|---|---:|---:|---:|---:|
| 4B | wmrepair_wm4 | 400 | 0.72 | 0.44 | 0.17 |
| 4B | wmrepair_wm14 | 400 | 0.69 | 0.47 | 0.33 |
| 4B | post_wmrepair_wm4 | 400 | 0.73 | 0.46 | 0.15 |
| 4B | inv_sreflect | 400 | 0.02 | 0.49 | nan |
| 14B | wmrepair_wm14 | 400 | 0.61 | 0.39 | 0.19 |
| 14B | inv_sreflect | 400 | 0.00 | 0.52 | nan |
