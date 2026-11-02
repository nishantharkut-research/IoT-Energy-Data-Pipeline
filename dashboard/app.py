"""Read-only Streamlit presentation for sealed finalized runs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dashboard.data import REQUIRED_VIEWS, load_finalized_run

VIEW_LABELS = {
    "provenance_status": "Run provenance",
    "throughput_layers": "Layer counts",
    "fault_disposition": "Fault disposition",
    "energy_quality": "Energy and quality",
    "storage_queries": "Storage and queries",
    "reconciliation": "Reconciliation",
}


def _label(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _metrics(streamlit: Any, row: dict[str, Any], fields: dict[str, str]) -> None:
    available = [(key, label) for key, label in fields.items() if key in row]
    for offset in range(0, len(available), 3):
        group = available[offset : offset + 3]
        for column, (key, label) in zip(
            streamlit.columns(len(group)), group, strict=True
        ):
            value = row[key]
            if isinstance(value, int) and not isinstance(value, bool):
                display = f"{value:,}"
            elif isinstance(value, float):
                display = f"{value:,.3f}"
            else:
                display = str(value) if value is not None else "Unavailable"
            column.metric(label, display)


def _table(streamlit: Any, rows: list[dict[str, Any]]) -> None:
    if rows:
        streamlit.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        streamlit.info("No entries recorded in this sealed view.")


def _show_row(streamlit: Any, name: str, row: dict[str, Any]) -> None:
    if name == "provenance_status":
        _table(
            streamlit,
            [
                {"Run attribute": _label(key), "Value": str(value)}
                for key, value in row.items()
                if "sha256" not in key
                and "hash" not in key
                and not isinstance(value, (dict, list))
            ],
        )
    elif name == "throughput_layers":
        _metrics(
            streamlit,
            row,
            {
                "bronze_deliveries": "Bronze deliveries",
                "silver_deliveries": "Silver deliveries",
                "gold_source_events": "Gold source events",
            },
        )
        _table(
            streamlit,
            [
                {"Layer count": _label(key), "Count": value}
                for key, value in row.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ],
        )
    elif name == "energy_quality":
        if row.get("comparison_scope") != "identical meter/start/end supports only":
            streamlit.info(
                "Energy and tariff figures from this older run require reanalysis."
            )
            return
        _metrics(
            streamlit,
            row,
            {
                "absolute_kwh_discrepancy": "Comparable interval discrepancy (kWh)",
                "affected_meter_periods": "Affected meter periods",
                "comparable_meter_period_count": "Comparable meter periods",
                "incomparable_meter_period_count": "Incomparable periods",
                "candidate_flagged_records": "Candidate flagged records",
                "verified_flagged_records": "Verified flagged records",
            },
        )
        for limit in row.get("coverage_limits", []):
            streamlit.caption(limit)
        streamlit.markdown("#### Hypothetical tariff scenarios")
        streamlit.caption(
            "Normalized hypothetical tariff scenarios in scenario currency units; "
            "not HKUST financial results."
        )
        _table(
            streamlit,
            [
                {
                    "Rate / kWh": scenario.get("normalized_rate"),
                    "Comparable exposure": scenario.get("gross_exposure"),
                    "Residual exposure": (
                        "Unknown"
                        if scenario.get("residual_exposure_after_verification") is None
                        else scenario["residual_exposure_after_verification"]
                    ),
                }
                for scenario in row.get("tariff_scenarios", [])
            ],
        )
    elif name == "storage_queries":
        _metrics(
            streamlit,
            row,
            {
                "candidate_storage_bytes": "Candidate storage (bytes)",
                "verification_storage_bytes": "Verification storage (bytes)",
                "verification_seconds": "Verification time (seconds)",
                "storage_overhead_ratio": "Recorded storage overhead ratio",
            },
        )
        streamlit.markdown("#### Query timings")
        _table(
            streamlit,
            [
                {
                    "Query": _label(query.get("query", "Query")),
                    "Repetitions": query.get("repetitions"),
                    "Rows": query.get("row_count"),
                    "Minimum (seconds)": query.get("seconds", {}).get("minimum"),
                    "Median (seconds)": query.get("seconds", {}).get("median"),
                    "Maximum (seconds)": query.get("seconds", {}).get("maximum"),
                }
                for query in row.get("query_results", [])
            ],
        )
        streamlit.markdown("#### Storage formats")
        _table(
            streamlit,
            [
                {
                    "Format": _label(format_name),
                    "Bytes": details.get("byte_size"),
                    "Files": details.get("file_count"),
                    "Recorded size relative to NDJSON": details.get(
                        "relative_to_ndjson"
                    ),
                    "Write time (seconds)": details.get("write_seconds"),
                }
                for format_name, details in row.get("storage_formats", {}).items()
            ],
        )
        streamlit.caption("Timings and size ratios are recorded sealed-run values.")
    elif name == "reconciliation":
        status = row.get("status")
        if status == "passed":
            streamlit.success("Reconciliation passed")
        else:
            streamlit.info(f"Recorded reconciliation status: {status or 'Unavailable'}")
        _metrics(
            streamlit,
            row,
            {
                "reconciliation_seconds": "Reconciliation time (seconds)",
            },
        )
        _table(
            streamlit,
            [
                {
                    "Comparison": label,
                    "Spark records": row[key].get("spark_record_count"),
                    "Hadoop records": row[key].get("hadoop_record_count"),
                    "Reported errors": len(row[key].get("errors", [])),
                }
                for key, label in (
                    ("source_record_comparison", "Source records"),
                    ("aggregate_comparison", "Aggregates"),
                )
                if key in row
            ],
        )
        _table(
            streamlit,
            [
                {"Layer count": _label(key), "Count": value}
                for key, value in row.get("layer_counts", {}).items()
            ],
        )


def _show_view(streamlit: Any, name: str, view: dict[str, Any]) -> None:
    streamlit.subheader(str(view.get("title", "View")))
    if view.get("description"):
        streamlit.caption(str(view["description"]))
    rows = view.get("rows")
    if not isinstance(rows, list):
        streamlit.info("No tabular summary recorded in this sealed view.")
    elif not rows:
        streamlit.info("No entries recorded in this sealed view.")
    elif name == "fault_disposition":
        _table(
            streamlit,
            [
                {
                    "Disposition": _label(row.get("disposition", "Unavailable")),
                    "Deliveries": row.get("delivery_count"),
                }
                for row in rows
            ],
        )
    else:
        for index, row in enumerate(rows):
            if len(rows) > 1:
                streamlit.markdown(f"#### Entry {index + 1}")
            _show_row(streamlit, name, row)
    with streamlit.expander("Provenance and details — exact sealed fields"):
        streamlit.json(view)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Auditable IoT Energy Pipeline", layout="wide")
    st.title("Auditable IoT Energy Data Pipeline")
    run_path = Path(
        st.sidebar.text_input(
            "Sealed finalized run directory",
            os.environ.get("IOT_ENERGY_RUN_DIR", "reports/finalized/fixture-clean"),
        )
    )
    try:
        run = load_finalized_run(run_path)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.caption(f"Run {run['replay_run_id']} — finalized, immutable, and reconciled")
    tabs = st.tabs([VIEW_LABELS[name] for name in REQUIRED_VIEWS])
    for tab, name in zip(tabs, REQUIRED_VIEWS, strict=True):
        with tab:
            _show_view(st, name, run["views"][name])


if __name__ == "__main__":
    main()
