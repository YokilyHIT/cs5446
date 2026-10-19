# Episode summary: eval460_ref_random_pre

Paired task set: 460 tasks. Reference arm: `random_pre`.

| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 2 | 11.7% | 11.3%–12.2% | -2.7 [-4.7, -1.0] | 0.06 (20/9), 0.01 (20/6) | 32.8% | -2.2 [-4.1, -0.5] | 27.39 | 66.4% | 0.0% | — | 0.00 | 27.39 | 38,396 | 1,569 | 91.91 |
| always | 2 | 14.6% | 14.3%–14.8% | +0.1 [-2.0, +2.2] | 1.00 (21/20), 0.86 (16/18) | 35.7% | +0.6 [-1.2, +2.5] | 27.12 | 70.2% | 100.0% | 43.7% | 27.12 | 54.25 | 91,080 | 3,898 | 211 |
| selective | 2 | 15.7% | 15.0%–16.3% | +1.2 [-0.8, +3.0] | 0.28 (17/25), 0.69 (11/14) | 35.5% | +0.4 [-1.4, +2.2] | 26.95 | 69.0% | 36.8% | 26.2% | 26.95 | 53.89 | 89,524 | 3,922 | 224 |
| random_pre | 2 | 14.5% | 14.3%–14.6% | — | — | 35.0% | — | 27.11 | 68.9% | 29.7% | 21.4% | 8.06 | 54.22 | 80,736 | 3,357 | 199 |
| gate_stuck | 2 | 15.5% | 14.8%–16.3% | +1.1 [-0.9, +3.0] | 1.00 (17/18), 0.16 (12/21) | 36.7% | +1.7 [-0.1, +3.4] | 26.87 | 69.1% | 56.2% | 35.9% | 15.09 | 53.74 | 85,223 | 3,496 | 206 |
| gate_learned | 2 | 14.3% | 14.1%–14.6% | -0.1 [-2.1, +1.8] | 1.00 (20/20), 1.00 (14/13) | 34.4% | -0.6 [-2.5, +1.2] | 27.13 | 67.3% | 41.2% | 24.7% | 11.19 | 54.26 | 82,929 | 3,457 | 204 |

McNemar cell format: p (ref-only successes / arm-only successes). ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). usage = steps where a WM prediction was shown to the planner / all steps. Δaction = second-pass action ≠ a_base, among steps with a second pass.

## Repeat stability

| arm | tasks whose success differs across reps |
|---|---:|
| none | 12 (2.6%) |
| always | 28 (6.1%) |
| selective | 30 (6.5%) |
| random_pre | 27 (5.9%) |
| gate_stuck | 23 (5.0%) |
| gate_learned | 20 (4.3%) |

## SR by task type (mean over reps)

| task type | n | none | always | selective | random_pre | gate_stuck | gate_learned |
|---|---:|---:|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 73 | 19.2% | 22.6% | 26.0% | 20.5% | 25.3% | 23.3% |
| pick_and_place_simple | 67 | 39.6% | 41.8% | 44.8% | 41.0% | 47.0% | 42.5% |
| pick_clean_then_place_in_recep | 71 | 7.0% | 12.7% | 11.3% | 12.7% | 11.3% | 12.7% |
| pick_cool_then_place_in_recep | 84 | 0.0% | 3.0% | 4.2% | 7.1% | 3.6% | 3.6% |
| pick_heat_then_place_in_recep | 72 | 11.8% | 13.9% | 15.3% | 11.8% | 13.2% | 9.7% |
| pick_two_obj_and_place | 93 | 0.0% | 1.1% | 0.5% | 0.5% | 1.1% | 1.6% |
