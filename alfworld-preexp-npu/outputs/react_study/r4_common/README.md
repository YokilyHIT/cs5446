# Round 4 / Phase 0: infrastructure, data freeze, power (2026-10-19)

Plan: `/home/ma-user/work/5446/react_study_full_research_plan_20261019.md`. Code: `preexperiments/react_study/`.

## Serving
`start_servers_r4.sh` (N4=4): Qwen3-4B-Instruct-2507 on NPU 0-3 (ports 8001-8004), Qwen3-14B on NPU 4-7
(ports 8011-8014), bf16, max-model-len 32768, one card each. `env_r4.sh` exports the endpoints:
`PREEXP_API_BASES` = 4B (default WM, and planner unless `P14=1`), `PREEXP_WM_ALT_*` = 14B with
`enable_thinking: false` (role `wm_alt`), and with `P14=1` also `PREEXP_PLANNER_*` = 14B (same as direction E).
8014 failed once at start (KV-cache memory check) and came up on restart.

## Code changes
| file | change |
|---|---|
| `common.py` | stages 30-37 (round 4); role `wm_alt` routed to `PREEXP_WM_ALT_BASES/MODEL/CHAT_KWARGS` |
| `agent.py` | `WM_ROLE` (module-level, set per process); new arms `resample_pre` (RT: same prompt, T=0.7, seed `_seed(task,step,1)`), `resample0_pre` (R0: same prompt and decoding, T=0), `oracle_pre` (true next obs), all opened by `gate_uniform(gate_seed, task, step) < p` and NC when closed -> with `--gate_seed 2027 --p_gate 0.3` they open on exactly the steps of `random_pre_nc_p0.3`; episode rows gain `n_resampled`, `n_gate_open` |
| `run_episodes.py` | `--wm_role {wm,wm_alt}`; run config records endpoints/models |
| `branch_r4.py` (new) | same-state branching with arms base/R0/RT/W4/W14/oracle/oracle_struct, K continuations per distinct first action under the planner's own `none` policy, reuse of round-2 step-0c continuations (4B only, guarded), `--regen N` generation-noise draws, continuations parallel within a point |
| `analyze_p2.py`, `wm_capability_r4.py`, `analyze_p3.py`, `sample_points_r4.py` (new) | Phase 1-3 analysis and state sampling |

`branch_k.py`, `analyze_round3.py` etc. are unchanged; round 2/3 results remain reproducible.

Smoke tests (3 tasks per arm, 2 branch points, both planners) passed: routing verified from each run's config
(`env` block), the random gate opens on identical steps across arms, reused continuations are picked up.

## Data split (frozen, `raw/split_manifest.json`)
* "used" = every `trial_T...` id appearing anywhere under `cs5446-master/` or `STAGE1_PATCH/` (1010 train ids) + dev600.
* Fresh candidates: 2543 train tasks. Seed 20261019, stratified by type:
  * `fresh_test600_games.txt` (100 per type, sha256 `c265b268...`): **Phase 7 only**, after the G3 freeze.
  * `label_pool500_games.txt` (448 tasks; only 32 look_at_obj left): Phase 4/6 labels, router train/calibration.
* `branch140_games.txt`: the 140 step-0c tasks (dev600 minus dev460). 14B states for Phase 2(b) come from here,
  not from dev460, so later router training never touches dev-evaluation tasks.
* Test-set wording: "unseen task instances, same scene distribution (ALFWorld train split)"; valid_unseen 134 is
  a repeated out-of-distribution evaluation.

## Power (`tables/power_plan.json`)
From dev460 (2 reps): per-task PR difference sd ~0.15-0.20, dominated by run noise (sd_run ~0.15; task x arm sd
0-0.11), so reps and tasks trade off almost 1:1. 80% power for a 2 pp PR difference needs ~350-580 tasks at 3 reps
(210-440 at 5 reps). Decision: Phase 5 dev460 x 3 reps; Phase 7 fresh 600 x 3 reps; unseen134 x 5 reps.

## Holm family size
`round3_dev460.md` (48 comparisons) is authoritative for round 3; READMEs that say 44 predate the last 4 arms.
