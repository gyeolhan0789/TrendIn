"""Kafka 발급 (S15P21A102-158). producer 를 주입받으므로 브로커가 필요 없다."""

import pytest

from trendin.common.collect.kafka_publisher import DeliveryFailed, KafkaEventPublisher

EVENT = {"event_id": "vogue-857991", "object_key": "fashion/vogue/rss/…/article.json"}


class FakeProducer:
    """librdkafka 대역. `capacity` 를 넘기면 `produce` 가 `BufferError` 를 올린다.

    delivery callback 은 실제 producer 처럼 `poll` · `flush` 안에서만 불린다. 그래서
    "produce 뒤에 poll 을 안 부르면 실패를 늦게 안다" 가 테스트로 드러난다.
    """

    def __init__(self, *, capacity: int | None = None, drain_on_poll: bool = True) -> None:
        self.queued: list[tuple[str, bytes, bytes]] = []
        self.delivered: list[bytes] = []
        self.polls: list[float] = []
        self.flushes: list[float] = []
        self._pending: list[tuple[object, object, object]] = []
        self._capacity = capacity
        self._drain_on_poll = drain_on_poll

    def produce(self, topic, key, value, on_delivery):
        if self._capacity is not None and len(self.queued) >= self._capacity:
            raise BufferError("Local: Queue full")
        self.queued.append((topic, key, value))
        self._pending.append((on_delivery, None, _Message(key)))

    def poll(self, timeout: float) -> int:
        self.polls.append(timeout)
        served, self._pending = self._pending, []
        for callback, err, msg in served:
            callback(err, msg)
        if self._drain_on_poll and timeout:
            # 브로커가 받아 큐가 빈다.
            self.delivered.extend(k for _, k, _ in self.queued)
            self.queued.clear()
        return len(served)

    def flush(self, timeout: float) -> int:
        self.flushes.append(timeout)
        self.poll(0)
        self.delivered.extend(k for _, k, _ in self.queued)
        self.queued.clear()
        return 0


class _Message:
    def __init__(self, key: bytes) -> None:
        self._key = key

    def key(self) -> bytes:
        return self._key


def make(producer, **kwargs) -> KafkaEventPublisher:
    return KafkaEventPublisher(topic="raw-file-ready", producer=producer, **kwargs)


def test_메시지가_토픽과_key_그대로_나간다():
    producer = FakeProducer()
    make(producer).publish("vogue", EVENT)
    topic, key, value = producer.queued[0]
    assert topic == "raw-file-ready"
    assert key == b"vogue"
    assert b'"event_id"' in value
    assert "…".encode("utf-8") in value  # ensure_ascii=False 로 한글·기호가 그대로


def test_publish_뒤에_poll_0_을_부른다():
    """콜백을 그 자리에서 소비한다. 안 하면 flush 까지 실패를 모른다."""
    producer = FakeProducer()
    make(producer).publish("vogue", EVENT)
    assert producer.polls == [0]


def test_큐가_차면_폴링으로_자리를_비우고_넣는다():
    producer = FakeProducer(capacity=1)
    publisher = make(producer, queue_full_wait=0.01, queue_wait_budget=1.0)
    publisher.publish("vogue", EVENT)
    publisher.publish("vogue", EVENT)  # 여기서 BufferError → poll → 재시도
    assert 0.01 in producer.polls
    assert len(producer.delivered) >= 1


def test_큐가_안_비면_예산을_넘기고_포기한다():
    """무한히 기다리면 수집 풀 슬롯을 잡은 태스크가 영원히 매달린다."""
    producer = FakeProducer(capacity=1, drain_on_poll=False)
    publisher = make(producer, queue_full_wait=0.0, queue_wait_budget=0.0)
    publisher.publish("vogue", EVENT)
    with pytest.raises(DeliveryFailed, match="비지 않았다"):
        publisher.publish("vogue", EVENT)


def test_flush_에서_안_나간_건이_있으면_올린다():
    class Stuck(FakeProducer):
        def flush(self, timeout):
            self.flushes.append(timeout)
            return 3

    publisher = make(Stuck())
    publisher.publish("vogue", EVENT)
    with pytest.raises(DeliveryFailed, match="3건"):
        publisher.flush()


def test_건별_전달_실패는_flush_에서_올라온다():
    """장부는 그대로 두고 다음 실행이 다시 낸다."""
    producer = FakeProducer()
    publisher = make(producer)
    publisher.publish("vogue", EVENT)
    publisher._on_delivery("Broker: Not enough replicas", _Message(b"vogue"))
    with pytest.raises(DeliveryFailed, match="Not enough replicas"):
        publisher.flush()


def test_실패_기록은_한_번_올리고_비운다():
    """다음 발급이 지난 실패를 다시 올리면 안 된다."""
    publisher = make(FakeProducer())
    publisher._on_delivery("에러", _Message(b"vogue"))
    with pytest.raises(DeliveryFailed):
        publisher.flush()
    publisher.flush()  # 두 번째는 통과한다


def test_전달_성공은_기록하지_않는다():
    publisher = make(FakeProducer())
    publisher._on_delivery(None, _Message(b"vogue"))
    publisher.flush()
