# Real-WM repair (no rules) vs oracle repair, dev460 x 2 reps

## 4B planner arms (460 tasks)

| arm | SR | PR | legal | gate open/step | repair given | tokens/task |
|---|---:|---:|---:|---:|---:|---:|
| none | 11.7% | 32.8% | 0.69 | 0.00 | nan | 40.0k |
| always | 14.6% | 35.7% | 0.72 | 0.00 | nan | 95.0k |
| oracle_every | 18.0% | 38.7% | 0.74 | 0.00 | nan | 78.6k |
| inv_resample | 14.9% | 35.0% | 0.77 | 0.30 | nan | 52.9k |
| inv_fail | 18.3% | 36.7% | 0.85 | 0.27 | nan | 51.9k |
| inv_repair | 29.1% | 41.0% | 0.90 | 0.23 | 0.38 | 46.5k |
| inv_proj | 14.2% | 36.2% | 1.00 | 0.26 | nan | 54.5k |
| wmrepair_wm4 | 23.9% | 43.5% | 0.88 | 0.26 | 0.80 | 56.4k |
| wmrepair_wm14 | 26.5% | 42.2% | 0.89 | 0.25 | 0.81 | 54.1k |

### 4B wmrepair (Holm over 3), PR

| contrast | Δ pp [95% CI] |
|---|---|
| wmrepair_wm14 - inv_fail | +5.5 [+3.5, +7.4] p=0.000 Holm=0.000 |
| wmrepair_wm4 - inv_fail | +6.8 [+4.6, +9.1] p=0.000 Holm=0.000 |
| inv_repair - wmrepair_wm14 | -1.2 [-3.5, +0.9] p=0.271 Holm=0.271 |

Exploratory SR:

* wmrepair_wm14 - inv_fail: +8.3 [+5.5, +11.1] p=0.000
* wmrepair_wm4 - inv_fail: +5.7 [+2.6, +8.7] p=0.001
* inv_repair - wmrepair_wm14: +2.6 [-0.4, +5.7] p=0.097
* always - none: +2.8 [+0.7, +5.0] p=0.012
* oracle_every - none: +6.3 [+4.0, +8.7] p=0.000
* inv_resample - none: +3.2 [+1.4, +4.9] p=0.001
* inv_fail - none: +6.5 [+4.3, +8.8] p=0.000
* inv_repair - none: +17.4 [+14.2, +20.7] p=0.000
* inv_proj - none: +2.5 [+0.2, +4.8] p=0.032
* wmrepair_wm4 - none: +12.2 [+9.3, +15.1] p=0.000
* wmrepair_wm14 - none: +14.8 [+12.0, +17.7] p=0.000

## 14B planner arms (460 tasks)

| arm | SR | PR | legal | gate open/step | repair given | tokens/task |
|---|---:|---:|---:|---:|---:|---:|
| none | 56.4% | 68.9% | 0.83 | 0.00 | nan | 29.1k |
| R_r30 | 60.0% | 71.5% | 0.83 | 0.31 | nan | 36.9k |
| inv_fail | 63.9% | 73.3% | 0.90 | 0.16 | nan | 34.3k |
| inv_repair | 69.5% | 76.7% | 0.95 | 0.12 | 0.48 | 31.0k |
| wmrepair_wm14 | 64.9% | 74.1% | 0.93 | 0.14 | 0.70 | 36.3k |

### 14B planner (Holm over 2), PR

| contrast | Δ pp [95% CI] |
|---|---|
| inv_repair - none | +7.8 [+5.6, +10.1] p=0.000 Holm=0.000 |
| wmrepair_wm14 - inv_fail | +0.8 [-1.3, +2.9] p=0.443 Holm=0.443 |

Exploratory SR:

* inv_repair - none: +13.0 [+9.8, +16.4] p=0.000
* wmrepair_wm14 - inv_fail: +1.0 [-1.8, +3.9] p=0.527
* R_r30 - none: +3.6 [+0.8, +6.4] p=0.015
* inv_fail - none: +7.5 [+4.6, +10.5] p=0.000
* inv_repair - none: +13.0 [+9.7, +16.4] p=0.000
* wmrepair_wm14 - none: +8.5 [+5.5, +11.4] p=0.000

