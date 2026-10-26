# Feasibility probes: what does a failing action need? (2026-10-21)

Motivation (round-4 diagnosis of 4B failures on dev460): 31% of 4B actions are not admissible although the
prompt lists the valid actions; 84% of heat/cool/clean attempts are inadmissible; success after picking the
target object is 0.27 (14B: 0.77); a bare "it fails" signal (oracle_struct, raw oracle obs) is worth ~0 per
decision. Question: is the missing piece *why* it fails and *what to do instead*?

Design (4B planner, dev460 x 2 reps, v2-list): intervene only when a_base is not admissible (and not
`check valid actions`), else execute a_base. Pre-registration: `tables/preregistration_probe.json`.
| arm | second pass sees |
|---|---|
| inv_resample | nothing (same prompt, T=0.7, seeded) |
| inv_fail | `preconditions.FAIL_BLOCK`: "a would have no effect, not valid now" |
| inv_repair | `preconditions.REPAIR_BLOCK`: environment-derived reason (location / held object / open state tracked from history + ALFWorld action rules) and an admissible repair action when one exists (45% of cases) -- an ORACLE upper bound of a repair-type world model |
| inv_proj | own Thought kept, Action re-decoded with vLLM guided_choice over admissible actions (no WM) |

## Results (`tables/probe_4b.md`)
| arm | SR | PR | legal | gate open/step | tokens/task |
|---|---:|---:|---:|---:|---:|
| none | 11.7% | 32.8% | 0.69 | - | 40.0k |
| always (4B WM every step) | 14.6% | 35.7% | 0.72 | - | 95.0k |
| oracle_every | 18.0% | 38.7% | 0.74 | - | 78.6k |
| inv_resample | 14.9% | 35.0% | 0.77 | 0.30 | 52.9k |
| inv_fail | 18.3% | 36.7% | 0.85 | 0.27 | 51.9k |
| **inv_repair** | **29.1%** | **41.0%** | 0.90 | 0.23 | 46.5k |
| inv_proj | 14.2% | 36.2% | 1.00 | 0.26 | 54.5k |

Primary (Holm over 3, PR): repair - fail +4.2 [+2.4, +6.0]; repair - proj +4.7 [+2.4, +7.0]; proj - none
+3.4 [+1.4, +5.5]; all Holm p < 0.001. Decision rule ("repair beats fail and proj by >= 2 pp, Holm < .05")
is met. SR: repair - none +17.4 [+14.2, +20.7], repair - oracle_every +11.1 [+7.6, +14.7].

## Reading
* The reason + repair content is what matters: a failure notice alone already equals oracle_every on SR
  (+6.5 vs none) at 66% of its tokens; adding *why* and *what first* adds +10.9 SR on top.
* Forcing legality (proj) is not enough: legal actions chosen without understanding the precondition do not
  help SR more than resampling.
* The gain is post-pick (seen/picked rates unchanged: 0.51 / 0.46), exactly the bottleneck found in the
  failure funnel.
* `inv_repair` uses hand-written ALFWorld precondition rules and true state tracking: it is an upper bound,
  close in spirit to rule-based feasibility methods (RPMS 2603.17831, WALL-E 2410.07484). Whether a frozen
  LLM world model can infer the reason and the repair is the open question for a method contribution.

## Real-WM repair (no rules), pre-registered in `tables/preregistration_wmrepair.json` (`tables/wmrepair.md`)
`inv_wmrepair`: on the same gate, the frozen WM gets task / history / observation / valid actions / the
failing action and must return the missing precondition and one valid repair action
(`preconditions.WM_REPAIR_PROMPT`); the planner then sees the same REPAIR_BLOCK format as the oracle arm.

| planner | arm | SR | PR | repair given | tokens/task |
|---|---|---:|---:|---:|---:|
| 4B | none | 11.7% | 32.8% | - | 40.0k |
| 4B | inv_fail | 18.3% | 36.7% | - | 51.9k |
| 4B | wmrepair, 4B WM (= same model: self-diagnosis) | 23.9% | **43.5%** | 0.80 | 56.4k |
| 4B | wmrepair, 14B WM | **26.5%** | 42.2% | 0.81 | 54.1k |
| 4B | inv_repair (oracle) | 29.1% | 41.0% | 0.38 | 46.5k |
| 14B | none | 56.4% | 68.9% | - | 29.1k |
| 14B | R (random 30%) | 60.0% | 71.5% | - | 36.9k |
| 14B | inv_fail | 63.9% | 73.3% | - | 34.3k |
| 14B | wmrepair, 14B WM | 64.9% | 74.1% | 0.70 | 36.3k |
| 14B | inv_repair (oracle) | 69.5% | 76.7% | 0.48 | 31.0k |

