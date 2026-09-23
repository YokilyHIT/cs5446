#!/usr/bin/env python
"""
Aggregate "the model answered with something that wasn't a legal admissible
action, and had to be forced onto a fallback" (`action_forced` /
`forced_action_count`, see preexperiments/common/alfworld_runner.py::ground_action)
across whichever episode-level result files currently exist, and hard-fail
if the rate is too high.

Why this exists (added after review): `ground_action` silently falls back to
a difflib closest-match or the first admissible action whenever the model's
raw output doesn't exactly match one. That fallback is necessary -- it keeps
one malformed generation from crashing an episode -- but it is also
invisible in the success-rate numbers: an agent that is actually just being
forced onto arbitrary actions most of the time will produce completed
episodes with normal-looking logs and a real (probably bad) success rate,
with nothing anywhere flagging that most of its "choices" weren't really
choices at all. Silently accepting that would make every downstream
experiment-A/B statistic meaningless without ever throwing an error.

Run this after the smoke test's episode-collection steps (wired into
scripts/run_smoke_test.sh) and optionally again after a full experiment run
to audit the same thing at scale.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (filename, has_steps_field) -- files without a per-record "steps" field
# (fixed-length episodes only) fall back to counting 1 "step" per record,
# which just means their contribution to the rate is by episode count
# rather than by raw action count; still a valid, if coarser, signal.
_EPISODE_FILES = [
    "A_train_episodes_raw.jsonl",
    "A_pairwise_episodes.jsonl",
    "A_topk_vs_all_raw.jsonl",
]


def _iter_records(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def compute_rate(results_dir: Path) -> tuple[int, int, dict]:
    total_forced = 0
    total_steps = 0
    per_file = {}

    for filename in _EPISODE_FILES:
        path = results_dir / filename
        file_forced = 0
        file_steps = 0
        for rec in _iter_records(path):
            forced = rec.get("forced_action_count")
            if forced is None:
                continue
            steps = rec.get("steps", 1)
            file_forced += forced
            file_steps += steps
        if file_steps:
            per_file[filename] = {"forced": file_forced, "steps": file_steps, "rate": file_forced / file_steps}
        total_forced += file_forced
        total_steps += file_steps

    b_summary_path = results_dir / "B_base_episode_success_summary.json"
    if b_summary_path.exists():
        b_summary = json.loads(b_summary_path.read_text(encoding="utf-8"))
        file_forced = b_summary.get("forced_action_count", 0)
        file_steps = b_summary.get("total_steps", 0)
        if file_steps:
            per_file["B_base_episode_success_summary.json"] = {
                "forced": file_forced, "steps": file_steps, "rate": file_forced / file_steps
            }
        total_forced += file_forced
        total_steps += file_steps

    return total_forced, total_steps, per_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results_dir", default=str(PROJECT_ROOT / "results"))
    parser.add_argument(
        "--max_rate", type=float, default=0.20,
        help="Abort with exit code 1 if the aggregate forced-action rate exceeds this fraction.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    total_forced, total_steps, per_file = compute_rate(results_dir)

    if total_steps == 0:
        print(
            "[check_forced_action_rate] no episode files with forced_action_count found yet "
            f"under {results_dir} -- nothing to check (this is expected before any episodes have run)."
        )
        return 0

    rate = total_forced / total_steps
    print(f"[check_forced_action_rate] per-file breakdown:")
    for filename, stats in per_file.items():
        print(f"  {filename}: {stats['forced']}/{stats['steps']} = {stats['rate']:.1%}")
    print(f"[check_forced_action_rate] overall: {total_forced}/{total_steps} = {rate:.1%}")

    if rate > args.max_rate:
        print(
            f"\nFAIL: forced-action rate {rate:.1%} exceeds the {args.max_rate:.0%} limit. "
            "This means the model's raw output failed to match any admissible action on a large "
            "fraction of steps and ground_action() had to fall back to a closest-match/first-action "
            "heuristic -- the agent has effectively been taking semi-random actions, and every "
            "success-rate number computed from these episodes is unreliable. Common causes: the "
            "REACT_ACTION_PROMPT isn't being followed (check the raw model output in the logs), "
            "the model is truncating output before finishing the action string (raise max_tokens), "
            "or admissible_actions extraction is returning the wrong strings (re-run "
            "scripts/inspect_alfworld_api.py).",
            file=sys.stderr,
        )
        return 1

    print(f"\nOK: forced-action rate {rate:.1%} is within the {args.max_rate:.0%} limit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
