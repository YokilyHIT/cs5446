#!/usr/bin/env bash
# Full-scale Experiment B (Prediction Confidence vs Planning Utility), spec
# sections 17-34. Run scripts/run_smoke_test.sh successfully first -- in
# particular its deterministic-replay unit test (spec section 39: a failing
# replay test means this whole experiment must not run).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

python -m preexperiments.world_model_utility.collect_decision_points
python -m preexperiments.world_model_utility.generate_foresight
python -m preexperiments.world_model_utility.build_counterfactual_pairs
python -m preexperiments.world_model_utility.evaluate_planning_gain
python -m preexperiments.world_model_utility.evaluate_oracle_gate
python -m preexperiments.world_model_utility.analyze

echo "Experiment B complete. See results/B_summary.json and figures/B_*.png"
