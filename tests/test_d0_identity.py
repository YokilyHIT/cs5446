"""Necessary identity eligibility and real portable evidence regressions."""
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("identity_export", ROOT / "tools/export_d0_identity_evidence.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_incomplete_identity_cannot_enter_verified_false_pool():
    known = {"job_id": "1", "service_instance_id": "service-a"}
    assert MODULE.classify([known, {"job_id": "1"}]) == "unknown"
    assert MODULE.classify([]) == "unknown"
    assert MODULE.classify([], local_event_exists=False) == "not_applicable"


def test_service_restart_and_retained_other_job_are_cross_job():
    a = {"job_id": "1", "service_instance_id": "service-a"}
    b = {"job_id": "1", "service_instance_id": "service-b"}
    c = {"job_id": "2", "service_instance_id": "service-a"}
    assert MODULE.classify([a, a]) == "false"
    assert MODULE.classify([a, b]) == "true"
    assert MODULE.classify([a, c]) == "true"


def test_real_evidence_covers_original_selection_and_physical_groups():
    evidence = json.loads((ROOT / "gpu_analysis/data/d0_identity_evidence.json").read_text(encoding="utf-8"))
    snapshot = json.loads((ROOT / "gpu_analysis/data/d0_snapshot.json").read_text(encoding="utf-8"))
    assert MODULE.digest({k: v for k, v in evidence.items() if k != "sha256"}) == evidence["sha256"]
    assert evidence["snapshot_content_sha256"] == snapshot["sha256"]
    assert {(s["canonical_game_id"], s["state_id"]) for s in evidence["states"]} == {
        (p["canonical_game_id"], p["state_id"]) for p in snapshot["points"]}
    assert {g["rollout_id"] for g in evidence["physical_groups"]} == {
        g["rollout_id"] for p in snapshot["points"] for g in p["physical_groups"]}
    assert len(evidence["physical_groups"]) == 117
    assert evidence["summary"]["status_counts"] == {"false": 67, "true": 1, "unknown": 0, "not_applicable": 3}
    cross = [s for s in evidence["states"] if s["status"] == "true"]
    assert cross[0]["state_id"].endswith(":19")
    assert {p["job_id"] for p in cross[0]["identity_pairs"]} == {"935310", "943506"}
    retained = [g for g in evidence["physical_groups"] if g["origin"] == "retained_original_sample"]
    assert len(retained) == 2
    assert all(g["identity"]["job_id"] == "935310" for g in retained)
    assert all(s["first_action_identity"] is None for s in evidence["states"] if s["status"] == "not_applicable")
