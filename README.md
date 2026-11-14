# MeterTrace

Smart-Meter Data Verification and Review

ABV-IIITM IoT Big Data Management coursework using public HKUST smart-meter telemetry.

The pipeline preserves Kafka deliveries, maintains a bounded streaming candidate, rebuilds exact finalized records, and checks them against independently implemented Hadoop computations. The submission includes a project report and a portable dashboard backed by saved experiment evidence.

**[Project report · PDF](docs/submission/project-report.pdf)** · **[Report source](docs/submission/project-report.tex)** · **[Measured results](docs/results/final/course-results.md)** · **[Demonstration guide](docs/demo-script.md)**

## Completed evaluation

| Experiment | Completed scope |
| --- | --- |
| Correctness | Clean, duplicate, delayed, malformed and combined delivery fixtures |
| Recovery | Uninterrupted versus interrupted-and-resumed fixture |
| Watermark | Retaining versus restrictive configuration |
| Scale | Three clean repetitions each at 100K and 1M source records |
| Storage and SQL | NDJSON/Parquet sizes and five queries, with three timing repetitions per query |

All **15 in-scope runs** finalized and passed the recorded exact source-record and aggregate comparisons. The three originally planned 5M runs are excluded because of resource and time constraints. This submission uses those existing results and starts no new experiment workloads.

The combined fixture accounts for **432 deliveries: 144 unique valid records, 144 duplicates and 144 quarantined deliveries**. In the restrictive watermark fixture, Silver contains **143** records while Gold and Hadoop retain **144**. Interrupted and uninterrupted fixture outputs match byte for byte for four semantic artifacts.

Median verification cost was **13.88 minutes at 100K** and **165.30 minutes at 1M**. These figures cover Gold, layer audit, Hadoop and reconciliation. They are not complete workflow durations. All 1M workflows recovered from interruption, and complete workflow timing is unavailable.

## Open the portable dashboard

The **Meter review demo** workspace offers three configured cases: late receipt, duplicate delivery and a source gap. Select a case, compare readings, add an analyst note, mark it reviewed and export the decision. It uses clearly labelled sample data, separately from measured experiment results. Decisions stay in browser memory until reset or refresh; export JSON to retain a copy.

From a fresh checkout, install **Python 3.11+ and Node.js 24**, then run:

```bash
git clone https://github.com/nishantharkut-research/IoT-Energy-Data-Pipeline.git
cd IoT-Energy-Data-Pipeline/dashboard/web
npm ci
npm run dev
```

Open **http://localhost:5173**. The React/TypeScript interface uses Mantine components, Recharts and Lucide icons with a consistent light theme. Its prestart command exports the original saved evidence with Python's standard library; no Python packages are needed for this viewer. If your platform names Python `python` instead of `python3`, run `python -m scripts.export_dashboard_evidence` from the repository root, then `npx vite --host 127.0.0.1 --port 5173` from `dashboard/web`.

The nine views cover overview/run register, source audit, delivery inspection, fault comparison, independent verification, watermark review, recovery, storage/SQL and the India use case. Run selection, search, filters, pagination, evidence dialogs and CSV/JSON exports work on the saved results.

![Dashboard overview](docs/submission/figures/dashboard/report-01-overview.png)

This viewer needs no dataset, external SSD, Kafka, Spark or Hadoop service. It checks SHA-256 bindings of the committed summary inputs, original scope/plan bindings and delivery equations. It **does not reverify original runtime artifacts** or connect to live meters. The original verification date and its scope remain visible. Build a local static bundle with `npm run build`; serve it with `npm run preview`.

The original strict sealed-run viewer remains separate:

```bash
# From the repository root, in a Python virtual environment:
python -m pip install -e ".[dashboard]"
python -m streamlit run dashboard/app.py --server.headless true
```

Choose **Sealed run files** and supply an original local finalized directory. It rejects missing, incomplete or altered registered evidence. Original sealed directories are excluded from Git and must be retained separately.

## Architecture

```mermaid
flowchart TD
    Source[HKUST Excel telemetry and Brick metadata] --> Prepare[Register, audit and canonicalize]
    Prepare --> Snapshot[Canonical Parquet and NDJSON]
    Prepare --> Quality[Source-quality ledger]
    Snapshot --> Replay[Deterministic Kafka replay]
    Replay --> Bronze[Bronze: every data delivery]
    Bronze --> Silver[Silver: watermark-bounded candidate]
    Bronze --> Quarantine[Quarantine: invalid deliveries]
    Bronze --> Completion{Replay completion and layer accounting}
    Completion --> Gold[Gold: exact batch rebuild from Bronze]
    Snapshot --> HDFS[HDFS canonical NDJSON]
    HDFS --> Hadoop[Independent Hadoop source records and aggregates]
    Gold --> Compare{Exact reconciliation}
    Hadoop --> Compare
    Silver --> Impact[Consumption comparison with explicit coverage]
    Compare --> Impact
    Impact --> Reports[SQL, storage and bound reports]
    Compare --> Seal[Validate and seal completed run]
    Reports --> Seal
    Seal --> Views[Read-only evidence views]
```

