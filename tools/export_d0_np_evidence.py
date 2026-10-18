"""Extract accepted physical recovery/call bindings, without running an audit or model.

Reads only the files already named by the portable source bindings. Actual
continuation request counts are independently checked by the cost exporter.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def export(source_root, data_dir):
    snapshot = read(data_dir / "d0_snapshot.json")
    paths = read(data_dir / "d0_rollout_summaries.json")
    sources = read(data_dir / "source_bindings.json")
    for document in (snapshot, paths, sources):
        require(document["sha256"] == digest({k: v for k, v in document.items() if k != "sha256"}),
                "Portable input content seal differs")
    bindings = {row["logical_path"]: row for row in sources["files"]}

    def bound_bytes(binding):
        raw = (source_root / binding["logical_path"]).read_bytes()
        require(len(raw) == binding["size"] and hashlib.sha256(raw).hexdigest() == binding["sha256"],
                "Archived source differs: " + binding["logical_path"])
        return raw

    # The portable source bindings retain the exact accepted final index. No
    # historical directory search or result-based selection is performed.
    index_binding = sources["final_evidence_index_source"]
    index = json.loads(bound_bytes(index_binding))
    require(index["status"] == "complete", "Final index is incomplete")
    run_roots = {}
    for entry in index["files"]:
        local = entry["local_path"].replace("\\", "/")
        marker = "/project/run-results/"
        if marker in local:
            prefix, suffix = local.split(marker, 1)
            run_id = suffix.split("/", 1)[0]
            # Relocate only the project-relative path recorded in the final
            # index. A resumed game's old call ledger stays in its original run.
            cache_relative = ".review-cache/" + prefix.split("/.review-cache/", 1)[1]
            run_root = cache_relative + marker + run_id
            require(run_id not in run_roots or run_roots[run_id] == run_root,
                    "Final index has conflicting archive roots")
            run_roots[run_id] = run_root
    by_file = defaultdict(list)
    for group in paths["groups"]:
        by_file[group["source_binding_path"]].append(group)
    rows = []
    for logical_path, summaries in by_file.items():
        binding = {key: bindings[logical_path][key] for key in ("logical_path", "size", "sha256")}
        records = [json.loads(line) for line in bound_bytes(binding).splitlines() if line.strip()]
        raw_by = {row["rollout_id"]: row for row in records}
        require(len(raw_by) == len(records) == len(summaries), "Physical rollout coverage differs")
        for group in summaries:
            raw = raw_by[group["rollout_id"]]
            for key in ("state_id", "state_spec_sha256", "rollout_id", "group_id", "branches",
                        "first_action", "new_mu_calls", "outcome_status", "measurement_validity", "Y_study"):
                require(raw[key] == group[key], "Portable rollout differs: " + key)
            audit = raw["call_audit"]
            # A retained cross-job physical rollout can refer to the original
            # job's audit, even when copied into the final accepted runner.
            audit_binding = None
            if audit is not None:
                suffix = audit["path"].replace("\\", "/").split("/project/run-results/", 1)[1]
                run_id, relative = suffix.split("/", 1)
                audit_path = Path(run_roots[run_id]) / relative
                audit_binding = {"logical_path": audit_path.as_posix(), "size": audit["size"], "sha256": audit["sha256"]}
            else:
                require(raw["new_mu_calls"] == 0 and not any(s["phase"] == "continuation" for s in raw["step_log"]),
                        "Positive continuation path lacks a ledger binding")
            recovery = raw["recovery"]
            timing = recovery.get("timings", {})
            rows.append({
                "canonical_game_id": group["canonical_game_id"],
                **{key: raw[key] for key in ("state_id", "group_id", "rollout_id", "branches", "new_mu_calls")},
                "rollout_file": binding,
                "rollout_sha256": digest(raw),
                "rollout_elapsed_s": raw["elapsed_s"],
                "recovery_timings": timing,
                "recovery": {"sha256": digest(recovery),
                    "input_validation_status": recovery["input_validation"]["status"],
                    "restoration_completed": timing.get("restoration_completed"),
                    "prefix_transitions": len(recovery.get("prefix_trace", []))},
                "call_audit": audit_binding,
            })
    require(len(rows) == 117 and len({r["rollout_id"] for r in rows}) == 117,
            "Expected all 117 distinct accepted physical rollouts")
    require(all(r["recovery"]["input_validation_status"] == "passed" and
                r["recovery"]["restoration_completed"] is True for r in rows), "Recovery is not accepted")
    document = {
        "schema_version": 1, "kind": "d0_accepted_physical_recovery_and_call_bindings",
        "status": "complete", "snapshot_content_sha256": snapshot["sha256"],
        "rollouts_content_sha256": paths["sha256"], "final_evidence_index": index_binding,
        "groups": rows,
        "scope": "All accepted physical groups; raw rollout identities and recovery objects bound. No model or environment is run.",
        "call_ledger_counts_verified_here": False,
        "call_verification": "Use cost evidence accepted_group_calls to verify fresh logical continuation requests; raw new_mu_calls alone is not the audit.",
        "timing_scope": "Original elapsed_s and recovery.timings for all 117 accepted physical rollouts; not job wall or allocation duration. Timing components can overlap and are not automatically additive.",
    }
    document["sha256"] = digest(document)
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "gpu_analysis/data")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    document = export(args.source_root.resolve(), args.data_dir.resolve())
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"groups": len(document["groups"]), "sha256": document["sha256"]}))


if __name__ == "__main__":
    main()
