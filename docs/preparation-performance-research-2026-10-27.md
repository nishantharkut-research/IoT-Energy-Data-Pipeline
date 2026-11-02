# Preparation performance: evidence and proposed replacement

Research date: 2026-10-27. This is a design recommendation, not an implemented or accepted replacement. The active SSD launcher and its frozen computation files were not changed by this research.

## Observed problem

The current preparation inserts full canonical JSON payloads into a SQLite `WITHOUT ROWID` table keyed by pseudorandom source hashes. It commits after ingesting all workbooks. This creates a large indexing workload and provides no reusable workbook checkpoints.

At approximately 21:29 IST, read-only inspection of the process's open workbook, matched to manifest traversal order and the completed source profiles, established that completed workbooks accounted for 11,644,634 of 63,273,828 physical rows (18.40%). This measures ingestion only; sorting/export/publication remain separate phases. The currently open workbook was `Resappled data/T15/GUI_NO.D0164.xlsx`.

Process counters showed approximately 734 GB requested reads while the database was approximately 34.6 GB. These are process I/O counters, not measured physical SSD reads; operating-system caching affects the relationship. They support investigation of repeated page access but do not independently prove its cause.

An isolated 40,000-record synthetic insertion benchmark produced:

| Layout | Insert seconds | Requested read bytes | Database bytes |
|---|---:|---:|---:|
| Current layout, default cache | 45.46 | 2,218,913,808 | 187,572,224 |
| Current layout, 128 MiB cache | 19.84 | 46,129,168 | 187,572,224 |
| Ordinary rowid table, 128 MiB cache | 13.82 | 16 | 167,559,168 |

Sorted payload hashes matched across all three. Timings exclude subsequent sorted-output iteration, use synthetic payloads, and were collected while the original job remained active. The runs are a diagnostic experiment, not a replicated end-to-end performance result or a guaranteed 3.3x full-data speedup. Scripts and results are in `D:/IoTBDM/diagnostics/`.

## Findings from primary sources

1. **SQLite documents this layout limitation.** `WITHOUT ROWID` is most suitable for small records. Its guidance gives roughly 200 bytes per row for 4 KiB pages and explains why large records tend to perform better in ordinary rowid tables. This matches the direction of the local benchmark; it does not establish an exact full-data size or ETA. [SQLite documentation, section 4](https://www.sqlite.org/withoutrowid.html#when_to_use_without_rowid).

2. **Sort bounded runs, then merge.** DuckDB's developers describe producing independent sorted runs and a k-way merge to reduce I/O when data exceeds memory. The ICDE 2023 paper studies relational sort implementation and the costs of comparing and moving records. These sources support separating ingestion from global ordering. [DuckDB sorting design, 2025](https://duckdb.org/2025/09/24/sorting-again), [Kuiper and Muehleisen, ICDE 2023](https://duckdb.org/pdf/ICDE2023-kuiper-muehleisen-sorting.pdf).

3. **Commit recoverable task outputs.** Dean and Ghemawat describe independent tasks, private temporary outputs, atomic publication, and recovery by re-execution. This supports workbook-level recovery boundaries; it does not make our Windows/USB implementation durable automatically. [MapReduce, OSDI 2004, sections 3.3 and 3.5](https://storage.googleapis.com/gweb-research2023-media/pubtools/4449.pdf).

4. **Bound partitions and output batches.** Arrow exposes file, row-group, and open-file limits. Dask recommends balancing partition memory against scheduling overhead; its 100-300 MiB guidance concerns in-memory pandas partitions, not compressed file sizes or a universal prescription for this project. [Arrow dataset documentation](https://arrow.apache.org/docs/python/dataset.html), [Dask Parquet guidance](https://docs.dask.org/en/latest/dataframe-parquet.html).

5. **Files alone are not checkpoints.** Arrow explicitly provides no dataset transactions or ACID guarantees and warns about incomplete writes and power loss. A verified completion manifest is therefore an application responsibility. [Arrow transaction limitations](https://arrow.apache.org/docs/python/dataset.html#a-note-on-transactions-acid-guarantees).

## Recommended design for this machine

These are engineering choices inferred from the sources and local evidence, not parameters prescribed by those papers.

- Use source workbooks as recovery units. Within each unit, cap the serialized-byte and row budgets of sorting buffers; a workbook must not be assumed to fit in RAM. Write sorted runs sequentially. Preserve valid and quality records separately, including empty-unit counts.
- Publish a unit only after closing outputs, recording input/rule/schema/implementation identities, output hashes and sizes, and physical/valid/quality counts. Flush durable state as supported by the filesystem. Treat incomplete or hash-invalid output as uncommitted. Do not promise immunity to SSD failure or sudden power loss.
- Resume by verifying the complete expected unit set and its dependencies, then skip only verified units. Prevent concurrent writers to the same workspace. Refuse incompatible inputs or rules.
- Merge in deterministic groups with a bounded number of open files. Check global source-ID uniqueness and ordering during the final merge. Preserve the existing source-quality sort order. Emit the existing final NDJSON and exact-decimal Parquet schema so downstream replay, Spark, and Hadoop contracts remain compatible.
- Publish the final immutable snapshot only after counts, artifact hashes, and the expected source set reconcile. Treat final merge/export as a separately reported stage. Initially, a failed final export may restart from completed units without rereading XLSX sources.
- Start by measuring one and two worker processes with an explicit total memory budget. Additional workers are conditional on observed CPU, disk throughput, and available RAM. Avoid another large dependency solely to partition 1,329 existing files.
- Record completed physical rows, valid/quality counts, elapsed time, current phase, output bytes, and per-unit durations. Separate ingestion ETA from merge/export ETA.

## Acceptance before switching execution

Compare exact canonical NDJSON and source-quality NDJSON against the existing implementation on representative source files, including high decimal scales and missing values. Compare Parquet records and schema exactly; file-byte identity depends on preserving writer batching and settings and must be checked separately if required. Exercise stop/restart, partial outputs, changed inputs/rules, empty units, and duplicate source IDs across units. Measure complete preparation including merge, hashing, and Parquet export, with peak disk use and memory. Use actual source data and label any concurrent-job contention.

Do not stop the current job merely on the strength of the insertion microbenchmark. Prepare and verify the replacement first, then perform a deliberate recorded handoff. Do not copy or query the active uncommitted SQLite database as a valid checkpoint. No change to the experiment matrix, canonical identities, precision, fault handling, or independent Hadoop verification is proposed.
