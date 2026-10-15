"""CPU-only descriptive metrics from an exported D0 snapshot (not a full report)."""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[1]
SIDE = ROOT / "research_progress/2026-10-10-d0-analysis/sidecar"
sys.path.insert(0, str(SIDE))

from analysis_tool import read, require, seal, verify_seal, write_new
from analysis_metrics import analyze
from analysis_cases import select_cases
from analysis_sensitivity import summarize_sensitivity


def file_binding(path):
    raw = path.read_bytes()
    return {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def implementation_bindings():
    manifest = read(ROOT / "tools/analysis_sources.json")
    bindings = []
    for entry in manifest["files"]:
        path = ROOT / entry["path"]
        actual = file_binding(path)
        require(actual == {key: entry[key] for key in ("size", "sha256")},
                "Original analysis source bytes changed: " + entry["path"])
        bindings.append({"path": entry["path"], **actual})
    for relative in ("tools/analyze_d0_snapshot.py", "tools/analysis_sources.json"):
        bindings.append({"path": relative, **file_binding(ROOT / relative)})
    return bindings


def cross_job_inventory(points):
    """Keep the exported labels visible without inferring service provenance."""
    groups = {label: [] for label in ("false", "true", "unknown", "not_applicable")}
    for point in points:
        value = point.get("cross_job_state")
        if value is False:
            label = "false"
        elif value is True:
            label = "true"
        elif value == "not_applicable":
            label = "not_applicable"
        else:
            require(value is None or value == "unknown", "Unknown cross_job_state label")
            label = "unknown"
        groups[label].append(point)
    return {
        "scope": "exported_state_labels_only; job/service evidence is not rebuilt by this CLI",
        "categories": {
            label: {"states": len(rows),
                    "games": len({p["canonical_game_id"] for p in rows}),
                    "original_weight_mass": math.fsum(p["statistical_weight"] for p in rows)}
            for label, rows in groups.items()
        },
        "exclusion_sensitivity_performed": False,
    }


def make_snapshot_analysis(dataset, source_binding):
    metrics = analyze(dataset)
    return {
        "schema_version": 1,
        "kind": "d0_portable_metrics_snapshot_analysis",
        "status": "metrics_only_development_description",
        "runtime_authorized": False,
        "formal_inference_accepted": False,
        "full_D0_report_complete": False,
        "D0_game_count": dataset["D0_game_count"],
        "original_selected_state_count": dataset["original_selected_state_count"],
        "source_snapshot": source_binding,
        "source_snapshot_content_sha256": dataset["sha256"],
        "collection_status_in_snapshot": dataset["status"],
        "metrics": metrics,
        "cases": select_cases(dataset, metrics["point_metrics"]),
        "game_sensitivity": summarize_sensitivity(dataset, metrics["point_metrics"]),
        "cross_job_inventory": cross_job_inventory(dataset["points"]),
        "costs": {"status": "not_computed", "reason": "Per-call source/local cost evidence is not an input to this CLI."},
        "validation_scope": {
            "snapshot_content_seal_verified": True,
            "original_source_copy_hashes_verified": True,
            "full_provenance_audit_performed": False,
            "cost_analysis_performed": False,
            "physical_behavior_analysis_performed": False,
            "N_P_selection_or_execution_performed": False,
        },
        "analysis_environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numeric_representation": "Python float; no score rounding/tolerance grouping",
            "summation": "math.fsum for weighted aggregates",
        },
        "limits": [
            "This analyzes the portable snapshot; it does not regenerate the snapshot from the entire accepted evidence chain.",
            "D0 development description only, not a complete D0 report or D1/E inference.",
            "Y differences are single observations, not measured true conditional utility differences.",
            "Missing observations remain missing; original 1/(J*k_j) weights and exact score ties are unchanged.",
            "Confidence is a ranking score, not calibrated probability; EM/token-F1 are text-match proxies.",
            "Game deletion ranges are sensitivity descriptions, not confidence intervals.",
            "No confidence interval, p-value, certified C bound or automatically selected D1 size is produced.",
            "Cross-job exclusion sensitivity, full physical-path diagnostics, per-call costs and N/P candidates remain separate work.",
        ],
        "new_model_calls": 0,
        "new_environment_instances": 0,
    }


def cell(value):
    return ("—" if value is None else str(value)).replace("|", "\\|").replace("\n", " ")


def render_markdown(report):
    lines = ["# D0 portable snapshot: descriptive metrics", "",
             "Status: `metrics_only_development_description`. This is not the complete D0 report.", "",
             f"Snapshot: {report['D0_game_count']} games, {report['original_selected_state_count']} originally selected states.", "",
             "Original weights are retained. A primary mean stays missing when its target has missing values; the available-case column describes only the observed intersection.", "",
             "| Pool / metric | Primary mean | Available-case mean | Target / observed states | Observed original weight mass |",
             "|---|---:|---:|---:|---:|"]
    for pool_name, pool in report["metrics"]["aggregate"].items():
        stats = [("Y_" + key, value) for key, value in pool["branch_available"].items()]
        stats += [("U_" + key, value) for key, value in pool["observed_U"].items()]
        stats += list(pool["accuracy"].items())
        for name, stat in stats:
            lines.append(f"| {pool_name} / {name} | {cell(stat['mean'])} | {cell(stat['available_case_mean'])} | {stat['target_denominator']['points']} / {stat['observed_denominator']['points']} | {cell(stat['observed_denominator']['original_weight_mass'])} |")
    lines += ["", "## Fixed development cases", ""]
    for category in report["cases"]["categories"]:
        lines.append(f"- `{category['category']}`: eligible {category['eligible_count']}; selected {cell(category['selected'])}; unavailable reason {cell(category['reason'])}.")
    lines += ["", "## Cross-job labels", "",
              "These are exported labels; this command does not re-audit job/service identities or calculate the exclusion sensitivity.", "",
              "| Label | States | Games | Original weight mass |", "|---|---:|---:|---:|"]
    for label, counts in report["cross_job_inventory"]["categories"].items():
        lines.append(f"| {label} | {counts['states']} | {counts['games']} | {counts['original_weight_mass']} |")
    lines += ["", "## Scope and remaining work", ""]
    lines += ["- " + item for item in report["limits"]]
    lines += ["", "The JSON contains the full metric intersections, fixed cases and game deletion sensitivity. Costs are explicitly not computed here; consult the separate accounting snapshot.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    source, output = args.dataset.resolve(), args.out.resolve()
    markdown = output.with_suffix(".md")
    require(output.suffix.lower() == ".json", "--out must be a .json file")
    require(not output.exists() and not markdown.exists(), "Output already exists; use a new output path")
    implementation = implementation_bindings()
    before = file_binding(source)
    dataset = read(source)
    verify_seal(dataset)
    report = make_snapshot_analysis(dataset, {"name": source.name, **before})
    report["implementation_files"] = implementation
    report = seal(report)
    rendered = render_markdown(report)
    require(file_binding(source) == before, "Input snapshot changed during analysis")
    require(implementation_bindings() == implementation, "Implementation changed during analysis")
    write_new(output, report)
    with markdown.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(rendered)
    print(f"{report['status']}: {output} and {markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
