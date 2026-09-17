#!/usr/bin/env python
"""크롤러 → Kafka → MinIO 연동 검증 (S15P21A102-159 AC 2·3·4).

계약은 `docs/spark-integration.md`. 이 스크립트는 그 문서가 적어 둔 것이 실제로 그런지
확인한다 — 봉투가 파싱되고, `object_key` 로 원문이 읽히고, `checksum` 이 맞고, Spark 키로는
쓰기가 안 되는지.

```sh
cd pipeline
./scripts/dev-setup.sh                          # 한 번. boto3·confluent-kafka 가 필요하다
.venv/bin/python scripts/verify-spark-integration.py         # fixture 모드 (기본)
.venv/bin/python scripts/verify-spark-integration.py --live   # 토픽에 쌓인 실제 수집 이벤트
```

**두 모드가 있는 이유** — fixture 모드는 크롤러를 돌리지 않고 계약만 확인한다(빠르고 어디서나
된다). `--live` 는 실제 크롤링 1회분이 소비 측까지 도달하는 것을 확인한다(AC 3). 크롤러를 한
번 돌린 뒤에 쓴다.

**셸이 아니라 Python 인 이유** — `datastore/scripts/verify.sh` 는 저장소가 살아 있는지만 보므로
`mc` 로 충분하다. 여기는 봉투에서 `object_key` · `checksum` 을 뽑아 대조해야 하는데 `mc` 이미지에
`grep` · `sed` · `awk` 가 없다. 그리고 이 경로는 소비 측이 실제로 쓰는 경로(read 전용 키 +
path-style S3 클라이언트)라, 같은 클라이언트로 확인하는 편이 낫다.

**호스트에서 돈다.** 컨테이너 밖이라 EXTERNAL 리스너와 공개된 MinIO 포트로 붙는다. 주소는
`datastore/.env` 에서 읽으므로 포트를 바꿔도 따라간다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

# Windows 콘솔 기본 코드페이지(cp949)는 이 파일과 계약 문서가 쓰는 문자를 못 찍고
# UnicodeEncodeError 로 죽는다. 검증이 인코딩 때문에 멈추면 안 되므로 여기서 못 박는다.
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
DATASTORE_ENV = REPO / "datastore" / ".env"
FIXTURES = PIPELINE / "spark" / "tests" / "fixtures" / "contract"

# 검증이 만드는 객체는 전부 이 접두어 아래에 둔다. 수집 데이터와 섞이지 않고, 끝에서
# 관리자 키로 지운다 — 크롤러 키에는 삭제 권한이 없다.
VERIFY_PREFIX = "_verify/spark-integration"

# 봉투 두 모양이 공통으로 가진 칸. 하나라도 없으면 계약 위반이다.
REQUIRED = ("event_id", "schema_version", "domain", "source_id", "status")
# 저작권법 제37조 출처 명시. 기사 이벤트에서 절대 비지 않는다 (web-collect.md 불변식 11).
ATTRIBUTION = ("url", "source_id", "published_at")
KNOWN_SCHEMA_VERSIONS = (1,)

fail = 0


def check(ok: bool, label: str, detail: str = "") -> bool:
    global fail
    if not ok:
        fail = 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
    return ok


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        sys.exit(f"{path} 가 없다 — .env.example 을 복사해 채운다")
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def s3_client(access_key: str, secret_key: str, endpoint: str):
    """소비 측이 쓰는 것과 같은 설정. `path` 주소 방식이 필수다 (spark-integration.md §5)."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


# --- 봉투 검증 ------------------------------------------------------------


def verify_event(event: dict, *, spark_s3, bucket: str, label: str, summary: bool) -> None:
    """봉투 하나. 수신한 토픽으로 기사와 요약을 구분한다 (spark-integration.md §3)."""
    missing = [f for f in REQUIRED if event.get(f) in (None, "")]
    check(not missing, f"{label} 공통 필드", f"빈 칸: {missing}" if missing else "")

    version = event.get("schema_version")
    check(
        version in KNOWN_SCHEMA_VERSIONS,
        f"{label} schema_version 이 아는 값",
        f"{version} (아는 값: {KNOWN_SCHEMA_VERSIONS})",
    )

    if summary:
        verify_summary_event(event, label=label)
    else:
        verify_article_event(event, spark_s3=spark_s3, bucket=bucket, label=label)


