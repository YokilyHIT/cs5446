# Episode summary: interim_dev600

Paired task set: 147 tasks. Reference arm: `none`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 2 | 30.3% | 29.3%–31.3% | — | — | 46.1% | — | 23.90 | 69.9% | 0.0% | — | 0.00 | 23.90 | 31,314 | 1,342 | 76.79 |
| rethink | 2 | 30.3% | 29.9%–30.6% | +0.0 [-5.1, +5.1] | 1.00 (10/9), 1.00 (10/11) | 48.9% | +2.8 [-1.3, +6.9] | 24.27 | 72.2% | 0.0% | 56.9% | 0.00 | 48.53 | 65,018 | 2,983 | 168 |
| loop_hint | 2 | 32.7% | 30.6%–34.7% | +2.4 [-1.0, +6.1] | 1.00 (4/3), 0.12 (6/14) | 50.1% | +4.0 [+1.3, +6.8] | 23.52 | 72.3% | 0.0% | 67.7% | 0.00 | 35.58 | 49,191 | 2,101 | 120 |
| always | 2 | 29.3% | 28.6%–29.9% | -1.0 [-6.1, +4.1] | 0.50 (12/8), 1.00 (9/10) | 47.6% | +1.6 [-2.3, +5.4] | 24.35 | 73.4% | 100.0% | 40.4% | 24.35 | 48.70 | 76,950 | 3,459 | 195 |
| oracle | 2 | 35.7% | 34.7%–36.7% | +5.4 [+0.7, +10.2] | 0.10 (5/13), 0.10 (5/13) | 52.4% | +6.3 [+2.8, +10.0] | 22.76 | 75.8% | 100.0% | 46.3% | 0.00 | 45.52 | 60,720 | 2,536 | 155 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 11 (7.5%) |
| rethink | 17 (11.6%) |
| loop_hint | 16 (10.9%) |
| always | 10 (6.8%) |
| oracle | 9 (6.1%) |

## SR by task type (mean over reps)

| task type | n | none | rethink | loop_hint | always | oracle |
|---|---:|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 29 | 31.0% | 24.1% | 39.7% | 25.9% | 25.9% |
| pick_and_place_simple | 49 | 54.1% | 56.1% | 58.2% | 56.1% | 63.3% |
| pick_clean_then_place_in_recep | 20 | 10.0% | 17.5% | 7.5% | 17.5% | 15.0% |
| pick_cool_then_place_in_recep | 10 | 5.0% | 0.0% | 0.0% | 0.0% | 10.0% |
| pick_heat_then_place_in_recep | 18 | 36.1% | 36.1% | 36.1% | 22.2% | 55.6% |
| pick_two_obj_and_place | 21 | 0.0% | 0.0% | 0.0% | 2.4% | 0.0% |
