"""Reproduce the complete D0 development description from portable evidence."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import math
from pathlib import Path
import platform

from analyze_d0_snapshot import (
    ROOT, analyze, select_cases, summarize_sensitivity, file_binding,
    implementation_bindings, read, require, verify_seal, seal, write_new,
)
from analysis_metrics import (
    _denominator, _pool, _relation, _ranking, weighted_quantile_memberships,
    UTILITY_PAIRS, BUDGET_BINS,
)


def summarize_subset(rows):
    """Use frozen metric primitives on a named subset; never change J or k_j."""
    core = [r for r in rows if r['core_A_eligible'] is True]
    unknown = [r for r in rows if r['core_A_eligible'] is None]
    paired_accuracy = [r for r in rows if r['confidence_accuracy_eligible']]
    relationships = {'confidence_accuracy': {}, 'accuracy_observed_U': {}}
    for quality in ('EM', 'token_F1'):
        relationships['confidence_accuracy'][quality] = _relation(
            paired_accuracy, lambda r: r['mean_logprob'], lambda r, q=quality: r[q], core)
        relationships['accuracy_observed_U'][quality] = {}
        for utility in UTILITY_PAIRS:
            paired = [r for r in paired_accuracy if r['observed_U'][utility] is not None]
            relationships['accuracy_observed_U'][quality][utility] = _relation(
                paired, lambda r, q=quality: r[q],
                lambda r, u=utility: r['observed_U'][u], paired_accuracy)
    membership = weighted_quantile_memberships(
        [r['mean_logprob'] for r in core], [r['statistical_weight'] for r in core])
    bins = []
    for b in range(4):
        fractional = []
        for row, probabilities in zip(core, membership['memberships']):
            if probabilities[b] > 0:
                item = deepcopy(row)
                item['statistical_weight'] *= probabilities[b]
                fractional.append(item)
        bins.append({'bin': b + 1, 'order': 'descending_mean_logprob',
                     'target_qualified_mass': .25, 'summary': _pool(fractional, bool(unknown))})
    return {
        'denominator': _denominator(rows),
        'aggregate': {'all_planned': _pool(rows), 'core_A': _pool(core, bool(unknown))},
        'relationships': relationships, 'confidence_bins': bins,
        'by_menu': {label: {'all_planned': _pool([r for r in rows if r['draft_in_visible_menu'] is value]),
                           'core_A': _pool([r for r in core if r['draft_in_visible_menu'] is value], bool(unknown))}
                    for value, label in ((True, 'inside'), (False, 'outside'), (None, 'unknown'))},
        'by_budget': {label: {'bounds_inclusive': list(bounds),
            'all_planned': _pool([r for r in rows if bounds[0] <= r['remaining_budget'] <= bounds[1]]),
            'core_A': _pool([r for r in core if bounds[0] <= r['remaining_budget'] <= bounds[1]], bool(unknown))}
            for label, bounds in BUDGET_BINS.items()},
        'ranking_diagnostics': {name: _ranking(core, field, target_incomplete=bool(unknown))
            for name, field in (('confidence', 'mean_logprob'), ('menu_outside_first', 'menu_outside_priority'),
                                ('prediction_length_longer', 'prediction_token_count'))},
    }


def cross_job_sensitivity(dataset, metrics, evidence):
    require(evidence['snapshot_content_sha256'] == dataset['sha256'], 'Identity evidence is for a different snapshot')
    identities = {(r['canonical_game_id'], r['state_id']): r for r in evidence['states']}
    rows = metrics['point_metrics']
    require(len(identities) == len(evidence['states']) == len(rows), 'Identity evidence has duplicate or missing states')
    require(set(identities) == {(r['canonical_game_id'], r['state_id']) for r in rows}, 'Identity membership differs')
    groups = {label: [] for label in ('false', 'true', 'unknown', 'not_applicable')}
    for row in rows:
        status = identities[(row['canonical_game_id'], row['state_id'])]['status']
        require(status in groups, 'Unknown job/service identity classification')
        groups[status].append(row)
    return {
        'scope': 'only states verified false from actual job_id/service_instance_id evidence',
        'main_analysis_unchanged': True,
        'categories': {label: {**_denominator(group), 'state_ids': [r['state_id'] for r in group]}
                       for label, group in groups.items()},
        'excluded_categories': ['true', 'unknown', 'not_applicable'],
        'weighting': 'original 1/(24*k_j) weights retained, then globally normalized within each metric intersection',
        'verified_false': summarize_subset(groups['false']),
        'evidence_content_sha256': evidence['sha256'],
    }


def integrity_summary(dataset, metrics, rollouts):
    """Only joins and missingness needed for the reported quantities."""
    groups = {g['rollout_id']: g for g in rollouts['groups']}
    require(len(groups) == len(rollouts['groups']), 'Duplicate physical rollout')
    referenced = set()
    for point in dataset['points']:
        for branch in point['branches'].values():
            rid = branch.get('rollout_id')
            if rid is not None:
                require(rid in groups, 'Branch rollout missing')
                referenced.add(rid)
    require(referenced == set(groups), 'Unlinked physical group')
    rows = metrics['point_metrics']
    source_failures = [p for p in rows if p['source_decision_status'] == 'source_draft_policy_failure']
    outcomes = {b: dict(Counter(str(p['Y'][b]) for p in rows)) for b in ('D', 'N', 'P')}
    differences = {u: dict(Counter(str(p['observed_U'][u]) for p in rows)) for u in UTILITY_PAIRS}
    actions = {u: {'changed': sum(p['action_changed'][u] == 1 for p in rows),
                   'comparable': sum(p['action_changed'][u] is not None for p in rows)} for u in UTILITY_PAIRS}
    return {
        'games': dataset['D0_game_count'], 'selected_states': len(rows), 'physical_groups': len(groups),
        'complete_DNP_states': sum(p['all_three_valid'] for p in rows),
        'source_draft_failures': _denominator(source_failures),
        'original_weight_mass': math.fsum(p['statistical_weight'] for p in rows),
        'branch_outcome_counts_unweighted': outcomes, 'observed_difference_counts_unweighted': differences,
        'action_changes_unweighted': actions,
        'D_check_status_counts': dict(Counter(p['D_check']['status'] for p in dataset['points'])),
        'D_new_mu_request_pairs': sum(p['D_check'].get('coverage', {}).get('new_mu_request_pairs', 0) for p in dataset['points']),
        'policy_failed_branches': [{'canonical_game_id': p['canonical_game_id'], 'state_id': p['state_id'],
                                   'branch': name, 'first_action': b.get('first_action'), 'raw_Y': b['raw_Y']}
                                  for p in dataset['points'] for name, b in p['branches'].items()
                                  if b['outcome_status'] == 'policy_failed'],
    }


def make_report(dataset, rollouts, identity, cost_evidence, accounting, np_evidence):
    from d0_paths import diagnostics, select_np_candidates
    from d0_costs import summarize_costs
    require(cost_evidence['np_evidence_content_sha256'] == np_evidence['sha256'],
            'Cost evidence binds different physical group evidence')
    metrics = analyze(dataset)
    cases = select_cases(dataset, metrics['point_metrics'])
    differing = {r['state_id'] for r in metrics['point_metrics']
                 if any(v is not None and v != 0 for v in r['observed_U'].values())}
    case_ids = {c['point']['state_id'] for c in cases['selected']}
    examples = [{'point': p, 'groups': [g for g in rollouts['groups'] if g['state_id'] == p['state_id']],
                 'fixed_case': p['state_id'] in case_ids, 'observed_difference_point': p['state_id'] in differing}
                for p in dataset['points'] if p['state_id'] in case_ids | differing]
    return {
        'schema_version': 1, 'kind': 'd0_complete_descriptive_report',
        'status': 'complete_development_description_with_explicit_evidence_limits',
        'full_D0_descriptive_report_complete': True,
        'collection_status': dataset['status'],
        'snapshot_content_sha256': dataset['sha256'],
        'integrity': integrity_summary(dataset, metrics, rollouts),
        'metrics': metrics,
        'cases': cases, 'path_examples': examples,
        'game_sensitivity': summarize_sensitivity(dataset, metrics['point_metrics']),
        'cross_job_sensitivity': cross_job_sensitivity(dataset, metrics, identity),
        'paths': diagnostics(dataset, rollouts, np_evidence),
        'costs': summarize_costs(cost_evidence, accounting),
        'np_candidates': select_np_candidates(dataset, rollouts, np_evidence, cost_evidence),
        'formal_inference': None, 'formal_C_bound': None, 'D1_size': None,
        'runtime_authorized': False, 'N_P_live_audit_completed': False,
        'new_model_calls': 0, 'new_environment_instances': 0, 'new_cluster_jobs': 0,
        'environment': {'python': platform.python_version(), 'implementation': platform.python_implementation()},
    }


def main(argv=None):
    from d0_report_markdown import render_markdown
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'gpu_analysis/data')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.out.resolve()
    markdown = output.with_suffix('.md')
    candidates = output.with_name(output.stem + '_np_candidates.json')
    require(output.suffix == '.json', '--out must end in .json')
    require(not any(p.exists() for p in (output, markdown, candidates)), 'Output exists; choose a new name')
    filenames = ('d0_snapshot.json', 'd0_rollout_summaries.json', 'd0_identity_evidence.json',
                 'd0_cost_evidence.json', 'final_accounting_summary.json', 'd0_np_evidence.json')
    inputs, bindings = [], []
    for name in filenames:
        path = args.data_dir.resolve() / name
        value = read(path)
        verify_seal(value)
        inputs.append(value)
        bindings.append({'name': name, **file_binding(path), 'content_sha256': value['sha256']})
    implementation = implementation_bindings()
    for relative in ('tools/build_d0_report.py', 'tools/d0_report_markdown.py', 'tools/d0_paths.py', 'tools/d0_costs.py',
                     'research_progress/2026-10-10-np-audit/sidecar/np_selection.py',
                     'research_progress/2026-10-10-np-audit/NP_AUDIT_SPEC.json'):
        implementation.append({'path': relative, **file_binding(ROOT / relative)})
    report = make_report(*inputs)
    report['input_files'] = bindings
    report['implementation_files'] = implementation
    report = seal(report)
    rendered = render_markdown(report)
    write_new(output, report)
    with markdown.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(rendered)
    write_new(candidates, report['np_candidates'])
    print(f"{report['status']}: {output}, {markdown} and {candidates}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
