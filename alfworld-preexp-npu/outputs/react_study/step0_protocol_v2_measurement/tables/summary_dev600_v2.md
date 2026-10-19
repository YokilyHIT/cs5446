# Episode summary: dev600_v2

Paired task set: 600 tasks. Reference arm: `none`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 2 | 22.2% | 22.2%–22.2% | — | — | 41.2% | — | 25.79 | 66.4% | 0.0% | — | 0.00 | 25.79 | 35,821 | 1,464 | 85.65 |
| always | 2 | 22.8% | 22.5%–23.0% | +0.6 [-1.7, +2.9] | 0.90 (34/36), 0.64 (35/40) | 42.7% | +1.4 [-0.3, +3.2] | 25.71 | 70.6% | 100.0% | 42.6% | 25.71 | 51.42 | 85,616 | 3,678 | 200 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 58 (9.7%) |
| always | 53 (8.8%) |

## SR by task type (mean over reps)

| task type | n | none | always |
|---|---:|---:|---:|
| look_at_obj_in_light | 100 | 28.0% | 30.5% |
| pick_and_place_simple | 100 | 48.5% | 49.0% |
| pick_clean_then_place_in_recep | 100 | 24.0% | 26.5% |
| pick_cool_then_place_in_recep | 100 | 5.5% | 7.0% |
| pick_heat_then_place_in_recep | 100 | 26.5% | 22.5% |
| pick_two_obj_and_place | 100 | 0.5% | 1.0% |
