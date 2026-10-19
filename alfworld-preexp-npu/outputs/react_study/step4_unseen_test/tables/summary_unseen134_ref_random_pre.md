# Episode summary: unseen134_ref_random_pre

Paired task set: 134 tasks. Reference arm: `random_pre`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 5 | 26.1% | 24.6%–26.9% | -3.2 [-7.4, +0.8] | 0.65 (11/8), 0.02 (13/3), 0.81 (10/8) | 41.4% | -2.9 [-5.9, +0.0] | 24.75 | 72.6% | 0.0% | — | 0.00 | 24.75 | 33,246 | 1,398 | 72.32 |
| loop_hint | 3 | 29.6% | 29.1%–30.6% | +0.2 [-4.0, +4.5] | 0.33 (6/11), 0.33 (11/6), 1.00 (8/9) | 44.0% | -0.2 [-3.7, +3.2] | 24.16 | 73.6% | 0.0% | 65.4% | 0.00 | 37.80 | 54,182 | 2,269 | 112 |
| always | 5 | 25.8% | 22.4%–27.6% | -3.5 [-7.4, +0.1] | 0.77 (7/5), 0.06 (14/5), 0.08 (12/4) | 42.3% | -1.9 [-4.6, +0.5] | 24.81 | 74.5% | 100.0% | 43.2% | 24.81 | 49.63 | 80,319 | 3,567 | 168 |
| oracle | 3 | 30.8% | 29.1%–33.6% | +1.5 [-3.2, +6.0] | 0.08 (6/15), 0.50 (12/8), 1.00 (9/10) | 46.6% | +2.4 [-0.4, +5.1] | 23.74 | 74.2% | 100.0% | 49.6% | 0.00 | 47.49 | 64,708 | 2,683 | 109 |
| selective_nomem | 3 | 28.4% | 26.9%–29.9% | -1.0 [-5.2, +3.2] | 1.00 (10/10), 0.24 (12/6), 0.82 (9/11) | 44.8% | +0.6 [-2.3, +3.5] | 24.38 | 77.0% | 37.4% | 26.2% | 24.38 | 48.75 | 77,730 | 3,477 | 109 |
| selective_em | 5 | 30.0% | 29.1%–31.3% | +0.6 [-2.7, +4.2] | 0.33 (6/11), 0.36 (12/7), 0.81 (8/10) | 45.4% | +1.2 [-1.4, +3.6] | 24.24 | 73.8% | 29.2% | 21.4% | 24.24 | 48.48 | 83,961 | 3,457 | 108 |
| random_pre | 3 | 29.4% | 26.9%–32.8% | — | — | 44.2% | — | 24.25 | 74.3% | 29.0% | 20.7% | 7.02 | 48.49 | 68,732 | 2,955 | 93.49 |
| gate_stuck | 3 | 29.1% | 25.4%–31.3% | -0.2 [-4.2, +3.7] | 0.33 (6/11), 0.05 (16/6), 0.50 (8/12) | 44.2% | -0.0 [-2.7, +2.6] | 24.35 | 76.1% | 55.9% | 35.4% | 13.61 | 48.71 | 74,110 | 3,157 | 151 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 23 (17.2%) |
| loop_hint | 19 (14.2%) |
| always | 23 (17.2%) |
| oracle | 27 (20.1%) |
| selective_nomem | 22 (16.4%) |
| selective_em | 27 (20.1%) |
| random_pre | 23 (17.2%) |
| gate_stuck | 23 (17.2%) |

## SR by task type (mean over reps)

| task type | n | none | loop_hint | always | oracle | selective_nomem | selective_em | random_pre | gate_stuck |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 18 | 42.2% | 46.3% | 37.8% | 35.2% | 25.9% | 37.8% | 37.0% | 38.9% |
| pick_and_place_simple | 24 | 41.7% | 45.8% | 44.2% | 52.8% | 48.6% | 51.7% | 54.2% | 52.8% |
| pick_clean_then_place_in_recep | 31 | 21.3% | 29.0% | 23.2% | 30.1% | 29.0% | 27.7% | 23.7% | 28.0% |
| pick_cool_then_place_in_recep | 21 | 11.4% | 9.5% | 8.6% | 12.7% | 15.9% | 13.3% | 17.5% | 9.5% |
| pick_heat_then_place_in_recep | 23 | 35.7% | 40.6% | 35.7% | 42.0% | 40.6% | 41.7% | 37.7% | 37.7% |
| pick_two_obj_and_place | 17 | 1.2% | 0.0% | 0.0% | 3.9% | 0.0% | 0.0% | 0.0% | 0.0% |
