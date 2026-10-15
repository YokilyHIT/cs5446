# Portable D0 snapshot input contract

The supported entry point is `python -B tools/analyze_d0_snapshot.py --dataset gpu_analysis/data/d0_snapshot.json --out gpu_analysis/generated/d0_metrics.json` from the repository root. Python 3.10 or newer and its standard library are sufficient. The command creates new JSON and Markdown outputs and refuses to overwrite either file.

The six original sidecar modules and `ANALYSIS_SPEC.json` retain their original paths and bytes. `analysis_metrics.py` binds the existing production text scorer by SHA-256. `tools/analysis_sources.json` records every copied file and its source path. Preserve those bytes when committing/checking out; use `-text` Git attributes for the listed paths. `analysis_tool.py` is retained for its helpers and the future full-report function; its original dataset/report CLI is not supported by this minimal checkout because its execution/input reconstruction dependencies are deliberately absent.

## Snapshot fields

The snapshot uses the existing `d0_descriptive_dataset` metric input structure. It is a portable export, not a claim that the original `load_bound_dataset` reconstruction has run.

- Root: `schema_version: 1`, `kind: "d0_descriptive_dataset"`, `status` (`complete` or `collection_incomplete`), `D0_game_count`, `original_selected_state_count`, `games`, `points`, `sha256`, and the export's provenance metadata.
- Each game: `canonical_game_id`, `original_k_j`, `original_game_weight: 1/J`, and collection `status`.
- Each point: `canonical_game_id`, `state_id`, `state_spec_sha256`, `original_k_j`, `statistical_weight: 1/(J*k_j)`, `step_id`, `remaining_budget: 30-step_id`, `source_decision_status`, `draft_action`, `draft_in_visible_menu`, `prediction_usable`, `confidence_scoreable`, `prediction`, `D_reference`, and `branches`.
- Prediction: preserve the original `wm_prediction`, `wm_mean_logprob`, `wm_confidence_logprob`, `wm_confidence_scope`, `wm_confidence_status`, `wm_prediction_token_count`, `wm_prediction_char_span`, and `wm_token_alignment`. Do not reconstruct the exp score, token count or alignment from displayed text. A full raw HTTP response is not needed by these functions; record its original evidence binding in the export.
- D reference: original `available`, `measurement_validity`, and `observation`, associated with the actual D first step. Keep original source rollout identity when available.
- Each D/N/P branch: `raw_Y` (integer 0/1 or null), `outcome_status`, `measurement_validity`, and `first_action` (parsed action or null). Preserve `first_action_policy_failure`, group/rollout identifiers, `new_mu_calls`, and failure reasons when exported.
- Preserve actual `D_check` and its status/coverage for case selection; do not invent a passing replay check. Preserve `cross_job_state` as true, false, unknown/null, or `not_applicable` with its source provenance.

A source draft failure stays in the original point denominator. Its `source_decision_status` is `source_draft_policy_failure`, prediction is absent/null, `prediction_usable` and `confidence_scoreable` are false, and all local Y values are null. A measured N first-action policy failure is different: it may have `raw_Y: 0`, `outcome_status: policy_failed`, `measurement_validity: valid`, and `first_action: null`; this preserves its measured utility while excluding it from parsed-action comparisons.

Seal the root object after removing `sha256`: SHA-256 of UTF-8 `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)`. The CLI checks this seal and source-copy bytes. This is an integrity check, not a replacement for verifying or reconstructing the original evidence chain.

## Analysis scope

The CLI calls unchanged `analyze`, `select_cases`, and `summarize_sensitivity`. It retains the original weights, exact score ties, missing-value rules, fixed case hashes, score directions and definitions. It inventories exported cross-job labels but does not claim the cross-job exclusion sensitivity has been completed.

The output is `metrics_only_development_description`. It has no full provenance audit, per-call cost reconstruction, physical behavior analysis, N/P candidate selection, N/P execution, GPU calls, environment instances, formal inference, or completed full D0 report. Separate accepted accounting totals may be shipped for context; they must not be inserted as fake per-call evidence.

## Future full-report input

Unchanged `make_report(dataset)` additionally requires a content `sha256`, collection fields (`no_observed_decision_games`, `collection_incomplete_games`, `admission_pending_games`), full diagnostic fields, and actual `cost_evidence` with `calls`, `games`, and `physical_groups`. Calls need original ledger identity and terminal/attempt evidence; physical groups need actual rollout/step records. The final accounting summary is not a substitute for those lists. Do not fill them with empty arrays or zero costs to make the full report execute. The final accepted evidence reader and complete per-call cost association remain follow-up work under `D0_ANALYSIS_MINIMAL_TASK.md`.

Existing pure-function regressions can be run with `python -B -m pytest research_progress/2026-10-10-d0-analysis/tests -q -p no:cacheprovider` after installing pytest. These tests use synthetic outcomes and do not validate GPU services or the entire real evidence export.
