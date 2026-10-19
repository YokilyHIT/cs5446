# Episode summary: legacy_sep14_dev140

Paired task set: 140 tasks. Reference arm: `none`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 1 | 17.9% | 17.9%–17.9% | — | — | 26.56 | — | 0.0% | — | 0.00 | — | — | — | — |
| always | 1 | 19.3% | 19.3%–19.3% | +1.4 [-3.6, +6.4] | 0.77 (5/7) | 26.09 | — | 100.0% | — | 26.09 | — | — | — | — |
| selective | 1 | 19.3% | 19.3%–19.3% | +1.4 [-3.6, +6.4] | 0.77 (5/7) | 26.58 | — | 27.6% | — | 26.58 | — | — | — | — |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## SR by task type (mean over reps)

| task type | n | none | always | selective |
|---|---:|---:|---:|---:|
| look_at_obj_in_light | 13 | 23.1% | 15.4% | 23.1% |
| pick_and_place_simple | 35 | 45.7% | 42.9% | 34.3% |
| pick_clean_then_place_in_recep | 27 | 3.7% | 3.7% | 3.7% |
| pick_cool_then_place_in_recep | 25 | 0.0% | 4.0% | 8.0% |
| pick_heat_then_place_in_recep | 16 | 12.5% | 25.0% | 18.8% |
| pick_two_obj_and_place | 24 | 12.5% | 16.7% | 25.0% |
