from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from iot_energy_pipeline import replay
from iot_energy_pipeline.replay import ConfluentKafkaProducer, ProduceRequest


class FakeNativeProducer:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.now = 0.0
        self.poll_timeouts: list[float] = []
        self.flush_timeouts: list[float] = []
        self.pending_polls = 0
        self.error: Any = None
        self.message: Any = SimpleNamespace(offset=lambda: 42)
        self.remaining = 0
        self.enqueue_error: Exception | None = None
        self.callback: Any = None
        self.produce_request: Any = None

    def produce(self, topic: str, **kwargs: Any) -> None:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.produce_request = (topic, kwargs)
        self.callback = kwargs["on_delivery"]

    def poll(self, timeout: float) -> int:
        self.poll_timeouts.append(timeout)
        if self.pending_polls:
            self.pending_polls -= 1
            self.now += timeout
            return 0
        self.callback(self.error, self.message)
        return 1

    def flush(self, timeout: float) -> int:
        self.flush_timeouts.append(timeout)
        return self.remaining


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> ConfluentKafkaProducer:
    monkeypatch.setitem(
        sys.modules, "confluent_kafka", SimpleNamespace(Producer=FakeNativeProducer)
    )
    producer = ConfluentKafkaProducer(
        {"bootstrap.servers": "fake:9092"}, acknowledgement_timeout=0.125
    )
    monkeypatch.setattr(
        replay, "time", SimpleNamespace(monotonic=lambda: producer._producer.now)
    )
    event_factory = replay.threading.Event

    def nonblocking_event() -> Any:
        event = event_factory()

        def forbidden_wait(timeout: Any = None) -> bool:
            pytest.fail("delivery must poll native events without a thread wait")

        event.wait = forbidden_wait
        return event

    monkeypatch.setattr(replay, "threading", SimpleNamespace(Event=nonblocking_event))
    return producer


@pytest.fixture
def produce_request() -> ProduceRequest:
    return ProduceRequest(
        topic="events",
        key="source",
        value="{}",
        partition=2,
        headers=(("record_type", "data"),),
        record_type="data",
        delivery_id="delivery",
    )


def test_ready_acknowledgement_returns_offset_without_thread_wait(
    adapter: ConfluentKafkaProducer,
    produce_request: ProduceRequest,
) -> None:
    assert adapter.produce(produce_request) == 42
    native = adapter._producer
    assert native.now == 0.0
    assert len(native.poll_timeouts) == 1
    assert 0 < native.poll_timeouts[0] <= adapter._timeout
    topic, kwargs = native.produce_request
    assert topic == produce_request.topic
    assert {key: value for key, value in kwargs.items() if key != "on_delivery"} == {
        "key": produce_request.key,
        "value": produce_request.value,
        "partition": produce_request.partition,
        "headers": list(produce_request.headers),
    }
    assert native.flush_timeouts == []


def test_produce_keeps_polling_until_acknowledged(
    adapter: ConfluentKafkaProducer,
    produce_request: ProduceRequest,
) -> None:
    adapter._producer.pending_polls = 2
    assert adapter.produce(produce_request) == 42
    assert len(adapter._producer.poll_timeouts) == 3


def test_missing_callback_times_out_with_polls_bounded_by_deadline(
    adapter: ConfluentKafkaProducer,
    produce_request: ProduceRequest,
) -> None:
    native = adapter._producer
    native.pending_polls = 100
    with pytest.raises(TimeoutError, match="Kafka acknowledgement timed out"):
        adapter.produce(produce_request)
    elapsed = 0.0
    for timeout in native.poll_timeouts:
        assert 0 < timeout <= adapter._timeout - elapsed
        elapsed += timeout
    assert elapsed == pytest.approx(adapter._timeout)


@pytest.mark.parametrize("timeout", [0.0, -1.0])
def test_expired_deadline_still_dispatches_ready_callback(
    adapter: ConfluentKafkaProducer,
    produce_request: ProduceRequest,
    timeout: float,
) -> None:
    adapter._timeout = timeout
    assert adapter.produce(produce_request) == 42
    assert adapter._producer.poll_timeouts == [0.0]


@pytest.mark.parametrize(
    ("error", "message", "expected"),
    [
        ("broker rejected", None, "Kafka delivery failed: broker rejected"),
        (None, None, "Kafka acknowledgement did not include a message"),
    ],
)
def test_invalid_acknowledgement_raises(
    adapter: ConfluentKafkaProducer,
    produce_request: ProduceRequest,
    error: Any,
    message: Any,
    expected: str,
) -> None:
    adapter._producer.error = error
    adapter._producer.message = message
    with pytest.raises(RuntimeError, match=expected):
        adapter.produce(produce_request)


def test_native_enqueue_error_propagates_without_polling(
    adapter: ConfluentKafkaProducer,
    produce_request: ProduceRequest,
) -> None:
    adapter._producer.enqueue_error = BufferError("queue full")
    with pytest.raises(BufferError, match="queue full"):
        adapter.produce(produce_request)
    assert adapter._producer.poll_timeouts == []


@pytest.mark.parametrize("remaining", [0, 2])
def test_flush_uses_configured_timeout_and_rejects_unacknowledged_messages(
    adapter: ConfluentKafkaProducer,
    remaining: int,
) -> None:
    adapter._producer.remaining = remaining
    if remaining:
        with pytest.raises(RuntimeError, match="Kafka flush left 2 unacknowledged"):
            adapter.flush()
    else:
        assert adapter.flush() is None
    assert adapter._producer.flush_timeouts == [adapter._timeout]
