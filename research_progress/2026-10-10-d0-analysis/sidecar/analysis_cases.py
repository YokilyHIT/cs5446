"""Deterministic development cases from the original D0-var planned points."""
from __future__ import annotations

import copy
import hashlib
import json

NAMESPACE = 'cs5446-direction-b-cases-v1'
CATEGORIES = ('observed_admission_positive', 'observed_admission_negative',
              'EM1_and_same_PD_action_or_observed_admission_zero',
              'policy_failure_or_insufficient_evidence')


def identity(row):
    return row['canonical_game_id'], row['state_id']


def order_key(row):
    serialized = json.dumps(list(identity(row)), ensure_ascii=False, separators=(',', ':'))
    raw = NAMESPACE + '\n' + serialized
    return hashlib.sha256(raw.encode('utf-8')).hexdigest(), serialized


def _valid(branch):
    return (branch.get('outcome_status') in ('complete', 'policy_failed')
            and branch.get('measurement_validity') == 'valid'
            and type(branch.get('raw_Y')) is int and branch['raw_Y'] in (0, 1))


def deficiency_reasons(point):
    reasons = []
    if point.get('source_decision_status') == 'source_draft_policy_failure':
        reasons.append('source_draft_policy_failure')
    for name in ('D', 'N', 'P'):
        branch = point['branches'][name]
        if branch.get('outcome_status') == 'policy_failed' or branch.get('first_action_policy_failure'):
            reasons.append(name + '_policy_failure')
        if not _valid(branch):
            reasons.append(name + '_result_unavailable_or_unqualified')
    if not point.get('prediction_usable'):
        reasons.append('prediction_unavailable')
    elif not point.get('confidence_scoreable'):
        reasons.append('prediction_unscoreable')
    reference = point.get('D_reference') or {}
    if not reference.get('available') or reference.get('measurement_validity') != 'valid':
        reasons.append('D_reference_unavailable_or_unqualified')
    if (point.get('D_check') or {}).get('status') != 'passed':
        reasons.append('D_check_not_passed')
    return reasons


def select_cases(dataset, point_metrics):
    points = dataset['points']
    pool = {identity(p): p for p in points}
    metrics = {identity(p): p for p in point_metrics}
    if len(pool) != len(points) or len(metrics) != len(point_metrics) or set(pool) != set(metrics):
        raise ValueError('Cases require each original planned point exactly once')
    eligible = {name: [] for name in CATEGORIES}
    for key, point in pool.items():
        d, p = point['branches']['D'], point['branches']['P']
        valid = _valid(d) and _valid(p)
        difference = p['raw_Y'] - d['raw_Y'] if valid else None
        em = metrics[key].get('EM')
        same_action = (isinstance(d.get('first_action'), str) and bool(d['first_action'])
                       and d['first_action'] == p.get('first_action'))
        if difference is not None and difference > 0:
            eligible[CATEGORIES[0]].append(key)
        if difference is not None and difference < 0:
            eligible[CATEGORIES[1]].append(key)
        if valid and em == 1 and (same_action or difference == 0):
            eligible[CATEGORIES[2]].append(key)
        if deficiency_reasons(point):
            eligible[CATEGORIES[3]].append(key)
    selected, used, coverage = [], set(), []
    for category in CATEGORIES:
        ordered = sorted(eligible[category], key=lambda key: order_key(pool[key]))
        remaining = [key for key in ordered if key not in used]
        chosen = remaining[0] if remaining else None
        coverage.append({'category': category, 'eligible_count': len(ordered),
                         'already_selected_count': len(ordered) - len(remaining),
                         'selected': list(chosen) if chosen else None,
                         'reason': None if chosen else 'all_eligible_already_selected' if ordered else 'category_absent'})
        if chosen is not None:
            used.add(chosen)
            selected.append({'category': category, 'order_hash': order_key(pool[chosen])[0],
                             'hash_identity_json': order_key(pool[chosen])[1],
                             'point': copy.deepcopy(pool[chosen]),
                             'metrics': copy.deepcopy(metrics[chosen]),
                             'evidence_limitations': deficiency_reasons(pool[chosen])})
    return {'pool': 'all_original_D0_var_planned_points', 'pool_count': len(points),
            'namespace': NAMESPACE, 'category_order': list(CATEGORIES),
            'categories': coverage, 'selected': selected, 'selected_count': len(selected),
            'fewer_than_three': len(selected) < 3, 'extra_sampling': False,
            'interpretation': 'Observed examples only; no causal rescue/harm or population-frequency claim'}
