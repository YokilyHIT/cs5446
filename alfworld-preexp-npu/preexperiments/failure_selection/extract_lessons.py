"""
Experiment A2 (spec section 9): turn each raw failure trajectory into one
reusable lesson via a single LLM call using FAILURE_LESSON_PROMPT verbatim.
"""
from __future__ import annotations

import argparse
import os
import re
from typing import Any, Dict, List

from preexperiments.common import prompts
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import append_jsonl, ensure_dirs, load_yaml_config, read_jsonl_all
from preexperiments.failure_selection._common import reset_output_file

_MAX_TRAJECTORY_STEPS = 20

_MISTAKE_RE = re.compile(r"mistake\s*:\s*(.+)", re.IGNORECASE)
_RULE_RE = re.compile(r"reusable rule\s*:\s*(.+)", re.IGNORECASE)


def _render_trajectory(step_records: List[Dict[str, Any]]) -> str:
    steps = step_records[-_MAX_TRAJECTORY_STEPS:]
    lines = [
        f"Action: {s.get('action', '')} -> Observation: {s.get('next_observation', '')}"
        for s in steps
    ]
    return "\n".join(lines)


def _parse_lesson(text: str) -> Dict[str, str]:
    mistake = None
    rule = None
    for line in text.splitlines():
        line = line.strip()
        if mistake is None:
            m = _MISTAKE_RE.match(line)
            if m:
                mistake = m.group(1).strip()
                continue
        if rule is None:
            m = _RULE_RE.match(line)
            if m:
                rule = m.group(1).strip()
    if mistake is None or rule is None:
        # Tolerate minor formatting drift rather than crashing the whole
        # run; store the raw text so a human can still inspect/fix it later.
        return {"mistake": "PARSE_FAILED", "lesson": text.strip()}
    return {"mistake": mistake, "lesson": rule}


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    input_file = args.input_file or os.path.join(results_dir, "A_failures_raw.jsonl")
    output_file = args.output_file or os.path.join(results_dir, "A_failure_lessons.jsonl")

    if not os.path.exists(input_file):
        raise FileNotFoundError(
            f"missing input file {input_file}, run collect_failures.py first."
        )

    failures = read_jsonl_all(input_file)
    if not failures:
        raise RuntimeError(f"{input_file} contains no failures; nothing to do.")

    reset_output_file(output_file)

    llm = load_client_from_config(config)
    temperature = config["experiment_a"]["lesson_temperature"]
    seed = 13

    parsed_ok = 0
    for failure in failures:
        prompt = prompts.FAILURE_LESSON_PROMPT.format(
            goal=failure["goal"],
            trajectory=_render_trajectory(failure["trajectory"]),
        )
        resp = llm.complete(prompt, seed=seed, temperature=temperature)
        parsed = _parse_lesson(resp.text)
        if parsed["mistake"] != "PARSE_FAILED":
            parsed_ok += 1

        record = {
            "failure_id": failure["failure_id"],
            "mistake": parsed["mistake"],
            "lesson": parsed["lesson"],
            "task_type": failure.get("task_type", "unknown"),
        }
        append_jsonl(output_file, record)

    print(
        f"[extract_lessons] lessons={len(failures)} parsed_ok={parsed_ok} "
        f"parse_failed={len(failures) - parsed_ok}\n  -> {output_file}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A2: extract one reusable lesson per failure.")
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    parser.add_argument("--input_file", default=None)
    parser.add_argument("--output_file", default=None)
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
