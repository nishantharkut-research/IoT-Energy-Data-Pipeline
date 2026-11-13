"""Export byte-exact validated summaries for the static React dashboard."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from dashboard.submission_data import INPUTS, load_submission_evidence

FILENAMES = {
    "results": "final-results.json",
    "scope": "final-scope.json",
    "plan": "experiment-plan.json",
    "source_audit": "source-audit.md",
}


def export_evidence(root: Path, output: Path) -> None:
    evidence = load_submission_evidence(root)
    if output.is_symlink():
        raise ValueError("refusing a symbolic-link export directory")
    output.mkdir(parents=True, exist_ok=True)
    entries = {}
    for name, relative in INPUTS.items():
        target = output / FILENAMES[name]
        if target.is_symlink():
            raise ValueError("refusing a symbolic-link export file")
        shutil.copyfile(root / relative, target)
        entries[name] = {
            **evidence["index"]["inputs"][name],
            "file": FILENAMES[name],
        }
    report = root / "docs/submission/project-report.pdf"
    manifest = {
        "schema_version": "web-evidence-v1",
        "inputs": entries,
        "runtime_reverified": False,
        "report_available": report.is_file(),
        "basis": "Saved results; original runtime artifacts are not reverified here",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if report.is_file():
        shutil.copyfile(report, output.parent / "project-report.pdf")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=root / "dashboard/web/public/evidence"
    )
    args = parser.parse_args()
    export_evidence(root, args.output)
    print("Exported validated saved evidence. No workload started.")


if __name__ == "__main__":
    main()
