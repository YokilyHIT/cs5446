# Episode summary: dev140_3reps

Paired task set: 140 tasks. Reference arm: `none`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 3 | 19.0% | 18.6%–19.3% | — | — | 35.3% | — | 26.48 | 93.9% | 0.0% | — | 0.00 | 26.48 | 20,680 | 1,578 | 87.11 |
| rethink | 3 | 19.0% | 17.9%–20.0% | -0.0 [-3.8, +4.0] | 1.00 (7/7), 1.00 (6/5), 1.00 (9/10) | 39.0% | +3.7 [+0.2, +7.3] | 26.47 | 92.3% | 0.0% | 42.2% | 0.00 | 52.93 | 42,437 | 3,208 | 172 |
| always | 3 | 22.6% | 20.7%–23.6% | +3.6 [-0.7, +7.9] | 0.26 (7/13), 0.12 (4/11), 0.77 (5/7) | 40.6% | +5.3 [+1.8, +9.0] | 25.60 | 93.1% | 100.0% | 25.3% | 25.60 | 51.20 | 57,220 | 3,835 | 198 |
| selective | 3 | 18.1% | 16.4%–19.3% | -1.0 [-3.6, +1.4] | 1.00 (4/4), 1.00 (4/4), 0.39 (8/4) | 38.5% | +3.2 [+0.5, +6.0] | 26.50 | 92.7% | 28.9% | 30.5% | 26.50 | 34.14 | 43,055 | 2,979 | 164 |
| random_post | 3 | 19.0% | 17.1%–20.7% | +0.0 [-2.9, +2.9] | 0.58 (8/5), 1.00 (6/7), 0.75 (4/6) | 38.2% | +2.9 [+0.4, +5.5] | 26.39 | 92.4% | 27.0% | 27.2% | 26.39 | 33.52 | 41,626 | 2,950 | 162 |
| random_pre | 3 | 21.7% | 20.7%–22.9% | +2.6 [-0.5, +6.0] | 0.27 (4/9), 0.51 (3/6), 0.55 (4/7) | 38.2% | +2.9 [+0.4, +5.6] | 26.15 | 93.5% | 27.1% | 28.1% | 7.10 | 33.25 | 30,401 | 2,162 | 120 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 11 (7.9%) |
| rethink | 22 (15.7%) |
| always | 15 (10.7%) |
| selective | 14 (10.0%) |
| random_post | 16 (11.4%) |
| random_pre | 18 (12.9%) |

## SR by task type (mean over reps)

| task type | n | none | rethink | always | selective | random_post | random_pre |
|---|---:|---:|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 13 | 23.1% | 17.9% | 25.6% | 17.9% | 23.1% | 17.9% |
| pick_and_place_simple | 35 | 41.0% | 44.8% | 47.6% | 46.7% | 42.9% | 46.7% |
| pick_clean_then_place_in_recep | 27 | 2.5% | 4.9% | 6.2% | 1.2% | 2.5% | 4.9% |
| pick_cool_then_place_in_recep | 25 | 8.0% | 12.0% | 9.3% | 2.7% | 4.0% | 4.0% |
| pick_heat_then_place_in_recep | 16 | 20.8% | 10.4% | 18.8% | 14.6% | 18.8% | 22.9% |
| pick_two_obj_and_place | 24 | 13.9% | 11.1% | 19.4% | 13.9% | 16.7% | 23.6% |
