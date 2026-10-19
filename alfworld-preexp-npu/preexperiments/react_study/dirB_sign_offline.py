"""Direction B, sign sub-problem (offline): given that foresight changed the action
(a_fore != a_base), can a cheap check of the two PREDICTED outcomes tell whether
switching helps (U>0) or hurts (U<0)?

For each step-0c point with a changed WM action, the WM additionally predicts the
outcome of a_fore. Rules (score > 0 => adopt a_fore):
  fail_avoid     +1 if pred(a_base) says "Nothing happens" and pred(a_fore) does not;
                 -1 if the reverse; 0 otherwise
  subgoal        (#goal-subgoal patterns matched by pred(a_fore)) - (same for pred(a_base));
                 patterns from progress.subgoals_for (object/receptacle are in the goal text)
  combined       fail_avoid + subgoal
Reports mean U_pr / U_success when the rule adopts vs rejects, and AUROC of the
score for U>0 among changed points.
"""
from __future__ import annotations

import json
import re
import threading

import numpy as np
from scipy.stats import mannwhitneyu

from preexperiments.common.alfworld_runner import extract_admissible, format_history, visible_actions
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.react_study.agent import replay
from preexperiments.react_study.common import MeteredLLM, stage_dir
from preexperiments.react_study.progress import subgoals_for
from preexperiments.react_study.protocol_v2 import PipelineV2, history_v2, init_room_obs


def nh(x):
    return "nothing happens" in (x or "").lower()


def n_sub(gamefile, pred):
    return sum(1 for pat in subgoals_for(gamefile) if re.search(pat, pred or ""))


def main():
    config = load_yaml_config("preexperiments/configs/preexperiment.yaml")
    pipe = PipelineV2(MeteredLLM(config), config.get("direction_b", {}), variant="list")
    s0 = stage_dir(10)
    pts = {json.loads(l)["point_id"]: json.loads(l) for l in open(s0 / "raw" / "branch_points.jsonl")}
    rows = [json.loads(l) for f in sorted((s0 / "raw").glob("branch_k.shard*.jsonl")) for l in open(f)]
    rows = [r for r in rows if r.get("replay_ok") and r["first_actions"]["wm"] != r["first_actions"]["base"]]
    out = stage_dir(21) / "raw" / "sign_offline.jsonl"
    done = {json.loads(l)["point_id"]: json.loads(l) for l in open(out)} if out.exists() else {}
    lock = threading.Lock()

    def one(r):
        p = pts[r["point_id"]]
        env, obs, info, history, d, init_obs = replay("train", p["gamefile"], p["prefix"])
        state = {"goal": p["goal"], "task_type": p["task_type"], "history": format_history(history, 50),
                 "history_v2": history_v2(init_room_obs(init_obs), history), "current_observation": obs,
                 "admissible_actions": visible_actions(extract_admissible(info))}
        pf = pipe.predict(state, r["first_actions"]["wm"])["wm_prediction"]
        return {"point_id": r["point_id"], "pred_fore": pf}

    def sink(_i, r, res):
        with lock, open(out, "a") as f:
            f.write(json.dumps(res) + "\n")
        done[res["point_id"]] = res

    ordered_map(one, [r for r in rows if r["point_id"] not in done], workers=16, label="sign", on_result=sink)
    res = {}
    for name in ("fail_avoid", "subgoal", "combined"):
        sc, upr, us = [], [], []
        for r in rows:
            p = pts[r["point_id"]]
            pb, pf = r.get("wm_prediction"), done[r["point_id"]]["pred_fore"]
            fa = (1 if nh(pb) and not nh(pf) else -1 if nh(pf) and not nh(pb) else 0)
            sg = n_sub(p["gamefile"], pf) - n_sub(p["gamefile"], pb)
            sc.append({"fail_avoid": fa, "subgoal": sg, "combined": fa + sg}[name])
            upr.append(r["U_pr"]["wm"]); us.append(r["U_success"]["wm"])
        sc, upr, us = map(np.array, (sc, upr, us))
        adopt = sc > 0
        pos, neg = sc[upr > 0], sc[upr < 0]
        res[name] = {"n_changed": int(len(sc)), "n_adopt": int(adopt.sum()), "n_reject_or_tie": int((~adopt).sum()),
                     "mean_Upr_adopt": float(upr[adopt].mean()) if adopt.any() else None,
                     "mean_Upr_rest": float(upr[~adopt].mean()) if (~adopt).any() else None,
                     "mean_Usucc_adopt": float(us[adopt].mean()) if adopt.any() else None,
                     "mean_Usucc_rest": float(us[~adopt].mean()) if (~adopt).any() else None,
                     "mean_Upr_all_changed": float(upr.mean()),
                     "auroc_score_Upos_vs_Uneg": float(mannwhitneyu(pos, neg).statistic / (len(pos) * len(neg)))
                     if len(pos) >= 3 and len(neg) >= 3 else None}
    (stage_dir(21) / "tables" / "sign_offline.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
