# Round 7 stage A: rule-verified WM repair (dev460 x 2)

## 4B planner (460 tasks x 2)

| arm | SR | PR | 14B calls / ep | tokens / ep | re-ask rate | reason agrees with rules (before -> after) |
|---|---:|---:|---:|---:|---:|---|
| inv_fail | 18.3 | 36.7 | 0.0 | 51.9k | - | - |
| inv_rules | 26.4 | 40.9 | 0.0 | 48.7k | - | - |
| frozen | 26.5 | 42.2 | 6.6 | 54.1k | - | - |
| inv_repair | 29.1 | 41.0 | 0.0 | 46.5k | - | - |
| inv_rpms | 28.5 | 41.4 | 0.0 | 47.3k | - | - |
| wmrules_concat | 29.5 | 42.6 | 5.9 | 52.5k | - | - |
| wmverify | 33.3 | 44.4 | 8.7 | 53.1k | 58% | 35% -> 75% |
| wmverify_learned | 26.2 | 41.5 | 12.7 | 60.2k | 0% | 32% -> 36% |

| contrast | dPR | dSR |
|---|---|---|
| wmverify - frozen | +2.3 [+0.1, +4.4] p=0.038 | +6.7 [+3.8, +9.7] p=0.000 |
| wmverify - wmrules_concat | +1.9 [-0.1, +3.9] p=0.059 | +3.8 [+1.2, +6.4] p=0.005 |
| wmverify - inv_rpms | +3.0 [+0.8, +5.1] p=0.006 | +4.8 [+1.7, +7.9] p=0.003 |
| wmverify_learned - frozen | -0.7 [-2.8, +1.4] p=0.545 | -0.3 [-3.0, +2.4] p=0.842 |
| wmverify_learned - wmrules_concat | -1.0 [-3.1, +1.0] p=0.315 | -3.3 [-6.0, -0.5] p=0.020 |
| wmverify_learned - inv_rpms | +0.1 [-2.1, +2.2] p=0.955 | -2.3 [-5.5, +0.9] p=0.158 |
| wmrules_concat - frozen | +0.4 [-1.7, +2.4] p=0.719 | +2.9 [+0.3, +5.5] p=0.028 |
| wmrules_concat - inv_rpms | +1.1 [-0.9, +3.2] p=0.294 | +1.0 [-1.7, +3.8] p=0.517 |

## 14B planner (460 tasks x 2)

| arm | SR | PR | 14B calls / ep | tokens / ep | re-ask rate | reason agrees with rules (before -> after) |
|---|---:|---:|---:|---:|---:|---|
| inv_fail | 63.9 | 73.3 | 0.0 | 34.3k | - | - |
| inv_rules | 67.0 | 75.0 | 0.0 | 31.9k | - | - |
| frozen | 64.9 | 74.1 | 3.6 | 36.3k | - | - |
| inv_repair | 69.5 | 76.7 | 0.0 | 31.0k | - | - |
| inv_rpms | 67.9 | 76.0 | 0.0 | 31.3k | - | - |
| wmrules_concat | 68.4 | 76.0 | 2.8 | 34.1k | - | - |
| wmverify | 69.5 | 76.4 | 3.9 | 34.0k | 57% | 21% -> 60% |
| wmverify_learned | 64.1 | 73.3 | 6.9 | 40.0k | 0% | 16% -> 19% |

| contrast | dPR | dSR |
|---|---|---|
| wmverify - frozen | +2.3 [+0.4, +4.1] p=0.015 | +4.6 [+2.1, +7.2] p=0.000 |
| wmverify - wmrules_concat | +0.4 [-1.2, +2.1] p=0.639 | +1.1 [-1.2, +3.4] p=0.367 |
| wmverify - inv_rpms | +0.4 [-1.3, +2.2] p=0.632 | +1.5 [-1.0, +4.0] p=0.248 |
| wmverify_learned - frozen | -0.8 [-2.5, +0.9] p=0.367 | -0.8 [-3.2, +1.7] p=0.569 |
| wmverify_learned - wmrules_concat | -2.7 [-4.4, -1.0] p=0.001 | -4.2 [-6.6, -1.8] p=0.001 |
| wmverify_learned - inv_rpms | -2.7 [-4.7, -0.7] p=0.010 | -3.8 [-6.9, -0.8] p=0.018 |
| wmrules_concat - frozen | +1.9 [+0.0, +3.8] p=0.047 | +3.5 [+0.9, +6.1] p=0.009 |
| wmrules_concat - inv_rpms | +0.0 [-1.8, +1.9] p=0.970 | +0.4 [-2.3, +3.0] p=0.786 |

## Pre-registered selection rule (dev PR above frozen AND concat for both planners)

* wmverify: qualifies
* wmverify_learned: does not qualify

