# Run-review dashboard rebuild

**Goal:** Replace the report-like Streamlit presentation with a coherent operator-facing application while preserving the completed experiment evidence and original strict viewer.

**User authorization:** Autonomous work continues under the existing submission task. The user explicitly requested better component libraries and supplied a peer report as a visual and narrative benchmark. No repeated design approval is required.

## Reference findings

The supplied 14-page attendance report explains roles, concrete workflows, controls and outcomes before implementation details. Its PDF pages 9–10 show complete application screens with navigation, selected context, actionable controls and clear state. Our earlier report showed cropped result panels. The new report must show recognisable complete application screens and explain what a user does with each one. No peer wording, figures, data or security claims will be copied.

## Decision

Additional Streamlit CSS would preserve the report-like interaction model. A shadcn/React rebuild offers editable primitives but adds unnecessary component scaffolding for this deadline. Select React + Vite + Mantine for application shell, accessible controls, tables and dialogs; Recharts for actual evidence charts; Lucide for consistent functional icons. This changes presentation, not distributed processing. The existing Streamlit strict artifact viewer remains available.

## Design and useful interactions

Light slate canvas, white navigation and panels, navy text, teal for agreed results and amber for review conditions. Body 16–18px, headings 30–34px, tabular numerals, restrained boundaries. No gradients, random trend lines, decorative gauges, fake maps or live-system claims.

Nine views: project overview, source audit, delivery inspector, fault comparison, verification, watermark/consumption, recovery, storage/SQL and a sourced India use case. Add working run selection/search/filtering, table-row inspection, exact-field/hash dialogs and JSON/CSV export. Every numerical display comes from saved evidence. Fixed copy, workflow diagrams and contextual labels are allowed; missing measurements stay unavailable.

## Files and checks

- [x] `scripts/export_dashboard_evidence.py`: validate the existing inputs with the Python loader, copy exact bytes plus index into a generated public bundle. Never synthesize sealed runs.
- [x] `dashboard/web/`: React/TypeScript app, Mantine shell and controls, Recharts, Lucide, lockfile. Browser checks original summary hashes and count equations before rendering. Explicit saved-evidence status, original verification date and original runtime limits.
- [x] Unit/contract checks: export preserves bytes; altered input rejected; browser evidence loader rejects mismatches; run filters/search and unknown handling work.
- [x] Capture all nine real views, inspect desktop/narrow layouts, selection, dialogs and downloads. Open the live app in the user's browser.
- [x] Update report with full-interface captures and implementation/use-case discussion, not disconnected chart fragments. Rebuild and visually inspect the PDF. Refresh README/handover and asset hashes.
- [x] Preserve original final JSON bytes. Run relevant tests and production build, then commit/push the corrected submission and refresh the standalone PDF/ZIP.

No new pipeline workloads, dataset downloads, alternative measurements, server database or utility field-effect claim. No authentication shell or controls pretending to manage live meters.
