# Round 5 offline analyses (fresh_test600 x 3 reps)

## 4B planner

### SR by task type

| task type | none | inv_fail | inv_rules | wmrepair_wm14 | inv_repair |
|---|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 27.3 | 36.0 | 33.0 | 46.3 | 38.7 |
| pick_and_place_simple | 44.7 | 54.7 | 56.0 | 61.7 | 60.3 |
| pick_clean_then_place_in_recep | 19.0 | 27.3 | 27.0 | 34.7 | 31.7 |
| pick_cool_then_place_in_recep | 6.7 | 14.3 | 13.3 | 21.7 | 18.7 |
| pick_heat_then_place_in_recep | 27.0 | 32.3 | 46.7 | 37.7 | 36.7 |
| pick_two_obj_and_place | 1.0 | 5.3 | 24.0 | 15.3 | 34.0 |

### Subgoal funnel

| arm | saw target | picked | success | P(success|picked) |
|---|---:|---:|---:|---:|
| none | 0.54 | 0.47 | 0.209 | 0.44 |
| inv_fail | 0.58 | 0.52 | 0.283 | 0.55 |
| inv_rules | 0.57 | 0.51 | 0.333 | 0.65 |
| wmrepair_wm14 | 0.60 | 0.55 | 0.362 | 0.66 |
| inv_repair | 0.57 | 0.51 | 0.367 | 0.71 |

### Failure categories at gate steps (environment-derived reason, from history only)

Cells: share of gate steps / executed action admissible / same failed action proposed again later.

| category | inv_fail | inv_rules | wmrepair_wm14 | inv_repair |
|---|---|---|---|---|
| not_at | 0.42 / 0.36 / 0.69 | 0.42 / 0.49 / 0.63 | 0.37 / 0.56 / 0.57 | 0.38 / 0.52 / 0.56 |
| already_at | 0.30 / 0.51 / 0.61 | 0.32 / 0.68 / 0.57 | 0.34 / 0.65 / 0.57 | 0.38 / 0.53 / 0.61 |
| holding_other | 0.10 / 0.38 / 0.86 | 0.09 / 0.36 / 0.85 | 0.12 / 0.35 / 0.85 | 0.05 / 0.39 / 0.70 |
| not_holding | 0.07 / 0.41 / 0.72 | 0.05 / 0.30 / 0.73 | 0.05 / 0.42 / 0.69 | 0.04 / 0.27 / 0.72 |
| closed | 0.00 / 1.00 / 0.00 | 0.00 / 0.88 / 0.75 | 0.00 / 0.67 / 0.00 | 0.00 / 1.00 / 0.33 |
| absent | 0.05 / 0.36 / 0.56 | 0.05 / 0.57 / 0.50 | 0.05 / 0.54 / 0.46 | 0.06 / 0.46 / 0.52 |
| open_state | 0.00 / 0.80 / 0.36 | 0.00 / 0.77 / 0.40 | 0.00 / 0.89 / 0.64 | 0.00 / 0.50 / 0.58 |
| other | 0.07 / 0.77 / 0.27 | 0.07 / 0.86 / 0.12 | 0.07 / 0.56 / 0.42 | 0.09 / 0.80 / 0.27 |
| gate steps | 11469 | 9947 | 9495 | 9052 |

### WM diagnosis vs environment-derived diagnosis (wmrepair_wm14)

* category agreement: 0.30; repair-action agreement (both exist): 0.42
* correct diagnosis (n=2812): executed admissible 0.65, recurs 0.55, repair adopted 0.35
* incorrect diagnosis (n=6683): executed admissible 0.52, recurs 0.61, repair adopted 0.29
* episodes with mostly correct diagnoses: SR 39.8% (n=530); mostly incorrect: SR 28.4% (n=940) -- correlational

Most frequent (environment category -> WM category): already_at->already_at 1523, not_at->absent 1008, not_at->not_at 994, not_at->other 826, already_at->absent 621, already_at->closed 605, other->absent 466, not_at->not_holding 385, holding_other->not_at 322, holding_other->not_holding 310


