"""계약 fixture 가 `events.py` 와 어긋나지 않는지 (S15P21A102-159).

fixture 는 소비 측(Spark, 169)이 Kafka·MinIO 없이 파싱·검증 코드를 짜는 유일한 근거다
(`pipeline/docs/spark-integration.md`). 봉투에 필드를 하나 더하거나 키 규칙을 고치면
fixture 가 조용히 낡는데, 낡은 fixture 는 없는 fixture 보다 나쁘다 — 소비 측이 그 모양대로
짜고 실제 토픽에서 터진다. 그래서 여기서 막는다.

fixture 를 다시 만드는 방법은 `pipeline/docs/spark-integration.md` 의 "fixture 갱신" 절.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from trendin.common.collect.events import article_event, run_summary_event
from trendin.common.collect.keys import article_key, raw_key
from trendin.common.collect.ledger import PendingArticle

CONTRACT = (
    pathlib.Path(__file__).resolve().parents[2] / "spark" / "tests" / "fixtures" / "contract"
)
OBJECTS = CONTRACT / "objects"


def load(name: str) -> dict:
    return json.loads((CONTRACT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def article_evt() -> dict:
    return load("article-event.json")


def _pending_from(evt: dict) -> PendingArticle:
    """fixture 가 적어 둔 값으로 장부 행을 되만든다.

    fixture 를 입력으로 봉투를 다시 만들어 fixture 자신과 비교한다. 이러면 `events.py` 의
    어떤 변화든 — 필드 추가, 값 규칙 변경, 접두어 변경 — 여기서 불일치로 드러난다.
    """
    from datetime import datetime

    return PendingArticle(
        source=evt["source_id"],
        article_id=evt["article_id"],
        domain=evt["domain"],
        url=evt["url"],
        title=evt["title"],
        published_at=datetime.fromisoformat(evt["published_at"]),
        collected_at=datetime.fromisoformat(evt["collected_at"]),
        article_key=evt["object_key"],
        article_sha256=evt["checksum"].removeprefix("sha256-"),
        raw_key=evt["raw_object_key"],
        members_only=evt["members_only"],
    )


def test_기사_이벤트_fixture_가_봉투_출력과_같다(article_evt):
    """`events.py` 를 고치고 fixture 를 안 고치면 여기서 걸린다.

    fixture 를 입력으로 되만들기 때문에 봉투를 그냥 지나가는 값(`title`·`url`)은 양쪽이
    함께 바뀌어 여기서 안 걸린다. 그쪽은 아래 `..._객체와_같다` 가 객체와 맞대어 잡는다.
    여기서 잡는 것은 봉투가 **계산하는** 것 — 필드 집합, `event_id` 형식, `checksum`
    접두어, `collected_at` 의 KST 변환, `record_count`·`format` 같은 상수다.
    """
    rebuilt = article_event(
        _pending_from(article_evt), bucket=article_evt["bucket"], run_id=article_evt["run_id"]
    )
    assert rebuilt == article_evt


# 봉투와 article.json 에 같이 실리는 값. 왼쪽이 봉투, 오른쪽이 article.json 의 이름이다.
SHARED_FIELDS = (
    ("url", "url"),
    ("title", "title"),
    ("published_at", "published_at"),
    ("domain", "domain"),
    ("source_id", "source"),
    ("article_id", "article_id"),
    ("members_only", "members_only"),
    ("raw_object_key", "raw_key"),
)


@pytest.mark.parametrize("evt_field,doc_field", SHARED_FIELDS)
def test_이벤트의_값이_객체와_같다(article_evt, evt_field, doc_field):
    """소비 측은 봉투만 읽고 `metadata.json` 을 읽지 않는다 (`02 §3`).

    그러려면 봉투의 값이 객체의 값과 같아야 한다. fixture 를 손으로 고쳐 둘이 어긋나면
    소비 측이 봉투를 신뢰할 수 없게 되는데, 그건 fixture 가 아니라 계약이 깨진 것이다.
    """
    doc = json.loads((OBJECTS / article_evt["object_key"]).read_bytes())
    assert article_evt[evt_field] == doc[doc_field]


def test_이벤트와_객체의_collected_at_이_같은_순간이다(article_evt):
    """봉투는 KST 오프셋, article.json 은 UTC 다 (`events._kst` · `Article._must_be_utc`).
    표기가 다르므로 문자열이 아니라 순간으로 비교한다."""
    from datetime import datetime

    doc = json.loads((OBJECTS / article_evt["object_key"]).read_bytes())
    assert datetime.fromisoformat(article_evt["collected_at"]) == datetime.fromisoformat(
        doc["collected_at"]
    )


def test_checksum_이_실제_객체의_해시다(article_evt):
    """소비 측이 이 fixture 로 checksum 검증을 짠다 (`02 §3`). 안 맞으면 자기 코드를 의심한다."""
    body = (OBJECTS / article_evt["object_key"]).read_bytes()
    assert article_evt["checksum"] == "sha256-" + hashlib.sha256(body).hexdigest()


def test_이벤트가_가리키는_객체가_전부_있다(article_evt):
    """`object_key` 는 항상, `raw_object_key` 는 회원 전용이 아닐 때 있어야 한다(불변식 2)."""
    assert (OBJECTS / article_evt["object_key"]).is_file()
    assert (OBJECTS / article_evt["raw_object_key"]).is_file()


def test_article_json_의_content_sha256_이_raw_객체의_해시다(article_evt):
    """`content_sha256` 은 raw 의 해시다 — 봉투의 `checksum`(article.json 의 해시)과 다른 값이다.

    이 검사가 개행 변환을 잡는다. `raw.xml` 은 LF 로 커밋되어 있는데 `core.autocrlf=true` 인
    작업자가 체크아웃하면 CRLF 가 되어 해시가 바뀐다. 그러면 fixture 는 "이 원문의 해시는
    이것" 이라고 거짓을 말하게 된다. `pipeline/.gitattributes` 가 그 변환을 막고, 여기가
    막혔는지 확인한다.
    """
    doc = json.loads((OBJECTS / article_evt["object_key"]).read_bytes())
    raw = (OBJECTS / article_evt["raw_object_key"]).read_bytes()
    assert doc["content_sha256"] == hashlib.sha256(raw).hexdigest()


def test_키가_키_규칙에서_나온_값이다(article_evt):
    """`keys.py` 를 고치면 fixture 의 경로도 같이 바뀌어야 한다(불변식 7)."""
    from datetime import datetime

    args = (
        article_evt["domain"],
        article_evt["source_id"],
        "rss",  # 키의 route 칸. 봉투에는 없고 경로에만 있다.
        datetime.fromisoformat(article_evt["published_at"]),
        article_evt["article_id"],
    )
    assert article_evt["object_key"] == article_key(*args)
    assert article_evt["raw_object_key"] == raw_key(*args)


def test_article_json_이_그_자체로_유효한_JSON_이다(article_evt):
    """소비 측이 s3a 로 읽어 바로 파싱한다. 생성 스크립트가 재포매팅했으면 여기서 안 걸리고
    checksum 쪽에서 걸리지만, 파싱 자체도 확인해 둔다."""
    body = (OBJECTS / article_evt["object_key"]).read_bytes()
    doc = json.loads(body)
    # 출처 명시 3종은 article.json 에도 반드시 있다 (불변식 11, 저작권법 제37조).
    for field in ("url", "source", "published_at"):
        assert doc[field]


@pytest.mark.parametrize(
    "name,status,record_count,reason",
    [
        ("run-summary-success.json", "success", 12, None),
        ("run-summary-failed.json", "failed", 0, "목록 페이지가 3회 연속 타임아웃"),
    ],
)
def test_요약_이벤트_fixture_가_봉투_출력과_같다(name, status, record_count, reason):
    evt = load(name)
    rebuilt = run_summary_event(
        source=evt["source_id"],
        domain=evt["domain"],
        run_id=evt["run_id"],
        logical_date=__import__("datetime").datetime.fromisoformat(evt["collected_at"]),
        status=status,
        record_count=record_count,
        bucket=evt["bucket"],
        failure_reason=reason,
    )
    assert rebuilt == evt


def test_요약_이벤트는_object_key_가_null_이고_기사수가_0_이_아닐_수_있다():
    """소비 측이 `object_key=null` 을 계약 위반으로 읽으면 정상 실행마다 DLQ 가 쌓인다.

    `record_count > 0` 인 fixture 를 일부러 둔 이유다 — 팀 계약 §5 는 배치 하나에 이벤트
    하나를 전제하지만 우리는 기사 하나에 이벤트 하나를 내고(설계 문서 #12 확정 7), 요약
    이벤트가 그 위에 하나 더 붙는다. 소비 측 분기 기준은 `object_key` 의 null 여부다.
    """
    evt = load("run-summary-success.json")
    assert evt["object_key"] is None
    assert evt["record_count"] > 0


def test_기사_이벤트의_run_id_는_발급한_실행이다(article_evt):
    """159 는 `null` 로 뒀다. 204 가 **발급한** 실행의 값으로 바꿨다.

    159 의 근거는 "기사는 실행에 속하지 않는다 — 이월분에서 거짓이 된다" 였고, 그건
    **수집한** 실행을 찍을 때 맞는 말이다. 앞 실행이 받아 두고 못 낸 기사에 그 실행을
    찍으면 거짓이 된다. 발급한 실행은 이월분에서도 거짓이 되지 않는다 — 그 기사를 실제로
    내보낸 회차가 하나뿐이라서다.

    바꾼 이유는 소비 측이 curated 를 `domain/published_date/source/run_id` 로 파티션하고
    재처리 단위를 그것으로 자르기 때문이다. `null` 이면 그 축이 없다. 덤으로 159 가
    `spark-integration.md` 에 적어 둔 "`run_id` 가 `nullable=False` 인데 기사는 항상 null"
    어긋남이 사라진다.
    """
    assert article_evt["run_id"]
    assert article_evt["article_id"]
