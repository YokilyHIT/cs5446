"""Pure cost accounting over bound, observed D0 source/local audit records.

No model/environment calls or filesystem reads. Totals describe supplied evidence,
never total allocated GPU cost. Missing evidence remains unknown. Request, attempt,
rollout, recovery and runner wall times overlap and must not be added together.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
import ntpath


PLANNER_STAGES = frozenset({
    'draft_reasoning', 'draft_action', 'replan_reasoning', 'replan_action',
    'no_info_reasoning', 'no_info_action', 'mixed_react',
    'no_info_fallback_reasoning', 'no_info_fallback_action', 'candidate_scoring',
})
BUDGET_KEYS = ('logical_model_calls', 'http_attempts_recorded', 'http_attempts_charged',
               'http_unknown_calls', 'fresh_restores', 'policy_content_failure_calls',
               'total_wall_s')
RECOVERY_TIMES = ('build_s', 'reset_s', 'build_reset_s', 'replay_s', 'validation_s',
                  'restore_wall_s', 'cleanup_s', 'total_s')


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def _number(value, integer=False):
    allowed = (int,) if integer else (int, float)
    return type(value) in allowed and math.isfinite(value) and value >= 0


def _text(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(name + ' must be a nonempty string')
    return value


def _measure(values, *, integer=False):
    """Unknown total, plus a retained known subtotal and its record denominator."""
    known = [v for v in values if _number(v, integer)]
    subtotal = sum(known) if integer else math.fsum(known)
    complete = bool(values) and len(known) == len(values)
    return {'known_sum': subtotal, 'total_for_observed_records': subtotal if complete else None,
            'known_records': len(known), 'unknown_records': len(values)-len(known),
            'observed_records': len(values), 'complete_for_observed_records': complete,
            'status': 'complete' if complete else 'no_records' if not values else 'partial_unknown'}


def _unique(rows, key_fn, label):
    seen, result = {}, []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(label + ' records must be objects')
        key, canonical = key_fn(row), _canonical(row)
        if key in seen:
            if seen[key] != canonical:
                raise ValueError('Conflicting duplicate ' + label + ': ' + repr(key))
            continue
        seen[key] = canonical
        result.append(row)
    return result


def _call_key(row):
    if row.get('scope') not in {'source', 'local'}:
        raise ValueError('Unknown cost call scope')
    binding = row.get('audit_file')
    if not isinstance(binding, dict):
        raise ValueError('A bound original audit_file is required')
    path = ntpath.normcase(ntpath.normpath(_text(binding.get('path'), 'audit path')))
    return row['scope'], path, _text(row.get('call_id'), 'call_id')


def _failure(terminal, role):
    if terminal is None:
        return 'terminal_missing', False
    if terminal.get('event') == 'request_error' or terminal.get('failure_kind') == 'technical':
        return 'technical', False
    if terminal.get('event') != 'request_success':
        return 'unclassified', False
    if terminal.get('response_contract_status') != 'ok':
        return 'technical_or_unverified_contract', False
    response = terminal.get('response') or {}
    action = terminal.get('action') or {}
    failure = terminal.get('failure_kind')
    if failure == 'policy_content':
        # F is the frozen Planner format/content counter, not WM unavailability,
        # off-menu actions, empty Thought, or every historical parser rejection.
        issues = terminal.get('collection_issues')
        allowed_issue = 'action:' + str(action.get('status'))
        capture_ok = (terminal.get('response_contract_status') == 'ok'
                      and terminal.get('collection_status') == 'incomplete'
                      and isinstance(issues, list) and all(x == allowed_issue for x in issues)
                      and isinstance(response.get('raw_text'), str)
                      and response.get('raw_finish_reason') in {'stop', 'length'})
        is_format = (response.get('raw_finish_reason') == 'length'
                     or action.get('status') == 'action_parser_failed'
                     and action.get('error_type') == 'EnvActionParseError'
                     and action.get('parser_reason') in {'missing_action', 'multiple_actions', 'empty_action'})
        if not capture_ok:
            return 'technical_or_unverified_content_label', False
        return 'policy_content', bool(role == 'planner' and is_format)
    if failure is not None:
        return 'unclassified', False
    if terminal.get('collection_status') == 'complete':
        return 'no_audited_failure', False
    return 'technical_or_unclassified', False


def _call(row):
    start, terminal = row.get('start'), row.get('terminal')
    if not isinstance(start, dict) or start.get('event') != 'request_start':
        raise ValueError('Logical call requires its original request_start')
    if start.get('call_id') != row['call_id']:
        raise ValueError('Call identity disagrees with request_start')
    context = start.get('context')
    if not isinstance(context, dict):
        raise ValueError('Request context is missing')
    if terminal is not None and (not isinstance(terminal, dict)
                                or terminal.get('call_id') != row['call_id']
                                or terminal.get('event') not in {'request_success', 'request_error'}):
        raise ValueError('Terminal call identity or event is invalid')
    stage = context.get('stage')
    role = 'world_model' if stage == 'world_model' else 'planner' if stage in PLANNER_STAGES else 'unknown'
    audit = ((terminal.get('response') if terminal.get('event') == 'request_success'
              else terminal.get('request_audit')) if terminal is not None else None)
    audit = audit if isinstance(audit, dict) else {}
    attempts = audit.get('request_attempts')
    attempt_list = attempts if isinstance(attempts, list) and all(isinstance(a, dict) for a in attempts) else []
    problems = []
    ledger_complete = row.get('ledger_status') == 'complete_records'
    http_complete = (terminal is not None and bool(attempt_list) and ledger_complete
                     and all(a.get('attempt_index') == n and a.get('sdk_max_retries') == 0
                             and a.get('status') in {'ok', 'response_error', 'request_error'}
                             for n, a in enumerate(attempt_list, 1)))
    if not http_complete:
        problems.append('http_attempt_total_unverified')
    totals = audit.get('request_usage_totals')
    totals = totals if isinstance(totals, dict) else {}
    observed_attempt_count = len(attempt_list)
    if _number(totals.get('total_attempts'), True) and totals['total_attempts'] != observed_attempt_count:
        problems.append('usage_attempt_count_disagrees_with_ledger')
        http_complete = False
    derived = {}
    for field in ('prompt_tokens', 'completion_tokens'):
        values = [(a.get('usage') or {}).get(field) if isinstance(a.get('usage'), dict) else None
                  for a in attempt_list]
        known = sum(v for v in values if _number(v, True))
        declared = totals.get('known_' + field)
        if _number(declared, True):
            # Retain declared partial usage when no per-attempt values survived.
            if attempt_list and declared != known:
                problems.append('usage_' + field + '_subtotal_disagrees_with_attempts')
            known = declared
        derived[field] = known
    usage_complete = (http_complete and totals.get('complete') is True
                      and totals.get('total_attempts') == observed_attempt_count
                      and totals.get('attempts_without_complete_usage') == 0
                      and totals.get('attempts_with_complete_usage') == observed_attempt_count
                      and all(a.get('usage_status') == 'ok'
                              and all(_number((a.get('usage') or {}).get(k), True)
                                      for k in ('prompt_tokens', 'completion_tokens'))
                              for a in attempt_list)
                      and not any(p.startswith('usage_') for p in problems))
    if not usage_complete:
        problems.append('total_tokens_unknown_known_subtotal_retained')
    failure, format_failure = _failure(terminal, role)
    return {'scope': row['scope'], 'game_id': row.get('game_id'), 'state_id': row.get('state_id'),
            'group_id': row.get('group_id'), 'phase': row.get('phase', 'unknown'),
            'call_id': row['call_id'], 'role': role, 'decision_role': context.get('decision_role'),
            'stage': stage, 'audit_file': deepcopy(row['audit_file']), 'record_sha256': _digest(row),
            'ledger_status': row.get('ledger_status'), 'failure_category': failure,
            'planner_format_failure': format_failure, 'http_attempts_recorded': observed_attempt_count,
            'http_attempts_total': observed_attempt_count if http_complete else None,
            'http_count_complete': http_complete, 'prompt_tokens_known': derived['prompt_tokens'],
            'completion_tokens_known': derived['completion_tokens'],
            'prompt_tokens_total': derived['prompt_tokens'] if usage_complete else None,
            'completion_tokens_total': derived['completion_tokens'] if usage_complete else None,
            'token_usage_complete': usage_complete,
            'request_elapsed_s': audit.get('elapsed_wall_s') if _number(audit.get('elapsed_wall_s')) else None,
            'attempt_elapsed_s': _measure([a.get('elapsed_wall_s') for a in attempt_list]),
            'backoff_elapsed_s': _measure([a.get('backoff_elapsed_wall_s') for a in attempt_list]),
            'problems': problems}


def _calls_summary(records):
    result = {'logical_calls_observed': len(records),
              'http_attempts_recorded': sum(r['http_attempts_recorded'] for r in records),
              'http_unknown_calls': sum(not r['http_count_complete'] for r in records),
              'http_attempts_total': _measure([r['http_attempts_total'] for r in records], integer=True),
              'request_elapsed_s': _measure([r['request_elapsed_s'] for r in records]),
              'failure_categories': dict(sorted(Counter(r['failure_category'] for r in records).items())),
              'planner_format_failure_calls': sum(r['planner_format_failure'] for r in records)}
    for field in ('prompt_tokens', 'completion_tokens'):
        metric = _measure([r[field + '_total'] for r in records], integer=True)
        metric['known_sum'] = sum(r[field + '_known'] for r in records)
        result[field] = metric
    for field in ('attempt_elapsed_s', 'backoff_elapsed_s'):
        metric = _measure([r[field]['total_for_observed_records'] for r in records])
        metric['known_sum'] = math.fsum(r[field]['known_sum'] for r in records)
        result[field] = metric
    return result


def _groups_summary(rows):
    records = []
    for item in rows:
        rollout = item.get('rollout')
        if not isinstance(rollout, dict):
            raise ValueError('A physical group requires its original rollout')
        recovery = rollout.get('recovery') or {}
        times = recovery.get('timings') or {}
        evidence = recovery.get('evidence') or {}
        steps = rollout.get('step_log')
        records.append({'game_id': item['game_id'], 'state_id': item['state_id'],
                        'group_id': item['group_id'], 'branches': deepcopy(item.get('branches')),
                        'elapsed_s': item.get('elapsed_s'), 'new_mu_calls': item.get('new_mu_calls'),
                        'raw_Y': rollout.get('Y_study'), 'outcome_status': item.get('outcome_status'),
                        'measurement_validity': item.get('measurement_validity'),
                        'environment_step_attempts': rollout.get('environment_step_attempts'),
                        'recorded_transitions': len(steps) if isinstance(steps, list) else None,
                        'prefix_returned_steps': evidence.get('replayed_actions'),
                        'recovery_timings': deepcopy(times),
                        'rollout_binding': deepcopy(item.get('rollout_binding')),
                        'record_sha256': _digest(item)})
    return {'physical_groups_observed': len(records),
            'logical_branch_labels': sum(len(r['branches']) for r in records if isinstance(r['branches'], list)),
            'shared_physical_groups': sum(isinstance(r['branches'], list) and len(r['branches']) > 1 for r in records),
            'rollout_elapsed_s': _measure([r['elapsed_s'] for r in records]),
            'new_mu_logical_calls': _measure([r['new_mu_calls'] for r in records], integer=True),
            'environment_step_attempts': _measure([r['environment_step_attempts'] for r in records], integer=True),
            'recorded_transitions': _measure([r['recorded_transitions'] for r in records], integer=True),
            'prefix_returned_steps': _measure([r['prefix_returned_steps'] for r in records], integer=True),
            'recovery_timings': {k: _measure([r['recovery_timings'].get(k) for r in records]) for k in RECOVERY_TIMES},
            'records': records}


def summarize_costs(cost_evidence):
    """Summarize a dataset or its cost_evidence without choosing an outcome subset.

    Calls are keyed by scope/original ledger path/call_id; physical groups by
    game/state/group. Exact duplicate references count once; conflicts fail closed.
    Raw outcomes are retained as evidence and never recoded by cost accounting.
    """
    if isinstance(cost_evidence, dict) and 'cost_evidence' in cost_evidence:
        cost_evidence = cost_evidence['cost_evidence']
    if not isinstance(cost_evidence, dict) or any(not isinstance(cost_evidence.get(k), list)
                                               for k in ('calls', 'games', 'physical_groups')):
        raise ValueError('cost_evidence requires calls, games and physical_groups lists')
    calls = _unique(cost_evidence['calls'], _call_key, 'call')
    games = _unique(cost_evidence['games'], lambda r: _text(r.get('game_id'), 'game_id'), 'game')
    groups = _unique(cost_evidence['physical_groups'],
                     lambda r: tuple(_text(r.get(k), k) for k in ('game_id', 'state_id', 'group_id')),
                     'physical group')
    records = [_call(row) for row in calls]
    grouped = defaultdict(list)
    for record in records:
        grouped[(record['scope'], record['role'], record['phase'], record['decision_role'])].append(record)
    game_rows = []
    for game in games:
        budget = game.get('manifest_budget') or {}
        local_calls = [r for r in records if r['scope'] == 'local' and r['game_id'] == game['game_id']]
        reconciliation = {}
        for name, observed in (('logical_model_calls', len(local_calls)),
                               ('http_attempts_recorded', sum(r['http_attempts_recorded'] for r in local_calls)),
                               ('policy_content_failure_calls', sum(r['planner_format_failure'] for r in local_calls))):
            declared = budget.get(name)
            reconciliation[name] = {'manifest': declared, 'observed_ledger': observed,
                                    'matches': declared == observed if _number(declared, True) else None}
        game_rows.append({'game_id': game['game_id'], 'collection_status': game.get('collection_status'),
                          'manifest_budget': deepcopy(game.get('manifest_budget')),
                          'finalization': deepcopy(game.get('finalization')),
                          'manifest_binding': deepcopy(game.get('manifest_binding')),
                          'finalization_binding': deepcopy(game.get('finalization_binding')),
                          'local_budget_reconciliation': reconciliation})
    return {'schema_version': 1, 'kind': 'd0_observed_cost_evidence_summary',
            'scope': 'supplied_bound_source_and_local_records_not_total_gpu_cost',
            'input_evidence_sha256': _digest(cost_evidence),
            'duplicate_references_removed': {'calls': len(cost_evidence['calls'])-len(calls),
                                            'games': len(cost_evidence['games'])-len(games),
                                            'physical_groups': len(cost_evidence['physical_groups'])-len(groups)},
            'calls': {'all_observed': _calls_summary(records),
                      'by_scope': {s: _calls_summary([r for r in records if r['scope'] == s]) for s in ('source', 'local')},
                      'by_scope_role_phase': [dict(scope=k[0], role=k[1], phase=k[2], decision_role=k[3],
                                                   **_calls_summary(v))
                                              for k, v in sorted(grouped.items(), key=lambda item: _canonical(item[0]))],
                      'records': records},
            'games': {'planned_game_records': len(games),
                      'collection_status_counts': dict(sorted(Counter(str(g.get('collection_status')) for g in games).items())),
                      'local_manifest_budget': {k: _measure([(g.get('manifest_budget') or {}).get(k) for g in games],
                                                           integer=k != 'total_wall_s') for k in BUDGET_KEYS},
                      'records': game_rows},
            'physical_groups': _groups_summary(groups),
            'unavailable_totals': {'allocated_gpu_seconds': None, 'total_job_wall_s': None,
                                   'source_episode_environment_steps': None,
                                   'np_replay_cost': None, 'total_resource_cost': None},
            'interpretation': [
                'Known subtotals include failed calls and retries; missing cost is never imputed as zero.',
                'http_attempts_charged is a runner reservation account, distinct from recorded attempts.',
                'Scope totals cover supplied records only; missing games and unfinished ledgers prevent full-run cost claims.',
                'Shared branch labels do not multiply physical calls, rollouts, or recovery.',
                'Request, attempt, rollout, recovery and runner times overlap; do not add these categories.',
                'Recovery total_s includes restore plus cleanup and excludes yielded rollout work; build_reset_s is a component aggregate.',
                'No job allocation, startup, queue, archive, preflight, or N/P replay accounting is inferred from local request logs.',
            ]}
