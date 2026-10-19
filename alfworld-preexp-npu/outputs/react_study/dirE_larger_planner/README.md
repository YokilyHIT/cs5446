# Direction E: does a stronger planner make better use of foresight?

Date: 2026-10-14. Planner swapped to **Qwen3-14B** (thinking disabled, `enable_thinking=false`); **the world model stays Qwen3-4B-Instruct-2507**. Protocol v2, the same 460 held-out dev tasks × 2 repeats. 4B-planner numbers come from step 0 / step 1 / direction A on the same tasks.
Code: `common.py` (MeteredLLM routes planner roles to `PREEXP_PLANNER_BASES` and injects `chat_template_kwargs`), `dirE_analyze.py`.
Deployment: 4B on NPU 0–1 (ports 8001–8002), 14B on NPU 2–7 (ports 8011–8016); see `start_servers_E.sh`.
Note: the original plan was Qwen3-30B-A3B-Instruct-2507, but the proxy bandwidth is only ~2 MB/s (61 GB ≈ 8.5 h), so the smaller Qwen3-14B (29.6 GB) was used instead; all files passed SHA256 checks.

## Results (`tables/planner_4b_vs_14b.md`)

| Planner | Arm | SR | PR | Legal action rate | tokens/task |
|---|---|---:|---:|---:|---:|
| 4B | none | 11.7% | 32.8% | 68.7% | 40.0k |
| 4B | always | 14.6% | 35.7% | 72.1% | 95.0k |
| 4B | oracle | 18.0% | 38.7% | 74.3% | 78.6k |
| 4B | random_pre_nc_p0.3 | 13.5% | 33.4% | 71.8% | 56.3k |
| **14B** | none | **56.4%** | **68.9%** | 82.6% | 29.1k |
| 14B | always | 55.8% | 68.9% | 84.5% | 70.8k |
| 14B | oracle | 56.7% | 68.8% | 85.6% | 58.8k |
| 14B | random_pre_nc_p0.3 | 58.5% | 71.2% | 84.1% | 40.5k |

| Contrast (paired bootstrap) | ΔSR [95% CI] | ΔPR [95% CI] |
|---|---|---|
| 14B none − 4B none | **+44.7 [+40.3, +49.0]** | +36.1 [+32.6, +39.5] |
| 4B: oracle − none | +6.3 [+4.0, +8.7] | +5.8 [+3.9, +7.8] |
| 4B: always − none | +2.8 [+0.7, +5.0] | +2.9 [+1.0, +4.8] |
| 14B: oracle − none | **+0.3 [−2.9, +3.7]** | −0.1 [−2.7, +2.4] |
| 14B: always − none | −0.7 [−4.1, +2.7] | −0.0 [−2.3, +2.3] |
| 14B: random_pre_nc_p0.3 − none | +2.1 [−0.9, +5.0] | +2.3 [+0.4, +4.3] (p = 0.018) |
| Gain shrinkage (14B gain − 4B gain): oracle | **−6.0 [−10.3, −1.7] (p = 0.006)** | −6.0 [−9.3, −2.6] (p < 0.001) |
| Gain shrinkage: always | −3.5 [−7.6, +0.7] | −2.9 [−6.1, +0.2] |

## Conclusions
1. **Planner capability dominates**: 4B → 14B adds +44.7 pp SR, an order of magnitude more than any foresight method (+2 to +6 pp).
2. **A stronger planner barely needs single-step foresight**: with 14B, even perfect prediction (oracle) adds only +0.3 pp, significantly less than with 4B (−6.0 pp, p = 0.006). This is the opposite of the hypothesis that "a stronger planner uses foresight better": a strong planner can infer the next observation itself, so single-step prediction carries almost no new information.
3. With 14B, only random 30% intervention still gives a small PR gain (+2.3, p = 0.018), consistent with direction A's finding that perturbation alone helps.
4. Implication: the value of single-step foresight is limited to a weak planner. For the method to still matter with a strong planner, the WM has to provide information the planner cannot infer (multi-step / longer horizon, unseen objects or receptacle contents), or move to harder environments.

## Run notes
- The oracle arm was too slow in its first launch (3 processes × 8 threads, bottlenecked by the per-process env lock). After 111 / 65 tasks finished, the remaining tasks were split into 8 parts × 2 reps and re-run with 4 threads per process (`launch_oracle_rest.sh`). After merging: 460 tasks per rep, no duplicates, no truncated rows.
- No errors in any log.

## Directory layout
```
raw/train/p14b_{none,always,random}_c{0,1,2}__rep{0,1}.jsonl
raw/train/p14b_oracle_{c*,r*}__rep{0,1}.jsonl   (c* = first launch, r* = re-split run)
raw/oracle_rest_rep*_part*                       re-split task lists
tables/planner_4b_vs_14b.{md,json}
start_servers_E.sh, launch_E.sh, launch_oracle_rest.sh, logs/
```
