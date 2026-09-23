#!/usr/bin/env bash
# Full-scale Experiment A (Selective Failure Learning), spec sections 7-16.
# Run scripts/run_smoke_test.sh successfully first.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

python -m preexperiments.failure_selection.collect_failures
python -m preexperiments.failure_selection.extract_lessons
python -m preexperiments.failure_selection.select_related_tasks
python -m preexperiments.failure_selection.evaluate_single_lessons
python -m preexperiments.failure_selection.score_failure_proxies
python -m preexperiments.failure_selection.evaluate_topk_vs_all
python -m preexperiments.failure_selection.analyze

echo "Experiment A complete. See results/A_summary.json and figures/A_*.png"
