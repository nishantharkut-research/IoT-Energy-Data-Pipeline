"""Check exact JSON/Parquet round trips in the running Spark environment."""

from __future__ import annotations

import argparse
import json
from decimal import Inexact, Rounded, localcontext
from pathlib import Path
from typing import Any

from jobs.spark.common import canonical_spark_schema
from jobs.spark.stream import _numeric_shape


def check_numeric_contract(spark: Any, output_root: Path) -> dict[str, Any]:
    """Exercise the real source witness and both Decimal38 endpoints."""
    from pyspark.sql import functions as functions

    if output_root.exists():
        raise FileExistsError(f"numeric check output already exists: {output_root}")
    output_root.mkdir(parents=True)
    bound = 10**38 - 1
    cases = [
        ("source-witness", "26724.7", 15, 26724700000000000000),
        ("positive-boundary", str(bound), 0, bound),
        ("negative-boundary", str(-bound), 0, -bound),
    ]
    inputs = [
        json.dumps(
            {
                "source_event_id": label,
                "original_numeric_text": original,
                "decimal_scale": scale,
                "scaled_value": scaled,
            }
        )
        for label, original, scale, scaled in cases
    ]
    expected = {label: scaled for label, _, _, scaled in cases}
    for raw in inputs:
        if _numeric_shape(raw) is not None:
            raise AssertionError("valid exact test value rejected by numeric guard")
    for value in (-(10**38), 10**38):
        if _numeric_shape(json.dumps({"scaled_value": value})) != "numeric_overflow":
            raise AssertionError("numeric guard accepted Decimal38 overflow")

    with localcontext() as context:
        context.prec = 6
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        parsed = (
            spark.createDataFrame([(raw,) for raw in inputs], ["raw"])
            .select(functions.from_json("raw", canonical_spark_schema()).alias("event"))
            .select(
                "event.source_event_id",
                "event.scaled_value",
                "event.decimal_scale",
                "event.original_numeric_text",
            )
        )
        observed = {
            row.source_event_id: int(row.scaled_value) for row in parsed.collect()
        }
        if observed != expected:
            raise AssertionError("Spark JSON parser changed an exact scaled integer")
        parquet = output_root / "roundtrip.parquet"
        parsed.write.mode("errorifexists").parquet(str(parquet))
        restored = spark.read.parquet(str(parquet))
        restored_values = {
            row.source_event_id: int(row.scaled_value) for row in restored.collect()
        }
        if restored_values != expected:
            raise AssertionError("Spark Parquet round trip changed a scaled integer")
        for line in restored.toJSON().collect():
            record = json.loads(line)
            value = record["scaled_value"]
            if type(value) is not int or value != expected[record["source_event_id"]]:
                raise AssertionError("Spark JSON export lost integer representation")

    result = {
        "schema_version": "spark-numeric-contract-check-v1",
        "status": "passed",
        "spark_version": spark.version,
        "storage_type": "decimal(38,0)",
        "python_decimal_precision": 6,
        "json_parse_parquet_and_json_export": [
            {"case": label, "exact_scaled_integer": str(value)}
            for label, value in sorted(expected.items())
        ],
        "overflow_guard_cases": [str(-(10**38)), str(10**38)],
        "scope": "three synthetic numeric cases; not a scale measurement",
    }
    with (output_root / "numeric-contract.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName(
        "iot-energy-numeric-contract-check"
    ).getOrCreate()
    try:
        print(
            json.dumps(check_numeric_contract(spark, args.output_root), sort_keys=True)
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
