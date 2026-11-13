> Submission document: [the complete project report PDF](submission/project-report.pdf). The text below is the earlier short project overview.

# Auditable IoT Energy Data Pipeline

## Problem and purpose

A streaming job can finish while its output omits late events, counts repeated
deliveries, or includes invalid measurements. This coursework accounts for every
delivery and checks the finalized answer using an independent computation.
The contribution is the implemented evidence chain and experiments across the
pipeline. It is not a new streaming algorithm.

## Data and preparation

The public HKUST smart-meter dataset is deposited under Dryad DOI
`10.5061/dryad.k3j9kd5h6`. Excel telemetry and Brick metadata are registered,
profiled, and converted to canonical NDJSON and Parquet. Raw and cleaned source
variants remain separate. Stable identifiers describe physical workbook rows.
Original timestamp and numeric text is retained, and scaled integers preserve
decimal values exactly.

The executed real-data snapshot uses Asia/Hong_Kong as an explicit experimental
timezone assumption, not an author-confirmed convention. Units and cumulative
reading semantics follow the recorded evidence contracts. The
[source audit](results/source-audit-2026-10-27.md) describes source preparation.

## Pipeline

Deterministic schedules replay events into Kafka, including controlled duplicate,
delayed, malformed, and interrupted delivery cases. Acknowledgements and terminal
records establish partition completion.

Spark preserves every data delivery in Bronze. Silver provides an operational
candidate with watermark-bounded deduplication. Invalid deliveries enter
categorized quarantine. Valid late events remain accounted for. After replay
completion, batch Gold rebuilds exact source records from Bronze, preserving
valid records omitted from Silver.

Canonical NDJSON separately enters HDFS. Independent Hadoop Streaming programs
reproduce source records and aggregates. Reconciliation checks declared exact
fields, layer conservation, and artifact hashes. Incomplete or unreconciled runs
cannot be sealed for the read-only dashboard.

## Experiments and findings

The final matrix contains five correctness schedules, interrupted and
uninterrupted recovery, retaining and restrictive watermarks, and three clean
repetitions each at 100K and 1M events. Storage and five SQL queries are measured
within the runs. The three originally planned 5M repetitions are excluded because
of resource and time constraints.

All 15 runs passed independent source-record and aggregate reconciliation.
The correctness schedules produced identical semantic Gold and Hadoop outputs.
Interrupted recovery reproduced all four semantic output artifacts byte for
byte. In the combined-fault fixture, 432 deliveries were accounted for as 144
unique valid records, 144 duplicates, and 144 quarantined deliveries.

The restrictive watermark reduced Silver from 144 to 143 records. Gold and
Hadoop both retained all 144. Two consumption periods changed; both were
incomparable with the verified result because duplicate timestamps made their
derivation ambiguous. Numeric discrepancy over comparable intervals was zero.
Total energy error and residual financial exposure remain unknown.

Median verification cost was 13.88 minutes at 100K and 165.30 minutes at 1M.
Scoped verification artifacts occupied about 253 MB and 2.52 GB, respectively.
These costs cover Gold, layer auditing, Hadoop, and reconciliation, rather than
the complete workflow or total runtime storage. Full counts, timing ranges,
storage ratios, query measurements, and evidence hashes are in the
[generated results](results/final/course-results.md).

## Interpretation and limits

These experiments show the usefulness and cost of retaining source evidence
alongside a bounded streaming candidate. Agreement between Spark and Hadoop
establishes agreement under declared contracts. It does not establish physical
measurement accuracy or complete temporal coverage in the source.

Consumption is derived only for supported cumulative-kWh readings. Initial
baselines, negative deltas, resets, and ambiguous timestamps are flagged.
Rates of 0.5, 1.0, and 2.0 currency units/kWh are hypothetical scenarios.
No HKUST tariff, financial result, or demonstrated saving is claimed.

All three 1M workflows required recovery, so complete workflow timings are
unavailable. Smaller query partitions were introduced for 1M; query timings
across scales are not a configuration-controlled comparison. Evidence is limited
to historical replay through 1M source records on one designated machine.

Future research could examine selective independent verification and its cost
versus detected errors under realistic fault distributions. Such work would
require a defined failure model, appropriate baselines, and further experiments.
The current project makes no production-readiness or research novelty claim.
