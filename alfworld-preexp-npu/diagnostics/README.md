# Diagnostics

Real-hardware measurements from `scripts/measure_baseline.py`, recorded here
as evidence for the spec-section-39 decision made in CHANGELOG-equivalent
notes (see `README_NPU_SETUP.md`'s prompt_style section): whether the
no-memory baseline success rate justified switching `sampling.prompt_style`
away from the default `"spec"`.

| file | run |
|---|---|
| `baseline_30.jsonl` | `sampling.prompt_style: spec`, `max_episode_steps: 30` (defaults) |
| `baseline_30_steps50.jsonl` | `spec` prompt, `max_episode_steps: 50` (tests spec section 39 remedy #2) |
| `baseline_30_adamem.jsonl` | `prompt_style: adamem_think`, `max_episode_steps: 30` (tests remedy #3) |

Each is 30 rows (one per evenly-strided `eval_in_distribution` task), fields:
`task_id, task_type, goal, success, steps, forced_actions,
longest_repeat_run, most_common_action, most_common_action_count,
distinct_actions`.

Measured on Ascend 910B3, Qwen3-4B-Instruct-2507, seed=13:

| | spec/30 | spec/50 | adamem_think/30 |
|---|---|---|---|
| success rate | 10.0% (3/30) | 13.3% (4/30) | **26.7% (8/30)** |
| looping episodes | 23% (7/30) | 27% (8/30) | 10% (3/30) |
| forced-action rate | 0.0% | 0.0% | 0.0% |
| mean steps | 27.9 | 45.4 | 24.9 |

Conclusion drawn from this: raising `max_episode_steps` was ruled out (62%
more compute for +1 success; successful episodes only needed 5-12 steps, so
the ceiling was never the bottleneck) and `prompt_style: adamem_think` was
adopted as the default remedy per spec section 39's third check ("reuse
AdaMEM's own no-memory prompt"). Re-run `scripts/measure_baseline.py` after
any change to the base model, prompt, or dataset version -- these numbers
are a property of that specific combination, not a fixed constant.
