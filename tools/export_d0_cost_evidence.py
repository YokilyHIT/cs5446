"""Read accepted archive pointers, verify used bytes and export compact call rows.

This is an offline data exporter; no production imports, model or environment
calls, finalization, ledger writes or network access. Original audit bodies stay
in the archive. Portable rows retain their record hashes and real usage records.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

from export_d0_snapshot import FINAL, check, digest, read, write_new
from d0_costs import summarize_costs

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "research_progress/2026-10-10-d0-analysis/sidecar"))
from analysis_costs import _call  # Frozen pure audit interpretation, unchanged.


def export(source_root, np_evidence_path, output):
    root = source_root.resolve()
    source_bindings = read(REPO / "gpu_analysis/data/source_bindings.json")
    portable = read(REPO / "gpu_analysis/data/final_accounting_summary.json")
    np_evidence = read(np_evidence_path)
    for name, value in (("N/P evidence", np_evidence), ("portable accounting", portable), ("source bindings", source_bindings)):
        check(digest({k: v for k, v in value.items() if k != "sha256"}) == value["sha256"], name + " seal differs")
    files = {}

    def local(path):
        text = str(path).replace("\\", "/")
        while "//" in text:
            text = text.replace("//", "/")
        for marker in ("/.review-cache/", "/cs5446_modified/"):
            if marker in text:
                return root / (marker[1:] + text.split(marker, 1)[1])
        return root / text

    def bind(path, expected=None, role="source"):
        path = path.resolve()
        key = path.relative_to(root).as_posix()
        if key not in files:
            raw = path.read_bytes()
            files[key] = {"logical_path": key, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "roles": []}
        item = files[key]
        if expected:
            check(item["sha256"] == expected["sha256"] and ("size" not in expected or item["size"] == expected["size"]), "Source hash differs: " + key)
        if role not in item["roles"]:
            item["roles"].append(role)
        return {k: item[k] for k in ("logical_path", "size", "sha256")}

    index_path = root / FINAL / "FINAL_EVIDENCE_INDEX.json"
    index = read(index_path)
    bind(index_path, role="final_evidence_index")
    final_index = {local(x["local_path"]).resolve(): x for x in index["files"]}
    accounting_path = root / FINAL / "FINAL_ACCOUNTING_SUMMARY.json"
    bind(accounting_path, final_index[accounting_path.resolve()], "final_accounting")
    accounting = read(accounting_path)
    check(portable["source"]["sha256"] == files[accounting_path.relative_to(root).as_posix()]["sha256"], "Portable accounting differs")
    exported_files = {x["logical_path"]: x for x in source_bindings["files"]}
    job_roots = {x["job_id"]: local(x["stage_result"]["local_path"]).parent for x in accounting["per_accepted_batch"]}
    # Exact archive locations for stopped/source attempts; all stage bytes are
    # checked against final accounting. No outcome-based archive search occurs.
    job_roots.update({
        "934277": root / ".review-cache/s934277/project/run-results/d0_source-934277",
        "934493": root / ".review-cache/src934493/project/run-results/d0_source-934493",
        "935310": root / ".review-cache/d0var-935310-20261012T140450Z/project/run-results/d0_var-935310",
        "944500": root / ".review-cache/j944500-20261014T104044Z/raw/project/run-results/d0_var-batch-944500",
    })
    for attempt in accounting["per_attempt"]:
        if attempt["job_id"] in job_roots:
            bind(job_roots[attempt["job_id"]] / "stage-result.json", attempt["stage_result_remote_binding"], "attempt_stage_result")

    audits = {}

    def add_audit(path, expected, role):
        bound = bind(path, expected, role)
        audits[bound["logical_path"]] = bound
        return bound

    def remote(path):
        value = str(path).replace("\\", "/")
        tail = value.split("run-results/", 1)[1]
        folder, relative = tail.split("/", 1)
        job = re.search(r"(\d+)$", folder).group(1)
        return job_roots[job] / relative

    for game in accounting["per_game"]:
        manifest = local(game["manifest"]["local_path"])
        bind(manifest, final_index[manifest.resolve()], "accepted_manifest")
        first_path = manifest.parent / "first_actions.jsonl"
        bind(first_path, exported_files[first_path.relative_to(root).as_posix()], "accepted_first_actions")
        for line in first_path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("call_audit"):
                spec = event["call_audit"]
                add_audit(remote(spec["path"]), spec, "accepted_first_action_audit")
            source = event["source_draft"]
            add_audit(remote(source["audit_path"]), {"sha256": source["audit_sha256"]}, "source_episode_audit")
            for spec in (event.get("resume_call_provenance") or {}).get("prior_audit_files", []):
                if "/calls/" in spec["path"] or spec["path"].endswith("/calls.jsonl"):
                    add_audit(remote(spec["path"]), spec, "prior_attempt_audit_including_failed_or_invalidated")
    for group in np_evidence["groups"]:
        if group["call_audit"]:
            spec = group["call_audit"]
            add_audit(local(spec["logical_path"]), spec, "accepted_group_audit")
    backend_reports = {x["job_id"]: x["backend_report"] for x in accounting["per_accepted_batch"]}
    for job, directory in job_roots.items():
        report_path = directory / "backend/report.json"
        if not report_path.exists():
            continue
        spec = backend_reports.get(job)
        bind(report_path, spec, "backend_report" if spec else "backend_report_self_sealed")
        report = read(report_path)
        check(report["sha256"] == digest({k: v for k, v in report.items() if k != "sha256"}), "Backend report seal differs")
        add_audit(report_path.parent / "calls.jsonl", report["artifacts"]["calls.jsonl"], "backend_acceptance_audit")

    rows, file_calls = [], {}
    for relative, binding in sorted(audits.items()):
        starts, terminals = {}, {}
        with (root / relative).open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                target = starts if record["event"] == "request_start" else terminals
                check(record["event"] in {"request_start", "request_success", "request_error"}, "Unknown audit event")
                check(record["call_id"] not in target, "Duplicate start/terminal")
                target[record["call_id"]] = (record, number)
        check(not set(terminals) - set(starts), "Terminal without request start")
        job = re.search(r"/d0_(?:source|var(?:-batch)?)-(\d+)/", relative).group(1)
        stage = "d0_source" if "/d0_source-" in relative else "d0_var"
        scope = "acceptance" if "/backend/" in relative else "source" if stage == "d0_source" else "local"
        file_calls[relative] = []
        for call_id, (start, line_number) in starts.items():
            terminal, terminal_line = terminals.get(call_id, (None, None))
            context = start["context"]
            phase = context.get("local_phase") or context.get("phase") or ("source_episode" if scope == "source" else "unknown")
            item = _call({"scope": "source" if scope == "source" else "local", "call_id": call_id,
                          "start": start, "terminal": terminal, "audit_file": {"path": relative, **binding},
                          "ledger_status": "complete_records" if terminal else "terminal_missing",
                          "phase": phase, "game_id": context.get("episode_id"),
                          "state_id": context.get("state_id"), "group_id": context.get("group_id")})
            audit = ((terminal.get("response") if terminal.get("event") == "request_success" else terminal.get("request_audit")) or {}) if terminal else {}
            attempts = [{k: a.get(k) for k in ("attempt_index", "status", "usage", "usage_status", "elapsed_wall_s", "backoff_elapsed_wall_s", "sdk_max_retries")}
                        for a in audit.get("request_attempts", [])]
            item.pop("audit_file")
            item.update({"scope": scope, "job_id": job, "campaign_stage": stage, "source_file": relative,
                         "start_line": line_number, "terminal_line": terminal_line,
                         "start_sha256": digest(start), "terminal_sha256": digest(terminal) if terminal else None,
                         "terminal_event": terminal.get("event") if terminal else None,
                         "attempts": attempts})
            rows.append(item)
            file_calls[relative].append(item)

    groups = []
    for group in np_evidence["groups"]:
        spec = group["call_audit"]
        calls = file_calls[spec["logical_path"]] if spec else []
        check(len(calls) == group["new_mu_calls"], "Physical group new-mu count differs")
        check(all(c["group_id"] == group["group_id"] and c["state_id"] == group["state_id"] and c["phase"] == "continuation" and c["terminal_sha256"] is not None for c in calls), "Physical group continuation call identity differs")
        groups.append({"rollout_id": group["rollout_id"], "group_id": group["group_id"],
                       "state_id": group["state_id"], "game_id": group["canonical_game_id"],
                       "call_ids": [c["call_id"] for c in calls], "audit_source": spec,
                       "rollout_source": group["rollout_file"], "rollout_record_sha256": group["rollout_sha256"],
                       "recovery_record_sha256": group["recovery"]["sha256"],
                       "rollout_elapsed_s": group["rollout_elapsed_s"], "recovery_timings": group["recovery_timings"],
                       "new_mu_calls": len(calls), "status": "verified_against_original_call_rows"})
    document = {"schema_version": 1, "kind": "derived_d0_real_call_cost_evidence",
                "accounting_source_sha256": portable["source"]["sha256"],
                "np_evidence_content_sha256": np_evidence["sha256"], "calls": rows,
                "accepted_group_calls": groups, "source_bindings": list(files.values()),
                "analysis_code": [{"path": path.relative_to(REPO).as_posix(),
                                   "size": path.stat().st_size,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                  for path in (Path(__file__).resolve(), REPO / "tools/d0_costs.py",
                                               REPO / "tools/export_d0_snapshot.py",
                                               REPO / "research_progress/2026-10-10-d0-analysis/sidecar/analysis_costs.py")],
                "counter_reconciliation": {
                    "935310": "Original audits contain 278 unique request_start records, 277 terminal records and 277 HTTP attempt records. Final accounting retains 277 recorded logical calls and 279 observed http_attempts_charged. The extra start has no terminal/HTTP-attempt record; its actual HTTP count, usage and outcome are unknown. The two-unit HTTP charge difference is conservative accounting, not evidence of two actual HTTP requests.",
                    "campaign": "Across 15 attempts: 2200 original request starts, 2199 terminals and 2199 saved HTTP attempts, versus accepted accounting counters of 2199 recorded logical calls and 2201 observed http_attempts_charged. The ledger is unchanged. Counts from incomplete attempts remain lower-coverage observations, not a complete campaign actual-cost total.",
                    "request_start_semantics": "A start records entry into an attempted logical model call, not proof of an HTTP request reaching the server. A missing terminal's zero saved attempts is missing evidence, not zero actual HTTP cost."},
                "coverage": {"campaign_attempts": 15, "call_audit_files": len(audits),
                             "logical_request_starts": len(rows), "accepted_physical_groups": len(groups),
                             "unrecorded_attempt_calls_unknown_jobs": [a["job_id"] for a in accounting["per_attempt"] if not a["counts_complete"]],
                             "no_local_stage_file": ["943125"],
                             "zero_observed_call_jobs": ["943125", "944500"]},
                "limitations": [
                    "Current campaign only; excludes earlier diagnostics, campaigns and smoke jobs.",
                    "Every exported row comes from an actual request_start; charged reservation totals are not expanded into rows.",
                    "Stopped-attempt recorded starts can omit other unrecorded calls; counts_complete=false never means actual total is known.",
                    "943125 has zero recorded calls in final accounting but its stage original was not located in the fixed archive map; no empty audit is invented.",
                    "Source 934277/934493 backend reports have matching self seals and audit artifact hashes; final accounting binds stage results, not these reports directly.",
                    "Missing HTTP/usage/terminal fields remain unknown; known subtotals include failed attempts where preserved.",
                    "The orphan 935310 request start is retained in cost rows and excluded from accepted physical-group calls. Starts and accepted accounting logical-call counters differ by one; neither value overwrites the other.",
                    "Rollout/recovery timings cover the 117 accepted physical groups only. Whole-runner time across accepted, resumed and stopped attempts is not exported; group elapsed is not runner/job wall time.",
                    "No wall-time addition across request, attempt, rollout and allocation; no monetary price or GPU busy-time inference."]}
    summary = summarize_costs(document, portable)
    document["reconciliation"] = {"complete_attempt_starts_match_recorded_counters": True,
                                  "start_minus_recorded_logical_by_job": {a["job_id"]: a["start_minus_accounting_logical"] for a in summary["per_attempt"]},
                                  "complete_attempt_http_match": True,
                                  "accepted_batch_split": {k: v["logical_calls"] for k, v in summary["ten_accepted_batches_split"].items()}}
    output.parent.mkdir(parents=True, exist_ok=True)
    write_new(output, document)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--np-evidence", type=Path, default=REPO / "gpu_analysis/data/d0_np_evidence.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.source_root, args.np_evidence, args.out), ensure_ascii=True, indent=2))
