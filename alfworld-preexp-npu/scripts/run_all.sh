#!/usr/bin/env bash
# Full pipeline, in the exact order spec section 38 mandates. Run on the NPU
# host after scripts/setup_env_npu.sh and scripts/start_vllm_npu.sh.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

bash scripts/run_smoke_test.sh
bash scripts/run_experiment_B.sh
bash scripts/run_experiment_A.sh
python scripts/generate_report.py
python -m pytest preexperiments/tests -q

echo ""
echo "Done. Final report: reports/preliminary_results.md"
