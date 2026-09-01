"""Spec section 37, test 7: the analysis scripts can independently rebuild
the main statistics from the raw JSONL/CSV files alone.

We prove this operationally: re-run each experiment's analyze.py a second
time against the same on-disk raw files and check the regenerated summary
JSON is identical to the first run's. If analyze.py secretly depended on
in-memory state from an earlier script invocation rather than purely on
disk contents, a second cold run would not reproduce the same numbers.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _rerun_and_diff(module: str, summary_path: Path):
    if not summary_path.exists():
        pytest.skip(f"{summary_path} not found -- run the full {module} pipeline first.")

    before = json.loads(summary_path.read_text(encoding="utf-8"))

    proc = subprocess.run(
        [sys.executable, "-m", module],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"{module} failed on rebuild:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )

    after = json.loads(summary_path.read_text(encoding="utf-8"))
    assert before == after, (
        f"{module} produced different summary output on a second cold run from the "
        f"same raw files -- analysis is not purely a function of on-disk data.\n"
        f"before={before}\nafter={after}"
    )


def test_experiment_a_analysis_is_reproducible(results_dir):
    _rerun_and_diff(
        "preexperiments.failure_selection.analyze",
        results_dir / "A_summary.json",
    )


def test_experiment_b_analysis_is_reproducible(results_dir):
    _rerun_and_diff(
        "preexperiments.world_model_utility.analyze",
        results_dir / "B_summary.json",
    )
