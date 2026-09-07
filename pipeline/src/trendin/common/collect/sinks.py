"""저장·발급의 이음매 (S15P21A102-158 의 인터페이스).

Protocol 뒤 실구현은 `minio_store.py` · `kafka_publisher.py` 다. 이 파일에는 boto3 도
confluent_kafka 도 airflow 도 없다 — 여기가 "태스크 함수는 Airflow 없이 테스트한다"
(README 규약 12)의 경계다.

봉투는 `events.py` 다. 이음매가 바뀔 때와 팀 계약이 바뀔 때는 서로 다른 이유라 파일을 나눈다.
"""

from __future__ import annotations

from typing import Any, Protocol

# raw 확장자별 content-type. route 와 확장자는 1:1 이다 (keys.ROUTE_EXT).
CONTENT_TYPES = {
    "xml": "application/xml",
    "html": "text/html; charset=utf-8",
    "json": "application/json",
}
ARTICLE_CONTENT_TYPE = "application/json"


class ObjectStore(Protocol):
    """원문 저장소. MinIO 는 S3 호환이라 구현은 그대로 실제 S3 에도 간다."""

    def put(self, key: str, body: bytes, content_type: str) -> None:
        """객체를 쓴다. 같은 키에 다시 쓰면 덮어쓴다 (불변식 7 — 키가 같으면 내용도 같다)."""
        ...

    def exists(self, key: str) -> bool:
        """`stat` 하나. 이벤트는 이게 참인 뒤에만 나간다 (불변식 5)."""
        ...


class EventPublisher(Protocol):
    """발급. 전달 보장은 at-least-once 고 중복은 소비 측이 `event_id` 로 거른다."""

    def publish(self, key: str, value: dict[str, Any]) -> None:
        """메시지를 큐에 넣는다. 이 시점에 전달이 끝났다고 보면 안 된다."""
        ...

    def flush(self) -> None:
        """큐를 비우고 전달을 확인한다. 실패한 메시지가 있으면 예외를 올린다."""
        ...