4B family (Holm over 3, PR): wm14 - fail +5.5 [+3.5, +7.4]; wm4 - fail +6.8 [+4.6, +9.1] (both Holm < 0.001);
oracle - wm14 -1.2 [-3.5, +0.9] (n.s.: the frozen WM recovers the oracle's PR gain; SR gap 2.6 [-0.4, +5.7]).
14B family (Holm over 2, PR): oracle repair - none +7.8 [+5.6, +10.1] (Holm < 0.001); wm14 - fail +0.8
[-1.3, +2.9] (n.s.).

Reading
* Decision rule met for the 4B planner: a frozen LLM, asked the right question at the right moment (only when
  its own action is not executable), supplies the precondition knowledge the planner fails to use. A
  separate stronger WM is not required (4B self-diagnosis ~ 14B WM).
* The strong planner still gains +13 SR from the oracle diagnosis, but not from the WM's: what it lacks is
  state the WM cannot infer (e.g. where things are, what is held/open), not rules.
* Contrast with rounds 1-3: next-observation foresight (always / W, any WM size) was not separable from a
  no-information resample; failure-triggered diagnosis + repair is +5.5-6.8 PR above a failure notice and
  +12-15 SR above none for the 4B planner.
* Caveats: dev460 has been used for development; the gate uses the admissible list the prompt already shows;
  no rule-retrieval (RPMS-style) or reflection baseline yet; 2 reps.

## Round 5 stage A: where does the repair come from? (`tables/round5A.md`, pre-registration `tables/preregistration_round5A.json`)
dev460 x 2 reps, same failure gate. New arms: inv_reflect (failure notice + "think about why"), inv_sreflect
(write "Missing precondition: ...; First step: ..." then act; same planner call), inv_rules (verb-indexed,
state-independent rule cards, RPMS-style simplified), inv_state (oracle state facts, no rules, no repair),
inv_wmpred (same WM, next-observation prediction), post_wmrepair (no admissible-list check: diagnose the
previous action after it returned "Nothing happens.").

| arm | 4B SR | 4B PR | 14B SR | 14B PR | 4B tokens |
|---|---:|---:|---:|---:|---:|
| none | 11.7 | 32.8 | 56.4 | 68.9 | 40.0k |
| inv_fail | 18.3 | 36.7 | 63.9 | 73.3 | 51.9k |
| inv_reflect | 18.7 | 37.8 | 62.4 | 71.9 | 52.0k |
| inv_sreflect | 17.3 | 37.1 | 61.4* | 72.0* | 53.4k |
| inv_wmpred (4B WM / 14B WM) | 15.4 / 15.3 | 35.9 / 35.1 | - / 61.2 | - / 72.7 | 58k |
| inv_state (oracle facts) | 21.0 | 38.2 | 65.2 | 73.5 | 50.9k |
| inv_rules (rule cards) | 26.4 | 40.9 | **67.0** | **75.0** | 48.7k |
| wmrepair, 4B WM | 23.9 | **43.5** | - | - | 56.4k |
| wmrepair, 14B WM | 26.5 | 42.2 | 64.9 | 74.1 | 54.1k |
| post_wmrepair, 4B WM | 19.5 | 39.7 | - | - | 44.5k |
| inv_repair (oracle) | **29.1** | 41.0 | **69.5** | **76.7** | 46.5k |
(*14B followed the structured-reflection format in only 3% of gate steps; the 4B planner in 93%.)

4B primary family (Holm over 4, PR): wmrepair_wm14 - reflect +4.4 [+2.3, +6.4]; - sreflect +5.1 [+2.9, +7.3];
- wmpred_wm14 +7.1 [+5.1, +9.1] (all Holm < 0.001); - rules +1.3 [-0.9, +3.5] (Holm 0.25; SR +0.1 [-3.0, +3.3]).
Secondary: wmrepair_wm4 - sreflect +6.4 [+4.2, +8.7]; wmrepair_wm4 - wmpred_wm4 +7.6 [+5.4, +9.9];
post_wmrepair - fail +3.0 [+0.8, +5.2]; post_wmrepair - wmrepair_wm4 -3.8 [-5.8, -1.9].
14B family: state - fail +0.3 [-1.6, +2.1] (n.s.); oracle repair - state +3.1 [+1.3, +5.0]; sreflect - fail -1.3 (n.s.).
Diagnosis agreement with the environment-derived repair (when one exists): 0.17 (4B WM), 0.33 (14B WM),
0.19 (14B WM, 14B planner) -- the repair helps although it rarely matches the oracle action exactly.

**Pre-registered freeze rule -> freeze inv_wmrepair with the 14B WM.** Reading, stated with its limits:
* RQ1 (interface): with the same WM and the same failure trigger, asking for the missing precondition + first
  repair beats asking for the next observation by +7.1-7.6 PR / +8.5-11.2 SR. Next-observation foresight on
  failures is worse than a bare failure notice.
* RQ2 (source): the repair content is not "reflect once more" (reflect ~ fail) and is not obtained by asking
  the planner to write the diagnosis inside its own step (sreflect, 4B: format followed 93%, no gain). The
  same 4B model in a separate diagnosis call is +6.4 PR better than in-context structured reflection:
  separating diagnosis from planning matters. However, hand-written verb-level rule cards (no WM call) are
  statistically indistinguishable from WM repair on the 4B planner and better on the 14B planner (67.0 vs
  64.9 SR, exploratory). The defensible claim is parity with an explicit rule base without authoring one,
  not superiority over it.
* RQ3 (capability): state facts alone do not help the 14B planner (+0.3 PR); the residual oracle gain comes
  from the combination of state + rule + repair, not from state tracking alone (the earlier "14B lacks state"
  hypothesis is not supported).
* Trigger: post-execution diagnosis (no admissible list) keeps about half the gain (+3.0 PR vs fail) but is
  -3.8 PR below the pre-execution gate (one wasted step per failure).
