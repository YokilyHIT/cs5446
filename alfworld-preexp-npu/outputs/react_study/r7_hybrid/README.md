# Round 7: rule-verified WM repair (stage 41)

Question: can a small rule set make the WM's failure diagnosis more reliable, without handing the rules to the
planner? The planner keeps the decision. Pre-registration: `tables/preregistration_r7.json`. Code: `hybrid_r7.py`.

| arm | what the planner sees at the failure gate | rules used for |
|---|---|---|
| frozen (`inv_wmrepair`, reused from probe_feasibility) | WM reason + first step | - |
| `inv_wmverify` | WM reason + first step, re-asked once if the symbolic check fails | checking the WM (hand cards + tracked state) |
| `inv_wmverify_learned` | WM reason + first step after a self-check against learned rules | checking the WM (WALL-E-style learned rules, no tracker) |
| `inv_wmrules_concat` (control) | WM reason + first step **and** rule cards + belief state | shown to the planner, no check |
| `inv_rpms` | rule cards + belief state | shown to the planner |

Stage A: dev460 x 2, 4B and 14B planners, NPU 0-3 only (`NDEV=4 N4=1`), launched 2026-10-29 (`launch_dev.sh`).
Stage B (fresh600 x 3) only if the selection rule in the pre-registration is met.

Recorded before the runs: on the frozen method's dev logs the symbolic check covers 87% / 76% of gate steps
(4B / 14B) and passes 36% / 33%, but episodes with mostly failing checks succeeded as often as those with mostly
passing ones -- the WM's wrong reasons may not be what limits the method.

Provenance: preconditions.py differs from the hash in p7_final/preregistration_round5_final.json because the
round-5 confound / follow-up code was added after that freeze. The frozen version is archived in
alfworld-patch-20261023 (sha256 ca345b85..., matches the pre-registration). Diff against it: `wm_repair_block` gained
an optional `mode` argument whose default returns exactly the old output, and new code was appended; the frozen
method's code path is unchanged.

## Stage A result (dev460 x 2, 2026-10-30; `analyze_r7.py`, `tables/dev_r7.md`)

| arm | 4B SR / PR | 14B SR / PR | 14B calls / ep (4B / 14B) |
|---|---|---|---|
| frozen WM repair | 26.5 / 42.2 | 64.9 / 74.1 | 6.6 / 3.6 |
| RPMS-style | 28.5 / 41.4 | 67.9 / 76.0 | 0 / 0 |
| concat (WM repair + RPMS block) | 29.5 / 42.6 | 68.4 / 76.0 | 5.9 / 2.8 |
| **verify, hand rules** | **33.3 / 44.4** | **69.5 / 76.4** | 8.7 / 3.9 |
| verify, learned rules | 26.2 / 41.5 | 64.1 / 73.3 | 12.7 / 6.9 |

* verify - frozen: 4B PR +2.3 [0.1, 4.4], SR +6.7; 14B PR +2.3 [0.4, 4.1], SR +4.6.
* verify - concat: 4B PR +1.9 [-0.1, 3.9], SR +3.8 [1.2, 6.4]; 14B PR +0.4 n.s.
* The check fails (re-ask) on 57-58% of gate steps; the WM's reason agrees with the rule category 35% -> 75% (4B)
  and 21% -> 60% (14B) after the re-ask. The learned-rule self-check barely changes the reasons (32% -> 36%) and
  does not help: the learned rules are too generic and miss carry-one-object.
* Selection rule met by `inv_wmverify` only -> stage B launched (`launch_fresh.sh`): inv_wmverify and concat on
  fresh600 x 3, both planners. The offline warning recorded before the runs did not hold on dev.

## Stage B result (fresh600 x 3, 2026-10-30; `analyze_r7.py --fresh`, `tables/fresh_r7.md`)

| arm | 4B SR / PR | 14B SR / PR | 14B calls / ep (4B / 14B) |
|---|---|---|---|
| frozen WM repair | 36.2 / 49.0 | 65.9 / 74.3 | 5.3 / 3.0 |
| RPMS-style | 37.2 / 48.1 | 70.7 / 77.0 | 0 / 0 |
| concat | 37.8 / 49.2 | 70.6 / 77.0 | 4.7 / 2.4 |
| verify (hand rules) | 38.9 / 49.4 | 71.0 / 77.0 | 7.2 / 3.6 |

Pre-registered (PR, Holm over 3 per planner):
* 4B: H1 verify - frozen +0.4 [-1.0, 1.8], **not supported** (SR +2.7 [0.7, 4.7], secondary); H2 verify - concat
  +0.1, **not supported**; H3 non-inferior to RPMS-style +1.3 [-0.4, 3.1], supported.
* 14B: H1 +2.6 [1.4, 3.9] Holm 0.0002, **supported** (SR +5.1); H2 -0.0 [-1.3, 1.2], **not supported**; H3 +0.0
  [-1.2, 1.2], supported.
* The re-ask does correct the WM's reasons (rule-category agreement 36% -> 78% on 4B, 18% -> 65% on 14B), but
  the planner does as well when it simply receives the rules + belief state next to the WM repair (concat).
  What closes the 14B gap is adding the rule knowledge, not checking the WM with it. The dev gains for 4B
  (+2.3 PR) shrank to +0.4 on fresh600 (selection on dev).