## 14B planner

### SR by task type

| task type | none | inv_fail | inv_rules | wmrepair_wm14 | inv_repair |
|---|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 75.0 | 78.0 | 82.7 | 84.7 | 82.0 |
| pick_and_place_simple | 83.0 | 86.3 | 88.0 | 86.3 | 86.7 |
| pick_clean_then_place_in_recep | 63.3 | 65.0 | 68.0 | 66.3 | 66.3 |
| pick_cool_then_place_in_recep | 32.0 | 43.3 | 49.0 | 48.0 | 47.3 |
| pick_heat_then_place_in_recep | 65.3 | 67.7 | 68.0 | 65.3 | 71.7 |
| pick_two_obj_and_place | 36.0 | 43.0 | 57.3 | 44.7 | 63.0 |

### Subgoal funnel

| arm | saw target | picked | success | P(success|picked) |
|---|---:|---:|---:|---:|
| none | 0.79 | 0.75 | 0.591 | 0.79 |
| inv_fail | 0.81 | 0.76 | 0.639 | 0.84 |
| inv_rules | 0.81 | 0.78 | 0.688 | 0.88 |
| wmrepair_wm14 | 0.81 | 0.78 | 0.659 | 0.84 |
| inv_repair | 0.82 | 0.79 | 0.695 | 0.88 |

### Failure categories at gate steps (environment-derived reason, from history only)

Cells: share of gate steps / executed action admissible / same failed action proposed again later.

| category | inv_fail | inv_rules | wmrepair_wm14 | inv_repair |
|---|---|---|---|---|
| not_at | 0.41 / 0.36 / 0.67 | 0.40 / 0.43 / 0.63 | 0.36 / 0.53 / 0.61 | 0.38 / 0.56 / 0.56 |
| already_at | 0.14 / 0.40 / 0.57 | 0.16 / 0.49 / 0.53 | 0.11 / 0.50 / 0.43 | 0.16 / 0.54 / 0.47 |
| holding_other | 0.21 / 0.18 / 0.76 | 0.16 / 0.26 / 0.62 | 0.21 / 0.30 / 0.73 | 0.12 / 0.55 / 0.40 |
| not_holding | 0.07 / 0.37 / 0.73 | 0.06 / 0.36 / 0.71 | 0.10 / 0.65 / 0.82 | 0.05 / 0.53 / 0.58 |
| closed | - | 0.00 / 1.00 / 0.00 | - | - |
| absent | 0.13 / 0.31 / 0.37 | 0.18 / 0.40 / 0.39 | 0.18 / 0.51 / 0.45 | 0.21 / 0.45 / 0.41 |
| open_state | 0.01 / 0.42 / 0.80 | 0.01 / 0.13 / 0.89 | 0.00 / 0.38 / 0.57 | 0.01 / 0.52 / 0.76 |
| other | 0.03 / 0.50 / 0.72 | 0.03 / 0.13 / 0.55 | 0.04 / 0.61 / 0.78 | 0.07 / 0.44 / 0.79 |
| gate steps | 6588 | 5110 | 5446 | 4378 |

### WM diagnosis vs environment-derived diagnosis (wmrepair_wm14)

* category agreement: 0.19; repair-action agreement (both exist): 0.32
* correct diagnosis (n=1024): executed admissible 0.60, recurs 0.49, repair adopted 0.37
* incorrect diagnosis (n=4422): executed admissible 0.46, recurs 0.64, repair adopted 0.31
* episodes with mostly correct diagnoses: SR 62.5% (n=248); mostly incorrect: SR 44.0% (n=798) -- correlational

Most frequent (environment category -> WM category): not_at->not_at 561, not_at->other 541, not_at->absent 464, holding_other->other 402, holding_other->not_at 357, already_at->closed 347, absent->not_at 309, not_at->not_holding 240, absent->absent 213, absent->other 212


