"""Pure fixed-hash selection of long-tail, different-action N/P groups.

The archive adapter owns evidence validation. This module validates the flat
inventory contract and never opens an environment, model, source file, or log.
Selection is independent of Y, utility, confidence, and observed improvement.
The exact inventory hash binds input order; selected identities are order
invariant. No returned plan authorizes execution or automatic retries.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math

NAMESPACE = "cs5446-direction-b-np-audit-v1"
SEED = 42
MIN_NEW_MU_CALLS = 10
TARGET_GROUPS = 6
MIN_GAMES = 4
MAX_GROUPS_PER_GAME = 2
OUTCOME_STATUSES = frozenset(("complete", "policy_failed", "technical_missing", "not_run"))
MEASUREMENT_STATUSES = frozenset(("valid", "pending_review", "technical_missing", "not_run", "not_applicable"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_json(value):
    """Reject non-JSON and nonfinite evidence instead of changing its bytes."""
    if isinstance(value, dict):
        require(all(isinstance(k, str) for k in value), "JSON object keys must be strings")
        for item in value.values():
            validate_json(item)
    elif isinstance(value, list):
        for item in value:
            validate_json(item)
    elif type(value) is float:
        require(math.isfinite(value), "Nonfinite evidence is not JSON")
    else:
        require(value is None or type(value) in (str, int, bool), "Evidence must contain only JSON values")


def canonical(value):
    validate_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def seal(value):
    result = deepcopy(value)
    result.pop("sha256", None)
    result["sha256"] = digest(result)
    return result


def check_seal(value):
    require(isinstance(value, dict) and isinstance(value.get("sha256"), str), "Missing content seal")
    require(value["sha256"] == digest({k: v for k, v in value.items() if k != "sha256"}), "Content seal differs")


def _nonempty(value, field):
    require(isinstance(value, str) and bool(value), "Missing or invalid " + field)
    return value


def _candidate(value):
    require(isinstance(value, dict), "Candidate must be an object")
    validate_json(value)
    item = deepcopy(value)
    # Reject preexisting selector annotations so an adapter cannot accidentally
    # carry selection decisions from a previous plan into this plan.
    reserved = {"candidate_key", "hash_input", "order_hash", "eligible_global_rank", "selection_pass",
                "selection_position", "eligible", "exclusion_reasons", "selected", "not_selected_reason"}
    require(not reserved.intersection(item), "Candidate contains reserved selection fields")
    for field in ("canonical_game_id", "state_id", "group_id", "first_action", "draft_action",
                  "outcome_status", "measurement_validity"):
        _nonempty(item.get(field), field)
    require(item["outcome_status"] in OUTCOME_STATUSES, "Unknown candidate outcome status")
    require(item["measurement_validity"] in MEASUREMENT_STATUSES, "Unknown candidate measurement validity")
    branches = item.get("branches")
    require(isinstance(branches, list) and branches and all(type(b) is str and b in ("D", "N", "P") for b in branches)
            and len(branches) == len(set(branches)), "Branches must be unique D/N/P identities")
    item["branches"] = sorted(branches)
    require(type(item.get("new_mu_calls")) is int and item["new_mu_calls"] >= 0,
            "new_mu_calls must be a nonnegative integer counting new logical mu calls")
    require(isinstance(item.get("binding"), dict) and item["binding"], "Candidate must retain a nonempty evidence binding")
    if "D" in branches:
        require(item["first_action"] == item["draft_action"], "D physical group does not execute cached draft")
    reasons = []
    if not {"N", "P"}.intersection(branches):
        reasons.append("no_N_or_P_branch")
    if item["first_action"] == item["draft_action"]:
        reasons.append("first_action_equals_D_draft")
    if item["outcome_status"] not in ("complete", "policy_failed"):
        reasons.append("source_outcome_not_comparable")
    if item["measurement_validity"] != "valid":
        reasons.append("source_measurement_not_valid")
    if item["new_mu_calls"] < MIN_NEW_MU_CALLS:
        reasons.append("fewer_than_10_new_mu_calls")
    identity = [item["canonical_game_id"], item["state_id"], item["group_id"]]
    hash_value = [NAMESPACE, SEED, *identity, item["branches"], item["first_action"]]
    item.update(candidate_key=canonical(identity), hash_input=canonical(hash_value), order_hash=digest(hash_value),
        eligible=not reasons, exclusion_reasons=reasons, eligible_global_rank=None,
        selected=False, selection_pass=None, selection_position=None, not_selected_reason=None)
    return item


def build_plan(inventory):
    """Validate, classify and select at most six groups in two fixed passes.

    Required candidate fields are canonical_game_id/state_id/group_id,
    branches, exact first_action/draft_action, new_mu_calls, outcome_status,
    measurement_validity, and a nonempty opaque binding object. Unknown
    outcome/validity statuses are rejected; known ineligible statuses are retained. Optional
    state_dispositions records source points without physical groups, such as
    a source draft policy failure; those records do not imply incompleteness.
    """
    require(isinstance(inventory, dict), "Inventory must be an object")
    validate_json(inventory)
    require(type(inventory.get("schema_version")) is int and inventory["schema_version"] == 1,
            "Unsupported inventory schema version")
    require(inventory.get("kind") == "np_audit_candidate_inventory", "Wrong inventory kind")
    require(inventory.get("status") in ("complete", "collection_incomplete"), "Unknown collection status")
    require(isinstance(inventory.get("candidates"), list), "Inventory candidates must be a list")
    if "sha256" in inventory:
        check_seal(inventory)
    dispositions = inventory.get("state_dispositions")
    require(dispositions is None and "state_dispositions" not in inventory or isinstance(dispositions, list)
            and all(isinstance(item, dict) and item for item in dispositions), "Invalid state dispositions")
    items = [_candidate(value) for value in inventory["candidates"]]
    identities, branch_owners, state_drafts = set(), {}, {}
    for item in items:
        key = item["candidate_key"]
        require(key not in identities, "Duplicate physical group identity: " + key)
        identities.add(key)
        state_key = (item["canonical_game_id"], item["state_id"])
        require(state_key not in state_drafts or state_drafts[state_key] == item["draft_action"],
                "One source state has conflicting D draft actions")
        state_drafts[state_key] = item["draft_action"]
        for branch in item["branches"]:
            assignment = (*state_key, branch)
            require(assignment not in branch_owners, "One logical branch is assigned to multiple physical groups")
            branch_owners[assignment] = key
    items.sort(key=lambda item: (item["order_hash"], item["hash_input"]))
    eligible = [item for item in items if item["eligible"]]
    for rank, item in enumerate(eligible, 1):
        item["eligible_global_rank"] = rank

    selected, game_counts = [], Counter()
    first_pass, second_pass = [], []
    complete = inventory["status"] == "complete"

    def choose(item, pass_number):
        item.update(selected=True, selection_pass=pass_number, selection_position=len(selected)+1)
        selected.append(item)
        game_counts[item["canonical_game_id"]] += 1

    if complete:
        for item in eligible:
            gid = item["canonical_game_id"]
            if len(selected) >= TARGET_GROUPS:
                decision = "target_already_reached"
            elif game_counts[gid]:
                decision = "game_already_selected_in_first_pass"
            else:
                choose(item, 1)
                decision = "selected"
            first_pass.append({"candidate_key": item["candidate_key"], "eligible_global_rank": item["eligible_global_rank"],
                               "decision": decision, "selection_position": item["selection_position"]})
        if len(selected) < TARGET_GROUPS:
            for item in eligible:
                gid = item["canonical_game_id"]
                if item["selected"]:
                    decision = "already_selected"
                elif len(selected) >= TARGET_GROUPS:
                    decision = "target_already_reached"
                elif game_counts[gid] >= MAX_GROUPS_PER_GAME:
                    decision = "per_game_cap_reached"
                else:
                    choose(item, 2)
                    decision = "selected"
                second_pass.append({"candidate_key": item["candidate_key"], "eligible_global_rank": item["eligible_global_rank"],
                                    "decision": decision, "selection_position": item["selection_position"]})
    for item in items:
        if item["selected"]:
            continue
        if not item["eligible"]:
            item["not_selected_reason"] = "excluded_by_frozen_eligibility"
        elif not complete:
            item["not_selected_reason"] = "collection_incomplete_no_subset_selection"
        elif len(selected) >= TARGET_GROUPS:
            item["not_selected_reason"] = "target_reached"
        else:
            require(game_counts[item["canonical_game_id"]] == MAX_GROUPS_PER_GAME,
                    "Unexpected unselected eligible group below cap")
            item["not_selected_reason"] = "per_game_cap_reached"

    reasons = []
    if not complete:
        reasons.append("collection_incomplete")
    if len(selected) < TARGET_GROUPS:
        reasons.append("fewer_than_6_selected_groups")
    if len(game_counts) < MIN_GAMES:
        reasons.append("fewer_than_4_selected_games")
    status = "blocked_collection_incomplete" if not complete else "coverage_insufficient" if reasons else "ready"
    excluded_counts = Counter(reason for item in items for reason in item["exclusion_reasons"])
    before_length = [item for item in items if not set(item["exclusion_reasons"]) - {"fewer_than_10_new_mu_calls"}]
    inventory_payload = {k: v for k, v in inventory.items() if k != "sha256"}
    failure_points = None if dispositions is None else sum(
        item.get("source_decision_status", item.get("status")) == "source_draft_policy_failure" for item in dispositions)
    plan = {"schema_version": 1, "kind": "np_audit_selection_plan", "status": status,
        "inventory_sha256": digest(inventory_payload), "inventory_status": inventory["status"],
        "inventory_metadata": deepcopy({k: v for k, v in inventory.items() if k not in ("candidates", "state_dispositions", "sha256")}),
        "protocol": {"namespace": NAMESPACE, "seed": SEED, "min_new_mu_calls": MIN_NEW_MU_CALLS,
            "target_groups": TARGET_GROUPS, "min_games": MIN_GAMES, "max_groups_per_game": MAX_GROUPS_PER_GAME,
            "hash_algorithm": "sha256", "serialization": "UTF-8 compact JSON; ensure_ascii=False; sort_keys=True",
            "hash_fields": ["namespace", "seed", "canonical_game_id", "state_id", "group_id", "sorted_branches", "exact_first_action"],
            "tie_break": "hash_input_ascending", "selection_order": "first_pass_selected_then_second_pass_selected",
            "new_mu_definition": "new continuation logical requests including terminal policy failure; excludes cached draft, first-action generation, HTTP retries",
            "outcome_confidence_utility_selection": False,
            "sampling_claim": "long_tail_engineering_probe_not_representative_or_probability_certification"},
        "coverage": {"status": "blocked" if not complete else "insufficient" if reasons else "sufficient",
            "selected_groups": len(selected), "selected_games": len(game_counts), "reasons": reasons,
            "per_game_selected": dict(sorted(game_counts.items())), "threshold_relaxed": False,
            "short_tail_backfill": False, "per_game_cap_preserved": True},
        "denominators": {"input_groups": len(items), "input_games": len({i["canonical_game_id"] for i in items}),
            "input_new_mu_calls": sum(i["new_mu_calls"] for i in items),
            "eligible_before_length_groups": len(before_length),
            "short_tail_excluded_groups": sum(i["new_mu_calls"] < MIN_NEW_MU_CALLS for i in before_length),
            "eligible_groups": len(eligible), "eligible_games": len({i["canonical_game_id"] for i in eligible}),
            "eligible_new_mu_calls": sum(i["new_mu_calls"] for i in eligible),
            "selected_groups": len(selected), "selected_games": len(game_counts),
            "selected_new_mu_calls": sum(i["new_mu_calls"] for i in selected),
            "excluded_groups": len(items)-len(eligible), "exclusion_reason_counts_nonexclusive": dict(sorted(excluded_counts.items())),
            "input_outcome_status_counts": dict(sorted(Counter(i["outcome_status"] for i in items).items())),
            "state_disposition_records": None if dispositions is None else len(dispositions),
            "source_draft_policy_failure_points": failure_points},
        "candidates": items, "selected": deepcopy(selected), "state_dispositions": deepcopy(dispositions),
        "selection_trace": {"eligible_global_order": [i["candidate_key"] for i in eligible],
            "first_pass": {"performed": complete, "visits": first_pass},
            "second_pass": {"performed": complete and bool(second_pass), "visits": second_pass}},
        "runtime_authorized": False, "automatic_retries": False, "automatic_threshold_changes": False,
        "statistical_acceptance": False, "selection_replay_tasks_available": complete and bool(selected),
        "evidence_binding_contract": "Archive adapter and CLI verify files and frozen events; selector validates basic schema and retains opaque bindings",
        "incomplete_collection_policy": "No executable selection from a completed subset; retain missing and excluded evidence"}
    return seal(plan)
