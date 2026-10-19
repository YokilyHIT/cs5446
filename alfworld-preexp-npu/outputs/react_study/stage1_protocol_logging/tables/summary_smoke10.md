# Episode summary: smoke10

Paired task set: 10 tasks. Reference arm: `none`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 2 | 30.0% | 30.0%–30.0% | — | — | 23.30 | 96.0% | 0.0% | — | 0.00 | 23.30 | 17,253 | 1,299 | 38.44 |
| rethink | 1 | 40.0% | 40.0%–40.0% | +10.0 [+0.0, +30.0] | 1.00 (0/1) | 23.10 | 81.4% | 0.0% | 29.0% | 0.00 | 46.20 | 34,283 | 2,490 | 69.50 |
| always | 1 | 40.0% | 40.0%–40.0% | +10.0 [+0.0, +30.0] | 1.00 (0/1) | 21.30 | 90.6% | 100.0% | 23.5% | 21.30 | 42.60 | 42,607 | 3,096 | 82.25 |
| selective | 1 | 30.0% | 30.0%–30.0% | +0.0 [+0.0, +0.0] | 1.00 (0/0) | 23.30 | 95.7% | 27.0% | 15.9% | 23.30 | 29.60 | 34,467 | 2,531 | 70.73 |
| random_post | 1 | 40.0% | 40.0%–40.0% | +10.0 [+0.0, +30.0] | 1.00 (0/1) | 21.90 | 90.0% | 28.8% | 22.2% | 21.90 | 28.20 | 32,483 | 2,446 | 67.67 |
| random_pre | 1 | 40.0% | 40.0%–40.0% | +10.0 [+0.0, +30.0] | 1.00 (0/1) | 22.90 | 90.4% | 28.8% | 33.3% | 6.60 | 29.50 | 25,712 | 1,809 | 52.73 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 0 (0.0%) |

## SR by task type (mean over reps)

| task type | n | none | rethink | always | selective | random_post | random_pre |
|---|---:|---:|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 1 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| pick_and_place_simple | 3 | 33.3% | 33.3% | 66.7% | 33.3% | 66.7% | 66.7% |
| pick_clean_then_place_in_recep | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| pick_cool_then_place_in_recep | 2 | 0.0% | 50.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| pick_heat_then_place_in_recep | 1 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| pick_two_obj_and_place | 1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
