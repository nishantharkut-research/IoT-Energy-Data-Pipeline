# Coursework submission implementation plan

**Goal:** Deliver a readable project report PDF, eight saved-evidence dashboard views, and a usable GitHub handover within the agreed 5–6-hour scope.

**Approved scope:** Complete the already implemented pipeline's submission. Use 15 completed experiments and existing source-audit summaries. No new distributed runs, new publication gate, fabricated sealed fixtures, live utility integration, or new financial-effect claim. The repository is https://github.com/nishantharkut-research/IoT-Energy-Data-Pipeline.

**Architecture:** Keep the existing strict sealed-run viewer. Add a portable submission viewer consuming byte-bound committed closure/scope/plan JSON and the published source-audit Markdown. Clearly distinguish summary validation now from the original runtime verification timestamp. Report figures and numerical tables derive from these same inputs. Source-audit counters in this checkout are published summaries; original audit JSON and physical meter data are absent.

## File responsibilities and execution

- [x] Evidence loader: `dashboard/submission_data.py`, `docs/results/submission/evidence-index.json`, and `tests/unit/test_submission_data.py`. Verify small-file byte bindings, original scope/plan hashes, 15 unique finalized runs, record/aggregate agreement, and layer equations. Reject changed, missing or inconsistent evidence. Derive source counts from the bound published audit; retain its evidence limitation.
- [x] Dashboard: `dashboard/submission.py`; minimally route `dashboard/app.py` between portable summaries and strict sealed-run files. Eight views: overview, source quality, delivery accounting, faults, independent verification, watermark/consumption, recovery, storage/SQL. Light theme, readable labels/units, unknown impact explicit. No automatic services or large rehashes.
- [x] Browser capture: `scripts/capture_submission_screenshots.py`, eight actual screenshots under `docs/submission/figures/`, and bounded browser checks for exceptions, horizontal overflow and narrow viewport. Screenshots must contain saved results rather than mock measurements.
- [x] Report: `docs/submission/project-report.tex` and PDF, vector architecture and finalization diagrams, generated result tables. Target 12–16 substantive pages, including references; adjust length for legibility rather than pad. Explain data, structural identity, exact arithmetic, controls, faults, comparison boundaries, recovery and measured costs. Use short captions, distinguish measurements from interpretations, cite primary documentation and dataset. No invented university identifiers or signatures.
- [x] Handover: update README, `docs/HANDOVER.md`, demo guide, and submission manifest with hashes. Provide Linux commands and a report link. No user must restore the SSD to view the portable summary dashboard. Explain what original artifacts are needed for deeper verification.
- [x] Acceptance: focused negative/positive tests, relevant existing suite, lint, eight real browser captures, visual PDF page review, numerical provenance, clean fresh-checkout setup, and original evidence bytes unchanged. Review final diff before committing/pushing to the named repository.

## Acceptance details

Combined fixture: 432 Bronze = 288 parsed-valid + 144 quarantine; 288 valid = 144 Silver + 144 duplicates. Restrictive watermark: 144 valid = 143 Silver + 1 late. Gold/Hadoop retain 144 source records. Terminal controls remain separate. Two incomparable consumption supports imply unknown total exposure; zero comparable subtotal is retained as a scoped result. Independent verification shares canonical input and cannot establish physical truth. All 1M runs recovered; full workflow times are unavailable and query settings differ by scale. Source-ID prefixes are not continuous meter-days.

## Progress and rulings

- 2026-11-13: New GitHub owner verified; default branch and base commit remain feat/coursework-foundation / 1bddfa9. Clean isolated feature branch created in the fresh checkout.
- Ruling: use committed closure JSON for the portable demo, not invented runtime files — original sealed directories are absent — full runtime verification remains unavailable here.
- Ruling: the 12–18-hour publication-gate proposal is deferred under the user's accepted 5–6-hour submission scope.
- Ruling: user explicitly authorized autonomous planning and execution; do not interrupt for repeated design approvals.

- Implementation: eight portable views and bound input loader complete. Original sealed-run mode retained. Seven reporting/UI checks added. Two existing symlink-handling failures reproduced and corrected.
- Verification: non-distributed unit/contract/property suite 580 passed, 7 skipped; lint and repository-independence scan pass. Two historical documentation paths made portable. Original final JSON and source-audit summary bytes remain unchanged.
- Presentation: 16-page LaTeX report; eight actual dashboard captures and two vector diagrams. Rendered PDF inspected; overlapping zero chart labels removed and finalization arrows routed to distinct inputs.
- Independent review: no actionable factual or evidence-handling findings. No new workload runs; publication-claim gate remains deferred.
- Fresh checkout: installed the dashboard extra in a separate environment, loaded all 15 saved runs, rendered all eight views, and confirmed that strict mode rejects absent original evidence.
- Delivery: use reviewed commits and a fast-forward update to the repository default branch; preserve original experiment history.