def verify_summary_event(event: dict, *, label: str) -> None:
    check(event.get("run_id") not in (None, ""), f"{label} 요약: run_id 가 있다")
    status = event.get("status")
    check(status in ("success", "failed"), f"{label} 요약: status", str(status))
    if status == "failed":
        check(bool(event.get("failure_reason")), f"{label} 요약: failed 면 failure_reason 이 있다")
    check(bool(event.get("run_started_at")), f"{label} 요약: logical date 가 있다")
    check("object_key" not in event and "record_count" not in event,
          f"{label} 요약: 기사 봉투 필드가 없다")
    emitted = event.get("emitted")
    check(type(emitted) is int and emitted >= 0, f"{label} 요약: emitted 는 0 이상의 정수")
    check((event.get("emitted_oldest_collected_at") is None) == (emitted == 0),
          f"{label} 요약: 발급 0건일 때만 가장 오래된 수집 시각이 null")
    collection = ("discovered", "stored", "skipped", "not_modified", "failed", "failed_by_stage",
                  "failures", "duration_ms", "members_only_stored", "paywalled_stored")
    check(all(key in event for key in collection), f"{label} 요약: 수집 결과 필드가 있다")
    if status == "failed":
        check(all(event.get(key) is None for key in collection), f"{label} 요약: 죽은 수집은 null")
    else:
        check(all(event.get(key) is not None for key in collection),
              f"{label} 요약: 수집 결과 보존")
        failures = event.get("failures")
        check(isinstance(failures, list) and len(failures) <= 10,
              f"{label} 요약: 실패 표본 10건 상한")
        if isinstance(failures, list):
            check(all(isinstance(f, dict) and isinstance(f.get("reason"), str)
                      and len(f["reason"]) <= 200 for f in failures),
                  f"{label} 요약: 사유 200자 상한")


def verify_article_event(event: dict, *, spark_s3, bucket: str, label: str) -> None:
    # 요약에는 없는 필드지만 기사 봉투에서는 계속 필수다.
    missing = [f for f in ("bucket", "collected_at") if event.get(f) in (None, "")]
    check(not missing, f"{label} 기사: 필수 필드", f"빈 칸: {missing}" if missing else "")
    # 발급한 실행의 값이다 (data-pipeline-design.md §5 필드 규약). 수집한 실행이 아니다.
    check(event.get("run_id") not in (None, ""), f"{label} 기사: run_id 가 있다")
    count = event.get("record_count")
    check(count == 1, f"{label} 기사: record_count=1", str(count))
    blank = [f for f in ATTRIBUTION if not event.get(f)]
    check(not blank, f"{label} 기사: 출처 명시 3종", f"빈 칸: {blank}" if blank else "")

    key = event.get("object_key")
    if not isinstance(key, str) or not key:
        check(False, f"{label} 기사: object_key 가 있다")
        return
    check(True, f"{label} 기사: object_key 가 있다")
    body = read_object(spark_s3, bucket, key, label=f"{label} 기사: object_key 읽기")
    if body is None:
        return

    digest = "sha256-" + hashlib.sha256(body).hexdigest()
    declared = event.get("checksum")
    check(
        digest == declared,
        f"{label} 기사: checksum 대조",
        "" if digest == declared else f"객체={digest} 봉투={declared}",
    )

    try:
        doc = json.loads(body)
    except json.JSONDecodeError as exc:
        check(False, f"{label} 기사: article.json 파싱", str(exc))
        return
    check(True, f"{label} 기사: article.json 파싱")

    # 봉투의 값이 객체의 값과 같아야 소비 측이 봉투만 읽고 처리할 수 있다.
    for evt_field, doc_field in (("url", "url"), ("title", "title"), ("article_id", "article_id")):
        same = event.get(evt_field) == doc.get(doc_field)
        check(same, f"{label} 기사: 봉투.{evt_field} == article.json.{doc_field}")

    raw_key = event.get("raw_object_key")
    if raw_key:
        read_object(spark_s3, bucket, raw_key, label=f"{label} 기사: raw_object_key 읽기")
    else:
        # 회원 전용·유료 표시 기사는 raw 를 저장하지 않는다 (불변식 2).
        check(
            event.get("members_only") is True or event.get("paywalled") is True,
            f"{label} 기사: raw 가 없으면 members_only 나 paywalled 다",
            f"members_only={event.get('members_only')} paywalled={event.get('paywalled')}",
        )


def read_object(spark_s3, bucket: str, key: str, *, label: str) -> bytes | None:
    """성공도 PASS 로 찍는다. 조용히 지나가면 무엇을 확인했는지 출력에서 알 수 없다."""
    try:
        body = spark_s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception as exc:  # noqa: BLE001 — 무엇이 와도 FAIL 로 찍고 계속 간다
        check(False, label, f"{type(exc).__name__}: {exc}")
        return None
    check(True, label, f"{len(body)} bytes")
    return body


