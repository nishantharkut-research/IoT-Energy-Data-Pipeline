# Six-minute demonstration

Use saved results. Start `scripts/show_completed_run.ps1`; the default is the
small combined-fault fixture. Open the generated results report alongside it.
Let initial integrity verification finish before presenting. No experiment
services or large live workloads are needed.

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:45 | README architecture | A completed job alone does not establish delivery completeness. We preserve deliveries and independently check the final result. |
| 0:45–1:30 | Run provenance | Public HKUST telemetry, stable physical-row identity, exact decimals, and separate source variants. Hong Kong timezone is an experimental assumption. |
| 1:30–2:30 | Combined fixture: counts and fault disposition | 432 data deliveries: 144 unique valid records, 144 duplicates, and 144 quarantined deliveries. Terminal control records are separate. |
| 2:30–3:20 | Reconciliation | Gold rebuilds from Bronze; Hadoop independently reads canonical NDJSON. Both record and aggregate comparisons have zero errors. |
| 3:20–4:20 | Restrictive watermark fixture | Change the run directory to `watermark-restrictive-r01`. Silver has 143 records; Gold and Hadoop have 144. Two consumption periods are incomparable. Zero discrepancy on comparable periods is not zero total energy error. |
| 4:20–5:20 | Generated verification, storage, and SQL results | Three repetitions each at 100K and 1M. Show timing ranges, compressed storage ratios, and five queries. Full 1M workflow timings are unavailable; query settings differ. |
| 5:20–6:00 | Recovery and limits | Interrupted recovery reproduces four semantic outputs. 5M is excluded. Financial scenarios are hypothetical, and residual exposure is unknown. |

The supported claim is delivery accounting, recovery from Bronze, and
independent exact verification through 1M source records. The results do not
demonstrate live deployment, a new algorithm, or actual billing savings.
