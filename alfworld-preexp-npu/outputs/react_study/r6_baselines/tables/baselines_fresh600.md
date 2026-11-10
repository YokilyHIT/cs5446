# Frozen method vs recent-work baselines (fresh600 x 3, aligned models and tasks)

## 4B planner (600 tasks x 3 reps)

| arm | SR | PR | 14B calls / ep | tokens / ep (14B) |
|---|---:|---:|---:|---:|
| none | 20.9% | 39.4% | 0.0 | 37.6k (0.0k) |
| inv_fail | 28.3% | 44.8% | 0.0 | 46.9k (0.0k) |
| inv_rules | 33.3% | 46.8% | 0.0 | 44.4k (0.0k) |
| wmrepair_wm14 (frozen) | 36.2% | 49.0% | 5.3 | 47.8k (4.5k) |
| inv_repair | 36.7% | 47.5% | 0.0 | 42.5k (0.0k) |
| walle | 26.8% | 48.2% | 54.5 | 118.2k (33.0k) |
| walle_rules | 27.3% | 46.0% | 44.7 | 101.6k (32.6k) |
| inv_rpms | 37.2% | 48.1% | 0.0 | 42.6k (0.0k) |
| expel | 12.9% | 24.1% | 0.0 | 56.7k (0.0k) |
| inv_expel | 28.1% | 43.4% | 0.0 | 52.2k (0.0k) |
| selective | 22.1% | 41.4% | 25.9 | 88.7k (13.1k) |
| selective_em | 23.4% | 41.9% | 25.8 | 95.9k (20.9k) |

### Pre-registered family: recent-method baselines (Holm over 5), PR; SR exploratory

| contrast | ΔPR | non-inferior (−2 pp) | ΔSR |
|---|---|---|---|
| wmrepair_wm14 - walle | +0.7 [-1.5, +2.9] p=0.520 Holm=0.636 | yes | +9.4 [+6.5, +12.3] p=0.000 |
| wmrepair_wm14 - walle_rules | +2.9 [+0.9, +4.9] p=0.004 Holm=0.012 | yes | +8.9 [+6.2, +11.6] p=0.000 |
| wmrepair_wm14 - inv_rpms | +0.9 [-0.8, +2.6] p=0.318 Holm=0.636 | yes | -1.0 [-3.5, +1.5] p=0.430 |
| wmrepair_wm14 - expel | +24.9 [+22.2, +27.6] p=0.000 Holm=0.000 | yes | +23.3 [+20.3, +26.6] p=0.000 |
| wmrepair_wm14 - inv_expel | +5.6 [+3.9, +7.3] p=0.000 Holm=0.000 | yes | +8.2 [+5.9, +10.4] p=0.000 |

### Pre-registered family: WorldEvolver-style confidence gate (Holm over 2), PR; SR exploratory

| contrast | ΔPR | non-inferior (−2 pp) | ΔSR |
|---|---|---|---|
| wmrepair_wm14 - selective | +7.6 [+5.8, +9.4] p=0.000 Holm=0.000 | yes | +14.2 [+11.6, +16.8] p=0.000 |
| wmrepair_wm14 - selective_em | +7.0 [+5.3, +8.8] p=0.000 Holm=0.000 | yes | +12.8 [+10.4, +15.4] p=0.000 |

## 14B planner (600 tasks x 3 reps)

| arm | SR | PR | 14B calls / ep | tokens / ep (14B) |
|---|---:|---:|---:|---:|
| none | 59.1% | 70.3% | 0.0 | 27.5k (0.0k) |
| inv_fail | 63.9% | 72.8% | 0.0 | 32.8k (0.0k) |
| inv_rules | 68.8% | 76.0% | 0.0 | 30.5k (0.0k) |
| wmrepair_wm14 (frozen) | 65.9% | 74.3% | 3.0 | 33.7k (2.6k) |
| inv_repair | 69.5% | 76.6% | 0.0 | 29.4k (0.0k) |
| walle | 55.0% | 69.4% | 36.5 | 78.8k (21.8k) |
| walle_rules | 54.4% | 68.8% | 32.1 | 73.4k (23.5k) |
| inv_rpms | 70.7% | 77.0% | 0.0 | 29.5k (0.0k) |
| expel | 53.2% | 63.4% | 0.0 | 44.8k (0.0k) |
| inv_expel | 64.1% | 72.3% | 0.0 | 34.7k (0.0k) |
| selective | 61.0% | 72.2% | 19.0 | 64.4k (9.6k) |
| selective_em | 59.8% | 71.3% | 19.2 | 72.6k (17.0k) |

### Pre-registered family: recent-method baselines (Holm over 5), PR; SR exploratory

| contrast | ΔPR | non-inferior (−2 pp) | ΔSR |
|---|---|---|---|
| wmrepair_wm14 - walle | +4.9 [+2.8, +7.1] p=0.000 Holm=0.000 | yes | +10.9 [+7.7, +14.1] p=0.000 |
| wmrepair_wm14 - walle_rules | +5.5 [+3.7, +7.4] p=0.000 Holm=0.000 | yes | +11.4 [+8.6, +14.3] p=0.000 |
| wmrepair_wm14 - inv_rpms | -2.6 [-3.9, -1.3] p=0.000 Holm=0.000 | no | -4.8 [-6.8, -2.9] p=0.000 |
| wmrepair_wm14 - expel | +10.9 [+8.3, +13.5] p=0.000 Holm=0.000 | yes | +12.7 [+9.5, +16.1] p=0.000 |
| wmrepair_wm14 - inv_expel | +2.1 [+0.6, +3.6] p=0.006 Holm=0.006 | yes | +1.8 [-0.3, +4.1] p=0.103 |

### Pre-registered family: WorldEvolver-style confidence gate (Holm over 2), PR; SR exploratory

| contrast | ΔPR | non-inferior (−2 pp) | ΔSR |
|---|---|---|---|
| wmrepair_wm14 - selective | +2.1 [+0.6, +3.7] p=0.006 Holm=0.006 | yes | +4.9 [+2.5, +7.3] p=0.000 |
| wmrepair_wm14 - selective_em | +3.0 [+1.3, +4.7] p=0.000 Holm=0.001 | yes | +6.1 [+3.6, +8.7] p=0.000 |

