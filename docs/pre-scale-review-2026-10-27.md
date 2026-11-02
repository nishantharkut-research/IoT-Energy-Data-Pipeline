# Pre-scale review: 27 October 2026

The project has substantial engineering depth, but the first successful fixture
matrix did not establish readiness for final real-data runs. The audit below
examined code, actual artifacts, and connections between stages. Tests supported
that work; they were not its sole basis.

## Trace and evidence

| Connection | What was checked | Result or limit |
| --- | --- | --- |
| Archive to workbook rows | Package hash, raw/clean separation, complete profiles, lexical numeric preservation, physical row identities | Both variants audited; repeated manifests/profiles identical |
| Rows to canonical events | Exact integer scaling, Brick joins, rejected source rows, timestamp conversion | Wide numeric round trip passed; real timestamp timezone remains unassigned |
| Schedule to broker to Bronze | Identities, receipts, partitions, offsets, terminal records, payload/header hashes | Nine v1 cases and three v2 cases checked, including cooperative producer resume |
| Bronze to Silver/Gold | Watermark behavior, delivery disposition, exact source coverage | Restrictive Silver has 143 sources; exact Gold has 144 in all nine fixtures |
| Canonical NDJSON to Hadoop | HDFS input binding, two completed Streaming jobs per run, independently reconstructed records/aggregates | All nine agree on 144 records and three aggregates |
| Verified records to consumption | Cumulative-unit gate, ambiguity/resets, interval boundaries, exact arithmetic | Corrected unsupported zero filling; identical temporal supports are required |
| Gold to SQL results | Parquet descriptors, projected values, sort order, cached timing policy | Full result values and digests independently reconstructed for all five queries in all three v2 runs |
| Reports to seal/dashboard | Originating data bindings, exact registered file set, hash verification | Corrected acceptance of drift before sealing; historical seals unchanged |
| Sealed runs to course report | Fixed matrix membership, machine/snapshot/plan bindings, workflow receipts, derived summaries | Publication checks executed counts/settings and recomputes summaries from bound evidence |

## Corrections and interpretation

The old restrictive-fixture decision report priced two unavailable Gold intervals
as zero consumption. Its reported 2 kWh discrepancy and tariff amounts are
withdrawn. Reanalysis identifies two incomparable periods, zero numeric
discrepancy on comparable intervals, and unknown residual exposure. A zero
subtotal does not mean that missing consumption or total uncertainty is zero.

The source and aggregate comparisons in the nine original runs remain valid.
The changes address decision interpretation, artifact provenance before sealing,
query measurement, report publication, and the loaded-manifest path boundary.
The detailed local review notes and regression reproductions are retained in
`tmp/pre-scale-*-review.md`, `tmp/decision-interval-fix.md`, and
`tmp/seal-bindings-fix.md`.

## Readiness gates

- Completed local verification: 709 passed, 11 skipped; Ruff, formatting,
  independence scan, and targeted type checks passed. Later reporting and
  display changes passed ten focused checks and a real-browser inspection.
- Production v2 completion and interruption/resume passed the actual Kafka,
  Spark, HDFS, and Hadoop path. All three 144-source cases finalized and their
  complete records, aggregates, delivery offsets, and five SQL results were
  checked independently. This supplies no 100K/1M/5M performance result.
- The full clean snapshot exceeds C: free capacity. D: has sufficient initial
  headroom for the planned layout; Docker access was verified. Source snapshot,
  outputs, and growing service persistence use the chosen layout. YARN scratch remains
  on Linux storage and requires internal-drive headroom.
- The deposited timestamp timezone still needs source evidence before the
  current canonical contract can convert those timestamps to UTC.
- After these gates, run 100K, then 1M, then 5M, with the fixed three repetitions.
  Recheck free space and inspect sealed results before each larger size.

## Runtime evidence

The three v2 cases have 144 / 432 / 432 Bronze data deliveries respectively,
0 / 144 / 144 quarantined deliveries, and 144 Silver and Gold sources each.
Each produced three independently agreed aggregates. The control and resumed
combined runs have identical semantic outputs. All owned services stopped.

The original restrictive output was reanalysed through the revised
reconciliation and business-report functions without altering its old seal.
The result has two incomparable periods and no priced comparable discrepancy.
`reports/generated/20261027/decision-reanalysis-proof.json` binds that result.

The dashboard now suppresses retired energy figures from older run views. The
production execution revision and the later display-only changes are recorded
separately in the final source manifest.

## What the project can claim

It demonstrates delivery accounting, bounded streaming behavior, exact batch
reconstruction, independent verification after canonicalization, and explicit
limits on operational consumption estimates. Completing the real-data matrix
will add measured verification cost, storage, query, and scale evidence.

This is a strong coursework systems project. A novel algorithm, production
exactly-once guarantee, or publishable research contribution has not been
established. Hadoop shares the canonical input: agreement cannot detect every
source-adapter error or prove that physical meter readings are accurate. The
Docker services execute on one physical machine, and controlled replay does not
measure live campus ingestion or a multi-machine cluster.
