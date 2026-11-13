"""Generate vector diagrams and report tables from the bound saved results."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from dashboard.submission_data import load_submission_evidence

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/submission/figures"
NAVY = "#18344a"
BLUE = "#eaf2f8"
TEAL = "#e8f3f0"
AMBER = "#fff1dd"


def canvas(height: float):
    fig, ax = plt.subplots(figsize=(10, height))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, height)
    ax.axis("off")
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99)
    return fig, ax


def box(ax, x, y, w, h, text, fill=BLUE):
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.03,rounding_size=0.05",
        linewidth=1.25,
        edgecolor=NAVY,
        facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(
        x, y, text, ha="center", va="center", fontsize=13, color=NAVY, linespacing=1.35
    )


def arrow(ax, start, end, points=None):
    if points:
        for a, b in zip([start] + points, points + [end], strict=True):
            if b == end:
                arrow(ax, a, b)
            else:
                ax.plot([a[0], b[0]], [a[1], b[1]], color=NAVY, lw=1.6)
    else:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=18,
                linewidth=1.6,
                color=NAVY,
                shrinkA=0,
                shrinkB=0,
            )
        )


def save(fig, name):
    for extension in ("pdf", "svg"):
        target = OUT / f"{name}.{extension}"
        fig.savefig(target, bbox_inches="tight", pad_inches=0.07)
        if extension == "svg":
            target.write_text(
                "\n".join(line.rstrip() for line in target.read_text().splitlines())
                + "\n",
                encoding="utf-8",
            )
    plt.close(fig)


def diagrams():
    fig, ax = canvas(8.2)
    box(ax, 5, 7.7, 4.5, 0.65, "HKUST workbooks + Brick metadata", "#f1f3f5")
    box(
        ax,
        5,
        6.5,
        4.5,
        0.85,
        "Register, audit and canonicalize\nStable row identity · exact decimal values",
    )
    box(
        ax,
        5,
        5.15,
        4.5,
        0.85,
        "Canonical snapshot\nParquet + NDJSON + source-quality ledger",
    )
    arrow(ax, (5, 7.35), (5, 6.95))
    arrow(ax, (5, 6.05), (5, 5.6))
    box(
        ax,
        2.4,
        3.8,
        4.1,
        0.85,
        "Deterministic Kafka replay\nSchedules · acknowledgements · terminals",
    )
    box(ax, 7.6, 3.8, 4.1, 0.85, "HDFS input\nCanonical NDJSON", TEAL)
    arrow(ax, (3.4, 4.7), (2.4, 4.25))
    arrow(ax, (6.6, 4.7), (7.6, 4.25))
    box(
        ax,
        2.4,
        2.45,
        4.1,
        0.85,
        "Spark Structured Streaming\nBronze · Silver · quarantine",
    )
    box(
        ax,
        7.6,
        2.45,
        4.1,
        0.85,
        "Independent Hadoop Streaming\nSource records + exact aggregates",
        TEAL,
    )
    arrow(ax, (2.4, 3.35), (2.4, 2.9))
    arrow(ax, (7.6, 3.35), (7.6, 2.9))
    box(
        ax,
        2.4,
        1.15,
        4.1,
        0.75,
        "Completion checks → batch Gold\nRebuild exact source events from Bronze",
    )
    arrow(ax, (2.4, 2.0), (2.4, 1.55))
    box(
        ax,
        7.6,
        1.15,
        4.1,
        0.75,
        "Reconciliation + saved reports\nCompare Gold with Hadoop outputs",
        TEAL,
    )
    arrow(ax, (4.48, 1.15), (5.5, 1.15))
    arrow(ax, (7.6, 2.0), (7.6, 1.55))
    ax.text(
        5,
        0.25,
        "Read-only dashboard: delivery accounting, "
        "comparison coverage and recorded costs",
        ha="center",
        color=NAVY,
        fontsize=12.5,
    )
    save(fig, "architecture")

    fig, ax = canvas(6.8)
    box(
        ax, 2.4, 6.1, 3.9, 0.8, "Kafka data deliveries\nBronze preserves every delivery"
    )
    box(
        ax,
        7.5,
        6.1,
        3.9,
        0.8,
        "Acknowledgements + terminal offsets\nReplay completion evidence",
        TEAL,
    )
    box(
        ax,
        2.4,
        4.6,
        3.9,
        0.85,
        "Parse and validate\nSource identity · event time · value",
    )
    arrow(ax, (2.4, 5.65), (2.4, 5.05))
    box(
        ax,
        7.5,
        4.6,
        3.9,
        0.85,
        "Exact batch Gold\nDeduplicate valid source IDs\nfrom Bronze",
        TEAL,
    )
    arrow(ax, (7.5, 5.65), (7.5, 5.05))
    arrow(ax, (4.4, 6.1), (6.5, 5.05))
    box(
        ax, 2.4, 2.95, 3.9, 0.85, "Operational Silver\nBounded event-time deduplication"
    )
    arrow(ax, (2.4, 4.15), (2.4, 3.4))
    box(
        ax,
        7.5,
        2.95,
        3.9,
        0.85,
        "Invalid deliveries → quarantine\nKeep payload and rejection category",
        AMBER,
    )
    arrow(ax, (4.4, 4.6), (5.5, 2.95), [(4.95, 4.6), (4.95, 2.95)])
    box(
        ax,
        5,
        1.1,
        5.4,
        1.0,
        "Finalization checks\nDelivery conservation · partition completion\n"
        "Gold/Hadoop agreement · artifact bindings",
        TEAL,
    )
    arrow(ax, (7.5, 2.5), (6.5, 1.65))
    arrow(ax, (2.4, 2.5), (3.5, 1.65))
    arrow(ax, (9.5, 4.6), (7.75, 1.1), [(9.85, 4.6), (9.85, 1.1)])
    ax.text(
        5,
        0.2,
        "A failed finalization check blocks a sealed run. "
        "Late valid records are not quarantine.",
        ha="center",
        color=NAVY,
        fontsize=12,
    )
    save(fig, "finalization")


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
    diagrams()
    tables()
