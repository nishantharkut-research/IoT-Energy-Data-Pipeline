"""Generate report tables from bound saved results.

The two process figures are maintained as editable SVG source files beside their
PDF report exports. This script writes only the result-derived table fragments.
"""

from __future__ import annotations

from pathlib import Path

from dashboard.submission_data import load_submission_evidence

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/submission/figures"


def tables():
    evidence = load_submission_evidence(ROOT)
    results = evidence["results"]
    lines = []
    for row in results["runs"][:9]:
        c = row["layer_counts"]
        label = (
            row["run_id"]
            .replace("correctness-", "")
            .replace("-r01", "")
            .replace("_", r"\_")
        )
        lines.append(
            f"{label} & {c['bronze_deliveries']:,} & {c['silver_deliveries']:,} & "
            f"{c['duplicate_valid_deliveries']:,} & {c['late_valid_deliveries']:,} & "
            f"{c['quarantine_deliveries']:,} & {row['source_records']:,} " + r"\\"
        )
    (OUT / "fixture-table.tex").write_text("\n".join(lines) + "\n")
    lines = []
    for row in results["performance_summary"]:
        t, b = row["verification_seconds"], row["verification_bytes"]
        lines.append(
            f"{row['event_count']:,} & {t['minimum'] / 60:.2f} & "
            f"{t['median'] / 60:.2f} & "
            f"{t['maximum'] / 60:.2f} & {b['median'] / 1e6:.2f} " + r"\\"
        )
    (OUT / "performance-table.tex").write_text("\n".join(lines) + "\n")
    lines = []
    for scale in (100000, 1000000):
        row = next(r for r in results["runs"] if r["event_count"] == scale)
        f = row["storage"]["formats"]
        lines.append(
            f"{scale:,} & {f['ndjson']['byte_size'] / 1e6:.2f} & "
            f"{f['parquet_zstd_unpartitioned']['relative_to_ndjson']:.4f} & "
            f"{f['parquet_zstd_partitioned']['relative_to_ndjson']:.4f} " + r"\\"
        )
    (OUT / "storage-table.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    tables()
