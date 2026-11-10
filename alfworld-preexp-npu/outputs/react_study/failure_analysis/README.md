# Failure analysis and round-5 offline analyses

* `tables/failure_analysis.md` (`failure_analysis.py`): dev460 `none` runs -- 4B: 31% inadmissible actions, 74% of
  failures end in a loop, success after picking the target 0.27 (14B 0.77); 84% of heat/cool/clean attempts are
  inadmissible. Motivated the failure-triggered repair probes (`probe_feasibility/`).
* `tables/deep_analysis.md` (`deep_analysis.py`): fresh_test600 x 3 reps, no new runs. Failure category = the
  environment-derived reason of the failing action computed from the episode history only
  (`preconditions.diagnose`; the analysis shadows `set` inside that module because the logs carry no admissible
  lists -- the module file itself, part of the frozen method, is unchanged). WM reasons are mapped to the same
  categories by regex (`wm_cat`); a manual spot check of the main mismatch cells confirmed they are genuine
  diagnosis errors, not classifier errors.

## 3. Where does the gain come from? (4B planner)
| task type | none | fail | rules | WM repair | oracle |
|---|---:|---:|---:|---:|---:|
| look_at_obj_in_light | 27.3 | 36.0 | 33.0 | **46.3** | 38.7 |
| pick_and_place_simple | 44.7 | 54.7 | 56.0 | **61.7** | 60.3 |
| pick_clean_then_place | 19.0 | 27.3 | 27.0 | **34.7** | 31.7 |
| pick_cool_then_place | 6.7 | 14.3 | 13.3 | **21.7** | 18.7 |
| pick_heat_then_place | 27.0 | 32.3 | **46.7** | 37.7 | 36.7 |
| pick_two_obj_and_place | 1.0 | 5.3 | 24.0 | 15.3 | **34.0** |

* Funnel: WM repair raises success after picking the target from 0.44 (none) / 0.55 (fail) to 0.66 (oracle 0.71);
  finding the target barely changes (0.54 -> 0.60). The gain is in executing the post-pick procedure.
* Per failure category (gate steps): the largest share is "not at the receptacle" (37-42%) and "already there"
  (30-38%). WM repair raises the share of executable next actions for "not at" from 0.36 (fail) to 0.56 and lowers
  recurrence of the same failed action from 0.69 to 0.57 -- the oracle reaches 0.52 / 0.56. For "already holding
  another object" (carry-one capacity) neither WM repair nor rule cards help (recurrence 0.85); the oracle does
  (0.70). pick_two (two objects, carry one at a time) is where WM repair is furthest from the oracle (15.3 vs 34.0).

## 4. Does a wrong diagnosis hurt? (WM repair, 14B WM)
* The WM's reason falls in the environment-derived category in only 30% of gate steps (4B planner; 19% with the
  14B planner); its repair action equals the environment-derived repair in 42% / 32% of cases where both exist.
  Typical errors: "object not present" when the agent is simply not at the receptacle (not_at->absent, 1008),
  "receptacle is closed" when the agent is already there (already_at->closed, 605).
* Correct diagnoses are locally better: executed action admissible 0.65 vs 0.52, same failure recurs 0.55 vs 0.61,
  repair adopted 0.35 vs 0.29. Episodes with mostly correct diagnoses succeed more often (39.8% vs 28.4%; 14B
  planner 62.5% vs 44.0%) -- correlational (easier episodes may yield easier diagnoses).
* So the method works although most diagnoses are wrong in detail: a plausible precondition plus a valid first
  step moves the planner off the failing action; precision still matters at the margin.

## 5. Capability (14B planner)
* Rule cards beat WM repair mainly on pick_two_obj (57.3 vs 44.7 SR) and, less, cool / pick_and_place; WM repair is
  better on look_at (84.7 vs 82.7). With the 14B planner the WM's category agreement drops to 0.19 (the
  remaining failures are harder), and for "already holding" failures WM repair still leaves recurrence at 0.73
  (oracle 0.40). The carry-one-object constraint is stated explicitly in the rule card for `take`; the WM rarely
  recovers it. The 14B gap is a specific missing rule, not general state tracking (cf. inv_state ~ fail).
