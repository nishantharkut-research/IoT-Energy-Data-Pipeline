# Submission verification

13 November 2026. This record concerns the portable presentation and software changes, not new distributed measurements. Exact versions and check counts are in [verification.json](verification.json); report and asset hashes are in [asset-manifest.json](asset-manifest.json).

| Check | Result |
| --- | --- |
| Unit, contract and property checks | 580 passed, 7 skipped |
| Ruff | Passed |
| Repository-independence scan | Passed |
| Git whitespace check | Passed |
| Portable input bindings and layer equations | Passed |
| Eight actual browser views | No page errors or horizontal page overflow |
| Additional viewport widths | 1280 and 720 pixels, no horizontal page overflow |
| Explicit sealed-run mode with missing evidence | Rejected, as required |
| Fresh checkout and separate environment | Dashboard extra installed; all eight views rendered with no runtime dataset |
| PDF | 16 pages, 8 dashboard captures, 2 vector diagrams; no unresolved references or overfull text warnings |
| Independent read-only review | No actionable factual or evidence-handling findings |

Skipped checks cover four Windows-specific rename cases, one mutation fixture whose size condition is not applicable, one duplicate-sheet case that openpyxl cannot construct, and one PySpark-dependent case. Kafka/Spark/Hadoop integration workloads were not rerun.

Two existing failures were reproduced before correction: registration ignored dangling file symlinks, and profiling accepted a workbook symlink. The existing regression tests now pass. Original final-results JSON, scope/plan JSON and published source-audit summary bytes were preserved.

The saved closure records verification of published original artifacts on 2 November 2026. This checkout checks those committed summaries and their bindings. It does not contain or freshly reverify the original runtime trees, full dataset or original audit JSON. A matching summary hash establishes a byte binding, not physical measurement accuracy or adversarial authenticity.

The presentation environment is separate from the original experiment environment. In particular, the PyArrow installed transitively for the current dashboard is not the original dataset extra's pinned range. No original measured timing is attributed to this presentation machine.
