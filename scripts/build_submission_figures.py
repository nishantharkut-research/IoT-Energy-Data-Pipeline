"""Generate vector diagrams and report tables from the bound saved results."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

from dashboard.submission_data import load_submission_evidence

matplotlib.rcParams["svg.hashsalt"] = "iot-energy-pipeline-report"

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


def draw_icon(ax, name, x, y, color=NAVY):
    """Draw small, consistent line icons inside the diagram cards."""
    ax.add_patch(Circle((x, y), 0.28, facecolor="white", edgecolor="#c5d3df", lw=1.0, zorder=4))
    lw = 1.45
    if name in {"file", "ledger", "stack"}:
        for offset in ([0] if name != "stack" else [-0.09, 0, 0.09]):
            ax.add_patch(Rectangle((x - 0.13 + offset, y - 0.16 + offset), 0.26, 0.32,
                                   fill=False, edgecolor=color, linewidth=lw, zorder=5))
        if name != "file":
            for row in (-0.07, 0, 0.07):
                ax.plot([x - 0.08, x + 0.08], [y + row, y + row], color=color, lw=lw, zorder=6)
    elif name in {"stream", "nodes", "spark"}:
        points = [(-0.13, -0.1), (0.12, 0), (-0.13, 0.12)]
        if name == "spark":
            points = [(-0.13, 0), (0, -0.13), (0.13, 0), (0, 0.13)]
        if name == "nodes":
            points = [(-0.13, 0.11), (0, -0.12), (0.13, 0.11)]
        for a, b in zip(points, points[1:] + points[:1]):
            ax.plot([x + a[0], x + b[0]], [y + a[1], y + b[1]], color=color, lw=lw, zorder=5)
        for dx, dy in points:
            ax.add_patch(Circle((x + dx, y + dy), 0.045, facecolor="white", edgecolor=color, lw=lw, zorder=6))
    elif name in {"database", "archive"}:
        ax.add_patch(Ellipse((x, y + 0.12), 0.28, 0.1, fill=False, edgecolor=color, lw=lw, zorder=5))
        ax.plot([x - 0.14, x - 0.14], [y + 0.12, y - 0.12], color=color, lw=lw, zorder=5)
        ax.plot([x + 0.14, x + 0.14], [y + 0.12, y - 0.12], color=color, lw=lw, zorder=5)
        ax.add_patch(Ellipse((x, y - 0.12), 0.28, 0.1, fill=False, edgecolor=color, lw=lw, zorder=5))
    elif name in {"check", "shield"}:
        if name == "shield":
            ax.add_patch(Polygon([(x - 0.15, y + 0.14), (x + 0.15, y + 0.14),
                                  (x + 0.12, y - 0.04), (x, y - 0.17),
                                  (x - 0.12, y - 0.04)], closed=True,
                                 fill=False, edgecolor=color, linewidth=lw, zorder=5))
        else:
            ax.add_patch(Circle((x, y), 0.16, fill=False, edgecolor=color, lw=lw, zorder=5))
        ax.plot([x - 0.08, x - 0.02, x + 0.1], [y, y - 0.07, y + 0.08], color=color, lw=1.8, zorder=6)
    elif name in {"clock", "window"}:
        ax.add_patch(Circle((x, y), 0.16, fill=False, edgecolor=color, lw=lw, zorder=5))
        ax.plot([x, x, x + 0.08], [y + 0.1, y, y - 0.04], color=color, lw=lw, zorder=6)
    elif name in {"warning", "funnel"}:
        ax.add_patch(Polygon([(x, y + 0.16), (x + 0.16, y - 0.13), (x - 0.16, y - 0.13)],
                             closed=True, fill=False, edgecolor=color, linewidth=lw, zorder=5))
        if name == "warning":
            ax.plot([x, x], [y + 0.05, y - 0.04], color=color, lw=1.8, zorder=6)
            ax.add_patch(Circle((x, y - 0.09), 0.015, facecolor=color, edgecolor=color, zorder=6))
        else:
            ax.plot([x - 0.1, x + 0.1], [y + 0.03, y + 0.03], color=color, lw=lw, zorder=6)
            ax.plot([x - 0.06, x + 0.06], [y - 0.04, y - 0.04], color=color, lw=lw, zorder=6)
    elif name == "dashboard":
        for dx in (-0.08, 0.08):
            for dy in (-0.08, 0.08):
                ax.add_patch(Rectangle((x + dx - 0.055, y + dy - 0.055), 0.11, 0.11,
                                       fill=False, edgecolor=color, linewidth=lw, zorder=5))


def box(ax, x, y, w, h, text, fill=BLUE, icon=None):
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
    if icon:
        icon_x = x - w / 2 + 0.4
        draw_icon(ax, icon, icon_x, y)
        text_x = x - w / 2 + 0.82
        alignment = "left"
    else:
        text_x = x
        alignment = "center"
    ax.text(
        text_x,
        y,
        text,
        ha=alignment,
        va="center",
        fontsize=14.5,
        color=NAVY,
        linespacing=1.35,
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
        fig.savefig(
            target,
            bbox_inches="tight",
            pad_inches=0.07,
            metadata={"Date": None}
            if extension == "svg"
            else {"CreationDate": None, "ModDate": None},
        )
        if extension == "svg":
            target.write_text(
                "\n".join(line.rstrip() for line in target.read_text().splitlines())
                + "\n",
                encoding="utf-8",
            )
    plt.close(fig)


def diagrams():
    fig, ax = canvas(8.2)
    box(ax, 5, 7.7, 4.5, 0.78, "HKUST workbooks\nBrick metadata", "#f1f3f5", "file")
    box(
        ax,
        5,
        6.5,
        4.5,
        0.85,
        "Register, audit and canonicalize\nStable row identity\nExact decimal values",
        icon="ledger",
    )
    box(
        ax,
        5,
        5.15,
        4.5,
        0.85,
        "Canonical snapshot\nParquet + NDJSON\nSource-quality ledger",
        icon="stack",
    )
    arrow(ax, (5, 7.35), (5, 6.95))
    arrow(ax, (5, 6.05), (5, 5.6))
    box(
        ax,
        2.4,
        3.8,
        4.1,
        0.85,
        "Deterministic Kafka replay\n"
        "Scheduled delivery + receipts\nTerminal partition records",
        icon="stream",
    )
    box(ax, 7.6, 3.8, 4.1, 0.85, "HDFS input\nCanonical NDJSON", TEAL, "database")
    arrow(ax, (3.4, 4.7), (2.4, 4.25))
    arrow(ax, (6.6, 4.7), (7.6, 4.25))
    box(
        ax,
        2.4,
        2.45,
        4.1,
        0.85,
        "Spark Structured Streaming\nBronze · Silver · quarantine",
        icon="spark",
    )
    box(
        ax,
        7.6,
        2.45,
        4.1,
        0.85,
        "Independent Hadoop job\nSource records + aggregates",
        TEAL,
        "nodes",
    )
    arrow(ax, (2.4, 3.35), (2.4, 2.9))
    arrow(ax, (7.6, 3.35), (7.6, 2.9))
    box(
        ax,
        2.4,
        1.15,
        4.1,
        0.75,
        "Completion checks → Gold\nRebuild Bronze by source ID",
        icon="check",
    )
    arrow(ax, (2.4, 2.0), (2.4, 1.55))
    box(
        ax,
        7.6,
        1.15,
        4.1,
        0.75,
        "Reconciliation + saved reports\nCompare Gold + Hadoop results",
        TEAL,
        "shield",
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
        fontsize=14,
    )
    save(fig, "architecture")

    fig, ax = canvas(6.8)
    box(
        ax, 2.4, 6.1, 3.9, 0.8, "Kafka data deliveries\nBronze stores every delivery"
        , icon="stream"
    )
    box(
        ax,
        7.5,
        6.1,
        3.9,
        0.8,
        "Replay completion evidence\nReceipts and terminal offsets",
        TEAL,
        "check",
    )
    box(
        ax,
        2.4,
        4.6,
        3.9,
        0.85,
        "Parse and validate\nCheck ID, time and value",
        icon="funnel",
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
        "database",
    )
    arrow(ax, (7.5, 5.65), (7.5, 5.05))
    arrow(ax, (4.4, 6.1), (6.5, 5.05))
    box(
        ax, 2.4, 2.95, 3.9, 0.85, "Operational Silver\nEvent-time deduplication",
        icon="clock",
    )
    arrow(ax, (2.4, 4.15), (2.4, 3.4))
    box(
        ax,
        7.5,
        2.95,
        3.9,
        0.85,
        "Invalid → quarantine\nRetain payload\nRecord rejection reason",
        AMBER,
        "warning",
    )
    arrow(ax, (4.4, 4.6), (5.5, 2.95), [(4.95, 4.6), (4.95, 2.95)])
    box(
        ax,
        5,
        1.1,
        5.4,
        1.0,
        "Finalization checks\nDelivery + offset accounting\nGold/Hadoop + artifact checks",
        TEAL,
        "shield",
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
        fontsize=14,
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