- **Bronze** archives every data delivery. Terminal partition controls are separate.
- **Silver** provides bounded operational deduplication. A valid late record is not quarantine.
- **Gold** reconstructs valid source events by exact source identity after completion. It does not inherit Silver's watermark omissions.
- **Hadoop** reads canonical NDJSON and imports no Spark transformations. Both implementations share canonical preparation.
- **Finalization** checks delivery conservation, partition termination, exact comparison agreement and artifact bindings.

## Data and interpretation

The dataset is deposited on [Dryad](https://doi.org/10.5061/dryad.k3j9kd5h6) and described in [Scientific Data](https://doi.org/10.1038/s41597-024-04106-1). The [published source audit](docs/results/source-audit-2026-10-27.md) records 63,273,828 resampled rows: 44,238,638 finite numeric readings and 19,035,190 missing numeric cells. This is **69.916% numeric-cell availability over published rows**, not an outage rate or complete temporal-coverage measurement.

Source identifiers use dataset version, variant, relative path, worksheet and physical row. Original numeric/timestamp text and exact scaled values are retained. Raw and resampled variants are not silently combined. Cumulative-kWh semantics follow recorded source evidence. Asia/Hong_Kong is an explicit experimental timezone assumption, not author-confirmed metadata.

The scale runs select source-ID-sorted prefixes from numeric canonical data. They are not continuous meter-day samples. Exact agreement applies to these selected inputs; it does not establish physical meter accuracy or completeness of the original source.

The restrictive watermark changes two consumption periods that have incomparable supports. The comparable-interval discrepancy is zero; total energy error and residual financial exposure remain unknown. Rates of 0.5, 1.0 and 2.0 currency units/kWh are hypothetical scenarios. No actual bill, Indian tariff or demonstrated saving is claimed.

The Indian utility connection is a proposed DISCOM review of metering-provider outputs: distinguish unavailable source readings, delivery exceptions and computation differences. [The use-case note](docs/india-use-case.md) maps Indian source evidence to the mechanisms and existing results. Commercial HES/MDM/VEE capabilities are acknowledged. Evaluation remains HKUST historical telemetry and controlled delivery faults. The coursework contribution is the implemented integration and its evidence, not a new streaming algorithm or a comparison proving superiority over commercial MDMS.

## Evidence and repository layout

| Path | Contents |
| --- | --- |
| `src/iot_energy_pipeline/` | Registration, canonicalization, replay, reconciliation, reporting and orchestration |
| `jobs/spark/` | Streaming layers, exact finalization, audits and benchmarks |
| `jobs/hadoop/` | Independent mapper/reducer and source-record computation |
| `schemas/`, `configs/`, `queries/` | Contracts, declared experiment settings and SQL |
| `dashboard/web/` | React/Mantine saved-evidence review workspace |
| `dashboard/*.py` | Saved-summary validation and original strict sealed-run viewer |
| `docs/results/final/` | Saved closure JSON, scope, original plan, tables and HTML report |
| `docs/results/submission/` | Input bindings and submission verification records |
| `docs/submission/` | LaTeX report, PDF, screenshots and vector diagrams |
| `tests/` | Unit, property, contract and integration checks |

The source-audit numbers in this checkout come from the committed audit Markdown. The original audit JSON, dataset, complete runtime trees and service volumes are not versioned. A summary hash establishes a byte binding, not authenticity of the original measurement or a fresh full-runtime audit.

## Check the code and rebuild the report

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/unit/test_submission_data.py tests/contract/test_final_evidence_bindings.py -q
```

For the broader non-distributed suite, install the dataset extras in a compatible Python environment (Python 3.11/3.12 for the original PyArrow range), then run `python -m pytest tests/unit tests/contract tests/property -q`. Docker integration checks are separate; do not interpret the portable viewer check as a new distributed experiment.

The report is built with LaTeX. To regenerate figures and actual browser captures, install the report extra with `python -m pip install -e ".[dashboard,report]"`, with Chrome/Chromium available:

```bash
python -m scripts.build_submission_figures
# Keep the dashboard running in another terminal.
python -m scripts.capture_operator_dashboard
cd docs/submission
latexmk -pdf -interaction=nonstopmode -halt-on-error project-report.tex
```

Frontend checks:

```bash
cd dashboard/web
npm ci
npm run check
```

See [the handover guide](docs/HANDOVER.md) for original artifact verification and the distinction between summary review and full reproduction. Historical execution documents are retained for provenance; the final scope and report take precedence over earlier planned work.
