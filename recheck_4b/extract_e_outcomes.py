"""Build the public per-episode E outcome table from the certified attempt evidence.

Run by the data owner, who holds the downloaded attempts (about 8.6 GB with call audits):
    python -B recheck_4b/extract_e_outcomes.py --attempts <local>/attempts.json --out-dir recheck_4b/data

Reads each certified episode JSONL plus, for policy failures only, the failing call in the
audit file. Game paths are reduced to ALFWorld "<task>/<trial>" identifiers so no machine
or cluster home path is published. Standard library only.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ARMS = ("always", "no_info", "none")
ROLES = ("draft", "no_info", "no_info_fallback", "replan")
COST = ("logical_calls", "http_attempts_recorded", "known_prompt_tokens", "known_completion_tokens",
        "sum_known_request_elapsed_s", "calls_without_latency", "calls_with_unknown_attempt_count",
        "attempts_without_complete_usage", "token_cost_complete")


def game_id(gamefile):
    parts = PurePosixPath(gamefile.replace("\\", "/")).parts
    if len(parts) < 3 or not parts[-2].startswith("trial_"):
        raise ValueError(f"unexpected gamefile layout: {gamefile!r}")
    return f"{parts[-3]}/{parts[-2]}"


def failing_call(audit_path, call_id):
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("event") == "request_success" and event.get("call_id") == call_id:
            response = event.get("response") or {}
            return response.get("raw_finish_reason"), response.get("completion_tokens")
    raise ValueError(f"failing call {call_id} not found in {audit_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--attempts", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    attempts = json.loads(args.attempts.read_text(encoding="utf-8"))["attempts"]
    if sorted((a["shard_index"], a["attempt"]) for a in attempts) != [(i, 1) for i in range(10)]:
        raise ValueError("expected exactly attempt 1 of shards 0..9 (the selected E attempts)")
    table, sources = [], []
    for entry in sorted(attempts, key=lambda a: a["shard_index"]):
        rows_path = Path(entry["output_root"]) / "data" / f"episode_level_{entry['run_id']}.jsonl"
        raw = rows_path.read_bytes()
        sources.append({"shard_index": entry["shard_index"], "run_id": entry["run_id"],
                        "rows_sha256": hashlib.sha256(raw).hexdigest(), "rows_bytes": len(raw)})
        for row in (json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()):
            if row["run_id"] != entry["run_id"] or row["arm"] not in ARMS:
                raise ValueError(f"unexpected row identity in {rows_path}")
            failure = None
            if row.get("policy_failure"):
                pf = row["policy_failure"]
                audit = rows_path.with_suffix(".calls") / f"task-{row['task_index']:06d}.jsonl"
                finish, tokens = failing_call(audit, pf["call_id"])
                failure = {"decision_role": pf.get("decision_role"), "reason": pf.get("reason"),
                           "step": pf.get("step"), "raw_finish_reason": finish, "completion_tokens": tokens}
            cost = row.get("call_cost") or {}
            by_role = row.get("call_cost_by_decision_role") or {}
            table.append({
                "shard_index": entry["shard_index"], "run_id": entry["run_id"], "task_index": row["task_index"],
                "arm": row["arm"], "game": game_id(row["gamefile"]), "task_type": row.get("task_type"),
                "Y_study": row["Y_study"], "outcome_status": row["outcome_status"],
                "environment_success": row.get("environment_success"),
                "termination_reason": row.get("termination_reason"), "steps": row.get("steps"),
                "n_world_model_calls": row.get("n_world_model_calls"),
                "planner_calls_by_role": {role: (by_role.get(role) or {}).get("logical_calls", 0) for role in ROLES},
                "cost": {field: cost.get(field) for field in COST},
                "policy_failure": failure,
            })
    keys = [(r["arm"], r["game"]) for r in table]
    if len(table) != 402 or len(set(keys)) != 402 or len({r["game"] for r in table}) != 134:
        raise ValueError("expected 134 distinct games x 3 arms")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "e_episode_outcomes.jsonl"
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in table).encode("utf-8")
    out.write_bytes(body)
    manifest = {
        "kind": "aim3_e_public_episode_outcomes",
        "rows": len(table), "games": 134, "arms": list(ARMS),
        "file": out.name, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
        "selected_attempts": sources,
        "game_identifier": "ALFWorld '<task>/<trial>' taken from the frozen gamefile path; machine prefixes removed",
        "failure_fields": "raw_finish_reason and completion_tokens read from the failing call in the certified call audit",
        "extraction_script": "recheck_4b/extract_e_outcomes.py",
        "scope": "Selected (first evidence-complete) attempt of every shard; certified on the cluster and locally.",
    }
    (args.out_dir / "DATA_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                                    encoding="utf-8", newline="\n")
    print(json.dumps({"rows": len(table), "sha256": manifest["sha256"]}))


if __name__ == "__main__":
    main()
