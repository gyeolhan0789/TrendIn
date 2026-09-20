"""저장소의 대체 구현 (S15P21A102-158 AC — MinIO 없이 크롤러를 테스트한다).

`tests/` 가 아니라 `src/` 에 두는 이유는 쓰는 쪽이 테스트만이 아니기 때문이다. 장애
시나리오 검증(S15P21A102-160), 수집 중단 탐지(199)가 같은 대역을 쓴다. 테스트 파일 안에
두면 두 곳이 각자 다른 대역을 만들고, 계약이 바뀔 때 한 곳만 고쳐진다.

no-op 이 아니라 **기억하는** 구현이다. 무엇이 어느 키에 쓰였는지 볼 수 없으면 "통과"가
아무것도 보장하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StoredObject:
    body: bytes
    content_type: str
    metadata: dict[str, str]


class InMemoryObjectStore:
    """dict 하나. 같은 키에 다시 쓰면 덮어써서 멱등(불변식 7)이 그 자리에서 보인다."""

    def __init__(
        self,
        *,
        swallow: set[str] | None = None,
        fail_put: set[str] | None = None,
        fail_exists: set[str] | None = None,
    ) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.put_calls: list[str] = []
        self.exists_calls: list[str] = []
        # put 은 받되 없는 척하는 키. 저장 확인 실패(불변식 5)를 재현한다.
        self._swallow = swallow or set()
        # 쓰기 자체가 실패하는 키. 부분 실패를 재현한다.
        self._fail_put = fail_put or set()
        # 조회가 실패하는 키. "없다"와 "물어보지 못했다"를 가른다.
        self._fail_exists = fail_exists or set()

    def put(
        self,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.put_calls.append(key)
        if key in self._fail_put:
            raise RuntimeError(f"일부러 실패시킨 쓰기: {key}")
        self.objects[key] = StoredObject(body, content_type, dict(metadata or {}))

    def exists(self, key: str) -> bool:
        self.exists_calls.append(key)
        if key in self._fail_exists:
            raise RuntimeError(f"일부러 실패시킨 조회: {key}")
        return key in self.objects and key not in self._swallow
