from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import pytest

SIDE = Path(__file__).resolve().parents[1] / 'sidecar'
spec = importlib.util.spec_from_file_location('analysis_cases_tested', SIDE / 'analysis_cases.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
spec = importlib.util.spec_from_file_location('analysis_diagnostics_tested', SIDE / 'analysis_diagnostics.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def point(sid, ys=(0, 0, 0), em=0, *, same=False, failure=False, valid=True):
    p = {'canonical_game_id': 'train/game', 'state_id': sid,
         'source_decision_status': 'source_draft_policy_failure' if failure else 'ready',
         'draft_action': 'look', 'draft_in_visible_menu': False,
         'prediction_usable': not failure, 'confidence_scoreable': not failure,
         'D_reference': {'available': not failure, 'observation': 'A real response.',
                         'measurement_validity': 'valid' if valid else 'pending_review'},
         'D_check': {'status': 'passed' if valid and not failure else 'not_applicable'},
         'branches': {b: {'raw_Y': ys[i] if not failure else None,
                         'measurement_validity': 'valid' if valid and not failure else 'pending_review',
                         'outcome_status': 'complete' if not failure else 'not_applicable_source_draft_failure',
                         'first_action': 'look' if b == 'D' or same else 'north'}
                      for i, b in enumerate(('D', 'N', 'P'))}}
    m = {'canonical_game_id': p['canonical_game_id'], 'state_id': sid, 'EM': em}
    return p, m


def run(*pairs):
    return c.select_cases({'points': [p for p, _ in pairs]}, [m for _, m in pairs])


def test_exact_frozen_hash_uses_namespace_newline_and_no_seed():
    p, _ = point('状态1')
    raw = json.dumps(['train/game', '状态1'], ensure_ascii=False, separators=(',', ':'))
    assert c.order_key(p) == (hashlib.sha256((c.NAMESPACE + '\n' + raw).encode()).hexdigest(), raw)


def test_four_categories_and_source_failure_kept():
    pairs = [point('positive', (0, 0, 1)), point('negative', (1, 1, 0)),
             point('accurate', (0, 0, 0), 1), point('failure', failure=True)]
    result = run(*pairs)
    assert [s['point']['state_id'] for s in result['selected']] == ['positive', 'negative', 'accurate', 'failure']
    assert result['selected_count'] == 4 and not result['extra_sampling']
    assert result['selected'][3]['point']['branches']['D']['raw_Y'] is None


def test_input_order_cannot_change_selected_cases():
    pairs = [point(str(i), (0, 0, 1)) for i in range(10)]
    assert run(*pairs) == run(*reversed(pairs))
    assert run(*pairs)['selected'][0]['point']['state_id'] == min((p for p, _ in pairs), key=c.order_key)['state_id']


def test_same_action_third_category_can_overlap_positive_but_no_duplicate():
    result = run(point('both', (0, 0, 1), 1, same=True), point('second', (0, 0, 0), 1))
    assert [s['point']['state_id'] for s in result['selected']] == ['both', 'second']
    assert result['categories'][2]['already_selected_count'] == 1


def test_absent_category_does_not_backfill_or_invent():
    result = run(point('only'))
    assert result['selected'] == [] and result['fewer_than_three']
    assert all(x['reason'] == 'category_absent' for x in result['categories'])


def test_raw_positive_pending_does_not_become_positive_case():
    result = run(point('pending', (0, 0, 1), 1, valid=False))
    assert [s['category'] for s in result['selected']] == [c.CATEGORIES[3]]
    assert result['selected'][0]['point']['branches']['P']['raw_Y'] == 1


def test_technical_outcome_with_stale_validity_is_never_a_positive_case():
    p, m = point('technical', (0, 0, 1), 1)
    p['branches']['P']['outcome_status'] = 'technical_missing'
    result = run((p, m))
    assert [s['category'] for s in result['selected']] == [c.CATEGORIES[3]]


def test_policy_failed_zero_is_a_real_case_not_missing():
    p, m = point('policy', (1, 1, 0))
    p['branches']['P']['outcome_status'] = 'policy_failed'
    result = run((p, m))
    assert result['selected'][0]['category'] == c.CATEGORIES[1]
    assert result['categories'][3]['reason'] == 'all_eligible_already_selected'


@pytest.mark.parametrize('mode', ['duplicate_point', 'duplicate_metric', 'missing_metric', 'extra_metric'])
def test_identity_join_is_exact(mode):
    p, m = point('one')
    points, metrics = [p], [m]
    if mode == 'duplicate_point': points.append(copy.deepcopy(p))
    if mode == 'duplicate_metric': metrics.append(copy.deepcopy(m))
    if mode == 'missing_metric': metrics.clear()
    if mode == 'extra_metric': metrics.append({**m, 'state_id': 'extra'})
    with pytest.raises(ValueError): c.select_cases({'points': points}, metrics)


def test_behavior_is_counted_once_per_physical_group_and_uses_real_feedback():
    p, _ = point('s')
    p['D_check'] = {'status': 'passed', 'coverage': {'prefix_transitions': 1, 'transition_pairs': 4,
                   'new_mu_request_pairs': 3, 'matched_new_mu_completions': 3,
                   'model_reproducibility_covered': True}}
    steps = [{'action': a, 'phase': 'first_action' if i == 0 else 'continuation', 'next_obs': obs}
             for i, (a, obs) in enumerate([('look', 'You find a room.'), ('look', 'Nothing happens.'),
                                          ('look', 'Something changes.'), ('north', 'Nothing happens. ')])]
    group = {'game_id': 'train/game', 'state_id': 's', 'group_id': 'shared',
             'branches': ['D', 'N', 'P'], 'measurement_validity': 'valid', 'step_log': steps}
    result = d.summarize_diagnostics({'points': [p], 'cost_evidence': {'physical_groups': [group]}})
    behavior = result['physical_behavior']
    assert behavior['physical_groups'] == 1
    assert behavior['adjacent_mu_repetition'] == {'numerator': 2, 'denominator': 3, 'rate': 2/3}
    assert behavior['mu_exact_Nothing_happens']['numerator'] == 1
    assert behavior['groups'][0]['longest_executed_action_streak'] == 3
    assert result['D_first_observation_records'][0]['D_reference']['observation'] == 'A real response.'
    assert result['D_checks']['coverage']['new_mu_request_pairs'] == 3


def test_missing_checks_and_step_logs_are_missing_not_zero_evidence():
    p, _ = point('s')
    p['D_check'] = None
    group = {'game_id': 'train/game', 'state_id': 's', 'group_id': 'missing'}
    result = d.summarize_diagnostics({'points': [p], 'cost_evidence': {'physical_groups': [group]}})
    assert result['D_checks']['status_counts'] == {'not_run': 1}
    assert result['physical_behavior']['missing_step_logs'] == 1
    assert result['physical_behavior']['adjacent_mu_repetition']['rate'] is None


def test_diagnostic_duplicate_groups_rejected():
    group = {'game_id': 'g', 'state_id': 's', 'group_id': 'r', 'step_log': []}
    with pytest.raises(ValueError):
        d.summarize_diagnostics({'points': [], 'cost_evidence': {'physical_groups': [group, group]}})


def test_diagnostic_preserves_first_divergence_and_numeric_evidence():
    p, _ = point('s')
    p['D_check'] = {'status': 'diverged', 'first_divergence': {'kind': 'backend_output_divergence'},
                    'numeric_differences': [{'field': 'token_logprobs'}]}
    result = d.summarize_diagnostics({'points': [p]})
    assert result['D_checks']['first_divergences'][0]['numeric_differences'] == [{'field': 'token_logprobs'}]
