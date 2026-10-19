# Stage 1: Freeze the ReAct protocol, add cost fields, recover the original logs

Date: 2026-10-12. Code: `preexperiments/react_study/` (new package; existing `direction_b` scripts unchanged).

## 1. Frozen protocol (shared by every later arm and stage)

| Item | Setting |
|---|---|
| Environment | ALFWorld (TextWorld), dev set = `eval_in_distribution` (valid_seen, 140 tasks), seen many times; used for development only |
| Formal test set | `eval_out_of_distribution` (valid_unseen, 134 tasks), **untouched in this round**, kept for Stage 5 |
| Stage 3 states | `train` split (on-policy ReAct trajectories), disjoint from dev/test tasks |
| Planner / WM | both Qwen3-4B-Instruct-2507, vLLM 0.11 (Ascend), 8 instances (one per card, TP=1) |
| Decoding | temperature=0, top_p=0.5, seed=42; ReAct output cap 256 tokens, WM cap 256 tokens |
| ReAct | `ACTION_PROMPT_REACT` (Thought/Action), strict parsing: no fuzzy match. A non-admissible action is passed to the environment verbatim (the environment returns "Nothing happens.") |
| History / budget | most recent 50 turns; at most 30 steps per task; `help` hidden |
| Memory | off (no Episodic Memory) |
| Selective threshold | tau = 0.9997 (inherited from the previous run's train-side calibration; **not re-tuned on dev this round**) |
| Random gate | p = 0.276 = step-level usage of the previous dev run's Selective arm (fixed before Stage 2 started); u_t = sha256(gate_seed=2026, task_id, step) |

## 2. Cost fields (in every episode row and every step row)

Every LLM call goes through `MeteredLLM`, broken down by role, **including WM predictions that are discarded and failed requests**:

- `cost.{planner_base, planner_second, wm}.{calls, prompt_tokens, completion_tokens, latency_s, failed_calls}`
- `planner_second` = the second ReAct pass (foresight or rethink)
- `wall_s` per episode; per step: `wm_called / foresight_used / rethink_used / gate_u / wm_prediction / wm_confidence_logprob / base_raw / second_raw / action_admissible`

## 3. Results

### 3.1 Original logs recovered (`raw/legacy_sep14/`)
The plan said the raw JSONL could not be found. It actually exists at `data/episode_level_react_confidencefix.jsonl` and matches the summary JSON exactly (25/27/27; WM calls 3653/3721). Paired re-analysis (`tables/summary_legacy_sep14_dev140.md`):

| Arm | SR | ΔSR vs None [95% CI] | McNemar p (None-only / arm-only successes) |
|---|---:|---|---:|
| None | 17.9% | — | — |
| Always | 19.3% | +1.4 [−3.6, +6.4] | 0.77 (5/7) |
| Selective | 19.3% | +1.4 [−3.6, +6.4] | 0.77 (5/7) |

Selective's **step-level** usage is 27.6%; the old report's 25.3% is an episode-level average.

### 3.2 Cost statement corrected
Selective is a post-hoc filter: it **still calls the WM at every step**. It saves only part of the second planning calls. On the 10-task smoke test: Always ≈ 45.7k tokens/task, Selective ≈ 37.0k (−19%), None ≈ 18.6k. The old report's "saves 75% of WM calls" should be withdrawn. Stage 2 gives the full numbers.

### 3.3 Smoke test (10 tasks × 6 arms; `tables/summary_smoke10.md`, `figures/sr_vs_tokens_smoke10.png`)
All arms run without errors, the cost fields are non-empty, and the call counts match each arm's definition (rethink: second-pass calls = steps; random_pre: WM calls ≈ 0.28 × steps).

### 3.4 Determinism and protocol consistency (important)

| Comparison (same 10 tasks) | Identical trajectories | Success disagreements | First divergence step |
|---|---:|---:|---|
| New code none rep0 vs rep1 | 4/10 | 0 | 1, 3, 5, 5, 5, 6 |
| Legacy none vs new none | 5/10 | 0 | 1, 2, 3, 5, 6 |
| Legacy always vs new always | 4/10 | 0 | 1, 3, 4, 8, 13, 17 |
| Legacy selective vs new selective | 3/10 | 0 | 1, 2, 3, 3, 6, 10, 11 |

Conclusions:
1. **temperature=0 does not give deterministic outputs.** vLLM batched inference (different batch composition and kernel accumulation order) makes two runs of the same arm diverge after a few steps. Any single run therefore carries serving noise. Stage 2 uses 3 repeats; Stage 3 uses a B0 repeat branch to measure the noise floor.
2. New code vs legacy diverges at about the same rate as rep vs rep, with success fully agreeing, so the new code reproduces the original protocol.

### 3.5 Legal action rate
Smoke: none 96.0%, always 90.6%, **rethink 81.4%**. The illegal actions are the model itself inventing non-admissible actions (`examine sidetable 2`, `move cloth 2 to countertop 1`), not parsing failures. The second pass (especially rethink) is more prone to inventing actions. Stage 2 reports the legal action rate.

## 4. Not done in this stage
- Progress Rate needs AgentBoard's subgoal annotations, which are not available locally. It is **not** substituted with expert-action match; this is left until AgentBoard is integrated.
- Best-of-k curves: no attempt-level retry logic yet; deferred to Stage 5.

## 5. Directory layout
```
raw/legacy_sep14/                 original Sep-14 raw JSONL + summary (copies)
raw/eval_in_distribution/         smoke test: <arm>__rep<k>.jsonl + .config.json
tables/summary_*.{md,json}        per-arm summaries;  per_task_*.csv
tables/determinism_*.json, legacy_vs_new_*.json   trajectory consistency
figures/sr_vs_tokens_smoke10.png
logs/                             run logs
```
