from __future__ import annotations

import hashlib

from jobs.spark.benchmark_queries import _consume_query_result


class JsonRows:
    def __init__(self, rows: list[str]) -> None:
        self.rows = rows

    def toLocalIterator(self, *, prefetchPartitions: bool = False):
        assert prefetchPartitions is False
        yield from self.rows


class Result:
    def __init__(self, rows: list[str]) -> None:
        self.rows = rows

    def toJSON(self) -> JsonRows:
        return JsonRows(self.rows)

    def count(self) -> int:
        raise AssertionError("count does not evaluate the projected result")


def test_query_consumption_includes_values_and_order() -> None:
    rows = ['{"value":1}', '{"value":2}']
    count, digest = _consume_query_result(Result(rows))
    assert count == 2
    assert digest == hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest()
    assert _consume_query_result(Result(['{"value":1}', '{"value":3}']))[1] != digest
    assert _consume_query_result(Result(list(reversed(rows))))[1] != digest


def test_empty_query_result_has_an_explicit_digest() -> None:
    assert _consume_query_result(Result([])) == (0, hashlib.sha256(b"").hexdigest())
