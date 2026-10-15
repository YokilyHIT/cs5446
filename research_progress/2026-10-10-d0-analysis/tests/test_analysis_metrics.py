"""Offline contracts: real frozen text scoring, synthetic event outcomes only."""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import random

import pytest

PATH = Path(__file__).resolve().parents[1] / "sidecar/analysis_metrics.py"
SPEC = importlib.util.spec_from_file_location("step5_metrics_tested", PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def dataset(counts=(2, 1)):
    games, points = [], []
    for j, k in enumerate(counts):
        gid = f"game-{j}"
        games.append({"canonical_game_id": gid, "original_k_j": k,
                      "original_game_weight": 1/len(counts), "status": "complete"})
        for t in range(k):
            points.append({"canonical_game_id": gid, "state_id": f"state-{t}",
                "original_k_j": k, "statistical_weight": 1/(len(counts)*k),
                "step_id": t, "remaining_budget": 30-t,
                "source_decision_status": "executed", "state_status": "complete",
                "draft_action": "open door", "draft_in_visible_menu": True,
                "prediction": {"wm_prediction": "The red door opens.",
                    "wm_mean_logprob": -.01*(t+j+1),
                    "wm_confidence_logprob": math.exp(-.01*(t+j+1)),
                    "wm_confidence_scope": "prediction_tokens_v2", "wm_confidence_status": "ok",
                    "wm_prediction_token_count": 4+t, "wm_prediction_char_span": [12, 31],
                    "wm_token_alignment": {"status": "ok"}},
                "prediction_status": "usable", "prediction_usable": True,
                "confidence_scoreable": True, "WM_fallback": False,
                "D_reference": {"observation": "A red door opens", "available": True,
                                "measurement_validity": "valid", "source_rollout_id": "D-run"},
                "branches": {b: {"outcome_status": "complete", "raw_Y": 0,
                    "measurement_validity": "valid", "first_action": "open door",
                    "in_visible_menu": True, "group_id": "one-shared-group",
                    "first_action_policy_failure": False, "new_mu_calls": 0,
                    "not_run_reason": None} for b in m.BRANCHES}, "physical_groups": []})
    return {"schema_version": 1, "kind": "d0_descriptive_dataset", "status": "complete",
            "D0_game_count": len(counts), "original_selected_state_count": len(points),
            "games": games, "points": points}


def outcomes(point, D, N, P):
    for branch, value in zip(m.BRANCHES, (D, N, P)):
        point["branches"][branch]["raw_Y"] = value


def invalidate(point, branch="P", validity="pending_review"):
    point["branches"][branch]["measurement_validity"] = validity


def score(point, mean):
    point["prediction"]["wm_mean_logprob"] = mean
    point["prediction"]["wm_confidence_logprob"] = math.exp(mean)


def test_frozen_source_and_normalized_metrics_multisets():
    assert m.METRICS_SHA256 == "817d43d6d708abe5eff102020e6b19434e8c34ce4384e7d0881b856ac85c8c8b"
    assert m.text_accuracy("The RED, door!", "a red door")["EM"] == 1
    assert m.text_accuracy("red red blue", "red blue blue")["token_F1"] == pytest.approx(2/3)
    assert m.text_accuracy("red-door", "red door")["EM"] == 0  # ASCII deletion, not split.
    assert m.text_accuracy("the", "a")["EM"] == 1  # Existing normalized-empty convention.


@pytest.mark.parametrize("prediction,reference,kwargs", [
    (None, None, {}), ("", "", {}), ("  ", "red", {}), ("red", "", {}),
    ("red", "red", {"usable": False}), ("red", "red", {"reference_valid": False}),
])
def test_missing_or_unusable_raw_content_never_scores_one(prediction, reference, kwargs):
    result = m.text_accuracy(prediction, reference, **kwargs)
    assert result["EM"] is None and result["token_F1"] is None


def test_original_game_equal_weights_and_no_reweight_after_qualification():
    data = dataset((3, 1))
    for point in data["points"][:3]:
        outcomes(point, 0, 0, 1)
    assert m.analyze(data)["aggregate"]["all_planned"]["observed_U"]["admission"]["mean"] == .5
    # Retain one of game 0's three selected points in core A. Its base weight
    # stays 1/6, while game 1's point stays 1/2: no per-game reset to 1/2 each.
    for point in data["points"][:2]:
        point["confidence_scoreable"] = False
    result = m.analyze(data)
    core = result["aggregate"]["core_A"]
    assert core["observed_U"]["admission"]["mean"] == pytest.approx(.25)
    assert core["denominator"]["original_weight_mass"] == pytest.approx(2/3)
    assert result["analysis_sets"]["accuracy_description"]["points"] == 4
    assert result["analysis_sets"]["confidence_accuracy"]["points"] == 2


def test_missing_outcome_is_not_zero_and_main_estimate_does_not_renormalize():
    data = dataset((1, 1))
    outcomes(data["points"][0], 0, 1, 1)
    outcomes(data["points"][1], 1, 0, 0)
    invalidate(data["points"][1])
    result = m.analyze(data)
    point = result["point_metrics"][1]
    assert point["raw_observed_U"]["admission"] == -1
    assert point["observed_U"]["admission"] is None
    stat = result["aggregate"]["core_A"]["observed_U"]["admission"]
    assert stat["mean"] is None and stat["available_case_mean"] == 1
    assert stat["missing_weight_mass"] == .5 and stat["missing_points"] == 1
    assert stat["reason"] == "missing_target_values"
    ranking = result["ranking_diagnostics"]["confidence"]
    assert ranking["G"]["admission"] is None
    assert ranking["available_complete_case_G"]["admission"] == 0


def test_three_branch_matched_set_decomposition_and_rescue_harm():
    data = dataset((1, 1))
    outcomes(data["points"][0], 0, 1, 1)
    outcomes(data["points"][1], 1, 1, 0)
    result = m.analyze(data)["aggregate"]["all_planned"]
    assert result["paired_complete"]["branch_means"] == {"D": .5, "N": 1, "P": .5}
    assert result["paired_complete"]["mean_observed_U"] == {"admission": 0, "info": -.5, "revision": .5}
    assert result["paired_complete"]["decomposition_error"] == 0
    assert result["observed_rescue"]["admission"]["mean"] == .5
    assert result["observed_harm"]["admission"]["mean"] == .5
    invalidate(data["points"][1], "N")
    unmatched = m.analyze(data)["aggregate"]["all_planned"]
    assert unmatched["branch_available"]["D"]["mean"] == .5
    assert unmatched["branch_available"]["N"]["mean"] is None
    assert unmatched["paired_complete"]["branch_means"] == {"D": 0, "N": 1, "P": 1}
    assert unmatched["paired_complete"]["decomposition_error"] == 0


def test_shared_physical_group_is_one_point_accuracy_event():
    data = dataset((1,))
    data["points"][0]["physical_groups"] = [{"group_id": "one-shared-group", "branches": ["D", "N", "P"]}]
    result = m.analyze(data)
    assert len(result["point_metrics"]) == 1
    assert result["analysis_sets"]["accuracy_description"]["points"] == 1
    assert result["aggregate"]["all_planned"]["action_changes"]["admission"]["mean"] == 0


def test_source_draft_failure_preserves_denominator_without_local_zero_or_confidence():
    data = dataset((1, 1))
    point = data["points"][0]
    point.update(source_decision_status="source_draft_policy_failure", prediction=None,
                 prediction_usable=False, confidence_scoreable=False)
    point["D_reference"] = {"available": False, "observation": None, "measurement_validity": "not_applicable"}
    for row in point["branches"].values():
        row.update(outcome_status="not_applicable_source_draft_failure", measurement_validity="not_applicable",
                   raw_Y=None, first_action=None)
    result = m.analyze(data)
    derived = result["point_metrics"][0]
    assert derived["core_A_eligible"] is False and derived["EM"] is None
    assert set(derived["observed_U"].values()) == {None}
    assert result["analysis_sets"]["original_planned"]["original_weight_mass"] == 1
    assert result["aggregate"]["all_planned"]["branch_available"]["D"]["mean"] is None
    point["branches"]["D"]["raw_Y"] = 0
    with pytest.raises(ValueError, match="cannot manufacture"):
        m.analyze(data)


def test_policy_failure_is_observed_zero_but_technical_missing_is_not():
    data = dataset((1,))
    point = data["points"][0]
    point["branches"]["P"].update(outcome_status="policy_failed", raw_Y=0, first_action=None)
    result = m.analyze(data)["point_metrics"][0]
    assert result["Y"]["P"] == 0 and result["action_changed"]["admission"] is None
    point["branches"]["P"]["raw_Y"] = 1
    with pytest.raises(ValueError, match="Policy failure"):
        m.analyze(data)
    point["branches"]["P"].update(outcome_status="technical_missing", measurement_validity="technical_evidence_incomplete")
    result = m.analyze(data)["point_metrics"][0]
    assert result["raw_Y"]["P"] == 1 and result["Y"]["P"] is None


def test_accuracy_uses_D_reference_and_does_not_require_score():
    data = dataset((1, 1))
    point = data["points"][0]
    point["confidence_scoreable"] = False
    point["prediction"]["wm_mean_logprob"] = None
    point["prediction"]["wm_confidence_logprob"] = None
    # A P-only observation, even an exact match, is never the reference.
    data["points"][1]["D_reference"]["observation"] = "Nothing happens."
    data["points"][1]["branches"]["P"]["next_observation"] = "The red door opens."
    result = m.analyze(data)
    assert result["point_metrics"][0]["accuracy_eligible"] is True
    assert result["point_metrics"][0]["confidence_accuracy_eligible"] is False
    assert result["point_metrics"][1]["EM"] == 0
    assert result["accuracy_description"]["EM"]["mean"] == .5
    data["points"][1]["D_reference"]["measurement_validity"] = "pending_review"
    result = m.analyze(data)["point_metrics"][1]
    assert result["D_reference_available"] is True and result["EM"] is None
    assert result["core_A_eligible"] is True


def test_unknown_qualification_and_unfinalized_raw_evidence_block_target_estimate():
    data = dataset((1, 1))
    data["status"] = "collection_incomplete"
    point = data["points"][1]
    point.update(prediction_usable=None, confidence_scoreable=None)
    for row in point["branches"].values():
        row["measurement_validity"] = "technical_evidence_incomplete"
    result = m.analyze(data)
    assert result["point_metrics"][1]["core_A_eligible"] is None
    assert result["weighting"]["core_A_unknown"]["points"] == 1
    assert result["aggregate"]["core_A"]["observed_U"]["admission"]["mean"] is None
    assert result["ranking_diagnostics"]["confidence"]["G"]["admission"] is None


def test_correlations_ties_degenerate_and_weighted_definition():
    assert m.average_ranks([7, 1, 7, 3]) == [3.5, 1, 3.5, 2]
    result = m.weighted_correlation([-3, -2, -1], [0, 1, 2], [.25, .25, .5])
    assert result["pearson"] == pytest.approx(1)
    assert result["spearman"] == pytest.approx(1)
    assert result["confidence_interval"] is None and result["p_value"] is None
    assert m.weighted_correlation([1, 1], [0, 1], [.5, .5])["undefined_reason"] == "constant_x"
    assert m.weighted_correlation([1, 2], [0, 0], [.5, .5])["undefined_reason"] == "constant_y"
    assert m.weighted_correlation([], [], [])["pearson"] is None
    assert m.weighted_correlation([1], [1], [1])["status"] == "undefined"


def test_fractional_tie_groups_are_not_split_by_id_or_outcome():
    result = m.weighted_quantile_memberships([3, 2, 2, 1], [.1, .2, .4, .3], bins=2)
    assert result["memberships"][0] == [1, 0]
    assert result["memberships"][1] == result["memberships"][2]
    assert result["memberships"][1][0] == pytest.approx(2/3)
    assert result["memberships"][3] == [0, 1]
    assert result["bin_weight_mass"] == [.5, .5]
    all_tied = m.weighted_quantile_memberships([1, 1, 1], [.1, .2, .7])
    assert all_tied["memberships"] == [[.25]*4]*3
    assert all_tied["status"] == "all_exactly_tied"


def test_mean_logprob_near_one_ranking_survives_equal_exp_scores():
    data = dataset((1, 1))
    score(data["points"][0], -1e-19)
    score(data["points"][1], -2e-19)
    outcomes(data["points"][0], 0, 0, 1)
    result = m.analyze(data)
    diagnostics = result["score_diagnostics"]
    assert diagnostics["exact_unique_exp_scores"] == 1
    assert diagnostics["exact_unique_mean_logprobs"] == 2
    assert result["ranking_diagnostics"]["confidence"]["G"]["admission"] == .25
    assert result["relationships"]["confidence_accuracy"]["EM"]["pearson"] is None


def test_three_G_random_constants_menu_partition_and_local_rerank():
    data = dataset((1, 1))
    high, low = data["points"]
    score(high, -.001); score(low, -.5)
    outcomes(high, 0, 0, 1)
    outcomes(low, 1, 0, 0)
    low["draft_in_visible_menu"] = False
    result = m.analyze(data)["ranking_diagnostics"]
    rank = result["confidence"]
    assert rank["G"] == {"admission": .5, "info": .25, "revision": .25}
    assert rank["weighted_coverage"] == .5 and rank["decomposition_error"] == 0
    assert rank["analytic_Random_G"] == {n: 0 for n in m.UTILITY_PAIRS}
    assert rank["constant_branch_means"] == {"D": .5, "N": 0, "P": .5}
    for name in m.UTILITY_PAIRS:
        assert sum(values[name] for values in rank["global_menu_contributions"].values()) == rank["G"][name]
        assert rank["within_menu_reranked"]["inside"][name] == 0
        assert rank["within_menu_reranked"]["outside"][name] == 0
    assert result["menu_outside_first"]["G"]["admission"] == -.5
    assert rank["observed_half_abs_discordance"] == .5
    assert rank["observed_half_abs_discordance_is_true_C_or_upper_bound"] is False


def test_prediction_length_uses_span_token_count_longer_first_or_unavailable():
    data = dataset((1, 1))
    data["points"][0]["prediction"]["wm_prediction_token_count"] = 20
    data["points"][1]["prediction"]["wm_prediction_token_count"] = 2
    outcomes(data["points"][0], 0, 0, 1)
    result = m.analyze(data)["ranking_diagnostics"]["prediction_length_longer"]
    assert result["G"]["admission"] == .25
    data["points"][1]["prediction"].pop("wm_prediction_char_span")
    result = m.analyze(data)["ranking_diagnostics"]
    assert result["prediction_length_longer"]["status"] == "unavailable"
    assert result["prediction_length_longer"]["reason"] == "score_missing_on_common_set"
    assert result["prediction_length_longer"]["common_denominator"]["points"] == 2
    assert result["prediction_length_longer"]["G"]["admission"] is None
    assert result["confidence"]["G"]["admission"] is not None


def test_all_zero_and_all_scores_tied_still_describe_without_false_inference():
    data = dataset((2, 1))
    for point in data["points"]:
        score(point, -.001)
    result = m.analyze(data)
    assert result["score_diagnostics"]["all_observed_admission_differences_zero"] is True
    assert result["score_diagnostics"]["all_zero_is_true_zero_utility_claim"] is False
    assert result["ranking_diagnostics"]["confidence"]["G"]["admission"] == 0
    assert all(x["probability"] == .5 for x in result["ranking_diagnostics"]["confidence"]["admission_probabilities"])
    assert result["relationships"]["accuracy_observed_U"]["EM"]["admission"]["pearson"] is None
    assert result["formal_inference"] is None and result["statistical_acceptance"] is False
    assert all(bin_["summary"]["denominator"]["original_weight_mass"] == .25 for bin_ in result["confidence_bins"])
    json.dumps(result, allow_nan=False)


def test_accuracy_to_U_relationship_is_nested_in_confidence_accuracy_pool():
    data = dataset((1, 1, 1))
    data["points"][0]["confidence_scoreable"] = False
    outcomes(data["points"][0], 0, 0, 1)
    data["points"][1]["prediction"]["wm_prediction"] = "Nothing happens"
    outcomes(data["points"][1], 1, 1, 0)
    outcomes(data["points"][2], 0, 0, 1)
    result = m.analyze(data)
    rel = result["relationships"]["accuracy_observed_U"]["EM"]["admission"]
    assert rel["n"] == 2 and rel["pearson"] == pytest.approx(1)
    assert result["accuracy_description"]["denominator"]["points"] == 3
    assert rel["intersection_denominator"]["original_weight_mass"] == pytest.approx(2/3)


def test_menu_and_budget_boundaries_and_input_order_invariance():
    data = dataset((3, 3))
    for point, remaining in zip(data["points"], [1, 10, 11, 20, 21, 30]):
        point["remaining_budget"], point["step_id"] = remaining, 30-remaining
    data["points"][0]["draft_in_visible_menu"] = None
    result = m.analyze(data)
    assert all(bin_["all_planned"]["denominator"]["points"] == 2 for bin_ in result["by_budget"].values())
    assert result["by_menu"]["unknown"]["all_planned"]["denominator"]["points"] == 1
    assert result["ranking_diagnostics"]["menu_outside_first"]["status"] == "unavailable"
    random.Random(42).shuffle(data["points"])
    data["games"].reverse()
    assert m.analyze(data) == result


def test_empty_original_game_is_explicit_and_no_plan_deletion_is_accepted():
    data = dataset((0, 1))
    result = m.analyze(data)
    assert result["weighting"]["target_population_incomplete"] is True
    assert result["aggregate"]["all_planned"]["branch_available"]["D"]["mean"] is None
    assert result["ranking_diagnostics"]["confidence"]["G"]["admission"] is None
    assert result["analysis_sets"]["original_planned"]["original_weight_mass"] == .5
    empty = m.analyze(dataset((0, 0)))
    assert empty["ranking_diagnostics"]["confidence"]["reason"] == "empty_common_set"
    assert empty["score_diagnostics"]["all_observed_admission_differences_zero"] is None
    data = dataset()
    data["points"].pop()
    with pytest.raises(ValueError, match="Missing planned point"):
        m.analyze(data)


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d.update(schema_version=True), "schema"),
    (lambda d: d.update(status="maybe"), "collection status"),
    (lambda d: d.update(original_selected_state_count=True), "denominator"),
    (lambda d: d["points"][0].update(statistical_weight=.25), "weight changed"),
    (lambda d: d["points"][0].update(statistical_weight=True), "weight changed"),
    (lambda d: d["points"][0].update(original_k_j=True), "weight changed"),
    (lambda d: d["points"][0].update(remaining_budget=31), "budget"),
    (lambda d: d["points"][0].update(prediction="bad"), "prediction record"),
    (lambda d: d["points"][0].update(prediction_usable=1), "qualification"),
    (lambda d: d["points"][0]["prediction"].update(wm_mean_logprob=float("nan")), "score evidence"),
    (lambda d: d["points"][0]["branches"]["D"].update(raw_Y=True), "raw Y"),
    (lambda d: d["points"][0]["branches"].pop("N"), "branch records"),
])
def test_malformed_inputs_are_rejected(mutate, match):
    data = dataset((1,))
    mutate(data)
    with pytest.raises(ValueError, match=match):
        m.analyze(data)


def test_duplicate_original_game_and_point_rejected():
    data = dataset((1, 1))
    data["games"][1]["canonical_game_id"] = data["games"][0]["canonical_game_id"]
    with pytest.raises(ValueError, match="Duplicate original game"):
        m.analyze(data)
    data = dataset((2,))
    data["points"][1]["state_id"] = data["points"][0]["state_id"]
    with pytest.raises(ValueError, match="duplicate planned point"):
        m.analyze(data)


def test_analyze_is_pure_and_public_helpers_reject_invalid_weights():
    data = dataset()
    before = deepcopy(data)
    m.analyze(data)
    assert data == before
    with pytest.raises(ValueError, match="weights positive"):
        m.weighted_mean([1, 2], [1, 0])
    with pytest.raises(ValueError, match="lengths differ"):
        m.weighted_correlation([1, 2], [3], [1, 1])
    with pytest.raises(ValueError, match="bins"):
        m.weighted_quantile_memberships([1], [1], bins=True)
