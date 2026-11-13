"""Portable presentation of the completed coursework's committed evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dashboard.submission_data import load_submission_evidence

PAGES = (
    "Overview",
    "Source quality",
    "Delivery accounting",
    "Fault handling",
    "Independent verification",
    "Watermark & consumption",
    "Recovery",
    "Storage & SQL",
)
NAVY = "#18344a"
BLUE = "#25669b"
TEAL = "#197c79"
AMBER = "#bd7926"
GREY = "#7b8997"


def _chart(
    st: Any,
    series: list[tuple[str, list[float], str]],
    labels: list[str],
    axis_title: str,
    height: int = 300,
    mode: str = "group",
) -> None:
    import plotly.graph_objects as go

    fig = go.Figure()
    for name, values, colour in series:
        fig.add_trace(
            go.Bar(
                name=name,
                x=labels,
                y=values,
                marker_color=colour,
                text=[
                    ""
                    if v == 0
                    else (f"{v:.2f}%" if axis_title == "NDJSON = 100%" else f"{v:,.0f}")
                    for v in values
                ],
                textposition="inside" if mode == "stack" else "outside",
                cliponaxis=False,
            )
        )
    fig.update_layout(
        height=height,
        barmode=mode,
        template="plotly_white",
        font={"family": "Arial, sans-serif", "size": 19, "color": NAVY},
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 20, "r": 20, "t": 40, "b": 15},
        legend={"orientation": "h", "y": 1.2, "x": 0},
        yaxis={"title": axis_title, "gridcolor": "#e5ebef", "rangemode": "tozero"},
        xaxis={"title": None},
        uniformtext={"minsize": 15, "mode": "show"},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _table(st: Any, rows: list[dict[str, Any]]) -> None:
    import pandas as pd

    frame = pd.DataFrame(rows)
    for column in frame.columns:
        frame[column] = frame[column].map(
            lambda value: f"{value:,}"
            if isinstance(value, int) and not isinstance(value, bool)
            else value
        )
    st.markdown(
        frame.to_html(index=False, escape=True, classes="evidence-table"),
        unsafe_allow_html=True,
    )


def _run(results: dict, run_id: str) -> dict:
    return next(row for row in results["runs"] if row["run_id"] == run_id)


def main(st: Any) -> None:
    root = Path(__file__).resolve().parents[1]
    try:
        evidence = load_submission_evidence(root)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        st.error(f"Saved evidence cannot be displayed: {exc}")
        st.stop()
        return
    results = evidence["results"]
    st.sidebar.markdown("### IoT Energy Pipeline")
    page = st.sidebar.radio("Explore the project", PAGES, label_visibility="collapsed")
    st.sidebar.divider()
    st.sidebar.caption("SAVED EXPERIMENT RESULTS")
    st.sidebar.write("9 fixture runs · 6 scale runs")
    st.sidebar.caption(
        "Original evidence verification: 2 November 2026. "
        "This viewer checks committed summary bindings, not the original runtime files."
    )
    st.markdown(
        "<div class='eyebrow'>ABV-IIITM · IoT Big Data Management</div>",
        unsafe_allow_html=True,
    )
    st.title(page)
    subtitles = {
        "Overview": (
            "Delivery accounting and independent verification for "
            "smart-meter telemetry."
        ),
        "Source quality": (
            "Published source availability and quality observations before replay."
        ),
        "Delivery accounting": (
            "Every delivery has a recorded disposition. Source "
            "identity survives retries."
        ),
        "Fault handling": (
            "Five controlled schedules, one unchanged finalized source result."
        ),
        "Independent verification": (
            "Spark and Hadoop agree on declared source fields and exact aggregates."
        ),
        "Watermark & consumption": (
            "A bounded streaming candidate and an exact finalized "
            "result answer different questions."
        ),
        "Recovery": (
            "Interrupted and uninterrupted fixture executions "
            "retain identical semantic outputs."
        ),
        "Storage & SQL": (
            "Recorded costs of verification, compressed storage and "
            "five read-only queries."
        ),
    }
    st.markdown(subtitles[page])

    if page == "Overview":
        a, b, c = st.columns(3)
        a.metric("Finalized runs", "15 / 15")
        b.metric("Largest completed workload", "1,000,000 records")
        c.metric("Exact comparison errors", "0")
        st.subheader("What the pipeline establishes")
        _table(
            st,
            [
                {
                    "Question": "Were received deliveries accounted for?",
                    "Evidence": "Bronze, duplicate, late and quarantine counts",
                    "Result": "Conservation holds in all 15 summaries",
                },
                {
                    "Question": "Did independent computations agree?",
                    "Evidence": "Exact source records and aggregates",
                    "Result": "No recorded comparison errors",
                },
                {
                    "Question": "Did interruption change the answer?",
                    "Evidence": "Four output-hash pairs",
                    "Result": "Fixture outputs are byte-identical",
                },
                {
                    "Question": "Can a watermark omit a valid event?",
                    "Evidence": "Restrictive watermark fixture",
                    "Result": "Silver 143; Gold and Hadoop 144",
                },
            ],
        )
        st.subheader("From a workbook row to a checked result")
        st.markdown(
            "**Register & prepare → Kafka replay → Spark layers → exact Gold → "
            "Hadoop comparison → saved report**"
        )
        st.info(
            "Processing agreement applies to the declared canonical input. "
            "It does not establish physical meter accuracy or "
            "complete source availability."
        )
        st.caption(
            "Scope: five correctness schedules, two recovery fixtures, "
            "two watermark fixtures, "
            "and three clean repetitions at each scale. The planned "
            "5M runs are excluded."
        )

    elif page == "Source quality":
        counts = evidence["source_counts"]
        total = counts["Physical data rows"]["clean"]
        finite = counts["Finite numeric readings"]["clean"]
        missing = counts["Missing numeric cells"]["clean"]
        a, b, c = st.columns(3)
        a.metric("Published resampled rows", f"{total:,}")
        b.metric("Missing numeric cells", f"{missing:,}")
        c.metric("Numeric-cell availability", f"{100 * finite / total:.3f}%")
        _chart(
            st,
            [("Finite numeric", [finite], BLUE), ("Missing numeric", [missing], AMBER)],
            ["Published resampled source"],
            "Rows",
            height=280,
            mode="stack",
        )
        st.caption(
            "63,273,828 = 44,238,638 numeric rows + 19,035,190 missing-value rows. "
            "The preparation records source-quality exclusions "
            "separately from delivery quarantine."
        )
        _table(
            st,
            [
                {
                    "Observation": key,
                    "Raw": counts[key]["raw"],
                    "Resampled": counts[key]["clean"],
                }
                for key in (
                    "Workbooks",
                    "Negative readings",
                    "Ordered numeric decreases",
                    "Duplicate decoded timestamps",
                    "Out-of-order timestamps",
                )
            ],
        )
        st.info(
            "Availability uses published rows as its denominator, "
            "not an independently expected "
            "reading schedule. Issue categories overlap; a decrease "
            "alone does not prove a reset."
        )
        st.caption(
            "Source: committed source-audit summary dated 27 October 2026. "
            "Original audit JSON and row-level source files are not "
            "included in this portable checkout."
        )

    elif page == "Delivery accounting":
        ids = [r["run_id"] for r in results["runs"]]
        selected = st.selectbox(
            "Recorded run", ids, index=ids.index("correctness-combined-r01")
        )
        run = _run(results, selected)
        layer = run["layer_counts"]
        a, b, c = st.columns(3)
        a.metric("Bronze data deliveries", f"{layer['bronze_deliveries']:,}")
        b.metric("Silver candidate records", f"{layer['silver_deliveries']:,}")
        c.metric("Gold source records", f"{run['source_records']:,}")
        st.subheader("Delivery conservation")
        st.markdown(
            f"**{layer['bronze_deliveries']:,} Bronze = "
            f"{layer['parsed_valid_deliveries']:,} parsed-valid + "
            f"{layer['quarantine_deliveries']:,} quarantine**"
        )
        st.markdown(
            f"**{layer['parsed_valid_deliveries']:,} parsed-valid = "
            f"{layer['silver_deliveries']:,} Silver + "
            f"{layer['duplicate_valid_deliveries']:,} duplicates + "
            f"{layer['late_valid_deliveries']:,} late**"
        )
        _chart(
            st,
            [
                (
                    "Deliveries",
                    [
                        layer[k]
                        for k in (
                            "silver_deliveries",
                            "duplicate_valid_deliveries",
                            "late_valid_deliveries",
                            "quarantine_deliveries",
                        )
                    ],
                    BLUE,
                )
            ],
            ["Silver", "Duplicate", "Late", "Quarantine"],
            "Data deliveries",
        )
        st.caption(
            f"{layer['terminal_records']} terminal control records "
            "are accounted for separately. "
            "Gold rebuilds from Bronze using exact source identity, "
            "not Silver's bounded state."
        )

    elif page == "Fault handling":
        rows = [r for r in results["runs"] if r["experiment"] == "correctness"]
        labels = [r["fault"].capitalize() for r in rows]
        _chart(
            st,
            [
                (
                    "Silver",
                    [r["layer_counts"]["silver_deliveries"] for r in rows],
                    BLUE,
                ),
                (
                    "Duplicates",
                    [r["layer_counts"]["duplicate_valid_deliveries"] for r in rows],
                    GREY,
                ),
                (
                    "Quarantine",
                    [r["layer_counts"]["quarantine_deliveries"] for r in rows],
                    AMBER,
                ),
            ],
            labels,
            "Data deliveries",
            330,
            "stack",
        )
        _table(
            st,
            [
                {
                    "Schedule": r["fault"],
                    "Bronze": r["layer_counts"]["bronze_deliveries"],
                    "Gold": r["source_records"],
                    "Hadoop": r["source_comparison"]["hadoop_record_count"],
                }
                for r in rows
            ],
        )
        st.success("All five schedules retain the same four semantic output hashes.")
        st.caption(
            "Controlled delivery faults are synthetic. Duplicate "
            "deliveries repeat unchanged source "
            "records; malformed deliveries are added alongside valid originals. "
            "This is not an estimate of faults in a live utility network."
        )

    elif page == "Independent verification":
        reference = results["runs"][0]
        a, b, c = st.columns(3)
        a.metric(
            "Source fields compared",
            len(reference["source_comparison"]["exact_fields"]),
        )
        b.metric(
            "Aggregate fields compared",
            len(reference["aggregate_comparison"]["exact_fields"]),
        )
        c.metric("Runs with matching comparisons", len(results["runs"]))
        families = [
            ("Correctness fixtures", lambda r: r["experiment"] == "correctness"),
            ("Recovery fixtures", lambda r: r["experiment"] == "recovery"),
            ("Watermark fixtures", lambda r: r["experiment"] == "watermark"),
            ("100K scale", lambda r: r["event_count"] == 100000),
            ("1M scale", lambda r: r["event_count"] == 1000000),
        ]
        rows = []
        for label, belongs in families:
            group = [r for r in results["runs"] if belongs(r)]
            rows.append(
                {
                    "Experiment family": label,
                    "Runs": len(group),
                    "Source records per run": group[0]["source_records"],
                    "Source errors": sum(
                        len(r["source_comparison"]["errors"]) for r in group
                    ),
                    "Aggregate errors": sum(
                        len(r["aggregate_comparison"]["errors"]) for r in group
                    ),
                }
            )
        _table(st, rows)
        st.info(
            "Independent implementations share the canonical input. "
            "Agreement checks downstream transformations; it does "
            "not independently validate "
            "the canonicalizer or the physical reading."
        )
        with st.expander("Exact fields and saved evidence bindings"):
            st.json(
                {
                    "source_fields": reference["source_comparison"]["exact_fields"],
                    "aggregate_fields": reference["aggregate_comparison"][
                        "exact_fields"
                    ],
                    "recorded_verification": results["verified_at_utc"],
                    "summary_inputs": evidence["index"]["inputs"],
                }
            )

    elif page == "Watermark & consumption":
        retaining = _run(results, "watermark-retaining-r01")
        restrictive = _run(results, "watermark-restrictive-r01")
        decision = restrictive["decision"]
        _chart(
            st,
            [
                (
                    "Silver",
                    [
                        retaining["layer_counts"]["silver_deliveries"],
                        restrictive["layer_counts"]["silver_deliveries"],
                    ],
                    BLUE,
                ),
                (
                    "Gold / Hadoop",
                    [retaining["source_records"], restrictive["source_records"]],
                    TEAL,
                ),
            ],
            ["Retaining watermark", "Restrictive watermark"],
            "Source records",
            290,
        )
        _table(
            st,
            [
                {
                    "Consumption comparison": "Derived intervals",
                    "Silver candidate": decision["candidate_interval_count"],
                    "Verified Gold": decision["verified_interval_count"],
                },
                {
                    "Consumption comparison": "Flagged records",
                    "Silver candidate": decision["candidate_flagged_record_count"],
                    "Verified Gold": decision["verified_flagged_record_count"],
                },
            ],
        )
        a, b, c = st.columns(3)
        a.metric("Comparable periods", decision["comparable_meter_period_count"])
        b.metric("Incomparable periods", decision["incomparable_meter_period_count"])
        c.metric(
            "Comparable discrepancy", f"{decision['absolute_kwh_discrepancy']} kWh"
        )
        st.warning(
            "Total energy error and residual financial exposure are unknown. "
            "Two periods lack matching interval supports; zero is "
            "only the comparable subtotal."
        )
        st.caption(
            "Consumption excludes ambiguous timestamp derivations "
            "under the existing conservative "
            "policy. These results do not demonstrate a 2 kWh loss "
            "or financial savings."
        )

    elif page == "Recovery":
        comparisons = results["recovery_semantic_equivalence"]["comparisons"]
        st.success(
            "All four interrupted / uninterrupted fixture output "
            "pairs are byte-identical."
        )
        _table(
            st,
            [
                {
                    "Semantic output": key.replace("_", " ").capitalize(),
                    "Uninterrupted SHA-256 prefix": value["uninterrupted_sha256"][:20],
                    "Resumed SHA-256 prefix": value["resumed_sha256"][:20],
                    "Full hashes match": value["uninterrupted_sha256"]
                    == value["resumed_sha256"],
                }
                for key, value in comparisons.items()
            ],
        )
        st.subheader("Recovered scale runs")
        _table(
            st,
            [
                {
                    "Run": r["run_id"],
                    "Source records": r["source_records"],
                    "Saved recovery receipt": "Present" if r["recovery"] else "Absent",
                    "Complete workflow timing": "Unavailable",
                }
                for r in results["runs"]
                if r["event_count"] == 1000000
            ],
        )
        st.info(
            "The fixture comparison tests semantic recovery. The "
            "three 1M runs also recovered, "
            "but their complete workflow durations cannot be "
            "reconstructed from the saved timings."
        )
        with st.expander("Full recorded output hashes"):
            st.json(comparisons)
        st.caption(
            "Hashes are read from the committed closure report. "
            "Original output files are not rehashed by this view."
        )

    elif page == "Storage & SQL":
        scale_ids = [
            r["run_id"] for r in results["runs"] if isinstance(r["event_count"], int)
        ]
        selected = st.selectbox("Recorded scale repetition", scale_ids)
        run = _run(results, selected)
        perf = next(
            row
            for row in results["performance_summary"]
            if row["event_count"] == run["event_count"]
        )
        a, b, c = st.columns(3)
        a.metric(
            "Verification median · 3 runs",
            f"{perf['verification_seconds']['median'] / 60:.2f} min",
        )
        b.metric(
            "Verification storage median",
            f"{perf['verification_bytes']['median'] / 1e6:,.2f} MB",
        )
        c.metric("Query repetitions", "3 per query")
        formats = run["storage"]["formats"]
        _chart(
            st,
            [
                (
                    "Stored size / NDJSON (%)",
                    [
                        100 * formats[k]["relative_to_ndjson"]
                        for k in (
                            "ndjson",
                            "parquet_zstd_unpartitioned",
                            "parquet_zstd_partitioned",
                        )
                    ],
                    BLUE,
                )
            ],
            ["NDJSON", "Zstd Parquet", "Partitioned Zstd Parquet"],
            "NDJSON = 100%",
            260,
        )
        _table(
            st,
            [
                {
                    "Query": row["query"].replace("_", " "),
                    "Result rows": row["row_count"],
                    "Minimum (s)": round(row["seconds"]["minimum"], 3),
                    "Median (s)": round(row["seconds"]["median"], 3),
                    "Maximum (s)": round(row["seconds"]["maximum"], 3),
                }
                for row in run["queries"]["results"]
            ],
        )
        st.caption(
            "Verification cost includes Gold, layer audit, Hadoop "
            "and reconciliation; it is not full workflow time. "
            "MB are decimal. Query settings differ between 100K and "
            "1M, so timings are not a controlled scaling "
            "comparison."
        )

    st.divider()
    st.caption(
        "Evidence: committed final-results.json and source-audit summary · "
        "Read-only presentation · HKUST evaluation, not an Indian utility deployment"
    )
