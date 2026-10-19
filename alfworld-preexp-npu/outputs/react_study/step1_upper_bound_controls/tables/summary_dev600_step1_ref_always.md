# Episode summary: dev600_step1_ref_always

Paired task set: 600 tasks. Reference arm: `always`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 2 | 22.2% | 22.2%–22.2% | -0.6 [-2.9, +1.7] | 0.90 (36/34), 0.64 (40/35) | 41.2% | -1.4 [-3.2, +0.3] | 25.79 | 66.4% | 0.0% | — | 0.00 | 25.79 | 35,821 | 1,464 | 85.65 |
| rethink | 2 | 19.8% | 19.7%–19.8% | -3.0 [-5.5, -0.6] | 0.07 (47/30), 0.07 (59/40) | 40.8% | -1.9 [-4.0, +0.1] | 26.45 | 68.7% | 0.0% | 58.0% | 0.00 | 52.90 | 74,510 | 3,269 | 180 |
| loop_hint | 2 | 22.5% | 21.2%–23.8% | -0.2 [-2.6, +2.2] | 0.43 (44/36), 0.66 (40/45) | 42.7% | +0.1 [-1.8, +1.9] | 25.72 | 67.8% | 0.0% | 68.1% | 0.00 | 40.11 | 58,568 | 2,443 | 139 |
| always | 2 | 22.8% | 22.5%–23.0% | — | — | 42.7% | — | 25.71 | 70.6% | 100.0% | 42.6% | 25.71 | 51.42 | 85,616 | 3,678 | 200 |
| oracle | 2 | 25.4% | 24.8%–26.0% | +2.7 [+0.2, +5.1] | 0.14 (31/45), 0.06 (33/51) | 44.6% | +1.9 [+0.1, +3.8] | 25.09 | 72.0% | 100.0% | 47.7% | 0.00 | 50.17 | 71,175 | 2,823 | 119 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 58 (9.7%) |
| rethink | 63 (10.5%) |
| loop_hint | 64 (10.7%) |
| always | 53 (8.8%) |
| oracle | 61 (10.2%) |

## SR by task type (mean over reps)

| task type | n | none | rethink | loop_hint | always | oracle |
|---|---:|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 100 | 28.0% | 17.0% | 28.0% | 30.5% | 31.5% |
| pick_and_place_simple | 100 | 48.5% | 50.5% | 51.0% | 49.0% | 54.5% |
| pick_clean_then_place_in_recep | 100 | 24.0% | 23.0% | 22.0% | 26.5% | 24.0% |
| pick_cool_then_place_in_recep | 100 | 5.5% | 8.0% | 8.0% | 7.0% | 11.0% |
| pick_heat_then_place_in_recep | 100 | 26.5% | 20.0% | 25.5% | 22.5% | 30.5% |
| pick_two_obj_and_place | 100 | 0.5% | 0.0% | 0.5% | 1.0% | 1.0% |