# --- Kafka ----------------------------------------------------------------


def consume(
    bootstrap: str, topic: str, *, want: set[str] | None, limit: int, timeout_s: float
) -> list[tuple[dict, dict]]:
    """토픽을 처음부터 읽는다. `(봉투, 메시지 메타)` 쌍을 돌려준다.

    메타(`key` · `partition` · `offset`)를 함께 돌려주는 이유는 계약에 message key 와 순서
    보장이 들어 있어서다 (`verify_kafka_placement`). 봉투만 보면 그 부분을 검증할 수 없다.

    `want` 가 있으면 그 `event_id` 들이 다 모일 때까지, 없으면 `limit` 건까지. group 은 매번
    새로 만든다 — 검증이 실제 소비 측의 오프셋을 건드리면 안 된다.
    """
    from confluent_kafka import Consumer, KafkaError

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": f"trendin-verify-{uuid.uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([topic])
    found: list[tuple[dict, dict]] = []
    seen: set[str] = set()
    import time

    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            error = msg.error()
            if error is not None:
                if error.code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"  경고  소비 오류: {error}")
                continue
            payload = msg.value()
            if payload is None:
                continue
            try:
                event = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue  # `_verify` 같은 손으로 넣은 메시지가 섞여 있을 수 있다
            if not isinstance(event, dict):
                continue
            eid = event.get("event_id")
            message_key = msg.key()
            meta = {
                "topic": msg.topic(),
                "key": message_key.decode("utf-8") if message_key else None,
                "partition": msg.partition(),
                "offset": msg.offset(),
            }
            if want is not None:
                if eid in want and eid not in seen:
                    seen.add(eid)
                    found.append((event, meta))
                    if seen >= want:
                        break
            else:
                # fixture 모드가 남긴 이벤트는 실제 수집분이 아니다. 토픽에는 보존
                # 기간(7일)만큼 남아 있는데 그 객체는 검증 끝에 지워지므로, 여기서 걸러내지
                # 않으면 `--live` 가 "원문을 못 읽는다" 로 실패한다.
                if eid and eid != "_verify" and not eid.startswith(VERIFY_PREFIX):
                    found.append((event, meta))
                    if len(found) >= limit:
                        break
    finally:
        consumer.close()
    return found


def verify_kafka_placement(records: list[tuple[dict, dict]]) -> None:
    """message key 와 순서 보장 (spark-integration.md §2).

    봉투만 봐서는 확인할 수 없는 부분이다. 계약이 *"같은 소스의 이벤트는 한 파티션에 모여
    순서가 보장된다"* 고 적어 놓았으므로, 그 말이 실제로 참인지 여기서 본다.

    파티션이 소스마다 배타적이라고는 하지 않는다 — key 해시가 겹치면 여러 소스가 한 파티션을
    같이 쓴다. 보장되는 것은 **key 단위 순서**다.
    """
    import collections

    mismatched = [
        (event.get("event_id"), meta["key"], event.get("source_id"))
        for event, meta in records
        if meta["key"] != event.get("source_id")
    ]
    check(
        not mismatched,
        "message key == source_id",
        f"불일치 {len(mismatched)}건: {mismatched[:3]}" if mismatched else f"{len(records)}건 확인",
    )

    partitions: dict[tuple[str, str], set[int]] = collections.defaultdict(set)
    for event, meta in records:
        source = event.get("source_id")
        if isinstance(source, str):
            partitions[(meta["topic"], source)].add(meta["partition"])
    split = {src: sorted(parts) for src, parts in partitions.items() if len(parts) > 1}
    check(
        not split,
        "토픽별로 같은 소스가 한 파티션에 모인다",
        f"쪼개진 소스: {split}" if split else f"{len(partitions)}개 소스",
    )



def publish(bootstrap: str, topic: str, events: list[dict]) -> None:
    """message key 는 `source_id` 다 (spark-integration.md §2)."""
    from confluent_kafka import Producer

    producer = Producer({"bootstrap.servers": bootstrap, "acks": "all", "enable.idempotence": True})
    errors: list[str] = []

    def on_delivery(err, _msg):
        if err is not None:
            errors.append(str(err))

    for event in events:
        producer.produce(
            topic,
            key=event["source_id"].encode("utf-8"),
            value=json.dumps(event, ensure_ascii=False).encode("utf-8"),
            on_delivery=on_delivery,
        )
    remaining = producer.flush(30.0)
    if remaining or errors:
        sys.exit(f"발행 실패: 남은 {remaining}건, 오류 {errors}")


