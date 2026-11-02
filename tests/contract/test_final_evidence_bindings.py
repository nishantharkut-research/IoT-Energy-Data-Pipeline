"""Published evidence must retain its byte-level bindings after Git checkout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def test_final_results_bind_the_versioned_plan_and_scope() -> None:
    directory = Path("docs/results/final")
    results = json.loads((directory / "final-results.json").read_bytes())
    scope_bytes = (directory / "final-coursework-scope.json").read_bytes()
    plan_bytes = (directory / "experiment-plan.json").read_bytes()
    assert hashlib.sha256(scope_bytes).hexdigest() == results["final_scope_sha256"]
    assert hashlib.sha256(plan_bytes).hexdigest() == results["original_plan_sha256"]
    assert (
        json.loads(scope_bytes)["original_plan_sha256"]
        == (results["original_plan_sha256"])
    )
