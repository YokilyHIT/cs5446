# Round 5 final evaluation: fresh600

## 4B planner (600 tasks x 3 reps)

| arm | SR | PR | legal | tokens/task |
|---|---:|---:|---:|---:|
| none | 20.9% | 39.4% | 0.71 | 37.6k |
| inv_fail | 28.3% | 44.8% | 0.87 | 46.9k |
| inv_reflect | 28.6% | 45.9% | 0.88 | 47.5k |
| inv_sreflect | 23.7% | 42.8% | 0.85 | 50.1k |
| inv_rules | 33.3% | 46.8% | 0.91 | 44.4k |
| wmrepair_wm4 | 29.7% | 46.6% | 0.90 | 53.0k |
| wmrepair_wm14 (frozen) | 36.2% | 49.0% | 0.91 | 47.8k |
| inv_repair | 36.7% | 47.5% | 0.91 | 42.5k |

### Pre-registered primary (4B, fresh600)

* H1 PR(frozen) - PR(inv_fail): +4.2 [+2.6, +5.7] p=0.000 Holm=0.000
* H3 SR(frozen) - SR(none): +15.3 [+12.7, +17.8] p=0.000 Holm=0.000
* H2 non-inferiority PR(frozen) - PR(inv_rules): +2.2 [+0.5, +3.9] p=0.010 -> NON-INFERIOR (margin -2 pp)

### Secondary contrasts (4B, uncorrected)

| contrast | ΔSR | ΔPR |
|---|---|---|
| wmrepair_wm14 - none | +15.3 [+12.7, +17.9] p=0.000 | +9.5 [+7.8, +11.3] p=0.000 |
| wmrepair_wm14 - inv_fail | +7.9 [+5.7, +10.1] p=0.000 | +4.2 [+2.6, +5.7] p=0.000 |
| wmrepair_wm14 - inv_reflect | +7.6 [+5.3, +9.9] p=0.000 | +3.0 [+1.4, +4.7] p=0.000 |
| wmrepair_wm14 - inv_sreflect | +12.6 [+10.2, +15.0] p=0.000 | +6.2 [+4.6, +7.8] p=0.000 |
| wmrepair_wm14 - inv_rules | +2.9 [+0.4, +5.4] p=0.021 | +2.2 [+0.5, +3.9] p=0.011 |
| wmrepair_wm4 - inv_fail | +1.3 [-0.9, +3.7] p=0.249 | +1.8 [-0.0, +3.5] p=0.053 |
| wmrepair_wm4 - wmrepair_wm14 | -6.6 [-8.7, -4.5] p=0.000 | -2.4 [-4.0, -0.9] p=0.003 |
| inv_rules - inv_fail | +5.0 [+2.6, +7.4] p=0.000 | +2.0 [+0.4, +3.5] p=0.012 |
| inv_repair - wmrepair_wm14 | +0.4 [-1.8, +2.7] p=0.702 | -1.5 [-3.1, +0.1] p=0.064 |
| inv_fail - none | +7.4 [+5.3, +9.4] p=0.000 | +5.4 [+4.0, +6.8] p=0.000 |
| inv_reflect - inv_fail | +0.3 [-1.6, +2.2] p=0.772 | +1.1 [-0.3, +2.5] p=0.110 |
| inv_sreflect - inv_fail | -4.7 [-6.8, -2.6] p=0.000 | -2.0 [-3.4, -0.6] p=0.005 |

## 14B planner (600 tasks x 3 reps)

| arm | SR | PR | legal | tokens/task |
|---|---:|---:|---:|---:|
| none | 59.1% | 70.3% | 0.85 | 27.5k |
| inv_fail | 63.9% | 72.8% | 0.91 | 32.8k |
| inv_reflect | 64.9% | 73.5% | 0.92 | 32.1k |
| inv_sreflect | 65.4% | 74.0% | 0.92 | 31.9k |
| inv_rules | 68.8% | 76.0% | 0.93 | 30.5k |
| wmrepair_wm14 (frozen) | 65.9% | 74.3% | 0.94 | 33.7k |
| inv_repair | 69.5% | 76.6% | 0.96 | 29.4k |

### Secondary contrasts (14B, uncorrected)

| contrast | ΔSR | ΔPR |
|---|---|---|
| wmrepair_wm14 - none | +6.8 [+4.4, +9.2] p=0.000 | +4.0 [+2.4, +5.6] p=0.000 |
| wmrepair_wm14 - inv_fail | +2.0 [-0.0, +4.1] p=0.053 | +1.5 [+0.2, +2.9] p=0.029 |
| wmrepair_wm14 - inv_reflect | +0.9 [-1.1, +2.9] p=0.363 | +0.8 [-0.6, +2.2] p=0.240 |
| wmrepair_wm14 - inv_sreflect | +0.5 [-1.5, +2.5] p=0.631 | +0.4 [-1.0, +1.7] p=0.615 |
| wmrepair_wm14 - inv_rules | -2.9 [-5.1, -0.8] p=0.008 | -1.7 [-3.1, -0.2] p=0.025 |
| inv_rules - inv_fail | +4.9 [+2.9, +7.1] p=0.000 | +3.2 [+1.8, +4.6] p=0.000 |
| inv_repair - wmrepair_wm14 | +3.6 [+1.4, +5.8] p=0.001 | +2.3 [+0.9, +3.7] p=0.001 |
| inv_fail - none | +4.8 [+2.7, +6.9] p=0.000 | +2.5 [+1.2, +3.9] p=0.000 |
| inv_reflect - inv_fail | +1.1 [-0.7, +2.8] p=0.242 | +0.7 [-0.5, +1.9] p=0.262 |
| inv_sreflect - inv_fail | +1.5 [-0.4, +3.4] p=0.140 | +1.1 [-0.3, +2.6] p=0.113 |

