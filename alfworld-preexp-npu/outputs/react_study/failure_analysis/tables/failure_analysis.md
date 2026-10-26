# Failure analysis (dev460 x 2 reps, protocol v2-list)

## 1. Action validity and loops

| run | episodes | SR | inadmissible actions | 'Nothing happens'/step | repeated action/step | failures ending in a loop |
|---|---:|---:|---:|---:|---:|---:|
| 4B none | 920 | 11.7% | 31.3% | 0.313 | 0.557 | 0.74 |
| 4B oracle_every | 920 | 18.0% | 25.7% | 0.257 | 0.460 | 0.58 |
| 14B none | 920 | 56.4% | 17.4% | 0.174 | 0.257 | 0.37 |

## 2. Subgoal funnel (AgentBoard subgoals)

| run | saw target | picked it up | success | P(pick | seen) | P(success | picked) |
|---|---:|---:|---:|---:|---:|
| 4B none | 0.51 | 0.43 | 0.117 | 0.85 | 0.27 |
| 4B oracle_every | 0.56 | 0.48 | 0.180 | 0.86 | 0.37 |
| 14B none | 0.78 | 0.74 | 0.564 | 0.94 | 0.77 |

## 3. Failure after picking the target, by task type

| run | task type | episodes that picked | failed after pick |
|---|---|---:|---:|
| 4B none | look_at_obj_in_light | 51 | 0.45 |
| 4B none | pick_and_place_simple | 64 | 0.17 |
| 4B none | pick_clean_then_place_in_recep | 43 | 0.77 |
| 4B none | pick_cool_then_place_in_recep | 22 | 1.00 |
| 4B none | pick_heat_then_place_in_recep | 76 | 0.78 |
| 4B none | pick_two_obj_and_place | 139 | 1.00 |
| 4B oracle_every | look_at_obj_in_light | 63 | 0.37 |
| 4B oracle_every | pick_and_place_simple | 75 | 0.13 |
| 4B oracle_every | pick_clean_then_place_in_recep | 56 | 0.66 |
| 4B oracle_every | pick_cool_then_place_in_recep | 27 | 0.56 |
| 4B oracle_every | pick_heat_then_place_in_recep | 80 | 0.65 |
| 4B oracle_every | pick_two_obj_and_place | 144 | 0.99 |
| 14B none | look_at_obj_in_light | 130 | 0.18 |
| 14B none | pick_and_place_simple | 104 | 0.01 |
| 14B none | pick_clean_then_place_in_recep | 86 | 0.13 |
| 14B none | pick_cool_then_place_in_recep | 68 | 0.28 |
| 14B none | pick_heat_then_place_in_recep | 111 | 0.16 |
| 14B none | pick_two_obj_and_place | 179 | 0.48 |

## 4. heat / cool / clean attempts

**4B none**: 430 attempts, 84% not admissible
* clean / away / NOT admissible / nothing happens: 112
* heat / at appliance / NOT admissible / nothing happens: 89
* cool / away / NOT admissible / nothing happens: 80
* clean / at appliance / NOT admissible / nothing happens: 52
* heat / at appliance / admissible / ok: 30
* heat / away / NOT admissible / nothing happens: 23
* cool / at appliance / admissible / ok: 21
* clean / at appliance / admissible / ok: 19

**4B oracle_every**: 297 attempts, 58% not admissible
* clean / away / NOT admissible / nothing happens: 61
* heat / at appliance / NOT admissible / nothing happens: 53
* heat / at appliance / admissible / ok: 45
* clean / at appliance / admissible / ok: 41
* cool / at appliance / admissible / ok: 40
* cool / away / NOT admissible / nothing happens: 25
* heat / away / NOT admissible / nothing happens: 19
* clean / at appliance / NOT admissible / nothing happens: 8

**14B none**: 483 attempts, 30% not admissible
* heat / at appliance / admissible / ok: 128
* cool / at appliance / admissible / ok: 105
* clean / at appliance / admissible / ok: 103
* cool / away / NOT admissible / nothing happens: 43
* cool / at appliance / NOT admissible / nothing happens: 38
* heat / at appliance / NOT admissible / nothing happens: 36
* clean / at appliance / NOT admissible / nothing happens: 16
* clean / away / NOT admissible / nothing happens: 11

