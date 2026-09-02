#!/usr/bin/env python
"""
Fills the fixed report template from spec section 36 using
results/A_summary.json and results/B_summary.json (written by
preexperiments/failure_selection/analyze.py and
preexperiments/world_model_utility/analyze.py respectively) plus the
environment fingerprint files from spec section 37
(ADAMEM_COMMIT.txt, gpu_info.txt) and preexperiment.yaml.

Run this LAST, after both experiments' analyze.py have produced their
summary JSON. Never writes claims stronger than "supported by preliminary
evidence" / "weakly supported" / "not supported under the current setup" --
those phrases are copied verbatim from each summary's `verdict`/
`interpretation` fields, never invented here (spec section 43).
"""
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path, default="(not recorded)"):
    return path.read_text(encoding="utf-8").strip() if path.exists() else default


def _fmt(value, digits=3):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _fmt_ci(point, ci):
    if point is None:
        return "N/A"
    if ci and len(ci) == 2:
        return f"{_fmt(point)} [{_fmt(ci[0])}, {_fmt(ci[1])}]"
    return _fmt(point)


def _fmt_ci_dict(d):
    """For the {point, ci_lo, ci_hi} shape used by experiment A's summary."""
    if not d:
        return "N/A"
    return _fmt_ci(d.get("point"), [d.get("ci_lo"), d.get("ci_hi")])


def _alfworld_version() -> str:
    """Spec section 36's report template asks for the ALFWorld version. Read it
    from the actually-installed distribution rather than leaving a pointer to
    requirements_lock.txt -- the version that produced the results is part of
    the result."""
    try:
        from importlib.metadata import version

        return version("alfworld")
    except Exception:
        return "(not installed / see requirements_lock.txt)"


