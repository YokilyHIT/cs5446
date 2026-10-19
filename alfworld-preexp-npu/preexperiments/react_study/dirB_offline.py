"""Direction B, offline screen: which pre-call signal predicts foresight utility?

On the step-0c K-continuation points (utility labels already measured), replay
each state and compute candidate gate signals:

  planner_action_lp    mean token logprob of the "Action: ..." line of the
                       temperature-0 ReAct completion (low = planner unsure)
  planner_full_lp      mean token logprob of the whole completion
  sample_disagree      fraction of N=5 temperature-0.7 samples whose action != a_base
  sample_n_distinct    number of distinct actions among a_base + the 5 samples
  base_inadmissible    a_base not in the admissible list (agent-visible)
  wm_predicts_failure  WM prediction contains "Nothing happens" (post-call)
  wm_changes_action    a_fore != a_base (post-call; needs the second planner call)
  wm_confidence        WM C_logprob (WorldEvolver)

Outputs AUROC of each signal for U>0 / U<0 / U!=0 (progress and success) on the
unbiased subset (tasks solvable by rep1) and on all points, plus the gain at
30% usage when ranking by the signal.
"""
from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr

from preexperiments.common.alfworld_runner import extract_admissible, format_history, visible_actions
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.react_study.agent import replay, _seed
from preexperiments.react_study.common import MeteredLLM, stage_dir
from preexperiments.react_study.protocol_v2 import PipelineV2, history_v2, init_room_obs

N_SAMPLES = 5


def action_line_lp(tok_lps, text):
    """Mean logprob of tokens that fall inside the last 'Action:' line's value."""
    ms = list(re.finditer(r"^[ \t]*action[ \t]*:[ \t]*(.+?)[ \t]*$", text or "", re.I | re.M))
    if not ms or not tok_lps:
        return float("nan")
    s, e = ms[-1].start(1), ms[-1].end(1)
    pos, acc = 0, []
    for t, lp in tok_lps:
        a, b = pos, pos + len(t)
        if b > s and a < e:
            acc.append(lp)
        pos = b
    return float(np.mean(acc)) if acc else float("nan")


def signals(pipe, p, r):
    env, obs, info, history, done, init_obs = replay("train", p["gamefile"], p["prefix"])
    adm = visible_actions(extract_admissible(info))
    state = {"goal": p["goal"], "task_type": p["task_type"], "history": format_history(history, 50),
             "history_v2": history_v2(init_room_obs(init_obs), history), "current_observation": obs,
             "admissible_actions": adm}
    prompt = pipe._react_prompt(state, "")
    resp = pipe.llm.complete(prompt, seed=pipe.seed, temperature=pipe.temperature, top_p=pipe.top_p,
                             max_tokens=pipe.max_tokens_action_react, logprobs=True)
    a_base = r["first_actions"]["base"]
    samples = [pipe.sample_action(state, "", 0.7, _seed(p["task_id"], p["t"], 100 + k))[0] for k in range(N_SAMPLES)]
    pred = r.get("wm_prediction") or ""
    return {"point_id": p["point_id"],
            "planner_action_lp": action_line_lp(resp.token_logprobs, resp.text),
            "planner_full_lp": resp.mean_logprob,
            "sample_disagree": float(np.mean([s != a_base for s in samples])),
            "sample_n_distinct": len(set(samples + [a_base])),
            "base_inadmissible": float(a_base not in adm),
            "wm_predicts_failure": float("nothing happens" in pred.lower()),
            "wm_changes_action": float(r["first_actions"]["wm"] != a_base),
            "wm_confidence": r.get("wm_confidence_logprob") if r.get("wm_confidence_logprob") is not None else float("nan"),
            "samples": samples}


def auroc(score, label):
    m = ~np.isnan(score)
    s1, s0 = score[m & label], score[m & ~label]
    if len(s1) < 3 or len(s0) < 3:
        return None
    return float(mannwhitneyu(s1, s0).statistic / (len(s1) * len(s0)))


