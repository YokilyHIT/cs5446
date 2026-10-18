"""Targeted checks for real D0 denominators and the cross-job subset adapter."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_d0_report import analyze, read, summarize_subset, cross_job_sensitivity, integrity_summary


@pytest.fixture(scope='module')
def data():
    snapshot = read(ROOT / 'gpu_analysis/data/d0_snapshot.json')
    return snapshot, analyze(snapshot)


def test_frozen_metrics_and_full_subset_match_existing_checkpoint(data):
    _, metrics = data
    baseline = read(ROOT / 'gpu_analysis/checkpoints/d0_metrics.json')['metrics']
    assert metrics == baseline
    subset = summarize_subset(metrics['point_metrics'])
    for key in ('aggregate', 'relationships', 'confidence_bins', 'by_menu', 'by_budget', 'ranking_diagnostics'):
        assert subset[key] == metrics[key]


def test_real_missingness_and_physical_denominators(data):
    snapshot, metrics = data
    result = integrity_summary(snapshot, metrics, read(ROOT / 'gpu_analysis/data/d0_rollout_summaries.json'))
    assert (result['games'], result['selected_states'], result['complete_DNP_states'], result['physical_groups']) == (24, 71, 68, 117)
    assert result['source_draft_failures']['points'] == 3
    assert result['source_draft_failures']['original_weight_mass'] == pytest.approx(7/144)
    assert result['action_changes_unweighted']['revision'] == {'changed': 20, 'comparable': 67}
    assert metrics['aggregate']['all_planned']['branch_available']['N']['mean'] is None
    assert result['observed_difference_counts_unweighted']['info'] == {'0': 66, '1': 1, '-1': 1, 'None': 3}


def test_verified_false_only_preserves_original_weights(data):
    snapshot, metrics = data
    evidence = read(ROOT / 'gpu_analysis/data/d0_identity_evidence.json')
    report = cross_job_sensitivity(snapshot, metrics, evidence)
    assert {k: v['points'] for k, v in report['categories'].items()} == {
        'false': 67, 'true': 1, 'unknown': 0, 'not_applicable': 3}
    subset = report['verified_false']['aggregate']['all_planned']
    assert subset['denominator']['original_weight_mass'] == pytest.approx(15/16)
    assert subset['observed_U']['admission']['mean'] == pytest.approx(-2/135)
    assert sum(r['statistical_weight'] for r in metrics['point_metrics']) == pytest.approx(1)
