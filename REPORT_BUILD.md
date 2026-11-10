# Report files

- `report.tex`: complete report entry point: main manuscript, supplementary appendices, references, then the two self-review pages.
- `report_supplement.tex`: supplementary content included by `report.tex` using `\input`; do not compile it separately.
- `report_references.bib`: verified bibliographic metadata, using arXiv versions consistently.
- `samplepaper.tex`: original template, preserved.

The main manuscript centers on the 4B planner with a 14B WM. It retains the template's anonymous author format and Times fonts. At the author's request, both documents use A4 paper with 25 mm margins, including headers and footers within that area, via `geometry`. This course-report layout overrides the standard LNCS text area; remove the `geometry` package line in both documents to restore the submission template's margins. Font sizes and line spacing are unchanged. The supplement is included after the conclusion as lettered appendices; references and self-review follow in the same PDF.

## Build

Body paragraphs use a consistent 1.5 em first-line indent with no extra paragraph gap. The `indentfirst` package also indents the first paragraph after a heading. Minor headings (`\paragraph`), including Research questions and the self-review questions, appear on their own line in bold with space above and below instead of running into the text. These settings in `report.tex` apply to the included supplement; captions and tables retain their own formatting. No local `overleaf.tex` was present when this adjustment was made. The additional heading spacing may affect the self-review pagination and should be checked after compilation.

Use a TeX distribution with Springer LNCS (`llncs.cls` and `splncs04.bst`), `geometry`, `newtx`, `booktabs`, `amsmath`, `graphicx`, `url` and T1 fonts. In Overleaf, start from the supplied LNCS template and upload these three report source files; set `report.tex` as the main document. Keep `report_supplement.tex` in the same directory; compiling `report.tex` includes it automatically.

From this directory with a local installation:

```text
pdflatex -interaction=nonstopmode -halt-on-error report.tex
bibtex report
pdflatex -interaction=nonstopmode -halt-on-error report.tex
pdflatex -interaction=nonstopmode -halt-on-error report.tex
```

No LaTeX compiler or LNCS class/style files were found in the current workspace/environment during preparation. Static checks cover environment/braces balance, citation keys, labels and references. A PDF, the main-content page count, table widths and the exact final two-page self-review layout have not been verified. The self-review has explicit page boundaries but overflow must still be checked in the compiled PDF.

## Author details still required

The template uses anonymous authors. Replace these only if an identified course-report version is needed. Self-review question 6 explicitly records unknown experimental checkpoint revisions, human-validation details and public-release information rather than inventing them. The authors should complete these items and review the AI-generated manuscript before submission. Manuscript assistance is disclosed as Codex on 2026-11-06; an unavailable exact backend identifier is not guessed.

## Evidence mapping

Source narrative: `alfworld-preexp-npu/reports/react_study/report_project_final_20261030.md`.

All paths below are relative to `alfworld-preexp-npu/outputs/react_study/`:

| Manuscript content | Recorded evidence |
| --- | --- |
| Main frozen evaluation and model-size controls | `p7_final/tables/final_fresh600.md` |
| Interface and follow-up controls | `p7_final/tables/confounds_followups.md` |
| Baselines | `r6_baselines/tables/baselines_fresh600.md` and `r6_baselines/README.md` |
| Mechanism analysis | `failure_analysis/tables/deep_analysis.md` |
| Development probes | `probe_feasibility/tables/probe_4b.md` and `probe_feasibility/tables/round5A.md` |
| Rule-based extensions | `r7_hybrid/tables/fresh_r7.md` |
| Repeated unseen evaluation | `p7_final/tables/final_unseen134.md` |

References were checked against the primary arXiv records for ReAct (2210.03629), ALFWorld (2010.03768), WALL-E (2410.07484), ExpeL (2308.10144), WorldEvolver (2606.30639) and RPMS (2603.17831). The experiment scores are the project's recorded results, not scores taken from those papers. No experiments were rerun for this writing task.

## Expanded course-report edition

The main text now contains ten tables: failure signals, development selection, protocol, frozen results, primary tests, interface ablations, task-type success, subgoal funnel, follow-up controls and aligned baselines. Additional prose explains parsing/fallback behavior, the gate exception for `check valid actions`, task heterogeneity, conditional-analysis limits and token-cost interpretation. All added numerical results are transcribed from existing result tables; no new experiments are claimed. This expanded course-report edition has not been fitted to the original short-paper page limit. Final page count and float placement require compilation.

## WHEN--WHAT--HOW narrative

The main manuscript is organized as Shared Experimental Setup, Study 1 (WHEN: predictive guidance and invocation timing), Study 2 (WHAT: failure analysis and oracle information), and Study 3 (HOW: frozen WM repair and its evaluation). The abstract, introduction roadmap, study transitions, discussion, conclusion and self-review follow this progression. Key timing and oracle evidence has been restored to the main text; the supplement retains the full prediction model-size matrix and other extensions.

The main text now has thirteen tables, including the research roadmap, matched forecast/resampling comparison and oracle probe. The new timing table and supplementary matrix are transcribed from `alfworld-preexp-npu/outputs/react_study/p3_mechanism_matrix/README.md`. Historical timing and memory results are identified separately from the main repair configuration and frozen fresh600 evaluation. No experiment was rerun for this restructuring.
