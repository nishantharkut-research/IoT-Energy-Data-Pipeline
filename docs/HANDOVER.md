# Project handover

## Submission documents

- [Project report](course-report.md): problem, data, implementation, findings, and limits.
- [Measured results](results/final/course-results.md): all runs, verification cost, storage, and SQL.
- [Machine-readable evidence](results/final/final-results.json): counts, hashes, timing records, and semantic comparisons.
- [Demonstration](demo-script.md): six-minute sequence using saved results.

The final scope contains nine fixtures and three repetitions each at 100K and
1M events. The 5M runs are excluded because of resource and time constraints.

## Open the dashboard

From the repository root, with the project Python environment active:

```powershell
.\scripts\show_completed_run.ps1
```

To choose a different environment or fixture:

```powershell
.\scripts\show_completed_run.ps1 -Python <path-to-python.exe> -RunId watermark-restrictive-r01
```

The light-mode dashboard validates the complete artifact registry and rejects
incomplete, altered, or unreconciled runs. It reads saved files and starts no
experiment services. Use a fixture for live presentation. Opening a 1M run
requires hashing its much larger artifact set.

Dependencies are in `pyproject.toml`. A fresh environment can install the package
with `python -m pip install -e ".[dashboard,dataset,kafka,dev]"`.
Runtime data is local and excluded from Git.

## Preserve the evidence

The runtime root is `reports/runtime/full-assumed-hkt-20261028-003/`.
The original plan and final scope are in
`reports/launches/full-resumable-hkt-002/experiment-plan.json` and
`final-coursework-scope.json`. The scope binds the original plan by SHA-256 and
excludes the three 5M repetitions. Preserve the canonical snapshot, source
package, sealed runtime folders, source audit, and launch receipts. Portable
summaries do not replace the underlying evidence.

## Regenerate the final report

This verifies scope-bound run seals, published Gold/Hadoop records and
aggregates, and the reports used for the handover. It starts no workloads.

```powershell
python -m scripts.close_coursework `
  --plan reports/launches/full-resumable-hkt-002/experiment-plan.json `
  --scope reports/launches/full-resumable-hkt-002/final-coursework-scope.json `
  --runtime reports/runtime/full-assumed-hkt-20261028-003 `
  --output docs/results/final
```

The `coursework-closure-v1` output records revised scope and recovered timings.
It does not label the original 18-run matrix as complete. The older strict
`course_report` command is for uninterrupted full matrices; use the closure
command above for these results.

Add `--full-artifact-check` to rehash the entire registered artifact set,
including runtime checkpoints and operational logs. That optional audit takes
substantially longer and is separate from the published-evidence check.

## Evidence boundaries

Independent agreement is demonstrated through 1M source records. The restrictive
watermark exposes a candidate omission while Gold remains complete. Monetary
rates are hypothetical, and residual exposure remains unknown. Hong Kong
timezone is an experimental assumption. Complete 1M workflow timings are
unavailable, and query settings differ between scales.