# --- 모드 -----------------------------------------------------------------


def load_fixtures() -> tuple[list[dict], dict[str, bytes]]:
    """fixture 를 읽고, 객체 키를 `_verify/` 아래로 옮긴다.

    실제 키(`fashion/vogue/...`)에 올리면 합성 샘플이 수집 데이터 자리에 섞인다. 봉투의
    나머지 칸은 손대지 않으므로 `checksum` 은 그대로 유효하다.
    """
    events, objects = [], {}
    names = (
        "article-event.json",
        "collect-run-summary-success.json",
        "collect-run-summary-failed.json",
    )
    for name in names:
        event = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        event["event_id"] = f"{VERIFY_PREFIX}-{event['event_id']}"
        for field in ("object_key", "raw_object_key"):
            if event.get(field):
                original = event[field]
                event[field] = f"{VERIFY_PREFIX}/{original}"
                objects[event[field]] = (FIXTURES / "objects" / original).read_bytes()
        events.append(event)
    return events, objects


def run_fixture_mode(cfg: dict) -> None:
    events, objects = load_fixtures()

    print("[1] fixture 객체를 크롤러 키로 올린다")
    crawler = s3_client(cfg["crawler_key"], cfg["crawler_secret"], cfg["minio_endpoint"])
    for key, body in objects.items():
        try:
            crawler.put_object(Bucket=cfg["bucket"], Key=key, Body=body)
            check(True, f"put {key}")
        except Exception as exc:  # noqa: BLE001
            check(False, f"put {key}", f"{type(exc).__name__}: {exc}")
    if fail:
        sys.exit("객체를 올리지 못했다. 나머지는 건너뛴다.")

    print("[2·3] 토픽별로 fixture 를 발행하고 되읽는다")
    got = []
    for topic, batch in (
        (cfg["topic"], [e for e in events if "object_key" in e]),
        (cfg["summary_topic"], [e for e in events if "run_started_at" in e]),
    ):
        if not topic:
            print("  건너뜀  요약 토픽이 설정되지 않았다")
            continue
        publish(cfg["bootstrap"], topic, batch)
        want = {e["event_id"] for e in batch}
        records = consume(cfg["bootstrap"], topic, want=want, limit=0, timeout_s=60)
        check(len(records) == len(want), f"{topic}: {len(want)}건 회수", f"{len(records)}건 받음")
        got.extend(records)

    print("[4] Kafka 배치와 순서")
    verify_kafka_placement(got)

    print("[5] 봉투와 원문을 검증한다 (Spark read 전용 키)")
    spark = s3_client(cfg["spark_key"], cfg["spark_secret"], cfg["minio_endpoint"])
    for event, meta in got:
        summary = meta["topic"] == cfg["summary_topic"]
        shape = "요약" if summary else "기사"
        verify_event(event, spark_s3=spark, bucket=cfg["bucket"],
                     label=f"[{shape}]", summary=summary)

    print("[6] Spark 키는 쓰기가 안 된다")
    verify_read_only(spark, cfg["bucket"])

    print("[7] 검증 객체를 지운다 (관리자 키)")
    cleanup(cfg, list(objects))


def run_live_mode(cfg: dict, limit: int) -> None:
    print(f"[1] 토픽에서 최대 {limit}건을 읽는다")
    got = consume(cfg["bootstrap"], cfg["topic"], want=None, limit=limit, timeout_s=60)
    if not got:
        sys.exit(
            "토픽에 이벤트가 없다. 크롤러를 한 번 돌린 뒤 다시 실행한다:\n"
            "  docker compose -f pipeline/compose.yaml run --rm airflow-cli "
            "airflow dags test fashion_collect"
        )
    if cfg["summary_topic"]:
        got.extend(consume(cfg["bootstrap"], cfg["summary_topic"],
                           want=None, limit=limit, timeout_s=60))
    articles = [e for e, m in got if m["topic"] == cfg["topic"]]
    summaries = [e for e, m in got if m["topic"] == cfg["summary_topic"]]
    check(True, f"{len(got)}건 읽음", f"기사 {len(articles)}건, 요약 {len(summaries)}건")
    # AC 3 — 실제 크롤링 1회분의 본문이 소비 측까지 도달했는지가 이 줄이다.
    check(
        bool(articles),
        "기사 이벤트가 하나 이상 있다",
        "" if articles else "요약만 왔다 — 수집된 기사가 없다",
    )

    print("[2] Kafka 배치와 순서")
    verify_kafka_placement(got)

    print("[3] 봉투와 원문을 검증한다 (Spark read 전용 키)")
    spark = s3_client(cfg["spark_key"], cfg["spark_secret"], cfg["minio_endpoint"])
    for event, meta in got:
        summary = meta["topic"] == cfg["summary_topic"]
        shape = "요약" if summary else "기사"
        label = f"[{shape} {event['event_id']}]"
        verify_event(event, spark_s3=spark, bucket=cfg["bucket"], label=label, summary=summary)

    print("[4] Spark 키는 쓰기가 안 된다")
    verify_read_only(spark, cfg["bucket"])


