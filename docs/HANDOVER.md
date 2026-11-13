# Submission handover

## Submit these two items

- [Project report PDF](submission/project-report.pdf), with [editable LaTeX source](submission/project-report.tex).
- Repository: https://github.com/nishantharkut-research/IoT-Energy-Data-Pipeline

The submitted scope is nine fixtures plus three clean repetitions each at 100K and 1M source records. The three 5M repetitions are excluded. The proposed additional report-claim publication gate is not part of this submission.

## Portable demonstration on Linux

With Python 3.11+ and Node.js 24 installed:

```bash
cd dashboard/web
npm ci
npm run dev
```

Open http://localhost:5173. The React/Mantine dashboard has nine views, a searchable experiment register, run inspection, source/run selectors, and CSV/JSON exports. `npm run build` creates a static bundle; `npm run preview` serves it locally. The prestart/prebuild step uses Python's standard library to export byte-exact saved summaries. No dataset, SSD or experiment services are needed.

The browser validates the exported summary SHA-256 bindings, original plan/scope bindings, run membership, recorded comparison agreement and delivery equations. Original runtime verification was recorded on 2 November 2026; this checkout does not repeat it. Source-audit figures come from the published Markdown because original audit JSON is absent here. The [demo guide](demo-script.md) provides a six-minute route; the [India note](india-use-case.md) explains the proposed utility-review role and its limits.

## Original sealed-run inspection

Run the original Python viewer first:

```bash
python -m pip install -e ".[dashboard]"
python -m streamlit run dashboard/app.py --server.headless true
```

Choose **Sealed run files** in the sidebar and provide an original finalized run directory. `dashboard/data.py` verifies its manifest seal and all registered artifacts. It rejects missing, incomplete, altered and unreconciled runs. The historical PowerShell launcher remains available on Windows:

```powershell
.\scripts\show_completed_run.ps1 -Python <path-to-python.exe> -RunId watermark-restrictive-r01
```

Original runtime directories are not committed. Preserve `reports/runtime/full-assumed-hkt-20261028-003/`, original replay receipts, source package, canonical snapshot and audit JSON on a reliable storage device. They are required for deeper artifact inspection or source reproduction. Do not delete them merely because the portable viewer works.

## Regenerate the original closure from saved runtime evidence

This command starts no Kafka/Spark/Hadoop workload, but it requires the original files and reads the published artifact set:

```bash
python -m scripts.close_coursework \
  --plan docs/results/final/experiment-plan.json \
  --scope docs/results/final/final-coursework-scope.json \
  --runtime reports/runtime/full-assumed-hkt-20261028-003 \
  --output <separate-review-directory>
```

Use a separate output directory to preserve the submitted closure bytes. `--full-artifact-check` additionally verifies the entire registered artifact set and can take substantially longer. It is unnecessary for opening the portable viewer.

## Rebuild the submission PDF

Install LaTeX and `python -m pip install -e ".[dashboard,report]"`. With Chrome/Chromium available:

```bash
python -m scripts.build_submission_figures
python -m scripts.capture_operator_dashboard
cd docs/submission
latexmk -pdf -interaction=nonstopmode -halt-on-error project-report.tex
```

Screenshots are actual captures of the running React dashboard on port 5173. `figures/dashboard/report-*.png` preserve the full desktop viewport, including navigation. Full-page captures are retained beside them. The report includes nine large landscape captures; longer content remains accessible in the live viewer and full-page PNGs. No synthetic measurements or fabricated finalized runs are used.

## Interpretation checklist

- Source availability and reconciliation refer to different populations.
- Gold recovers received valid records from Bronze, not genuinely unreceived physical readings.
- Independent Spark/Hadoop transformations share canonical preparation.
- The watermark case has incomparable intervals; zero comparable subtotal is not zero total exposure.
- All 1M workflows recovered. Complete workflow times are unavailable.
- SQL uses cached-result workloads, including result serialization and hashing; settings differ by scale.
- The timezone is assumed. Monetary rates are hypothetical. Indian deployment effectiveness was not evaluated.
