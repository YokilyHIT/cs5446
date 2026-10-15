"""Descriptive D0 metrics with original game/state weights and explicit loss.

No confidence intervals, hypothesis tests, true utility estimates, or C upper
bounds are produced. Source data remain unchanged. Text scoring executes the
hash-bound existing metrics implementation; no model or environment is used.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
import hashlib
import math
from pathlib import Path
from types import ModuleType

METRICS_SHA256 = "817d43d6d708abe5eff102020e6b19434e8c34ce4384e7d0881b856ac85c8c8b"
METRICS_PATH = Path(__file__).resolve().parents[3] / "alfworld-preexp-npu/preexperiments/direction_b/metrics.py"
_raw = METRICS_PATH.read_bytes()
if hashlib.sha256(_raw).hexdigest() != METRICS_SHA256:
    raise ImportError("Frozen text metric source hash differs")
_text = ModuleType("d0_bound_text_metrics")
exec(compile(_raw, str(METRICS_PATH), "exec"), _text.__dict__)
del _raw

BRANCHES = ("D", "N", "P")
UTILITY_PAIRS = {"admission": ("P", "D"), "info": ("P", "N"), "revision": ("N", "D")}
BUDGET_BINS = {"b_1_10": (1, 10), "b_11_20": (11, 20), "b_21_30": (21, 30)}


def require(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _vectors(values, weights):
    require(len(values) == len(weights), "Value/weight lengths differ")
    require(all(finite(v) for v in values) and all(finite(w) and w > 0 for w in weights),
            "Observed values must be finite and weights positive")


def weighted_mean(values, weights):
    _vectors(values, weights)
    return math.fsum(v*w for v, w in zip(values, weights))/math.fsum(weights) if values else None


def average_ranks(values):
    require(all(finite(v) for v in values), "Ranks require finite observations")
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks, left = [0.0]*len(values), 0
    while left < len(order):
        right = left+1
        while right < len(order) and values[order[right]] == values[order[left]]:
            right += 1
        rank = (left+1+right)/2
        for index in order[left:right]:
            ranks[index] = rank
        left = right
    return ranks


def _pearson(xs, ys, weights):
    # Scale before squaring; mean logprob can be close to zero or very negative.
    scale_x, scale_y = max(map(abs, xs)) or 1, max(map(abs, ys)) or 1
    x, y = [v/scale_x for v in xs], [v/scale_y for v in ys]
    mx, my = weighted_mean(x, weights), weighted_mean(y, weights)
    vx = math.fsum(w*(v-mx)**2 for v, w in zip(x, weights))
    vy = math.fsum(w*(v-my)**2 for v, w in zip(y, weights))
    if vx == 0 or vy == 0:
        return None
    covariance = math.fsum(w*(a-mx)*(b-my) for a, b, w in zip(x, y, weights))
    denominator = math.sqrt(vx)*math.sqrt(vy)
    return max(-1.0, min(1.0, covariance/denominator)) if denominator else None


def weighted_correlation(xs, ys, weights):
    """Weighted Pearson and weighted Pearson of ordinary average tie ranks.

    The latter is an explicitly defined exploratory Spearman-style statistic;
    neither has an inferential interval or a claim of monotonic-transform
    invariance for Pearson. Missing observations must be selected explicitly.
    """
    _vectors(xs, weights)
    _vectors(ys, weights)
    reason = "fewer_than_two_pairs" if len(xs) < 2 else (
        "constant_x_and_y" if len(set(xs)) == len(set(ys)) == 1 else
        "constant_x" if len(set(xs)) == 1 else "constant_y" if len(set(ys)) == 1 else None)
    pearson = None if reason else _pearson(xs, ys, weights)
    spearman = None if reason else _pearson(average_ranks(xs), average_ranks(ys), weights)
    if reason is None and (pearson is None or spearman is None):
        reason = "numerically_zero_variance"
    return {"pearson": pearson, "spearman": spearman,
        "status": "undefined" if reason else "descriptive", "undefined_reason": reason,
        "n": len(xs), "weight_mass": math.fsum(weights),
        "spearman_definition": "weighted_Pearson_of_unweighted_average_ranks",
        "confidence_interval": None, "p_value": None}


def weighted_quantile_memberships(scores, weights, bins=4):
    """Descending score bins; exact ties get equal fractional membership.

    Rational arithmetic on supplied binary float weights defines boundaries
    exactly; only returned probabilities/masses are converted to float.
    No outcome, identifier, or within-tie row order is used to break a tie.
    """
    _vectors(scores, weights)
    require(type(bins) is int and bins > 0, "bins must be positive integer")
    if not scores:
        return {"memberships": [], "groups": [], "bin_weight_mass": [0.0]*bins, "status": "empty"}
    raw = [Fraction(w) for w in weights]
    total = sum(raw)
    normalized = [w/total for w in raw]
    membership = [[Fraction(0)]*bins for _ in scores]
    groups, cumulative = [], Fraction(0)
    for score in sorted(set(scores), reverse=True):
        indices = [i for i, value in enumerate(scores) if value == score]
        mass = sum(normalized[i] for i in indices)
        fractions = [max(Fraction(0), min(cumulative+mass, Fraction(b+1, bins))
                        - max(cumulative, Fraction(b, bins)))/mass for b in range(bins)]
        for i in indices:
            membership[i] = fractions
        groups.append({"score": score, "count": len(indices), "weight_mass": float(mass),
                       "memberships": [float(f) for f in fractions]})
        cumulative += mass
    return {"memberships": [[float(f) for f in row] for row in membership], "groups": groups,
        "bin_weight_mass": [float(sum(normalized[i]*membership[i][b] for i in range(len(scores)))) for b in range(bins)],
        "status": "all_exactly_tied" if len(groups) == 1 else "descriptive",
        "tie_rule": "identical_fraction_for_every_member_of_an_exact_score_group"}


def text_accuracy(prediction, reference, *, usable=True, reference_valid=True):
    reason = ("prediction_not_usable" if usable is not True else
              "reference_not_valid" if reference_valid is not True else
              "prediction_missing_or_blank" if not isinstance(prediction, str) or not prediction.strip() else
              "reference_missing_or_blank" if not isinstance(reference, str) or not reference.strip() else None)
    return {"EM": None if reason else _text.exact_match(prediction, reference),
            "token_F1": None if reason else _text.token_f1(prediction, reference),
            "status": "unavailable" if reason else "descriptive", "reason": reason}


def _conjunction(a, b):
    return False if a is False or b is False else True if a is True and b is True else None


def _derive(point):
    require(point.get("prediction") is None or isinstance(point["prediction"], dict), "Invalid prediction record")
    require(point.get("D_reference") is None or isinstance(point["D_reference"], dict), "Invalid D reference")
    prediction = point.get("prediction") or {}
    usable, scoreable = point.get("prediction_usable"), point.get("confidence_scoreable")
    require(usable is None or type(usable) is bool, "Invalid prediction qualification")
    require(scoreable is None or type(scoreable) is bool, "Invalid confidence qualification")
    if usable is True:
        require(isinstance(prediction.get("wm_prediction"), str) and prediction["wm_prediction"].strip(),
                "Usable prediction lacks nonblank content")
    mean, exp_score = prediction.get("wm_mean_logprob"), prediction.get("wm_confidence_logprob")
    if scoreable is True:
        require(prediction.get("wm_confidence_scope") == "prediction_tokens_v2" and
                prediction.get("wm_confidence_status") == "ok" and finite(mean) and mean <= 0 and
                finite(exp_score) and 0 <= exp_score <= 1, "Scoreable prediction lacks frozen score evidence")
    reference = point.get("D_reference") or {}
    reference_valid = reference.get("available") is True and reference.get("measurement_validity") == "valid"
    accuracy = text_accuracy(prediction.get("wm_prediction"), reference.get("observation"),
                             usable=usable, reference_valid=reference_valid)
    raw_y, valid_y, branch_valid, actions = {}, {}, {}, {}
    for branch in BRANCHES:
        row = point["branches"][branch]
        raw_y[branch] = row.get("raw_Y")
        require(raw_y[branch] is None or type(raw_y[branch]) is int and raw_y[branch] in (0, 1), "Invalid raw Y")
        require(row.get("outcome_status") != "policy_failed" or raw_y[branch] in (None, 0), "Policy failure cannot have Y=1")
        branch_valid[branch] = (row.get("outcome_status") in ("complete", "policy_failed")
            and row.get("measurement_validity") == "valid" and raw_y[branch] is not None)
        valid_y[branch] = raw_y[branch] if branch_valid[branch] else None
        action = row.get("first_action")
        require(action is None or isinstance(action, str) and action, "Invalid parsed first action")
        actions[branch] = action
    if point["source_decision_status"] == "source_draft_policy_failure":
        require(usable is False and scoreable is False and not prediction and all(v is None for v in raw_y.values()),
                "Source draft failure cannot manufacture a confidence event or local Y")
    observed, raw_observed, changed = {}, {}, {}
    for name, (a, b) in UTILITY_PAIRS.items():
        observed[name] = valid_y[a]-valid_y[b] if valid_y[a] is not None and valid_y[b] is not None else None
        raw_observed[name] = raw_y[a]-raw_y[b] if raw_y[a] is not None and raw_y[b] is not None else None
        changed[name] = int(actions[a] != actions[b]) if actions[a] is not None and actions[b] is not None else None
    token_count, span = prediction.get("wm_prediction_token_count"), prediction.get("wm_prediction_char_span")
    length_available = (prediction.get("wm_confidence_scope") == "prediction_tokens_v2" and
        type(token_count) is int and token_count > 0 and isinstance(span, list) and len(span) == 2 and
        all(type(x) is int for x in span) and 0 <= span[0] < span[1] and
        prediction.get("wm_token_alignment", {}).get("status") == "ok")
    core = _conjunction(usable, scoreable)
    reasons = []
    if core is not True:
        reasons.append("core_A_qualification_unknown" if core is None else "not_usable_and_scoreable")
    if accuracy["reason"]:
        reasons.append(accuracy["reason"])
    reasons.extend("branch_"+b+"_not_valid_observed" for b in BRANCHES if not branch_valid[b])
    return {k: point[k] for k in ("canonical_game_id", "state_id", "original_k_j", "statistical_weight",
        "step_id", "remaining_budget", "source_decision_status", "draft_in_visible_menu")} | {
        "EM": accuracy["EM"], "token_F1": accuracy["token_F1"], "accuracy_status": accuracy["status"],
        "mean_logprob": mean if finite(mean) else None, "exp_score": exp_score if finite(exp_score) else None,
        "prediction_token_count": token_count if length_available else None,
        "core_A_eligible": core, "accuracy_eligible": accuracy["status"] == "descriptive",
        "confidence_accuracy_eligible": core is True and accuracy["status"] == "descriptive",
        "prediction_usable": usable, "confidence_scoreable": scoreable,
        "D_reference_available": reference.get("available") is True,
        "Y": valid_y, "raw_Y": raw_y, "branch_valid": branch_valid,
        "all_three_valid": all(branch_valid.values()), "observed_U": observed, "raw_observed_U": raw_observed,
        "actions": actions, "action_changed": changed, "exclusion_reasons": reasons}


def _denominator(rows):
    return {"points": len(rows), "games": len({r["canonical_game_id"] for r in rows}),
            "original_weight_mass": math.fsum(r["statistical_weight"] for r in rows)}


def _stat(rows, getter, *, population_incomplete=False):
    available = [(row, getter(row)) for row in rows if getter(row) is not None]
    values, weights = [v for _, v in available], [r["statistical_weight"] for r, _ in available]
    known = _denominator([r for r, _ in available])
    mean = weighted_mean(values, weights)
    missing = len(rows)-len(available)
    reason = "empty_target_set" if not rows else "target_population_incomplete" if population_incomplete else "missing_target_values" if missing else None
    return {"mean": None if reason else mean, "available_case_mean": mean,
        "observed_weighted_sum": math.fsum(v*w for v, w in zip(values, weights)),
        "target_denominator": _denominator(rows), "observed_denominator": known,
        "missing_points": missing,
        "missing_weight_mass": math.fsum(r["statistical_weight"] for r in rows if getter(r) is None),
        "status": "unavailable" if reason else "descriptive", "reason": reason,
        "available_case_is_target_estimate": reason is None}


def _pool(rows, incomplete=False):
    paired = [r for r in rows if r["all_three_valid"]]
    utility = {name: _stat(rows, lambda r, n=name: r["observed_U"][n], population_incomplete=incomplete) for name in UTILITY_PAIRS}
    pair_means = {name: weighted_mean([r["observed_U"][name] for r in paired], [r["statistical_weight"] for r in paired]) for name in UTILITY_PAIRS}
    return {"denominator": _denominator(rows),
        "branch_available": {b: _stat(rows, lambda r, b=b: r["Y"][b], population_incomplete=incomplete) for b in BRANCHES},
        "observed_U": utility,
        "observed_rescue": {n: _stat(rows, lambda r, n=n: None if r["observed_U"][n] is None else int(r["observed_U"][n] > 0), population_incomplete=incomplete) for n in UTILITY_PAIRS},
        "observed_harm": {n: _stat(rows, lambda r, n=n: None if r["observed_U"][n] is None else int(r["observed_U"][n] < 0), population_incomplete=incomplete) for n in UTILITY_PAIRS},
        "action_changes": {n: _stat(rows, lambda r, n=n: r["action_changed"][n], population_incomplete=incomplete) for n in UTILITY_PAIRS},
        "paired_complete": {"scope": "available_complete_cases_with_original_weights_conditioned_globally",
            "denominator": _denominator(paired), "excluded_noncomplete_points": len(rows)-len(paired),
            "branch_means": {b: weighted_mean([r["Y"][b] for r in paired], [r["statistical_weight"] for r in paired]) for b in BRANCHES},
            "mean_observed_U": pair_means,
            "decomposition_error": None if not paired else pair_means["admission"]-pair_means["info"]-pair_means["revision"]},
        "accuracy": {name: _stat(rows, lambda r, n=name: r[n], population_incomplete=incomplete) for name in ("EM", "token_F1")}}


def _relation(rows, x, y, base):
    xs, ys, weights = [x(r) for r in rows], [y(r) for r in rows], [r["statistical_weight"] for r in rows]
    return {**weighted_correlation(xs, ys, weights), "intersection_denominator": _denominator(rows),
        "base_denominator": _denominator(base), "excluded_from_intersection": len(base)-len(rows),
        "scope": "explicit_observed_intersection_original_weights_globally_conditioned"}


def _ranking(rows, score_key, *, target_incomplete=False):
    """Available common three-branch set; never subtract unpaired means."""
    paired = [r for r in rows if r["all_three_valid"]]
    missing_score = [r for r in paired if r.get(score_key) is None]
    if not paired or missing_score:
        return {"status": "unavailable", "reason": "empty_common_set" if not paired else "score_missing_on_common_set",
            "G": {n: None for n in UTILITY_PAIRS}, "available_complete_case_G": {n: None for n in UTILITY_PAIRS},
            "common_denominator": _denominator(paired), "missing_score_points": len(missing_score),
            "admission_probabilities": [], "global_menu_contributions": None, "within_menu_reranked": None}
    scores, weights = [r[score_key] for r in paired], [r["statistical_weight"] for r in paired]
    boundary = weighted_quantile_memberships(scores, weights, bins=2)
    g = [p[0] for p in boundary["memberships"]]
    total = math.fsum(weights)
    observed_g = {name: math.fsum(w/total*(p-.5)*r["observed_U"][name] for r, w, p in zip(paired, weights, g)) for name in UTILITY_PAIRS}
    complete = not target_incomplete and len(paired) == len(rows)
    menu_contributions, within = {}, {}
    for value, label in ((True, "inside"), (False, "outside"), (None, "unknown")):
        positions = [i for i, r in enumerate(paired) if r["draft_in_visible_menu"] is value]
        menu_contributions[label] = {n: math.fsum(weights[i]/total*(g[i]-.5)*paired[i]["observed_U"][n] for i in positions) for n in UTILITY_PAIRS}
        local_scores, local_weights = [scores[i] for i in positions], [weights[i] for i in positions]
        local_g = weighted_quantile_memberships(local_scores, local_weights, bins=2)["memberships"]
        within[label] = {n: weighted_mean([(p[0]-.5)*paired[i]["observed_U"][n] for i, p in zip(positions, local_g)], local_weights) for n in UTILITY_PAIRS}
    return {"status": "descriptive" if complete else "available_complete_case_only",
        "G": observed_g if complete else {n: None for n in UTILITY_PAIRS},
        "available_complete_case_G": observed_g, "common_denominator": _denominator(paired),
        "target_denominator": _denominator(rows), "missing_score_points": 0,
        "admission_probabilities": [{"canonical_game_id": r["canonical_game_id"], "state_id": r["state_id"], "probability": p} for r, p in zip(paired, g)],
        "weighted_coverage": math.fsum(w/total*p for w, p in zip(weights, g)),
        "tie_status": boundary["status"], "analytic_Random_G": {n: 0.0 for n in UTILITY_PAIRS},
        "constant_branch_means": {b: weighted_mean([r["Y"][b] for r in paired], weights) for b in BRANCHES},
        "decomposition_error": observed_g["admission"]-observed_g["info"]-observed_g["revision"],
        "observed_half_abs_discordance": .5*weighted_mean([abs(r["observed_U"]["admission"]) for r in paired], weights),
        "observed_half_abs_discordance_is_true_C_or_upper_bound": False,
        "global_menu_contributions": menu_contributions, "within_menu_reranked": within,
        "formal_interval": None, "p_value": None}


def analyze(dataset):
    require(isinstance(dataset, dict) and type(dataset.get("schema_version")) is int and dataset.get("schema_version") == 1 and dataset.get("kind") == "d0_descriptive_dataset",
            "Wrong descriptive dataset schema")
    require(dataset.get("status") in ("complete", "collection_incomplete"), "Unknown collection status")
    games, points, count = dataset["games"], dataset["points"], dataset["D0_game_count"]
    require(type(count) is int and count > 0 and len(games) == count, "Original game denominator differs")
    game_map = {g["canonical_game_id"]: g for g in games}
    require(len(game_map) == count, "Duplicate original game identity")
    seen, per_game = set(), Counter()
    for game in games:
        require(isinstance(game["canonical_game_id"], str) and game["canonical_game_id"], "Invalid game identity")
        require(type(game["original_k_j"]) is int and 0 <= game["original_k_j"] <= 3, "Invalid original selected-state count")
        require(finite(game.get("original_game_weight", 1/count)) and game.get("original_game_weight", 1/count) == 1/count, "Original game weight changed")
    for point in points:
        gid, sid = point["canonical_game_id"], point["state_id"]
        require(gid in game_map and isinstance(sid, str) and sid and (gid, sid) not in seen, "Unknown or duplicate planned point")
        seen.add((gid, sid)); per_game[gid] += 1
        k = game_map[gid]["original_k_j"]
        require(k > 0 and type(point["original_k_j"]) is int and point["original_k_j"] == k and
                finite(point["statistical_weight"]) and point["statistical_weight"] == 1/(count*k),
                "Original k_j or 1/(J*k_j) weight changed")
        require(type(point["step_id"]) is int and 0 <= point["step_id"] < 30 and
                type(point["remaining_budget"]) is int and point["remaining_budget"] == 30-point["step_id"], "Invalid budget")
        require(point["draft_in_visible_menu"] is None or type(point["draft_in_visible_menu"]) is bool, "Invalid menu indicator")
        require(isinstance(point.get("branches"), dict) and all(isinstance(point["branches"].get(b), dict) for b in BRANCHES), "Missing branch records")
    require(all(per_game[g] == game["original_k_j"] for g, game in game_map.items()), "Missing planned point rows; do not renormalize deletion")
    require(type(dataset.get("original_selected_state_count")) is int and dataset.get("original_selected_state_count") == len(points), "Selected-state denominator differs")
    rows = [_derive(p) for p in sorted(points, key=lambda p: (p["canonical_game_id"], p["state_id"]))]
    for row in rows:
        row["menu_outside_priority"] = None if row["draft_in_visible_menu"] is None else int(not row["draft_in_visible_menu"])
    core = [r for r in rows if r["core_A_eligible"] is True]
    unknown = [r for r in rows if r["core_A_eligible"] is None]
    incomplete = dataset["status"] != "complete" or any(g["original_k_j"] == 0 for g in games)
    core_incomplete = incomplete or bool(unknown)
    confident_accuracy = [r for r in rows if r["confidence_accuracy_eligible"]]
    accuracy_rows = [r for r in rows if r["accuracy_eligible"]]
    relationships = {"confidence_accuracy": {}, "accuracy_observed_U": {}}
    for name in ("EM", "token_F1"):
        relationships["confidence_accuracy"][name] = _relation(confident_accuracy, lambda r: r["mean_logprob"], lambda r, n=name: r[n], core)
        relationships["accuracy_observed_U"][name] = {}
        for utility in UTILITY_PAIRS:
            paired = [r for r in confident_accuracy if r["observed_U"][utility] is not None]
            relationships["accuracy_observed_U"][name][utility] = _relation(paired, lambda r, n=name: r[n], lambda r, u=utility: r["observed_U"][u], confident_accuracy)
    quantiles = weighted_quantile_memberships([r["mean_logprob"] for r in core], [r["statistical_weight"] for r in core])
    confidence_bins = []
    for b in range(4):
        fractional = []
        for row, probabilities in zip(core, quantiles["memberships"]):
            if probabilities[b] > 0:
                item = deepcopy(row)
                item["statistical_weight"] *= probabilities[b]
                fractional.append(item)
        confidence_bins.append({"bin": b+1, "order": "descending_mean_logprob", "target_qualified_mass": .25,
                                "summary": _pool(fractional, core_incomplete)})
    means, exps = [r["mean_logprob"] for r in core], [r["exp_score"] for r in core]
    nonmissing_u = [r["observed_U"]["admission"] for r in core if r["observed_U"]["admission"] is not None]
    return {"schema_version": 1, "kind": "d0_descriptive_metrics", "status": "descriptive_only",
        "metric_source_sha256": METRICS_SHA256, "point_metrics": rows,
        "weighting": {"rule": "original_1_over_J_kj_then_global_conditioning", "original_games": count,
            "original_selected_states": len(rows), "core_A_known": _denominator(core),
            "core_A_unknown": _denominator(unknown), "target_population_incomplete": incomplete,
            "missing_data_policy": "target_mean_null_with_explicit_available_case_description"},
        "aggregate": {"all_planned": _pool(rows, incomplete), "core_A": _pool(core, core_incomplete)},
        "analysis_sets": {"original_planned": _denominator(rows), "core_A_known": _denominator(core),
            "core_A_unknown": _denominator(unknown), "accuracy_description": _denominator(accuracy_rows),
            "confidence_accuracy": _denominator(confident_accuracy)},
        "accuracy_description": {"scope": "usable_prediction_and_valid_D_reference_including_unscoreable_predictions",
            "denominator": _denominator(accuracy_rows), "excluded_planned_points": len(rows)-len(accuracy_rows),
            "EM": _stat(accuracy_rows, lambda r: r["EM"]),
            "token_F1": _stat(accuracy_rows, lambda r: r["token_F1"])},
        "by_menu": {label: {"all_planned": _pool([r for r in rows if r["draft_in_visible_menu"] is value], incomplete),
                            "core_A": _pool([r for r in core if r["draft_in_visible_menu"] is value], core_incomplete)}
                    for value, label in ((True, "inside"), (False, "outside"), (None, "unknown"))},
        "by_budget": {label: {"bounds_inclusive": list(bounds),
            "all_planned": _pool([r for r in rows if bounds[0] <= r["remaining_budget"] <= bounds[1]], incomplete),
            "core_A": _pool([r for r in core if bounds[0] <= r["remaining_budget"] <= bounds[1]], core_incomplete)} for label, bounds in BUDGET_BINS.items()},
        "relationships": relationships, "confidence_bins": confidence_bins,
        "score_diagnostics": {"denominator": _denominator(core), "ranking_field": "wm_mean_logprob",
            "mean_logprob_min": min(means) if means else None, "mean_logprob_max": max(means) if means else None,
            "exp_score_min": min(exps) if exps else None, "exp_score_max": max(exps) if exps else None,
            "exact_unique_mean_logprobs": len(set(means)), "exact_unique_exp_scores": len(set(exps)),
            "exact_tie_groups": quantiles["groups"], "bin_memberships": quantiles["memberships"],
            "score_status": quantiles["status"], "all_observed_admission_differences_zero": all(v == 0 for v in nonmissing_u) if nonmissing_u else None,
            "all_zero_is_true_zero_utility_claim": False},
        "ranking_diagnostics": {name: _ranking(core, field, target_incomplete=core_incomplete)
            for name, field in (("confidence", "mean_logprob"), ("menu_outside_first", "menu_outside_priority"), ("prediction_length_longer", "prediction_token_count"))},
        "game_summaries": [{"canonical_game_id": gid, "original_k_j": game["original_k_j"],
            "all_planned": _pool([r for r in rows if r["canonical_game_id"] == gid], incomplete),
            "core_A": _pool([r for r in core if r["canonical_game_id"] == gid], core_incomplete)} for gid, game in sorted(game_map.items())],
        "formal_inference": None, "statistical_acceptance": False, "runtime_authorized": False,
        "interpretation": "Single observed Y differences and textual proxies; no true-U/C, causal bottleneck, determinism, or population-certification claim"}
