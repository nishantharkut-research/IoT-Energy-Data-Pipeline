# Reproducibility

Reproduction is an immutable sequence. A later stage refuses to overwrite an
earlier result and binds the exact hashes it consumed.

1. Verify the downloaded Dryad wrapper and its inner archive without extracting
   it implicitly.
2. Extract to an internal, reliable local path and register either `raw` or
   `clean` as one source variant.
3. Profile the registered files and audit them against
   `configs/hkust-v5-source-layout.json`.
4. Review a `canonicalization-rules-v1` document. Its timezone, unit,
   measurement kind, decimal scale, and evidence are explicit; its source
   layout file is hash-bound.
5. Build canonical NDJSON and Zstandard Parquet. NDJSON is the portable oracle
   input; Parquet is analytical storage.
6. Capture `machine-metadata-v1` and compile `experiment-plan-v1`. Compilation
   performs no workload execution.
7. On the designated machine only, use the explicitly gated executor. Every
   run receives a unique topic, schedule, receipt, terminal records, layer
   audit, Gold output, Hadoop outputs, reconciliation report, decision report,
   query benchmark, storage benchmark, and final seal.
8. For the completed 100K/1M coursework scope, use `scripts.close_coursework`
   as documented in [the handover guide](HANDOVER.md). It checks published
   evidence hashes and semantic equivalence, preserves recovered timing limits,
   and records the exclusion of 5M. The older `experiment-results-v1` generator
   remains available for uninterrupted full matrices.

Production-size replay artifacts use closed version-2 contracts. Canonical
selection is streamed, delivery ordering is externally sorted through a local
SQLite work file, and the deterministic schedule is written as NDJSON. Kafka
acknowledgements are appended to a separate NDJSON ledger; the small receipt
stores its count, byte size, and SHA-256 rather than embedding millions of
records. Resume accepts only a byte- and record-validated schedule prefix.
Fixture-only paths retain the in-memory version-1 representation for compact
tests, but do not define the production scale architecture.

Canonicalization, telemetry cadence audit, and Spark-Hadoop reconciliation
consume rows incrementally or use disk-backed ordering. Decision comparison
also orders events on disk, but its affected-period and flagged-record output
lists grow with the reported population; arbitrary quality failures can make
those reports large.

The normal CI workflow runs only unit, property, and contract tests. Distributed
fixture acceptance is executed separately and requires actual Kafka, Spark,
HDFS, and YARN evidence. Local integration fixtures do not replace this check.
The 1M and larger workloads are never run live
during the course demonstration.

Absolute source paths are intentionally absent from persisted semantic
identities. Runtime data remains ignored by Git and must stay under the
repository runtime directory used by Docker Compose.

File integrity descriptors hash stored bytes. Protocol identifiers such as
`replay_manifest_hash` and the snapshot's `dataset_manifest_sha256` fingerprint
canonical JSON content. Their definitions differ from checksums of the
pretty-printed manifest files; final seals retain separate file hashes.

## Designated SSD layout on Windows

The audited working tree is copied without changing source bytes to
`<SSD>/IoTBDM/IoT-Energy-Data-Pipeline`. Its execution manifest records each file's
SHA-256. The existing Python dependencies remain on C:; `PYTHONPATH` selects the
audited SSD source explicitly, and the runtime audit checks that import path.

Use the optional Compose storage file with a fresh service-data directory:

```powershell
$env:COMPOSE_FILE = 'compose.yaml;compose.storage.yaml'
$env:PIPELINE_SERVICE_DATA_DIR = '<repository>/reports/service-data/<attempt>'
$env:PYTHONPATH = '<repository>/src;<repository>'
```

This places Kafka persistence, HDFS data, and Spark spill on the SSD. YARN scratch
and Hadoop daemon logs retain Linux storage: the actual Docker bind-mount probe
returned mode `777` after `chmod`, and YARN rejected its cache directory. A WSL
metadata mount did not preserve those modes through this Docker configuration.
[Microsoft's WSL permissions guide](https://learn.microsoft.com/en-us/windows/wsl/file-permissions)
explains the distinction between Windows permissions and Linux metadata.

The source snapshot and retained run directories also use the SSD. YARN's
temporary shuffle/localization space still consumes internal-drive capacity;
check both drives before each larger size. Attach the SSD before Docker starts,
verify host/container access, and keep the disk connected until services stop.
Full snapshot construction has a payload-only peak lower bound of 107.45 GB;
Parquet, SQLite overhead, and experiment artifacts require additional space.
