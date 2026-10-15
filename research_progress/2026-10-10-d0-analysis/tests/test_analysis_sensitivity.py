from pathlib import Path
import importlib.util
import sys
import pytest

SIDE = Path(__file__).resolve().parents[1] / 'sidecar'
sys.path.insert(0, str(SIDE))
spec = importlib.util.spec_from_file_location('analysis_sensitivity_tested', SIDE / 'analysis_sensitivity.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def row(gid, sid, value, weight, score=-1):
    return {'canonical_game_id': gid, 'state_id': sid, 'statistical_weight': weight,
            'EM': value, 'token_F1': value, 'mean_logprob': score,
            'Y': {'D': value, 'N': value, 'P': value},
            'observed_U': {'admission': value, 'info': value, 'revision': 0},
            'core_A_eligible': True, 'accuracy_eligible': True, 'confidence_accuracy_eligible': True,
            'all_three_valid': True, 'draft_in_visible_menu': True, 'menu_outside_priority': 0,
            'prediction_token_count': 3}


def dataset(*gids):
    return {'status': 'complete', 'games': [{'canonical_game_id': gid} for gid in gids]}


def test_unequal_retained_points_use_original_weights_and_game_omissions():
    records = [row('g1', 'a', 1, 1/6), row('g1', 'b', 0, 1/6), row('g2', 'c', 0, 1/2)]
    result = s.summarize_sensitivity(dataset('g1', 'g2'), records)
    m = result['means']['EM']
    assert m['observed_subset']['mean'] == pytest.approx(.2)
    assert m['by_game'][0]['mean'] == .5
    assert m['leave_one_game_out_range'] == [0, .5]
    assert [r['mean'] for r in m['leave_one_game_out']] == [0, .5]
    assert result['confidence_intervals'] is None and result['formal_G_C_acceptance'] is False


def test_all_zero_does_not_become_zero_width_interval():
    result = s.summarize_sensitivity(dataset('a', 'b'), [row('a', 's', 0, .5), row('b', 's', 0, .5)])
    assert result['means']['U_admission']['observed_subset']['mean'] == 0
    assert result['means']['U_admission']['leave_one_game_out_range'] is None
    assert result['means']['U_admission']['range_unavailable_reason'] == 'constant_observed_values'
    assert result['confidence_intervals'] is None
    assert result['relationships']['mean_logprob__EM']['observed_subset']['pearson'] is None


def test_partial_collection_and_empty_games_remain_visible():
    ds = {**dataset('a', 'b', 'c'), 'status': 'collection_incomplete'}
    result = s.summarize_sensitivity(ds, [row('a', 's', 1, 1/3)])
    assert result['collection_status'] == 'collection_incomplete'
    mean = result['means']['EM']
    assert len(mean['by_game']) == 3 and mean['contributing_games'] == 1
    assert mean['by_game'][1]['mean'] is None
    assert mean['leave_one_game_out_range'] is None


def test_correlations_recompute_ranks_after_dropping_whole_game():
    records = [row('a', '1', 0, .25, -3), row('a', '2', 1, .25, -1),
               row('b', '3', 1, .25, -2), row('b', '4', 0, .25, -1)]
    result = s.summarize_sensitivity(dataset('a', 'b'), records)
    relation = result['relationships']['mean_logprob__EM']
    assert relation['leave_one_game_out'][0]['spearman'] == pytest.approx(-1)
    assert relation['leave_one_game_out'][1]['spearman'] == pytest.approx(1)


def test_unknown_game_rejected():
    with pytest.raises(ValueError):
        s.summarize_sensitivity(dataset('a'), [row('b', 's', 1, 1)])


def test_G_sensitivity_reconditions_common_pool_and_recomputes_boundary():
    records = [row('a', '1', 1, .25, -1), row('a', '2', 0, .25, -2),
               row('b', '3', -1, .25, -1), row('b', '4', 0, .25, -2)]
    result = s.summarize_sensitivity(dataset('a', 'b'), records)
    rows = result['rankings']['confidence']['leave_one_game_out']
    assert rows[0]['ranking']['available_complete_case_G']['admission'] == -.25
    assert rows[1]['ranking']['available_complete_case_G']['admission'] == .25
    assert all(x['ranking']['weighted_coverage'] == .5 for x in rows)
    assert result['rankings']['confidence']['sensitivity_ranges']['admission']['range'] == [-.25, .25]
