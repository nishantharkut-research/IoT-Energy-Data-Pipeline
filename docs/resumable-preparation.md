# Resumable dataset preparation

`iot_energy_pipeline.resumable_snapshot.build_resumable_snapshot` produces the existing `snapshot-manifest-v1` outputs from reusable workbook units. It uses the same source adapter, source identities, decimal conversion and Parquet schema as `build_snapshot`.

Each worker sorts bounded buffers of serialized rows, writes sorted runs, then merges them into one valid-event file and one source-quality file per workbook. The default serialized buffer budget is 16 MiB per stream; Python objects, parser state and Brick metadata consume additional memory. A workbook does not have to fit in memory. The final merge opens at most 32 input files per group. Duplicate source identities are rejected.

Each completed workbook directory contains both output files and a checkpoint with source identity, SHA-256 hashes, byte sizes and row counts. Outputs are closed and flushed before publication. Resume verifies the workspace identity, source hashes and completed output hashes. A partial workbook is rebuilt. Changed rules or implementation require a new workspace. A partial final export restarts from completed workbooks.

An OS-owned lock prevents two parent writers. A separate lock protects each workbook, including against workers surviving a terminated Windows parent. A replacement worker waits up to ten minutes for that lease, then checks whether the previous worker committed the unit. It cleans incomplete files only while holding that unit's lock. This is process-recovery protection, not a guarantee against SSD failure or power loss.

The workspace and published snapshot must share a filesystem for directory publication. Use separate, non-overlapping directories. Keep the workspace until the published snapshot is independently verified. Interrupted final exports are removed only from the workspace's designated `export` directory; committed workbook outputs remain.

The progress callback reports completed workbooks and physical rows, merge stages and processed merge/export rows. Ingestion percentages do not include final sorting, export and hashing. Resume begins by checking hashes, so verification time precedes new ingestion.

## Validation on 2026-10-27

The targeted suite passed 65 tests covering existing canonical behavior, exact decimal extremes, byte-equivalent snapshots, multiple workers and merge passes, interrupted preparation/export, corrupt checkpoints, exclusive writers and surviving worker leases. Ruff, relevant mypy checks and the independence scan passed.

A three-workbook real-source sample contained 122,036 physical rows: 81,848 valid events and 40,188 source-quality rows. Legacy preparation took 142.98 seconds; chunked preparation took 68.23 seconds with one worker and 52.53 seconds with two. NDJSON, Parquet and source-quality hashes matched. This is a single diagnostic sample with the old full preparation still running, not a replicated full-scale benchmark. Recovery-lock changes were subsequently checked in the focused suite and a final source-sample execution.

Preparation checkpoints do not make the entire experiment launcher resumable. Spark stream checkpoints and controlled producer recovery remain separate mechanisms. A partially executed experiment matrix still needs deliberate recovery into suitable run directories; do not overwrite sealed runs.
