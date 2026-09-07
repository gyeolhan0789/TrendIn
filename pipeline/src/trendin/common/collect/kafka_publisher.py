"""Kafka 발급 (S15P21A102-158 의 최소 구현).

`confluent-kafka` 를 직접 쓴다. Airflow 의 Kafka provider 를 쓰지 않는 이유는
README 규약 12 — 태스크 함수는 Airflow 없이 테스트한다.

`produce()` 는 큐에 넣기만 하고 전달을 기다리지 않는다. 그래서 **`flush()` 가 성공한 뒤에만
장부에 발급 시각을 적어야 한다**(flow.publish_pending). 전달 실패를 삼키면 장부에는 나갔다고
적혀 있고 토픽에는 없는 기사가 생긴다.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from trendin.common.collect.env import require_env

logger = logging.getLogger("trendin.collect.kafka")

BOOTSTRAP_ENV = "TRENDIN_KAFKA_BOOTSTRAP"
TOPIC_ENV = "TRENDIN_KAFKA_TOPIC_RAW_FILE_READY"


class DeliveryFailed(RuntimeError):
    """브로커가 받지 못한 메시지가 있다. 장부는 그대로 두고 다음 실행이 다시 낸다."""


FLUSH_TIMEOUT = 30.0
# 큐가 찼을 때 한 번에 폴링할 시간과, 포기하기까지의 총 예산.
QUEUE_FULL_WAIT = 0.5
QUEUE_WAIT_BUDGET = 30.0


class KafkaEventPublisher:
    """`EventPublisher` 의 실구현. 토픽 하나에 기사 이벤트와 요약 이벤트가 함께 흐른다."""

    def __init__(
        self,
        *,
        topic: str,
        producer,
        queue_full_wait: float = QUEUE_FULL_WAIT,
        queue_wait_budget: float = QUEUE_WAIT_BUDGET,
    ) -> None:
        self._topic = topic
        self._producer = producer
        self._queue_full_wait = queue_full_wait
        self._queue_wait_budget = queue_wait_budget
        self._errors: list[str] = []

    @classmethod
    def from_env(cls) -> "KafkaEventPublisher":
        from confluent_kafka import Producer

        bootstrap = require_env(BOOTSTRAP_ENV)
        return cls(
            topic=require_env(TOPIC_ENV),
            producer=Producer(
                {
                    "bootstrap.servers": bootstrap,
                    # 브로커가 전부 받았다고 할 때까지 성공으로 보지 않는다.
                    "acks": "all",
                    "enable.idempotence": True,
                    "linger.ms": 50,
                }
            ),
        )

    def _on_delivery(self, err, msg) -> None:
        if err is not None:
            self._errors.append(str(err))
            logger.error("발급 실패: %s", err)

    def publish(self, key: str, value: dict[str, Any]) -> None:
        """큐에 넣는다. 큐가 차 있으면 자리가 빌 때까지 예산 안에서 기다린다.

        `publish_pending` 이 한 번에 수백 건을 넣고 `flush` 는 그 뒤다. 브로커가 느리면
        librdkafka 큐가 차서 `produce` 가 `BufferError` 를 올리는데, 그대로 두면 태스크가
        거기서 죽고 앞서 넣은 것까지 확인되지 않은 채 끝난다. 무한히 기다리지도 않는다 —
        수집 풀 슬롯을 잡은 태스크가 영원히 매달리면 다른 소스가 못 돈다.
        """
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        encoded_key = key.encode("utf-8")
        deadline = time.monotonic() + self._queue_wait_budget
        while True:
            try:
                self._producer.produce(
                    self._topic,
                    key=encoded_key,
                    value=payload,
                    on_delivery=self._on_delivery,
                )
                break
            except BufferError:
                if time.monotonic() >= deadline:
                    raise DeliveryFailed(
                        f"발급 큐가 {self._queue_wait_budget:.0f}초 안에 비지 않았다 (key={key})"
                    ) from None
                # 잠들지 않고 폴링으로 자리를 비운다. poll 이 곧 대기다.
                self._producer.poll(self._queue_full_wait)
        # delivery callback 을 여기서 소비한다. 안 부르면 flush 까지 콜백이 쌓이기만 하고
        # 실패를 늦게 안다.
        self._producer.poll(0)

    def flush(self) -> None:
        remaining = self._producer.flush(FLUSH_TIMEOUT)
        if remaining:
            self._errors.append(f"{remaining}건이 {FLUSH_TIMEOUT:.0f}초 안에 안 나갔다")
        if self._errors:
            errors, self._errors = self._errors, []
            raise DeliveryFailed("; ".join(errors))
