from datetime import date

import grpc

from app.scripts.seed import PRODUCT_A, clear_and_seed
from app.shared.cache import cache_delete_prefix, cache_get, cache_set
from app.shared.resilience import RetryPolicy, call_grpc_with_retry
from app.transport.grpc.domain_clients import MasterDataDomainClient
from app.transport.kafka.consumer import KafkaEventConsumer
from app.transport.kafka.events import EventEnvelope
from app.transport.kafka.publisher import KafkaEventPublisher


def setup_function():
    clear_and_seed()
    cache_delete_prefix("")


class FakeRpcError(grpc.RpcError):
    def __init__(self, code, details="temporary failure"):
        super().__init__()
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


def test_grpc_retry_recovers_from_transient_errors():
    attempts = []

    def rpc(request, timeout=None, metadata=None):
        attempts.append(timeout)
        if len(attempts) < 3:
            raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)
        return "ok"

    result = call_grpc_with_retry(
        rpc,
        object(),
        operation="test.Operation",
        target="test:1",
        policy=RetryPolicy(timeout_seconds=0.25, max_attempts=3, backoff_seconds=0),
    )
    assert result == "ok"
    assert attempts == [0.25, 0.25, 0.25]


def test_grpc_retry_does_not_repeat_permanent_error():
    attempts = 0

    def rpc(request, timeout=None, metadata=None):
        nonlocal attempts
        attempts += 1
        raise FakeRpcError(grpc.StatusCode.INVALID_ARGUMENT)

    try:
        call_grpc_with_retry(
            rpc,
            object(),
            operation="test.Operation",
            target="test:1",
            policy=RetryPolicy(timeout_seconds=0.1, max_attempts=5, backoff_seconds=0),
        )
    except FakeRpcError:
        pass
    else:
        raise AssertionError("permanent gRPC error must be propagated")
    assert attempts == 1


def test_redis_style_cache_api_and_invalidation():
    cache_set("costing-context:p1:2026-09-01", {"value": 1}, 60)
    cache_set("other:key", {"value": 2}, 60)
    assert cache_get("costing-context:p1:2026-09-01") == {"value": 1}
    deleted = cache_delete_prefix("costing-context:")
    assert deleted == 1
    assert cache_get("costing-context:p1:2026-09-01") is None
    assert cache_get("other:key") == {"value": 2}


def test_costing_context_second_read_uses_cache():
    client = MasterDataDomainClient()
    period = date(2026, 9, 1)
    first = client.get_costing_context(PRODUCT_A, period)

    class FailStub:
        def GetCostingContext(self, *args, **kwargs):
            raise AssertionError("network must not be used on cache hit")

    client.stub = FailStub()
    second = client.get_costing_context(PRODUCT_A, period)
    assert second == first


def test_kafka_publisher_retries_bounded_number_of_times():
    event = EventEnvelope.create("TestEvent", "tests", {"x": 1})

    class Publisher(KafkaEventPublisher):
        def __init__(self):
            super().__init__(
                bootstrap_servers="unused:9092", max_attempts=3, backoff_seconds=0
            )
            self.attempts = 0

        def _send_once(self, event):
            self.attempts += 1
            if self.attempts < 3:
                raise TimeoutError("broker temporarily unavailable")

    publisher = Publisher()
    publisher.publish(event)
    assert publisher.attempts == 3


def test_kafka_consumer_retries_handler_before_success():
    event = EventEnvelope.create("TestEvent", "tests", {"x": 1})
    attempts = []

    def handler(_event):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("temporary processing error")

    consumer = KafkaEventConsumer(
        "test-group",
        {"TestEvent": handler},
        max_attempts=3,
        backoff_seconds=0,
    )
    assert consumer._process(event) is True
    assert len(attempts) == 3


def test_kafka_consumer_moves_poison_message_to_dead_letter_after_retries():
    event = EventEnvelope.create("TestEvent", "tests", {"x": 1})
    dead_letters = []

    def handler(_event):
        raise ValueError("bad payload")

    consumer = KafkaEventConsumer(
        "test-group",
        {"TestEvent": handler},
        max_attempts=2,
        backoff_seconds=0,
    )
    consumer._send_to_dead_letter = lambda failed_event, error: (
        dead_letters.append((failed_event, error)) or True
    )
    assert consumer._process(event) is True
    assert len(dead_letters) == 1
    assert dead_letters[0][0].eventId == event.eventId