def main():
    config = load_yaml_config("preexperiments/configs/preexperiment.yaml")
    pipe = PipelineV2(MeteredLLM(config), config.get("direction_b", {}), variant="list")
    s0 = stage_dir(10)
    pts = {json.loads(l)["point_id"]: json.loads(l) for l in open(s0 / "raw" / "branch_points.jsonl")}
    rows = {json.loads(l)["point_id"]: json.loads(l) for f in sorted((s0 / "raw").glob("branch_k.shard*.jsonl"))
            for l in open(f)}
    rep1 = {}
    for f in (s0 / "raw" / "train").glob("dev_v2_c*_none__rep1.jsonl"):
        for l in open(f):
            x = json.loads(l)
            rep1[x["task_id"]] = x["success"]
    out_dir = stage_dir(21)
    cache = out_dir / "raw" / "signals.jsonl"
    done = {json.loads(l)["point_id"]: json.loads(l) for l in open(cache)} if cache.exists() else {}
    todo = [pid for pid in sorted(rows) if pid not in done and rows[pid].get("replay_ok")]
    lock = threading.Lock()

    def sink(_i, pid, res):
        with lock, open(cache, "a") as f:
            f.write(json.dumps(res) + "\n")
        done[pid] = res

    ordered_map(lambda pid: signals(pipe, pts[pid], rows[pid]), todo, workers=16, label="dirB", progress_every=20,
                on_result=sink)
    names = ["planner_action_lp", "planner_full_lp", "sample_disagree", "sample_n_distinct", "base_inadmissible",
             "wm_predicts_failure", "wm_changes_action", "wm_confidence"]
    # sign convention: higher score => open the gate. Low logprob / confidence => uncertain => open.
    flip = {"planner_action_lp": -1, "planner_full_lp": -1, "wm_confidence": -1}
    res = {}
    for subset in ("unbiased", "all"):
        pids = [pid for pid in sorted(done) if subset == "all" or rep1.get(rows[pid]["task_id"])]
        R = {}
        for tgt in ("pr", "success"):
            for interv in ("wm", "oracle"):
                u = np.array([rows[pid][f"U_{tgt}"][interv] for pid in pids])
                for n in names:
                    sc = flip.get(n, 1) * np.array([done[pid][n] if done[pid][n] is not None else np.nan
                                                    for pid in pids], float)
                    k = int(round(0.3 * len(u)))
                    order = np.argsort(-np.nan_to_num(sc, nan=-1e9) + np.random.default_rng(0).uniform(0, 1e-9, len(u)))
                    R[f"{interv}/{tgt}/{n}"] = {
                        "auroc_pos": auroc(sc, u > 0), "auroc_neg": auroc(sc, u < 0), "auroc_nonzero": auroc(sc, u != 0),
                        "spearman": float(spearmanr(sc[~np.isnan(sc)], u[~np.isnan(sc)]).statistic),
                        "gain_at_30": float(u[order[:k]].sum() / len(u)),
                        "random_at_30": float(0.3 * u.mean()), "oracle_at_30": float(np.sort(u)[::-1][:k].sum() / len(u))}
        res[subset] = {"n": len(pids), "signals": R}
    (out_dir / "tables" / "offline_signal_screen.json").write_text(json.dumps(res, indent=2))
    L = ["# Direction B offline screen (step-0c points)", ""]
    for subset, v in res.items():
        L += [f"## {subset} (n={v['n']}) — target U_pr(wm)", "",
              "| signal | AUROC U>0 | AUROC U<0 | AUROC U≠0 | Spearman | gain@30% | random@30% | oracle@30% |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for n in names:
            e = v["signals"][f"wm/pr/{n}"]
            f = lambda x: "—" if x is None else f"{x:.3f}"
            L.append(f"| {n} | {f(e['auroc_pos'])} | {f(e['auroc_neg'])} | {f(e['auroc_nonzero'])} | {e['spearman']:+.3f} | "
                     f"{e['gain_at_30']:+.4f} | {e['random_at_30']:+.4f} | {e['oracle_at_30']:+.4f} |")
        L.append("")
    (out_dir / "tables" / "offline_signal_screen.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
