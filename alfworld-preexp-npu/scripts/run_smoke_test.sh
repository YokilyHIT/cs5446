#!/usr/bin/env bash
# Spec section 6 + section 38 steps 5-8: mandatory smoke tests that MUST pass
# before any full-scale run. Run this from the project root, with the vLLM
# server already up (scripts/start_vllm_npu.sh) and ALFWorld installed
# (scripts/setup_env_npu.sh).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "== Step 0: ALFWorld API assumptions =="
python scripts/inspect_alfworld_api.py

echo ""
echo "== Step 1: unit tests that don't need a full pipeline run =="
python -m pytest preexperiments/tests/test_llm_client.py preexperiments/tests/test_alfworld_env.py preexperiments/tests/test_replay.py -v

echo ""
echo "== Step 2: 10-episode baseline smoke test (5 train + 5 eval_in_distribution) =="
python -m preexperiments.failure_selection.collect_failures --max_episodes 5 --output_file results/_smoke_A_failures_raw.jsonl
python - <<'PY'
from preexperiments.common.alfworld_runner import ALFWorldEnvAdapter, reset_and_attach, rollout
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import load_yaml_config, new_run_id
from preexperiments.common.alfworld_runner import build_single_game_adapter, extract_task_id
from preexperiments.failure_selection._common import extract_goal

config = load_yaml_config("preexperiments/configs/preexperiment.yaml")
llm = load_client_from_config(config)
probe = ALFWorldEnvAdapter(config, config["splits"]["evaluation"])
game_files = sorted(probe.game_files)[:5]

successes = 0
for gf in game_files:
    adapter = build_single_game_adapter(config, config["splits"]["evaluation"], gf)
    obs, info = reset_and_attach(adapter)
    goal = extract_goal(obs, info)
    result = rollout(
        adapter, llm=llm, config=config, run_id=new_run_id("smokeB"),
        task_id=extract_task_id(gf), game_id_or_path=gf,
        split=config["splits"]["evaluation"], seed=13, goal=goal, observation=obs,
    )
    print(f"eval episode {gf}: success={result.success} steps={result.steps}")
    successes += int(result.success)

print(f"eval_in_distribution smoke test: {successes}/{len(game_files)} succeeded")
assert len(game_files) == 5, "expected 5 eval_in_distribution smoke episodes"
PY

echo ""
echo "== Step 3: deterministic replay unit test (mandatory gate, spec section 39) =="
python -m pytest preexperiments/tests/test_replay.py -v

echo ""
echo "== Step 4: Experiment B mini-smoke-test (10 decision points) =="
python -m preexperiments.world_model_utility.collect_decision_points
python -m preexperiments.world_model_utility.generate_foresight
python -m preexperiments.world_model_utility.build_counterfactual_pairs --max_points 10

echo ""
echo "== Step 5: Experiment A mini-smoke-test (a handful of failures, capped at 3 evaluated) =="
echo "   (this intentionally (re)writes the DEFAULT results/A_failures_raw.jsonl etc. --"
echo "    scripts/run_experiment_A.sh will overwrite these with the full-scale run later)"
python -m preexperiments.failure_selection.collect_failures --max_episodes 10
python -m preexperiments.failure_selection.extract_lessons
python -m preexperiments.failure_selection.select_related_tasks
python -m preexperiments.failure_selection.evaluate_single_lessons --max_failures 3

echo ""
echo "All smoke tests passed. Safe to proceed to scripts/run_experiment_A.sh and scripts/run_experiment_B.sh."
