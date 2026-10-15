"""Game-level dispersion and leave-one-game-out diagnostics, never intervals."""
from __future__ import annotations

import math


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _summary(rows):
    mass = math.fsum(r[2] for r in rows)
    if mass == 0:
        return {'n': 0, 'base_weight_mass': 0, 'mean': None, 'weighted_dispersion': None}
    mean = math.fsum(r[1] * r[2] for r in rows) / mass
    dispersion = math.fsum(r[2] * (r[1] - mean) ** 2 for r in rows) / mass
    return {'n': len(rows), 'base_weight_mass': mass, 'mean': mean, 'weighted_dispersion': dispersion}


def _mean_diagnostic(rows, games):
    overall = _summary(rows)
    by_game = [{'canonical_game_id': gid, **_summary([r for r in rows if r[0] == gid])} for gid in games]
    contributing = sum(x['n'] > 0 for x in by_game)
    removed = [{'removed_game': gid, **_summary([r for r in rows if r[0] != gid])} for gid in games]
    values = [r['mean'] for r in removed if r['mean'] is not None]
    reason = ('no_observed_values' if not rows else 'fewer_than_two_contributing_games' if contributing < 2
              else 'constant_observed_values' if len({r[1] for r in rows}) == 1 else None)
    return {'observed_subset': overall, 'contributing_games': contributing, 'by_game': by_game,
            'leave_one_game_out': removed,
            'leave_one_game_out_range': [min(values), max(values)] if values and reason is None else None,
            'range_unavailable_reason': reason}


def summarize_sensitivity(dataset, point_metrics):
    from analysis_metrics import weighted_correlation, _ranking
    games = [g['canonical_game_id'] for g in dataset['games']]
    if len(set(games)) != len(games):
        raise ValueError('Duplicate game in sensitivity denominator')
    if any(p['canonical_game_id'] not in games for p in point_metrics):
        raise ValueError('Unplanned game in sensitivity evidence')
    means, relationships = {}, {}
    for field in ('EM', 'token_F1', 'Y_D', 'Y_N', 'Y_P', 'U_admission', 'U_info', 'U_revision'):
        rows = []
        for p in point_metrics:
            if field.startswith('Y_'):
                value = p['Y'][field[-1]]
            elif field.startswith('U_'):
                value = p['observed_U'][field[2:]] if p['core_A_eligible'] is True else None
            else:
                value = p[field]
            if _finite(value):
                rows.append((p['canonical_game_id'], value, p['statistical_weight']))
        means[field] = {**_mean_diagnostic(rows, games),
                        'analysis_scope': 'core_A_valid_observed_pair' if field.startswith('U_') else
                                          'all_planned_valid_observed_branch' if field.startswith('Y_') else
                                          'usable_prediction_and_valid_D_reference'}
    targets = [('mean_logprob', quality, None) for quality in ('EM', 'token_F1')]
    targets += [(quality, 'U_' + utility, utility) for quality in ('EM', 'token_F1')
                for utility in ('admission', 'info', 'revision')]
    for xname, yname, utility in targets:
        rows = []
        for p in point_metrics:
            allowed = p['confidence_accuracy_eligible']
            x = p[xname]
            y = p[yname] if utility is None else p['observed_U'][utility]
            if allowed and _finite(x) and _finite(y):
                rows.append((p['canonical_game_id'], x, y, p['statistical_weight']))
        def corr(records):
            return weighted_correlation([r[1] for r in records], [r[2] for r in records], [r[3] for r in records])
        contributing = len({r[0] for r in rows})
        removed = [{'removed_game': gid, **corr([r for r in rows if r[0] != gid])} for gid in games]
        ranges = {}
        for method in ('pearson', 'spearman'):
            values = [r[method] for r in removed if r.get(method) is not None]
            ranges[method] = {'range': [min(values), max(values)] if values and contributing >= 2 else None,
                              'defined_omissions': len(values), 'undefined_omissions': len(games) - len(values)}
        relationships[xname + '__' + yname] = {'observed_subset': corr(rows), 'contributing_games': contributing,
                                               'leave_one_game_out': removed, 'sensitivity_ranges': ranges}
    core = [p for p in point_metrics if p['core_A_eligible'] is True]
    rankings = {}
    for name, field in (('confidence', 'mean_logprob'), ('menu_outside_first', 'menu_outside_priority'),
                        ('prediction_length_longer', 'prediction_token_count')):
        omissions = [{'removed_game': gid,
                      'ranking': _ranking([p for p in core if p['canonical_game_id'] != gid], field,
                                          target_incomplete=True)} for gid in games]
        ranges = {}
        for utility in ('admission', 'info', 'revision'):
            values = [o['ranking']['available_complete_case_G'][utility] for o in omissions
                      if o['ranking']['available_complete_case_G'][utility] is not None]
            reason = ('fewer_than_two_defined_omissions' if len(values) < 2 else
                      'constant_observed_descriptor' if len(set(values)) == 1 else None)
            ranges[utility] = {'range': [min(values), max(values)] if reason is None else None,
                               'undefined_reason': reason, 'defined_omissions': len(values)}
        rankings[name] = {'scope': 'available_common_core_A_cases; rerank and recondition after omitting a whole game',
                          'leave_one_game_out': omissions, 'sensitivity_ranges': ranges}
    return {'method': 'per_game_dispersion_and_leave_one_game_out',
            'collection_status': dataset['status'], 'planned_games': len(games),
            'scope': 'Available, qualified observations with original planned-point weights; exclusions remain in main denominators',
            'means': means, 'relationships': relationships, 'rankings': rankings,
            'confidence_intervals': None, 'p_values': None, 'ICC': None,
            'formal_G_C_acceptance': False,
            'limits': ['Sensitivity ranges are not confidence intervals or uncertainty bounds.',
                      'Between-point and between-game dispersion do not identify latent utility variance or r=1 sampling noise.',
                      'No correction for common job effects; Q5 simulation and formal inference remain pending.']}
