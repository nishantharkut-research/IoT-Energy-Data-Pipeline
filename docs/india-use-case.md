# Indian smart-meter data-review use case

The intended user is a DISCOM analyst reviewing data or reports supplied through an AMISP. The project provides a reproducible way to account for received readings, explain processing exclusions, rebuild a finalized result, and compare that result with a separately implemented computation.

The evaluated system uses HKUST campus telemetry and controlled replay. It has not been connected to an Indian utility. The India connection motivates a proposed application of the implemented mechanisms.

## Evidence and scope

| Source | Relevant observation | Scope |
| --- | --- | --- |
| [CSIS original utility survey, 30 October 2026](https://www.csis.org/analysis/meters-machine-learning-building-ai-ready-utilities-india) | Communication failures and data-integration limitations can constrain the use of meter data. | TNPDCL and Tata Power-operated Odisha utilities; not a national prevalence estimate. |
| [MSEDCL AMISP procurement, 19 September 2022](https://www.mahadiscom.in/supplier/wp-content/uploads/2022/09/FILE_MMD_T-NSC-06_0922_version_1_1663594929641-Package-1.pdf), §2.4.4, PDF p. 185 | Original received raw data, VEE data and edit trails are already required. | One procurement specification; not proof of this prototype's compliance. |
| [CAG Tripura report, 2025](https://cag.gov.in/uploads/download_audit_report/2025/6--Chapter-4-069ccbc5e407049.02992125.pdf), printed p. 144 | Historical communication and missing management-reporting problems limited project performance assessment. | Observations about a particular project in 2018–2021; not a current nationwide failure rate. |

These sources justify examining whether usable, traceable data reaches an analyst. They do not establish that our synthetic faults reproduce the frequency or distribution of Indian network failures.

## How the implementation helps

| Review question | Mechanism | Existing result |
| --- | --- | --- |
| Was the source already incomplete? | Registration, profiling and a separate quality ledger. | 19,035,190 missing numeric cells in 63,273,828 published resampled HKUST rows. This denominator is published rows, not an expected meter schedule. |
| Did retries or lateness change the operational result? | Bronze retains deliveries; Silver is bounded; Gold rebuilds received valid source identities. | Combined fixture: 432 deliveries accounted for. Restrictive case: Silver 143; Gold/Hadoop 144. |
| Is the final computation internally consistent? | Independent Hadoop source/aggregate implementation compared field by field with Spark Gold. | All 15 saved runs agree on declared exact fields. Both engines share canonical preparation. |
| Can a zero discrepancy be relied on? | Match consumption supports and retain incomparable periods explicitly. | Comparable subtotal zero, two incomparable periods, total exposure unknown. |
| Does recovery change the finalized answer? | Saved receipts/checkpoints and semantic output comparison. | Four fixture artifact pairs match between interrupted and uninterrupted executions. |

Gold can recover a received valid event excluded by Silver. It cannot recreate a physical reading that never reached the system. The proposed analyst can investigate processing completeness without confusing it with physical measurement accuracy or source availability.

## Position alongside existing systems

Commercial MDM systems already provide validation, estimation and editing, raw retention, quality monitoring and audit trails. The coursework contribution is an inspectable integration of delivery accounting, exact batch reconstruction, independent computation and explicit comparison coverage. We have not demonstrated vendor superiority or a first-of-its-kind algorithm.

A possible deployment places a review layer alongside HES/MDM, using authorized exports. Adoption would require actual data adapters, verified meter/register semantics, timezone and identifier contracts, agreed review rules, security and access design, representative fault histories, and field evaluation. Those are future work, not completed project features.

No actual billing loss, rupee saving, prepaid-balance protection, physical-meter repair or statutory compliance is claimed. The normalized tariff rates in the experiment are hypothetical currency units, not Indian tariffs.
