# D0 portable development snapshot

This is a **derived analysis snapshot**, exported from already accepted local D0 evidence on 2026-10-15. It is not an original acceptance artifact, a new experiment, a complete production audit, or the final research report. `status: complete` describes the accepted data collection; it does not claim that every analysis or evidence audit is complete.

## Included files

| File | Content |
|---|---|
| `d0_snapshot.json` | All 24 original games and all 71 selected points, with the original game/state weights, state observations/history/visible menus, budget, D/N/P outcomes and statuses, prediction/confidence metadata, actual D first observation, D replay coverage, grouping, and source bindings. |
| `d0_rollout_summaries.json` | All 117 accepted physical groups, with their action/observation/step/success/done trajectories. Branches sharing a physical group reference the same rollout. No selection by outcome. |
| `final_accounting_summary.json` | A faithful small excerpt of the accepted final accounting: recorded and conservatively charged totals, all 15 attempts, accepted batch split, policy-stop accounting, and coverage. |
| `source_bindings.json` | SHA-256/size/logical-path bindings for the 148 source files used or checked by the exporter. The original archive files are not included. |

The four JSON files total **1,971,598 bytes**. Each contains a `sha256` seal over the canonical JSON object after removing that top-level field: UTF-8, `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, `allow_nan=False`. This detects accidental changes to the export; a matching seal alone does not independently authenticate its origin.

## Preserved semantics

- There are 68 valid D/N/P points and 3 source-draft failures. The 3 failures remain in the 71-point denominator with their original weights. Their local prediction and all three local outcomes are null; source-episode outcomes, where present, are a separate field.
- One N first-action policy failure is a valid observed local `Y=0`, with a missing executable N action. It is retained in outcome statistics and excluded only from comparisons requiring two executable first actions.
- Each game retains weight `1/24`; each of its original selected points retains `1/(24*k_j)`. Original weight mass is 1.0; valid D/N/P weight mass is 0.9513888888888888. No point is removed or silently reweighted by the exporter.
- D references are actual first observations from accepted D rollouts. Export checks equality against both `prediction_references.jsonl` and the first rollout step. Predictions are not used as their own references.
- The complete original `D_check` records remain: 68 passed and 3 not applicable. One passed check covers environment transitions only (0 new model-request pairs). `cross_job_state` is membership in the accepted final cross-job state list: exactly 1 of 71 is true; false means not marked cross-job in that final list.
- Confidence is a ranking score, not a calibrated success probability. Both `wm_mean_logprob` and `wm_confidence_logprob` are preserved. The compact prediction retains the original alignment/status/token-count/character-span metadata and other small original fields. Only the large `wm_token_logprobs` array is omitted, with the complete original prediction object's canonical SHA-256 retained separately.
- `raw_Y` and `outcome_status` come from accepted final branch tasks. `physical_groups` come from final manifests, not the earlier first-action plan's provisional statuses.

The verified unweighted cross-checks are D/N/P successes **9/8/8**, executable first-action changes N **20/67**, P **31/68**, and EM **28/68**. These counts are diagnostic checks; the analysis code computes the prespecified weighted descriptive quantities.

## Cases and trajectory joins

Formal development examples must still use the frozen `analysis_cases.select_cases` hash order over all 71 points. Join a selected point's branch `rollout_id` to `d0_rollout_summaries.json.groups[].rollout_id`. A missing rollout for the N first-action policy failure is expected; its failure evidence is on the point. No invented trajectory is supplied.

For navigation only, both observed unequal-D/N/P points belong to original game 14, `pick_clean_then_place_in_recep-DishSponge-None-CounterTop-427/trial_T20190909_010951_843989`:

| State suffix | Step / remaining budget | D,N,P outcomes | Note |
|---|---|---|---|
| `:10` | 10 / 20 | 1,0,1 | N first-action `missing_action` policy failure; D/P have real trajectories. |
| `:16` | 16 / 14 | 1,1,0 | The observed P-D difference is -1. |

These are observed differences within the accepted development sample, not proof of causal rescue/harm or population frequency. This navigation table does not replace the hash selection or justify deleting the other points.

## Cost and evidence limits

The accounting excerpt is not `cost_evidence` and is not accepted as a replacement by the production cost-analysis pipeline. Recorded counters for stopped attempts can be incomplete. Conservative charged values are not successful model calls or counts of observed policy failures; the original 935310 reservation and unknown-outcome treatment remain explicit. Do not turn this excerpt into fabricated empty audit records.

Full request/response audits, raw token/top-logprob arrays, full per-step menus, runtime/hardware receipts, and restoration artifacts remain in the source archive. This package supports CPU descriptive metrics, fixed-hash cases, and specified sensitivity summaries. It does not independently re-run full provenance, branch-cost attribution, endpoint reconstruction, or production `make_report` validation.

## Reproduce the export from the source archive

The source project archive must include the original completion directory, source selection bundle/shards, referenced `.review-cache` runner files, and the independent count comparison. The exporter does not download these missing originals. From the portable package directory, run:

```sh
python tools/export_d0_snapshot.py --source-root /path/to/original-project-archive --out /path/to/new-export
```

This writes `new-export/data/` and refuses an existing data output directory. It uses Python's standard library and reads only existing source files. It checks accepted manifests/finalizations against the final evidence index, runner files against the prior independent SHA-256/size bindings, source shards against the original bundle, and all points against the independent review. Source-bundle selected-state membership, original weights, budgets, actual D observations, prediction hashes, and failure semantics are also checked. Logical source paths are relative to the original project root; neither personal local drive paths nor personal remote-home prefixes are shipped.

The shipped CPU analysis command is documented in the package's main README. It needs only this small snapshot; re-exporting requires the private original archive.
