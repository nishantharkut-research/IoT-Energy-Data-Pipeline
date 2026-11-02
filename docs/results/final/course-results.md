# IoT Energy Data Pipeline: final results

All 15 runs in the final coursework scope passed independent reconciliation. Published evidence was freshly hash-verified against scope-bound run seals. This report uses existing results; generating it starts no Kafka, Spark, or Hadoop workloads.

The final scope includes nine fixtures and three repetitions each at 100K and 1M source events. The original three 5M runs are excluded because of resource and time constraints.

## Correctness and delivery accounting

| Run | Gold/source records | Bronze | Duplicates | Late | Quarantine | Silver |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| correctness-clean-r01 | 144 | 144 | 0 | 0 | 0 | 144 |
| correctness-duplicate-r01 | 144 | 288 | 144 | 0 | 0 | 144 |
| correctness-delayed-r01 | 144 | 144 | 0 | 0 | 0 | 144 |
| correctness-malformed-r01 | 144 | 288 | 0 | 0 | 144 | 144 |
| correctness-combined-r01 | 144 | 432 | 144 | 0 | 144 | 144 |
| recovery-uninterrupted-r01 | 144 | 144 | 0 | 0 | 0 | 144 |
| recovery-interrupted_resumed-r01 | 144 | 144 | 0 | 0 | 0 | 144 |
| watermark-retaining-r01 | 144 | 144 | 0 | 0 | 0 | 144 |
| watermark-restrictive-r01 | 144 | 144 | 0 | 1 | 0 | 143 |
| scale-100000-r01 | 100,000 | 100,000 | 0 | 0 | 0 | 100,000 |
| scale-100000-r02 | 100,000 | 100,000 | 0 | 0 | 0 | 100,000 |
| scale-100000-r03 | 100,000 | 100,000 | 0 | 0 | 0 | 100,000 |
| scale-1000000-r01 | 1,000,000 | 1,000,000 | 0 | 0 | 0 | 1,000,000 |
| scale-1000000-r02 | 1,000,000 | 1,000,000 | 0 | 0 | 0 | 1,000,000 |
| scale-1000000-r03 | 1,000,000 | 1,000,000 | 0 | 0 | 0 | 1,000,000 |

All source-record and aggregate comparison error lists are empty. The five correctness schedules produce identical semantic Gold and Hadoop outputs. Interrupted and uninterrupted recovery outputs also match byte for byte for all four semantic artifacts.

## Watermark and decision impact

The retaining watermark preserves 144 source events in Silver. The restrictive watermark preserves 143, while Gold and Hadoop both retain all 144. The missing candidate record changes two meter periods. Both periods have incomparable interval supports; the verified result flags an ambiguous duplicate timestamp.

Comparable intervals have zero measured kWh discrepancy in these runs. This subtotal does not establish zero total energy error. Residual exposure is unknown. The 0.5, 1.0, and 2.0 rates are hypothetical normalized scenarios, not HKUST tariffs or savings.

## Verification cost

Time includes Gold finalization, layer auditing, Hadoop computation, and reconciliation. It excludes streaming and the later storage/query benchmarks. Storage is the scoped verification artifact set, not total runtime disk usage.

| Events | Repetitions | Minimum (min) | Median (min) | Maximum (min) | Median verification storage (MB, decimal) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100,000 | 3 | 13.63 | 13.88 | 14.10 | 252.78 |
| 1,000,000 | 3 | 163.42 | 165.30 | 165.97 | 2522.71 |

All three 1M workflows were interrupted and recovered. Complete workflow timing is unavailable. The component timings above remain recorded measurements; they are not uninterrupted end-to-end timings.

## Storage and SQL

Each row is one completed scale repetition. Ratios are stored bytes divided by canonical NDJSON bytes. Smaller is better for space.

| Run | NDJSON (MB) | Zstd Parquet unpartitioned / NDJSON | Zstd Parquet partitioned / NDJSON |
| --- | ---: | ---: | ---: |
| scale-100000-r01 | 112.04 | 0.0615 | 0.3038 |
| scale-100000-r02 | 112.04 | 0.0615 | 0.3038 |
| scale-100000-r03 | 112.04 | 0.0615 | 0.3038 |
| scale-1000000-r01 | 1120.65 | 0.0601 | 0.1654 |
| scale-1000000-r02 | 1120.65 | 0.0601 | 0.1654 |
| scale-1000000-r03 | 1120.65 | 0.0601 | 0.1654 |

