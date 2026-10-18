"""Export bounded, offline D0 local job/service identity evidence.

Reads only accepted manifests, their runtime receipts, and accepted first-action
and rollout records. It follows retained samples to their original manifest.
This is not a production audit or a per-HTTP service instrumentation claim.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


FINAL = Path("cs5446_modified/research_progress/2026-10-14-d0var-completion")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def classify(identities, *, local_event_exists=True):
    """Only complete, identical observed pairs qualify as verified false."""
    if not local_event_exists:
        return "not_applicable"
    complete = {(x.get("job_id"), x.get("service_instance_id")) for x in identities
                if x.get("job_id") and x.get("service_instance_id")}
    if len(complete) > 1:
        return "true"
    if not identities or any(not x.get("job_id") or not x.get("service_instance_id")
                             for x in identities):
        return "unknown"
    return "false"


def remote_relative(value):
    value = str(value).replace("\\", "/")
    return value.split("/project/", 1)[1] if "/project/" in value else value


def export(source_root, snapshot_path, source_bindings_path):
    root = source_root.resolve()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    check(digest({k: v for k, v in snapshot.items() if k != "sha256"}) == snapshot["sha256"],
          "Snapshot seal mismatch")
    prior = json.loads(source_bindings_path.read_text(encoding="utf-8"))
    check(digest({k: v for k, v in prior.items() if k != "sha256"}) == prior["sha256"],
          "Source binding seal mismatch")
    expected = {row["logical_path"]: row for row in prior["files"]}
    bindings = {}

    def logical(path):
        return path.resolve().relative_to(root).as_posix()

    def read(path, bound=None, *, lines=False):
        name = logical(path)
        raw = path.read_bytes()
        actual = {"logical_path": name, "size": len(raw),
                  "sha256": hashlib.sha256(raw).hexdigest()}
        target = bound or expected.get(name)
        check(target is not None, "Unbound original: " + name)
        check(actual["sha256"] == target["sha256"] and actual["size"] == target["size"],
              "Original byte binding mismatch: " + name)
        bindings[name] = actual
        return ([json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
                if lines else json.loads(raw))

    index = read(root / FINAL / "FINAL_EVIDENCE_INDEX.json")
    accounting = read(root / FINAL / "FINAL_ACCOUNTING_SUMMARY.json")

    def local(value):
        value = str(value).replace("\\", "/")
        for marker in ("/.review-cache/", "/cs5446_modified/"):
            if marker in value:
                return root / (marker[1:] + value.split(marker, 1)[1])
        return root / value

    for row in index["files"]:
        expected[logical(local(row["local_path"]))] = row
    accepted_paths = [local(g["manifest"]["local_path"]) for g in accounting["per_game"]]
    projects = sorted({next(p for p in mp.parents if p.name == "project") for mp in accepted_paths})
    manifest_cache = {}
    runtime_cache = {}

    def resolve(remote):
        relative = remote_relative(remote)
        candidates = [p / relative for p in projects if (p / relative).is_file()]
        check(len(candidates) == 1, "Ambiguous/missing indexed origin: " + relative)
        return candidates[0]

    def manifest(path):
        name = logical(path)
        if name not in manifest_cache:
            manifest_cache[name] = read(path)
        return manifest_cache[name]

    def runtime(path):
        name = logical(path)
        if name in runtime_cache:
            return runtime_cache[name]
        m = manifest(path)
        project = next(p for p in path.parents if p.name == "project")
        pairs = []
        sources = []
        for field, receipt in (("inputs.admission", m["inputs"]["admission"]),
                               ("final_input_check", m.get("final_input_check"))):
            if not receipt:
                continue
            if receipt.get("$evidence"):
                rp = project / receipt["path"]
                receipt = read(rp, receipt)
                body = receipt.get("body", receipt)
                sources.append({"logical_path": logical(rp), "field": "body"})
            else:
                body = receipt
                sources.append({"logical_path": name, "field": field})
            check(body.get("status") == "passed", "Runtime admission is not passed: " + name)
            pairs.append({"job_id": body.get("job_id"),
                          "service_instance_id": body.get("service_instance_id")})
        check(pairs, "No runtime admission: " + name)
        check(all(p == pairs[0] for p in pairs), "Runtime identity changed within manifest: " + name)
        result = {**pairs[0], "origin_manifest": name,
                  "runtime_sources": sources,
                  "terminal_runtime_receipt_present": bool(m.get("final_input_check"))}
        runtime_cache[name] = result
        return result

    points = {p["state_id"]: p for p in snapshot["points"]}
    states, groups = [], []
    for game, mp in zip(accounting["per_game"], accepted_paths):
        m = manifest(mp)
        check(m["status"] == "complete" and m["canonical_game_id"] == game["game_id"],
              "Accepted manifest has wrong game or status")
        check(runtime(mp)["job_id"] == str(game["job_id"]), "Accepted runtime job differs")
        resume = m.get("resume_provenance", {})
        for ref in resume.get("prior_input_files", []):
            # Bind only originals actually read, not the entire recovery archive.
            if ref["path"].endswith(("/runner/manifest.json", "/runner/first_actions.jsonl")):
                expected[logical(resolve(ref["path"]))] = ref
        firsts = read(mp.parent / "first_actions.jsonl", lines=True)
        rolls = read(mp.parent / "rollouts.jsonl", lines=True)
        check(len(rolls) == game["physical_groups"], "Accepted group count mismatch")
        origin_by_group = {g["group_id"]: g for g in resume.get("active_group_provenance", [])}
        grouped = {}
        for row in rolls:
            audit = row.get("call_audit")
            provenance = origin_by_group.get(row["group_id"], {}).get("origin", "accepted_attempt")
            if audit:
                origin = resolve(str(Path(remote_relative(audit["path"])).parent.parent / "manifest.json"))
                identity_basis = "bound_continuation_audit_path_and_origin_runtime_receipts"
            else:
                check(row["model_calls"] == row["new_mu_calls"] == 0 and not resume,
                      "Missing continuation audit for nonzero calls or resumed group")
                origin = mp
                identity_basis = "zero_mu_calls_environment_group_in_accepted_manifest"
            observed = runtime(origin)
            original_manifest = manifest(origin)
            check(original_manifest["canonical_game_id"] == game["game_id"], "Origin manifest has wrong game")
            original_groups = {g["group_id"]: g for g in original_manifest["planned_groups"]}
            check(row["group_id"] in original_groups
                  and original_groups[row["group_id"]]["rollout_id"] == row["rollout_id"],
                  "Accepted group is absent from its execution manifest")
            if provenance == "retained_original_sample":
                check(origin != mp, "Retained group incorrectly attributed to accepting job")
            else:
                check(origin == mp, "New group points to another execution origin")
            evidence = {"canonical_game_id": game["game_id"], "state_id": row["state_id"],
                        "group_id": row["group_id"], "rollout_id": row["rollout_id"],
                        "branches": row["branches"], "origin": provenance,
                        "identity_basis": identity_basis,
                        "identity": observed, "accepted_rollouts_source": logical(mp.parent / "rollouts.jsonl"),
                        "call_audit_binding": ({**audit, "path": remote_relative(audit["path"])} if audit else None),
                        "call_audit_bytes_read_for_identity": False}
            groups.append(evidence)
            grouped.setdefault(row["state_id"], []).append(evidence)
        for first in firsts:
            sid = first["state_id"]
            point = points[sid]
            check(point["canonical_game_id"] == game["game_id"], "State/game association differs")
            check({g["group_id"] for g in grouped.get(sid, [])}
                  == {g["group_id"] for g in point["physical_groups"]}, "Snapshot group coverage differs")
            local_exists = first["local_confidence_event_exists"]
            check(local_exists == point["local_confidence_event_exists"], "Local event eligibility differs")
            first_source = logical(mp.parent / "first_actions.jsonl")
            first_identity = None
            if local_exists:
                audit = first.get("call_audit")
                if audit:
                    origin = resolve(str(Path(remote_relative(audit["path"])).parent.parent / "manifest.json"))
                else:
                    check(first.get("resume_call_provenance"), "No first-action origin")
                    origin = resolve(remote_relative(resume["prior_runner_directory"]) + "/manifest.json")
                    original_first_path = origin.parent / "first_actions.jsonl"
                    originals = read(original_first_path, lines=True)
                    matches = [x for x in originals if x["state_id"] == sid]
                    check(len(matches) == 1, "Retained first-action source absent")
                    for branch in ("N", "P"):
                        check(matches[0]["branches"][branch]["call_id"] == first["branches"][branch]["call_id"],
                              "Retained branch call ID differs")
                    check(matches[0]["prediction"] == first["prediction"], "Retained prediction differs")
                    first_source = logical(original_first_path)
                first_identity = runtime(origin)
            identities = ([first_identity] if first_identity else []) + [g["identity"] for g in grouped.get(sid, [])]
            status = classify(identities, local_event_exists=local_exists)
            states.append({"canonical_game_id": game["game_id"], "state_id": sid,
                           "status": status, "statistical_weight": point["statistical_weight"],
                           "snapshot_label": point["cross_job_state"],
                           "first_action_identity": first_identity,
                           "first_action_source": first_source,
                           "physical_group_ids": [g["group_id"] for g in grouped.get(sid, [])],
                           "identity_pairs": [dict(zip(("job_id", "service_instance_id"), pair)) for pair in sorted(
                               {(i["job_id"], i["service_instance_id"]) for i in identities})]})
    check(len(states) == 71 and {s["state_id"] for s in states} == set(points), "State coverage is not 71")
    check(len(groups) == len({g["rollout_id"] for g in groups}) == 117, "Physical group coverage is not 117")
    counts = Counter(s["status"] for s in states)
    result = {"schema_version": 1, "kind": "d0_local_identity_evidence",
              "snapshot_content_sha256": snapshot["sha256"],
              "scope": "Local first-action generation and D/N/P physical continuation execution; cached source drafts excluded.",
              "verification": "Original manifest/record bytes and referenced runtime admission receipts checked; retained groups traced to original execution manifest.",
              "limitations": ["Offline recorded identity evidence, not a live service verification.",
                              "Call logs do not directly instrument service_instance_id; execution origin is associated through bound audit paths and runtime receipts.",
                              "No production hydration/finalization or complete HTTP audit was rerun."],
              "summary": {"states": len(states), "physical_groups": len(groups),
                          "status_counts": {k: counts[k] for k in ("false", "true", "unknown", "not_applicable")},
                          "original_weight_by_status": {k: sum(s["statistical_weight"] for s in states if s["status"] == k)
                                                        for k in ("false", "true", "unknown", "not_applicable")}},
              "states": states, "physical_groups": groups,
              "source_bindings": sorted(bindings.values(), key=lambda x: x["logical_path"])}
    result["sha256"] = digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=Path("gpu_analysis/data/d0_snapshot.json"))
    parser.add_argument("--source-bindings", type=Path, default=Path("gpu_analysis/data/source_bindings.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    check(not args.out.exists(), "Output exists; choose a new path")
    result = export(args.source_root, args.snapshot, args.source_bindings)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
