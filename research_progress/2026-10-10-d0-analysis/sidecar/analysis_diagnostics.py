"""Descriptive replay coverage and physical-path behavior, without model calls."""
from __future__ import annotations

from collections import Counter
import math


def _ratio(num, den):
    return {'numerator': num, 'denominator': den, 'rate': num / den if den else None}


def summarize_diagnostics(dataset):
    points = dataset['points']
    checks = Counter((p.get('D_check') or {}).get('status', 'not_run') for p in points)
    divergences = []
    coverage = Counter()
    references = []
    for point in points:
        check = point.get('D_check') or {}
        cv = check.get('coverage') or {}
        for field in ('prefix_transitions', 'transition_pairs', 'new_mu_request_pairs', 'matched_new_mu_completions'):
            value = cv.get(field, 0)
            if type(value) is not int or value < 0:
                raise ValueError('Invalid replay coverage: ' + field)
            coverage[field] += value
        coverage['model_covered_states'] += cv.get('model_reproducibility_covered') is True
        if check.get('first_divergence') or check.get('numeric_differences'):
            divergences.append({'canonical_game_id': point['canonical_game_id'], 'state_id': point['state_id'],
                                'status': check.get('status'), 'first_divergence': check.get('first_divergence'),
                                'numeric_differences': check.get('numeric_differences', [])})
        references.append({'canonical_game_id': point['canonical_game_id'], 'state_id': point['state_id'],
                           'draft_action': point.get('draft_action'),
                           'draft_in_visible_menu': point.get('draft_in_visible_menu'),
                           'D_reference': point.get('D_reference'),
                           'measurement_validity': point['branches']['D'].get('measurement_validity')})
    paths = dataset.get('cost_evidence', {}).get('physical_groups', [])
    seen, rows = set(), []
    total_comparable = total_repeated = total_mu = total_nothing = 0
    missing_logs = 0
    for group in paths:
        key = group['game_id'], group['state_id'], group['group_id']
        if key in seen:
            raise ValueError('Duplicate physical group in behavior evidence')
        seen.add(key)
        steps = group.get('step_log', group.get('rollout', {}).get('step_log'))
        if not isinstance(steps, list):
            missing_logs += 1
            continue
        comparable = repeated = mu_steps = nothing = longest = streak = 0
        previous = None
        for step in steps:
            action = step.get('action')
            if not isinstance(action, str):
                raise ValueError('Behavior evidence lacks executed action')
            streak = streak + 1 if action == previous else 1
            longest = max(longest, streak)
            if step.get('phase') == 'continuation':
                mu_steps += 1
                nothing += step.get('next_obs') == 'Nothing happens.'
                if previous is not None:
                    comparable += 1
                    repeated += action == previous
            previous = action
        total_comparable += comparable
        total_repeated += repeated
        total_mu += mu_steps
        total_nothing += nothing
        rows.append({'game_id': key[0], 'state_id': key[1], 'group_id': key[2],
                     'branches': group.get('branches'), 'measurement_validity': group.get('measurement_validity'),
                     'executed_transitions': len(steps), 'executed_mu_transitions': mu_steps,
                     'adjacent_mu_repetition': _ratio(repeated, comparable),
                     'mu_exact_Nothing_happens': _ratio(nothing, mu_steps),
                     'longest_executed_action_streak': longest})
    def denominator(rows):
        return {'states': len(rows), 'games': len({p['canonical_game_id'] for p in rows}),
                'original_weight_mass': math.fsum(p.get('statistical_weight', 0) for p in rows)}
    def categories(getter):
        labels = sorted({str(getter(p)) for p in points})
        return {label: denominator([p for p in points if str(getter(p)) == label]) for label in labels}
    flow = {'planned': denominator(points),
            'source_decision_status': categories(lambda p: p.get('source_decision_status')),
            'local_confidence_event_exists': categories(lambda p: p.get('local_confidence_event_exists')),
            'prediction_usable': categories(lambda p: p.get('prediction_usable')),
            'confidence_scoreable': categories(lambda p: p.get('confidence_scoreable')),
            'WM_fallback': categories(lambda p: p.get('WM_fallback')),
            'reference_available': categories(lambda p: (p.get('D_reference') or {}).get('available')),
            'reference_validity': categories(lambda p: (p.get('D_reference') or {}).get('measurement_validity')),
            'branches': {b: {'outcome_status': categories(lambda p, b=b: p['branches'][b].get('outcome_status')),
                             'measurement_validity': categories(lambda p, b=b: p['branches'][b].get('measurement_validity'))}
                         for b in ('D', 'N', 'P')}}
    return {'qualification_and_failure_flow': flow,
            'raw_partial_rollout_evidence': dataset.get('raw_partial_rollout_evidence', []),
            'N_P_cross_job_check': {'status': 'not_supplied',
                                   'reason': 'This dataset contains D0-var source and local logs, not separate-job N/P receipts',
                                   'passed': False},
            'D_checks': {'planned': len(points), 'status_counts': dict(sorted(checks.items())),
                         'coverage': dict(coverage), 'first_divergences': divergences,
                         'scope': 'Selected D source paths only; cached draft is not a new model test'},
            'D_first_observation_records': references,
            'physical_behavior': {'physical_groups': len(paths), 'missing_step_logs': missing_logs,
                                  'groups': rows, 'adjacent_mu_repetition': _ratio(total_repeated, total_comparable),
                                  'mu_exact_Nothing_happens': _ratio(total_nothing, total_mu),
                                  'cached_first_action_boundary': 'First executed mu action is compared with cached first action; longest streak includes cached first action',
                                  'weights': 'Physical path counts, including observed partial paths; not state population weights',
                                  'interpretation': 'Behavior diagnostics do not establish a cause of utility outcomes'}}