The five read-only SQL queries cover meter, building, time window, quality, and exposure. Each query has three timing repetitions per run and a full ordered result hash. The following figures are medians in seconds within each run. 100K uses the original query settings; 1M uses smaller partitions. This is not a configuration-controlled scaling comparison.

| Run | Query | Rows | Minimum (s) | Median (s) | Maximum (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| scale-100000-r01 | meter | 123 | 7.452 | 7.572 | 10.343 |
| scale-100000-r01 | building | 36,302 | 3.616 | 3.748 | 4.211 |
| scale-100000-r01 | time_window | 100,000 | 6.000 | 6.048 | 6.639 |
| scale-100000-r01 | quality | 0 | 0.274 | 0.350 | 0.405 |
| scale-100000-r01 | exposure | 3 | 0.696 | 0.764 | 0.801 |
| scale-100000-r02 | meter | 123 | 7.620 | 7.752 | 11.222 |
| scale-100000-r02 | building | 36,302 | 3.928 | 4.088 | 4.863 |
| scale-100000-r02 | time_window | 100,000 | 6.292 | 6.604 | 7.147 |
| scale-100000-r02 | quality | 0 | 0.239 | 0.277 | 0.551 |
| scale-100000-r02 | exposure | 3 | 0.692 | 0.740 | 0.904 |
| scale-100000-r03 | meter | 123 | 7.628 | 7.688 | 10.784 |
| scale-100000-r03 | building | 36,302 | 3.568 | 4.000 | 4.700 |
| scale-100000-r03 | time_window | 100,000 | 6.068 | 6.380 | 6.896 |
| scale-100000-r03 | quality | 0 | 0.258 | 0.294 | 0.433 |
| scale-100000-r03 | exposure | 3 | 0.672 | 0.812 | 0.815 |
| scale-1000000-r01 | meter | 1,207 | 87.344 | 88.424 | 92.709 |
| scale-1000000-r01 | building | 363,998 | 50.480 | 51.315 | 51.628 |
| scale-1000000-r01 | time_window | 1,000,000 | 80.232 | 81.328 | 82.250 |
| scale-1000000-r01 | quality | 0 | 4.653 | 5.793 | 5.929 |
| scale-1000000-r01 | exposure | 3 | 0.715 | 0.841 | 0.903 |
| scale-1000000-r02 | meter | 1,207 | 82.232 | 82.476 | 86.410 |
| scale-1000000-r02 | building | 363,998 | 50.164 | 50.180 | 51.816 |
| scale-1000000-r02 | time_window | 1,000,000 | 85.164 | 85.900 | 87.464 |
| scale-1000000-r02 | quality | 0 | 5.285 | 5.550 | 6.065 |
| scale-1000000-r02 | exposure | 3 | 0.776 | 0.844 | 0.931 |
| scale-1000000-r03 | meter | 1,207 | 88.624 | 88.724 | 91.282 |
| scale-1000000-r03 | building | 363,998 | 54.679 | 54.844 | 55.380 |
| scale-1000000-r03 | time_window | 1,000,000 | 89.664 | 90.076 | 90.759 |
| scale-1000000-r03 | quality | 0 | 5.197 | 5.858 | 5.893 |
| scale-1000000-r03 | exposure | 3 | 0.760 | 0.795 | 0.942 |

## Interpretation and limits

These experiments demonstrate delivery accounting, exact recovery from Bronze, and agreement with an independently implemented Hadoop computation through 1M source records. They do not establish live deployment performance, measurement accuracy, financial savings, or a new streaming algorithm.

- No performance or correctness claim beyond 1M events from these experiments.
- All 1M workflows were interrupted; complete workflow timings are unavailable.
- Query configurations differ between 100K and 1M; their query timings are not a controlled scaling comparison.
- Asia/Hong_Kong is an experimental timezone assumption. Monetary values are hypothetical scenarios, not HKUST financial results.

## Evidence

- Original experiment plan SHA-256: `f4655fbe410f0a97fc58df7ff71f1f817f47f0a1d284dad8c4f64d198bccbe09`
- Final scope record SHA-256: `6c875acb6e799807d2f83dc2de2843b1586b9ab7ef390fd7b6c47c40c315d666`
- Fresh evidence verification completed: 2026-11-02T03:14:22.302960+00:00
- Verification scope: scope-bound run seals and published Gold/Hadoop outputs, manifests, reconciliation, decision, query, storage, and machine reports; runtime checkpoints and operational logs were not rehashed
- Machine-readable run summaries, exact comparison fields, query hashes, and cross-run semantic hashes: `final-results.json`.
