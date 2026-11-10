# Round 7 stage B: rule-verified WM repair on fresh600 x 3 (pre-registered)

## 4B planner (600 tasks x 3 reps)

| arm | SR | PR | 14B calls / ep | tokens / ep |
|---|---:|---:|---:|---:|
| none | 20.9 | 39.4 | 0.0 | 37.6k |
| inv_fail | 28.3 | 44.8 | 0.0 | 46.9k |
| inv_rules | 33.3 | 46.8 | 0.0 | 44.4k |
| frozen | 36.2 | 49.0 | 5.3 | 47.8k |
| inv_repair | 36.7 | 47.5 | 0.0 | 42.5k |
| RPMS-style | 37.2 | 48.1 | 0.0 | 42.6k |
| concat | 37.8 | 49.2 | 4.7 | 46.5k |
| verify (hand rules) | 38.9 | 49.4 | 7.2 | 47.8k |

Check: re-ask on 57% of gate steps; reason agrees with the rule category 36% -> 78% after the re-ask.

| hypothesis | dPR [95% CI] | test p | Holm | holds | dSR [95% CI] |
|---|---|---:|---:|---|---|
| H1: verify - frozen (> 0) | +0.4 [-1.0, +1.8] | 0.5814 | 1.0000 | no | +2.7 [+0.7, +4.7] p=0.009 |
| H2: verify - concat (> 0) | +0.1 [-1.4, +1.7] | 0.8625 | 1.0000 | no | +1.1 [-0.9, +3.2] p=0.276 |
| H3: verify - RPMS-style (non-inferior, -2 pp) | +1.3 [-0.4, +3.1] | 0.0001 | 0.0004 | yes | +1.7 [-0.7, +4.0] p=0.163 |

## 14B planner (600 tasks x 3 reps)

| arm | SR | PR | 14B calls / ep | tokens / ep |
|---|---:|---:|---:|---:|
| none | 59.1 | 70.3 | 0.0 | 27.5k |
| inv_fail | 63.9 | 72.8 | 0.0 | 32.8k |
| inv_rules | 68.8 | 76.0 | 0.0 | 30.5k |
| frozen | 65.9 | 74.3 | 3.0 | 33.7k |
| inv_repair | 69.5 | 76.6 | 0.0 | 29.4k |
| RPMS-style | 70.7 | 77.0 | 0.0 | 29.5k |
| concat | 70.6 | 77.0 | 2.4 | 31.8k |
| verify (hand rules) | 71.0 | 77.0 | 3.6 | 32.4k |

Check: re-ask on 59% of gate steps; reason agrees with the rule category 18% -> 65% after the re-ask.

| hypothesis | dPR [95% CI] | test p | Holm | holds | dSR [95% CI] |
|---|---|---:|---:|---|---|
| H1: verify - frozen (> 0) | +2.6 [+1.4, +3.9] | 0.0001 | 0.0002 | yes | +5.1 [+3.2, +7.0] p=0.000 |
| H2: verify - concat (> 0) | -0.0 [-1.3, +1.2] | 0.9413 | 0.9413 | no | +0.4 [-1.3, +2.2] p=0.655 |
| H3: verify - RPMS-style (non-inferior, -2 pp) | +0.0 [-1.2, +1.2] | 0.0008 | 0.0016 | yes | +0.3 [-1.4, +2.0] p=0.760 |

