# Episode summary: dev600_em

Paired task set: 600 tasks. Reference arm: `none`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 2 | 22.2% | 22.2%–22.2% | — | — | 41.2% | — | 25.79 | 66.4% | 0.0% | — | 0.00 | 25.79 | 35,821 | 1,464 | 85.65 |
| always | 2 | 22.8% | 22.5%–23.0% | +0.6 [-1.7, +2.9] | 0.90 (34/36), 0.64 (35/40) | 42.7% | +1.4 [-0.3, +3.2] | 25.71 | 70.6% | 100.0% | 42.6% | 25.71 | 51.42 | 85,616 | 3,678 | 200 |
| always_em | 2 | 22.3% | 21.3%–23.3% | +0.2 [-2.1, +2.4] | 0.66 (43/38), 0.49 (34/41) | 42.0% | +0.7 [-1.1, +2.6] | 25.82 | 71.4% | 100.0% | 47.1% | 25.82 | 51.64 | 93,663 | 3,680 | 162 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 58 (9.7%) |
| always | 53 (8.8%) |
| always_em | 70 (11.7%) |

## SR by task type (mean over reps)

| task type | n | none | always | always_em |
|---|---:|---:|---:|---:|
| look_at_obj_in_light | 100 | 28.0% | 30.5% | 29.0% |
| pick_and_place_simple | 100 | 48.5% | 49.0% | 50.0% |
| pick_clean_then_place_in_recep | 100 | 24.0% | 26.5% | 19.5% |
| pick_cool_then_place_in_recep | 100 | 5.5% | 7.0% | 7.0% |
| pick_heat_then_place_in_recep | 100 | 26.5% | 22.5% | 27.5% |
| pick_two_obj_and_place | 100 | 0.5% | 1.0% | 1.0% |
