# Experiment execution record

The user authorized distributed fixtures and real-data experiments on 27 October
2026, and subsequently authorized the attached SSD for experiment storage.

## Active execution: 21:49 IST

The original full preparation attempt was stopped after a verified replacement
passed source-data equivalence and speed checks. Its uncommitted database and
logs remain intact. The replacement launcher is
`reports/launches/full-resumable-hkt-002/execute_full_runs.py`; its actual Python
process started as PID 36492. `state.json`, `stdout.log`, `stderr.log` and
`handoff.json` in that launch directory record execution and provenance.

Preparation now uses two workers, bounded sorted runs, verified workbook
checkpoints and a final external merge. At 21:49:33 IST, 26 workbooks containing
22,131 physical rows had committed. These early files are small; workbook
percentage must not be substituted for row percentage. The state file reports
both. No real-data Kafka/Spark experiment has completed yet.

The three-workbook diagnostic sample contains 122,036 source rows. Legacy
preparation took 142.98 seconds, compared with 52.62 seconds for the final
two-worker candidate. Canonical NDJSON, source-quality NDJSON and Parquet hashes
matched. The focused suite passed 65 tests; the surviving-worker regression was
then strengthened with explicit synchronization and passed again. A focused
review found a worker-lifetime race; per-workbook OS locks corrected it.

Execution-source manifest `execution-source-manifest-resumable-002.json` freezes
152 files. The launcher keeps Windows awake while running. Preparation can resume
completed units; a partial final export restarts from those units. The full
experiment matrix is not automatically resumable. See
[preparation recovery details](resumable-preparation.md).

## Verified evidence

- Complete raw and clean registration, structural profiles, and exact telemetry
  audits are saved under `reports/generated/20261027/`.
- Repeated registration and repeated profiling are byte-identical for both
  variants. Source counts and hash references are in the source-audit report.
- The first complete Docker acceptance matrix finalized all nine cases. Each
  case has 144 canonical source records and three aggregates agreed by Spark
  and two actual Hadoop Streaming jobs. Recovery records are identical.
- The restrictive watermark retains 143 Silver sources; retaining keeps 144.
  Both retain all 144 in exact Gold. These are synthetic fixture observations.
- Independent reopening checked every sealed artifact, plus actual records,
  aggregates, broker offsets, layer counts, and completed Hadoop job logs.
- Latest broad local verification after the logic corrections: 709 passed,
  11 skipped. Log: `tmp/pre-scale-final-local-verification-v2.log`.
- Ruff, formatting, independence scanning, and targeted type checks passed.

## Findings corrected before scale

The first fixture acceptance was insufficient to declare the project ready.
The subsequent code and artifact audit found and corrected these issues:

1. Missing or differently supported consumption intervals were compared with
   zero. Comparison now requires identical meter/start/end supports; unavailable
   values remain null, tariff totals are qualified subtotals, and residual
   exposure is unknown.
2. Sealing could accept bytes changed after reconciliation. It now rechecks
   replay, canonical, Gold, Hadoop, candidate, disposition, and Parquet descriptors
   against their originating bindings before capturing the final registry.
3. Query timing counted cached rows. It now consumes all projected ordered
   values, retains result digests and three actual durations, and validates Gold
   Parquet against the reconciled source export before timing.
4. Course report generation trusted unbound summary values. It now requires the
   complete fixed matrix, copied execution evidence, sealed workflow receipts,
   and recomputed summaries and cross-run outcomes.
5. Loaded source manifests accepted Windows paths outside the declared root.
   The path boundary now rejects those forms and resolved directory escapes.

The original nine sealed runs remain unchanged. Their source-preservation and
Spark-Hadoop agreement evidence stands. Their old energy-discrepancy and tariff
figures must not be used: the restrictive fixture's two affected periods have
incomparable coverage, rather than an established 2 kWh error.

## Earlier storage and source-evidence review

The planned full clean snapshot needs at least 107.45 GB temporarily for payloads
alone. C: had about 72 GB free. The attached D: SSD started with about 459 GB free (about 455 GB after audit
setup); a host
and Docker read/write/hash round trip passed. `compose.storage.yaml` places
Kafka/HDFS persistence and Spark spill on the selected disk.

The production-v2 proof completed three fresh SSD-backed runs: clean, combined
faults, and combined faults interrupted after one acknowledgement and resumed.
All three sealed, with identical exact Gold and Hadoop outputs. Six actual Hadoop
Streaming jobs completed. An independent reader checked canonical records,
Gold Parquet, aggregates, Bronze payloads/offsets, terminal offsets, Silver,
quarantine, and the complete values/digests of all five SQL queries.

| Synthetic case | Bronze deliveries | Quarantine | Silver sources | Gold/oracle sources |
| --- | ---: | ---: | ---: | ---: |
| Clean | 144 | 0 | 144 | 144 |
| Combined | 432 | 144 | 144 | 144 |
| Combined interrupted/resumed | 432 | 144 | 144 | 144 |

Evidence: `reports/runtime/production-v2-audit-20261027-002/` (relative to the project root).
`production-v2-acceptance.json` binds the executed source revision and seals;
`independent-checks.json` records the independent reconstruction. The first SSD
attempt stopped at startup because its YARN cache could not retain Unix modes.
YARN scratch and daemon logs now use Linux storage. Both input and result
artifacts from the failed attempt remain preserved.

The distributed proof used execution-source manifest `audited-v3`. Subsequent
changes only add the dashboard guard for retired energy estimates and propagate
current decision fields into local-fixture views. Ten focused publication/view
checks passed, and a real browser accepted the new run, rejected an incomplete
path, and suppressed the old retired energy figures. These changes are recorded
in the final source manifest separately from the executed runtime revision.

No 100K, 1M, or 5M real-data run has started. The source timezone remains
undocumented in the reviewed README, article and pinned author code. Under the
user's instruction to proceed with full autonomy, these runs use Asia/Hong_Kong
as an explicitly recorded experimental assumption, not an author-confirmed fact.
The rules and output manifest retain that qualification and the original source
timestamp text. The user did not separately select or confirm that timezone.

See [the pre-scale review](pre-scale-review-2026-10-27.md) for the trace and limits.
