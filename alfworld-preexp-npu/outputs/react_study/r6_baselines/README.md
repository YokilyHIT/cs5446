# Round 6: recent-work baselines aligned with the frozen method

Pre-registration: `tables/preregistration_baselines.json` (written before any fresh600 run of these arms).
Code: `preexperiments/react_study/baselines_r6.py` (prompts / blocks), arms in `agent.py` (`walle`, `inv_rpms`,
`expel`, `inv_expel`), learning scripts `learn_walle_rules.py`, `learn_expel_insights.py`, analysis
`analyze_baselines_r6.py`. Launch: `launch_baselines.sh` (servers restarted with N4=3: 4B on NPU 0-2 / ports
8001-8003, 14B on NPU 3-7 / ports 8011-8015, because the WALL-E-style arms call the 14B model at every step).

## Alignment
Planners unchanged (Qwen3-4B-Instruct-2507, Qwen3-14B thinking off). Every world-model / knowledge role uses the
same frozen Qwen3-14B as the frozen method. Protocol v2-list, T=0, top_p 0.5, seed 42, 30 steps. Evaluation on
fresh600 x 3 (same task list and repetitions as `p7_final`). Learning uses only the label-pool `none` runs (448
training-split tasks, disjoint from fresh600 and unseen134).

| arm | baseline | what the planner gets | trigger |
|---|---|---|---|
| `walle` | WALL-E-style (2410.07484), no rules | WM judges every proposed action without the valid-action list; on predicted failure Feedback + Suggestion, planner revises (<= 2 revisions) | every step, WM-judged |
| `walle_rules` | WALL-E-style with learned rules | same, WM prompt includes the learned rules | every step, WM-judged |
| `inv_rpms` | RPMS-style (2603.17831) | verb-relevant rule cards + belief state tracked from observations, rules first | failure gate (as frozen) |
| `expel` | ExpeL-style (AAAI 2024) | 15 insights from the planner's own trajectories in every prompt | every step |
| `inv_expel` | ExpeL-style at the gate | the same insights at the failure gate | failure gate |

Deviations from the original methods (also in the pre-registration): WALL-E rules learned in natural language by
the 14B model, 2 iterations, one-step MPC with <= 2 revisions; RPMS without episodic memory, rule base = our
rule cards; ExpeL without retrieval of successful trajectories as extra in-context examples.

## Learned knowledge
* WALL-E rules (`raw/walle_rules.json`, log `tables/walle_rule_learning.json`): judgement accuracy of the 14B WM
  on 300 balanced validation transitions 0.680 without rules -> 0.797 after iteration 1 (10 rules) -> 0.793 after
  iteration 2 (6 rules; the last iteration is used, as specified). Some learned rules are wrong for ALFWorld
  (e.g. "examining always succeeds", "heating needs the device to be open"); they are kept as learned.
* ExpeL insights (`raw/expel_insights_p4b.json`, `raw/expel_insights_p14b.json`): 15 each, from 35 / 45
  success-failure pairs and 21 / 24 success batches; mostly "be at the target and hold the object before moving
  / heating", with near-duplicates as produced by the procedure.

## Results (fresh600 x 3; `tables/baselines_fresh600.md`, `analyze_baselines_r6.py`)
| arm | 4B SR | 4B PR | 4B 14B calls / ep | 4B tokens / ep | 14B SR | 14B PR |
|---|---:|---:|---:|---:|---:|---:|
| none | 20.9 | 39.4 | 0 | 37.6k | 59.1 | 70.3 |
| failure only | 28.3 | 44.8 | 0 | 46.9k | 63.9 | 72.8 |
| rule cards | 33.3 | 46.8 | 0 | 44.4k | 68.8 | 76.0 |
| **frozen WM repair** | 36.2 | **49.0** | 5.3 | 47.8k | 65.9 | 74.3 |
| oracle repair | 36.7 | 47.5 | 0 | 42.5k | 69.5 | 76.6 |
| WALL-E-style, no rules | 26.8 | 48.2 | 54.5 | 118.2k | 55.0 | 69.4 |
| WALL-E-style, learned rules | 27.3 | 46.0 | 44.7 | 101.6k | 54.4 | 68.8 |
| **RPMS-style** (rules + belief state) | **37.2** | 48.1 | 0 | 42.6k | **70.7** | **77.0** |
| ExpeL-style, every step | 12.9 | 24.1 | 0 | 56.7k | 53.2 | 63.4 |
| ExpeL-style, at the gate | 28.1 | 43.4 | 0 | 52.2k | 64.1 | 72.3 |

