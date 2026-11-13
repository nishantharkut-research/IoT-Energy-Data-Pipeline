"""Record byte bindings for the existing bounded submission inputs; starts no jobs."""

from __future__ import annotations

import json
from pathlib import Path

from dashboard.submission_data import INPUTS, sha256


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    index = {
        "schema_version": "submission-evidence-index-v1",
        "purpose": (
            "Portable saved-results presentation; not a new "
            "experiment or runtime verification"
        ),
        "inputs": {
            name: {
                "path": relative,
                "byte_size": (root / relative).stat().st_size,
                "sha256": sha256(root / relative),
            }
            for name, relative in INPUTS.items()
        },
        "source_audit_basis": (
            "Published audit Markdown; original audit JSON is not in this checkout"
        ),
        "runtime_basis": (
            "Recorded verification in closure JSON; original "
            "runtime files are not reverified here"
        ),
    }
    output = root / "docs/results/submission/evidence-index.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
