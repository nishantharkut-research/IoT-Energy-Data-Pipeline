# Six-minute saved-results demonstration

Start the dashboard with `python -m streamlit run dashboard/app.py`. Keep the default **Submission results** mode. No experiment services, attached dataset or large workload are needed. Open the [report PDF](submission/project-report.pdf) alongside it.

| Time | Dashboard view | Explain |
| --- | --- | --- |
| 0:00–0:40 | Overview | We account for deliveries and independently check finalized results. Fifteen saved runs cover correctness, recovery, watermark behaviour and two scales. |
| 0:40–1:20 | Source quality | The published resampled source has 63.27M rows and 19.04M missing numeric cells. Numeric-cell availability is not temporal coverage. Selected-run agreement answers a different question. |
| 1:20–2:00 | Delivery accounting | The default combined fixture has 432 Bronze deliveries: 288 valid and 144 quarantine. The 288 valid deliveries split into 144 Silver and 144 duplicates. Terminals are separate. |
| 2:00–2:30 | Fault handling | Five controlled schedules produce the same finalized semantic result. Injected delivery faults are not observed utility-network fault rates. |
| 2:30–3:15 | Independent verification | Spark and independent Hadoop programs agree on 23 source fields and 10 aggregate fields. Both share canonical input, so this is not physical truth verification. |
| 3:15–4:10 | Watermark & consumption | Restrictive Silver has 143 records; Gold/Hadoop have 144. Two consumption periods are incomparable. The comparable subtotal is zero and total exposure is unknown. |
| 4:10–4:50 | Recovery | Four interrupted/uninterrupted output-hash pairs match. The 1M runs also recovered; full workflow durations are unavailable. |
| 4:50–6:00 | Storage & SQL | Show measured verification costs, compressed storage ratios and five query workloads. Explain the cost scope, cached-result timing and different query configurations. Close with the report and GitHub link. |

If asked about novelty, explain the engineering integration: exact source reconstruction after bounded streaming, delivery conservation, independent exact comparison and inspectable evidence. Do not claim a new streaming algorithm, actual billing savings or an Indian field deployment.

If asked to inspect original artifacts, select **Sealed run files** only when the original finalized directory is available. The default viewer checks saved summary bindings; it does not silently recreate or rehash missing runtime evidence.