Pre-registered families (frozen - baseline, PR, Holm over 5; non-inferiority margin -2 pp):
| baseline | 4B ΔPR | 4B ΔSR | 14B ΔPR | 14B ΔSR |
|---|---|---|---|---|
| WALL-E-style | +0.7 [-1.5, 2.9] (Holm .64), NI | +9.4 [6.5, 12.3] | **+4.9** [2.8, 7.0] (Holm <.001) | +10.9 [7.8, 14.0] |
| WALL-E-style + rules | **+2.9** [0.9, 4.9] (Holm .012) | +8.9 [6.2, 11.6] | **+5.5** [3.7, 7.4] (<.001) | +11.4 [8.6, 14.3] |
| RPMS-style | +0.9 [-0.8, 2.6] (Holm .64), NI | -1.0 [-3.5, 1.5] | **-2.6** [-3.9, -1.3] (<.001), not NI | -4.8 [-6.8, -2.9] |
| ExpeL-style, every step | **+24.9** [22.2, 27.6] (<.001) | +23.3 [20.3, 26.6] | **+10.9** [8.3, 13.5] (<.001) | +12.7 [9.4, 16.0] |
| ExpeL-style, at the gate | **+5.6** [3.9, 7.3] (<.001) | +8.2 [5.9, 10.4] | **+2.1** [0.5, 3.6] (Holm .006) | +1.8 [-0.4, 4.1] |

WALL-E-style judge quality (300 sampled rejection steps per arm, valid-action lists recovered by replay):
| arm | steps with >= 1 rejection | rejected action was actually valid (false alarm) |
|---|---:|---:|
| 4B, no rules | 0.65 | 0.53 |
| 4B, learned rules | 0.46 | 0.44 |
| 14B, no rules | 0.47 | 0.67 |
| 14B, learned rules | 0.34 | 0.54 |

## Reading
* **Trigger quality.** A world model that judges every action itself (WALL-E-style) rejects 34-65% of steps and
  about half of its rejections are false alarms; learned rules lower both but not enough. PR is similar to the
  frozen method for the 4B planner, but SR is 9 pp lower at ~10x the 14B calls, and for the 14B planner it is
  below no intervention (55.0 vs 59.1 SR). An environment-grounded failure signal is what makes failure-time
  guidance cheap and safe; this also confirms the method's dependence on such a signal.
* **Explicit rules + belief state are the strongest baseline.** RPMS-style guidance ties the frozen method on
  the 4B planner (non-inferiority holds both ways in PR) and beats it on the 14B planner (-2.6 PR, -4.8 SR),
  even exceeding the oracle-repair comparator there (70.7 vs 69.5 SR). It needs no model call but a hand-written
  rule base and a hand-designed state tracker.
* **Learned insights do not substitute for diagnosis.** ExpeL-style insights in every prompt hurt both planners
  badly (4B SR 12.9%); shown only at the gate they equal a failure notice. Automatically learned knowledge was
  weaker than both the frozen world model and the hand-written rules in this setting.
* Claim after this round: for a weak planner, a frozen world model consulted at environment-signalled failures
  matches a hand-built rules-plus-state system without building one, and beats learned-rule and learned-insight
  alternatives; for a strong planner, hand-built explicit rules plus state are better.

## WorldEvolver-style confidence gate (`launch_selective.sh`, `tables/preregistration_selective.json`)
Run on NPU 0-3 only (1 x 4B, 3 x 14B; `NDEV=4 N4=1 start_servers_r4.sh`). Threshold recalibrated for the 14B world
model on label-pool states (`calib_selective_r6.py`, `tables/selective_calibration.json`: tau 0.999998 for the 4B
planner's states, 0.999994 for the 14B planner's).
Interruption: launched 2026-10-29 10:57; at 11:01 all run processes and the vLLM servers were terminated
externally together with the previous session (logs end without an error; logs kept in `logs/interrupted_20261029/`).
75 complete episodes were kept, partial lines checked, and the runs resumed at 14:19 with the same script; finished
tasks are skipped. The online episodic memory of the `selective_em` arms restarts empty in each resumed process
(each process had completed only 3-6 episodes before the interruption).

Status: complete (2026-10-29 18:58), 4 arms x 1800 episodes, 600 tasks x 3 reps each, no errors.
Gate usage on world-model-called steps: 4B 27.5% (memory 28.3%), 14B 31.1% (memory 46.4%) -- close to the 30% target.

| arm | 4B SR | 4B PR | 14B calls / ep (4B) | tokens / ep (4B) | 14B SR | 14B PR |
|---|---:|---:|---:|---:|---:|---:|
| frozen WM repair | 36.2 | 49.0 | 5.3 | 47.8k | 65.9 | 74.3 |
| confidence gate | 22.1 | 41.4 | 25.9 | 88.7k | 61.0 | 72.2 |
| confidence gate + episodic memory | 23.4 | 41.9 | 25.8 | 95.9k | 59.8 | 71.3 |

Pre-registered family (frozen - gate, PR, Holm over 2 per planner):
* 4B: vs gate +7.6 [5.8, 9.4] (SR +14.2), vs gate + memory +7.0 [5.3, 8.8] (SR +12.8); Holm p < 0.001.
* 14B: vs gate +2.1 [0.6, 3.7] Holm 0.006 (SR +4.9), vs gate + memory +3.0 [1.3, 4.7] Holm 0.001 (SR +6.1).
* The confidence gate is close to no intervention (none: 4B 20.9 / 39.4, 14B 59.1 / 70.3) at ~5x the world-model calls
  of the frozen method; next-observation foresight selected by confidence does not supply what the planner lacks.
