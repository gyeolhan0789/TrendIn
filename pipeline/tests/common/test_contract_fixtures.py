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
        _pending_from(article_evt),
        bucket=article_evt["bucket"], run_id=article_evt["run_id"]
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
    "name", ["collect-run-summary-success.json", "collect-run-summary-failed.json"]
)
def test_요약_이벤트_fixture_가_봉투_출력과_같다(name):
    from datetime import datetime

    from trendin.common.collect.flow import SourceOutcome
    from trendin.common.collect.ledger import EmittedStats

    evt = load(name)
    fields = ("discovered", "stored", "skipped", "not_modified", "failed", "failed_by_stage",
              "failures", "duration_ms", "members_only_stored")
    outcome = None
    if evt["status"] == "success":
        outcome = SourceOutcome.from_dict({
            "source": evt["source_id"], "domain": evt["domain"],
            **{key: evt[key] for key in fields},
        })
    else:
        assert all(evt[key] is None for key in fields)
    oldest = evt["emitted_oldest_collected_at"]
    rebuilt = run_summary_event(
        source=evt["source_id"], domain=evt["domain"], run_id=evt["run_id"],
        logical_date=datetime.fromisoformat(evt["run_started_at"]), status=evt["status"],
        outcome=outcome,
        emitted=EmittedStats(evt["emitted"], datetime.fromisoformat(oldest) if oldest else None),
        failure_reason=evt["failure_reason"],
    )
    assert rebuilt == evt


def test_요약_fixture는_수집보다_많은_이월_발급을_담는다():
    evt = load("collect-run-summary-success.json")
    assert "object_key" not in evt and "record_count" not in evt
    assert evt["stored"] == 1
    assert evt["emitted"] == 12
    assert evt["failed"] == 2
    assert len(evt["failures"]) == 2
    assert evt["emitted_oldest_collected_at"] == "2026-09-01T11:10:00+09:00"


def test_기사_이벤트의_run_id_는_발급한_실행이다(article_evt):
    """이름은 소비 측 `EVENT_SCHEMA` 그대로, 뜻은 발급 실행이다 (`02 §2`)."""
    assert article_evt["run_id"] == "20260903T100000"
    assert article_evt["article_id"]


@pytest.fixture
def verifier():
    import importlib.util

    path = CONTRACT.parents[3] / "scripts" / "verify-spark-integration.py"
    spec = importlib.util.spec_from_file_location("verify_spark_integration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_연동_검증도_새_요약_봉투를_받고_토픽_사이_파티션을_비교하지_않는다(verifier):
    event = load("collect-run-summary-success.json")
    verifier.verify_event(event, spark_s3=None, bucket="raw-data", label="요약", summary=True)
    assert verifier.fail == 0
    verifier.verify_kafka_placement([
        (load("article-event.json"), {"topic": "raw-file-ready", "key": "vogue", "partition": 4}),
        (event, {"topic": "collect-run-summary", "key": "vogue", "partition": 0}),
    ])
    assert verifier.fail == 0
    # 기사 토픽에 요약이 잘못 들어오면 object_key=null로 요약이라고 받아들이면 안 된다.
    verifier.verify_event(event, spark_s3=None, bucket="raw-data", label="오발급", summary=False)
    assert verifier.fail > 0


@pytest.mark.parametrize("summary_topic", ["", "collect-run-summary"])
def test_연동_fixture_발행은_요약을_기사_토픽에_섞지_않는다(verifier, monkeypatch, summary_topic):
    from types import SimpleNamespace

    published = {}
    monkeypatch.setattr(verifier, "s3_client",
                        lambda *args: SimpleNamespace(put_object=lambda **kw: None))
    monkeypatch.setattr(verifier, "publish",
                        lambda bootstrap, topic, events: published.setdefault(topic, events))

    def consume(bootstrap, topic, **kw):
        return [(event, {"topic": topic, "key": event["source_id"], "partition": 0})
                for event in published[topic]]

    monkeypatch.setattr(verifier, "consume", consume)
    monkeypatch.setattr(verifier, "verify_event", lambda *args, **kw: None)
    monkeypatch.setattr(verifier, "verify_read_only", lambda *args: None)
    monkeypatch.setattr(verifier, "cleanup", lambda *args: None)
    verifier.run_fixture_mode(dict(
        crawler_key="fake", crawler_secret="fake", spark_key="fake", spark_secret="fake",
        minio_endpoint="fake", bucket="raw-data", bootstrap="fake",
        topic="raw-file-ready", summary_topic=summary_topic,
    ))
    assert len(published["raw-file-ready"]) == 1
    assert published["raw-file-ready"][0]["run_id"]
    if summary_topic:
        assert len(published[summary_topic]) == 2
        assert all("object_key" not in e for e in published[summary_topic])
    else:
        assert set(published) == {"raw-file-ready"}
    assert verifier.fail == 0


@pytest.mark.parametrize("field", ["bucket", "collected_at"])
@pytest.mark.parametrize("value", ["missing", None, ""])
def test_기사_필수_필드는_객체가_정상이어도_비어_있으면_검증에_실패한다(verifier, field, value):
    import io

    class FixtureS3:
        def get_object(self, *, Bucket, Key):
            assert Bucket == "raw-data"
            return {"Body": io.BytesIO((OBJECTS / Key).read_bytes())}

    event = load("article-event.json")
    verifier.verify_event(event, spark_s3=FixtureS3(), bucket="raw-data",
                          label="정상 기사", summary=False)
    assert verifier.fail == 0

    if value == "missing":
        del event[field]
    else:
        event[field] = value
    verifier.verify_event(event, spark_s3=FixtureS3(), bucket="raw-data",
                          label="필수 필드 누락", summary=False)
    assert verifier.fail == 1
