# Resumable preparation implementation plan

Goal: replace the large indexed staging database with bounded sorted runs and verified workbook checkpoints, preserving the published snapshot contract.

Approved scope: user instruction "do what is best", following the sourced preparation design. Keep the active SSD computation unchanged until a verified replacement is ready.

- [x] Add failing integration tests for exact legacy equivalence, interrupted resume, corrupt checkpoints, incompatible rules, and cross-run duplicate rejection.
- [x] Implement bounded sorted runs, bounded-fan-in merge, per-workbook completion manifests, exclusive workspace and worker locks, and optional two-process execution. Reuse the canonical row adapter and exact Parquet schema.
- [x] Verify unit/integration regressions, actual source subset equivalence and end-to-end timings. Record results including contention from the old job.
- [x] Freeze a new source revision and launcher with preparation progress and restart support. Stop only the identified old launcher after the replacement passes; retain its artifacts as an abandoned attempt.
- [x] Launch resumable full preparation on SSD. Verify process, progress and stderr. Update execution status and document remaining experiment recovery limitations.