def verify_read_only(spark_s3, bucket: str) -> None:
    """성공하면 안 된다. 성공하면 정책이 잘못 붙은 것이다 (AC 4)."""
    try:
        spark_s3.put_object(Bucket=bucket, Key=f"{VERIFY_PREFIX}/should-fail", Body=b"x")
    except Exception as exc:  # noqa: BLE001
        check(True, "Spark 키 write 거부", type(exc).__name__)
        return
    check(False, "Spark 키로 쓰기가 성공했다 — minio-init 의 spark-read 정책을 확인한다")


def cleanup(cfg: dict, keys: list[str]) -> None:
    """크롤러 키에는 삭제 권한이 없다. 관리자 키로 지운다."""
    admin = s3_client(cfg["root_user"], cfg["root_password"], cfg["minio_endpoint"])
    for key in keys + [f"{VERIFY_PREFIX}/should-fail"]:
        try:
            admin.delete_object(Bucket=cfg["bucket"], Key=key)
        except Exception:  # noqa: BLE001, S110 — 지우지 못해도 수명 주기가 90일에 정리한다
            pass
    check(True, f"{len(keys)}개 삭제")


def main() -> None:
    parser = argparse.ArgumentParser(description="크롤러 → Kafka → MinIO 연동 검증")
    parser.add_argument(
        "--live",
        action="store_true",
        help="토픽에 쌓인 실제 수집 이벤트를 검증한다 (AC 3). 기본은 fixture 모드",
    )
    parser.add_argument("--limit", type=int, default=20, help="--live 에서 읽을 최대 건수")
    args = parser.parse_args()

    env = load_env(DATASTORE_ENV)
    pipeline_env_path = PIPELINE / ".env"
    pipeline_env = load_env(pipeline_env_path) if pipeline_env_path.is_file() else {}
    kafka_host = env.get("KAFKA_EXTERNAL_HOST", "127.0.0.1")
    kafka_port = env.get("KAFKA_EXTERNAL_PORT", "29092")
    cfg = {
        "bucket": env.get("MINIO_BUCKET", "raw-data"),
        "topic": env.get("KAFKA_TOPIC_RAW_FILE_READY", "raw-file-ready"),
        "summary_topic": pipeline_env.get("TRENDIN_KAFKA_TOPIC_RUN_SUMMARY", "").strip(),
        # 컨테이너 밖이라 EXTERNAL 리스너와 공개 포트로 붙는다.
        "bootstrap": f"{kafka_host}:{kafka_port}",
        "minio_endpoint": f"http://127.0.0.1:{env.get('MINIO_API_PORT', '9000')}",
        "crawler_key": env.get("MINIO_CRAWLER_ACCESS_KEY", ""),
        "crawler_secret": env.get("MINIO_CRAWLER_SECRET_KEY", ""),
        "spark_key": env.get("MINIO_SPARK_ACCESS_KEY", ""),
        "spark_secret": env.get("MINIO_SPARK_SECRET_KEY", ""),
        "root_user": env.get("MINIO_ROOT_USER", ""),
        "root_password": env.get("MINIO_ROOT_PASSWORD", ""),
    }
    for name in ("crawler_key", "crawler_secret", "spark_key", "spark_secret"):
        if not cfg[name]:
            sys.exit(f"datastore/.env 의 {name} 이 비어 있다")

    print(f"토픽 {cfg['topic']} @ {cfg['bootstrap']}")
    print(f"버킷 {cfg['bucket']} @ {cfg['minio_endpoint']}")
    print()

    if args.live:
        run_live_mode(cfg, args.limit)
    else:
        run_fixture_mode(cfg)

    print()
    if fail:
        print("실패한 항목이 있다. 위 FAIL 을 확인한다.")
        sys.exit(1)
    print("전부 통과.")


if __name__ == "__main__":
    main()