def build_report(config_path: Path, results_dir: Path) -> str:
    import yaml

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    adamem_commit = _read_text(PROJECT_ROOT / "ADAMEM_COMMIT.txt")
    gpu_info = _read_text(PROJECT_ROOT / "gpu_info.txt")
    # gpu_info.txt is `npu-smi info` output on Ascend hosts (nvidia-smi on GPU
    # hosts). Its first line is an ASCII table border, so take the first line
    # that actually carries text -- e.g. "npu-smi 25.5.1  Version: 25.5.1".
    gpu_info_line = gpu_info
    if gpu_info != "(not recorded)":
        informative = [
            ln.strip() for ln in gpu_info.splitlines()
            if ln.strip().strip("+-|= ")
        ]
        gpu_info_line = informative[0].strip("| ") if informative else gpu_info.splitlines()[0]

    a = _read_json(results_dir / "A_summary.json") or {}
    b = _read_json(results_dir / "B_summary.json") or {}

    a_counts = a.get("data_counts", {})
    a_delta = a.get("a6_delta_distribution", {})
    a_luck = a.get("a6_luck_baseline", {})
    a_corr = a.get("a7_correlation", {})
    a_sr = a.get("a8_success_rates", {})
    a_go = a.get("go_no_go", {})

    lines = []
    lines.append("# Preliminary Experiment Results")
    lines.append("")
    lines.append("## Environment")
    lines.append(f"- AdaMEM commit: {adamem_commit}")
    lines.append(f"- ALFWorld version: {_alfworld_version()}")
    lines.append(f"- Qwen model: {config['model']['name']}")
    lines.append(f"- GPU: {gpu_info_line}")
    lines.append(f"- seeds: {config['seeds']}")
    lines.append("")
    lines.append("# Experiment A")
    lines.append("")
    lines.append("## Data")
    lines.append(f"- train episodes: {a_counts.get('train_episodes', 'N/A')}")
    lines.append(f"- failures: {a_counts.get('failures_collected', 'N/A')}")
    lines.append(f"- evaluated failures: {a_counts.get('failures_evaluated_pairwise', 'N/A')}")
    lines.append(f"- evaluation episodes: {a_counts.get('pairwise_episodes', 'N/A')} pairwise + {a_counts.get('topk_vs_all_episodes', 'N/A')} topk-vs-all")
    lines.append("")
    lines.append("## Main numbers")
    lines.append(f"- P(delta < 0): {_fmt(a_delta.get('p_delta_lt0'))}")
    lines.append(f"- P(delta = 0): {_fmt(a_delta.get('p_delta_eq0'))}")
    lines.append(f"- P(delta > 0): {_fmt(a_delta.get('p_delta_gt0'))}")
    lines.append(f"- Var(delta): {_fmt(a_delta.get('var_delta'))}")
    lines.append(f"- Spearman U vs delta: {_fmt_ci(a_corr.get('rho_u'), [a_corr.get('ci_lo'), a_corr.get('ci_hi')])}")
    lines.append(
        f"- luck-baseline p-value for P(delta<=0) (chance-level heterogeneity check, "
        f"n_sim={a_luck.get('n_simulations', 'N/A')}): {_fmt(a_luck.get('p_delta_le0_pvalue'))}"
    )
    lines.append(f"- NoMemory SR: {_fmt_ci_dict(a_sr.get('NoMemory'))}")
    lines.append(f"- AllLessons SR: {_fmt_ci_dict(a_sr.get('AllLessons'))}")
    lines.append(f"- RandomK SR: {_fmt_ci_dict(a_sr.get('RandomK'))}")
    lines.append(f"- TopK SR: {_fmt_ci_dict(a_sr.get('TopK'))}")
    lines.append("")
    lines.append("## Decision")
    lines.append(a_go.get("verdict", "N/A"))
    lines.append("")
    lines.append("## Interpretation")
    lines.append(a_go.get("interpretation", "(experiment A not yet run -- see results/A_summary.json)"))
    lines.append("")
    lines.append("# Experiment B")
    lines.append("")
    lines.append("## Data")
    lines.append(f"- decision points: {b.get('decision_points', 'N/A')}")
    lines.append(f"- changed-action points: {b.get('changed_points', 'N/A')}")
    lines.append(f"- calibration points: {b.get('calibration_points', 'N/A')}")
    lines.append(f"- evaluation points: {b.get('evaluation_points', 'N/A')}")
    lines.append("")
    lines.append("## Main numbers")
    lines.append(f"- mismatch rate: {_fmt(b.get('mismatch_rate'))}")
    lines.append(f"- rho(self-confidence, planning gain): {_fmt_ci(b.get('rho_self'), b.get('rho_self_ci'))}")
    lines.append(f"- rho(semantic-correctness, planning gain): {_fmt_ci(b.get('rho_sem'), b.get('rho_sem_ci'))}")
    lines.append(f"- oracle upper-bound gain: {_fmt_ci(b.get('oracle_gain'), b.get('oracle_gain_ci'))}")
    lines.append(f"- helpful foresight rate: {_fmt(b.get('helpful_rate'))}")
    lines.append(f"- harmful foresight rate: {_fmt(b.get('harmful_rate'))}")
    lines.append("")
    lines.append("## Decision")
    lines.append(b.get("verdict", "N/A"))
    lines.append("")
    lines.append("## Interpretation")
    lines.append(b.get("interpretation", "(experiment B not yet run -- see results/B_summary.json)"))
    lines.append("")
    lines.append("# Recommendation")

    def _is_go(verdict: str) -> bool:
        # Both analyze.py scripts now emit the SAME short tag convention
        # (GO / WEAK-GO / NO-GO / INCONCLUSIVE) as `verdict`, with the
        # required sentence-level phrasing living only in `interpretation`.
        # An earlier version of this check compared against "STRONG"/"GO"
        # prefixes that experiment B's verdict field never actually
        # produced, so direction B could never be recommended regardless of
        # its results -- fixed by using an exact tag match instead.
        return verdict.strip().upper() == "GO"

    a_verdict = a_go.get("verdict", "")
    b_verdict = b.get("verdict", "")
    a_is_go = _is_go(a_verdict)
    b_is_go = _is_go(b_verdict)
    a_inconclusive = a_verdict.strip().upper() == "INCONCLUSIVE"
    b_inconclusive = b_verdict.strip().upper() == "INCONCLUSIVE"

    if a_inconclusive or b_inconclusive:
        inconclusive_dirs = ", ".join(
            d for d, flag in (("A", a_inconclusive), ("B", b_inconclusive)) if flag
        )
        rec = (
            f"inconclusive for direction(s) {inconclusive_dirs} -- this run did not collect enough "
            "signal to judge (see the Interpretation section above for what to fix), so no GO/NO-GO "
            "recommendation should be drawn for it yet; re-run after addressing the stated issue "
            "before deciding."
        )
    elif a_is_go and not b_is_go:
        rec = "Candidate A"
    elif b_is_go and not a_is_go:
        rec = "Candidate B"
    elif a_is_go and b_is_go:
        rec = "Candidate A and Candidate B (both preliminarily supported -- prioritize by team bandwidth)"
    else:
        rec = "neither (neither direction cleared its preliminary go/no-go bar under the current setup)"
    lines.append(rec)
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "preexperiments/configs/preexperiment.yaml"))
    parser.add_argument("--results_dir", default=str(PROJECT_ROOT / "results"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "reports/preliminary_results.md"))
    args = parser.parse_args()

    report = build_report(Path(args.config), Path(args.results_dir))
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
