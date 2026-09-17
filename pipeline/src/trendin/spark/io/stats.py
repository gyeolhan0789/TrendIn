"""`pl_batch_stat` — 버린 것과 고친 것을 센다.

규격은 [03 §7](../../../../spark/docs/03-normalization-spec.md) 과 [08 §3] 이다.

**필터로 사라진 문서를 조용히 넘기지 않는다.** 생존율이 갑자기 떨어지면 소스가 HTML 구조를
바꿨거나 생산자 어댑터가 깨진 것이고, 이 숫자가 없으면 "왜 이번 주 언급량이 줄었지" 에
답할 수 없다.

**표를 좁고 길게 둔다** — `(실행, 지표, 차원) → 값` 이다. 지표마다 컬럼을 두면 [03 §7] 의
목록이 늘 때마다 DDL 이 바뀌고, 그때 옛 행은 새 컬럼이 `NULL` 이라 "0 건" 과 "안 셌음" 이
구분되지 않는다. 좁은 표에서는 행이 없는 것이 곧 안 셌음이다.

**Spark 를 거치지 않고 드라이버에서 직접 넣는다.** 행이 서른 개 안팎이라 스테이징 테이블을
왕복할 값이 없다 — [08 §4] 가 "서비스 테이블은 스테이징, 내부 잡다한 것은 자유" 로 허용한
자리다. 서비스 테이블이 아니고, 한 트랜잭션으로 들어간다.

**실행 단위로 한 번 쓴다.** `Trigger.AvailableNow` 는 마이크로배치를 여럿 낼 수 있고 그 배치들이
같은 `ingest_run_id` 를 쓴다. 배치마다 upsert 하면 뒤 배치가 앞 배치 값을 덮고, 재처리에서
사라진 `(metric, dimension)` 행은 아무도 지우지 않는다. 그래서 `RunStats` 가 배치마다 원자료
건수를 메모리에 누적하고, 실행 끝에 `BatchStats.replace()` 가 그 실행의 행을 지우고 다시
넣는다 — `curated` · `contents` 쓰기가 전부 끝난 뒤라, 쓰기가 죽은 실행의 통계는 남지 않는다.
비율(`survival_rate`)과 분포(`body_len_*`)는 누적한 원자료에서 그때 다시 계산한다.

**[02 §4] 의 `(일자, 소스)` 수집 상태는 여기 없다.** 같은 표를 쓰지만([08 §3]) 근거가
처리 이력의 요약 이벤트라 정제 통계와 출처가 다르다. 이 묶음(S3)의 범위는 정제 통계까지고,
수집 상태 집계는 그 표에 지표 계열 하나를 더하는 별도 작업이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc
from trendin.spark.io.ledger import safe_job
from trendin.spark.normalize.adapters.protocol import BASIS_BODY

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

TABLE = "pl_batch_stat"

# 지표 이름. **값이 곧 집계 키다** — 바꾸면 옛 실행의 행과 이어지지 않는다.
INPUT = "input"
KEPT = "kept"
SURVIVAL_RATE = "survival_rate"
EXCLUDED = "excluded"
NEAR_DUPLICATE = "near_duplicate"
BODY_MISSING = "body_missing"
PUBLISHED_AT_CORRECTED = "published_at_corrected"
LANG = "lang"
BODY_LEN_AVG = "body_len_avg"
BODY_LEN_P50 = "body_len_p50"
BODY_LEN_P90 = "body_len_p90"
BODY_LEN_MAX = "body_len_max"
# 백필 전용 ([02 §6] 모드 B). 목록 조회 시점에 이미 아는 것이라 정제 집계와 출처가 다르다.
BACKFILL_LISTED = "backfill_listed"
# checksum 메타데이터가 없어 검증을 건너뛴 객체 수. 그 규약이 확정되기 전에 올라간 것들이다 —
# 없는 값을 실패로 처리하면 옛 객체를 재처리에서 통째로 버리므로 통과시키고 여기 센다.
BACKFILL_CHECKSUM_MISSING = "backfill_checksum_missing"

# 본문 없는 문서의 차원. [03 §7] 이 "`members_only` / `route=api` 별로" 를 요구한다 —
# 둘을 합치면 회원 전용 판별이 깨졌는지 알 수 없다. 유료 표시도 같은 이유로 따로 센다.
BODY_MISSING_MEMBERS_ONLY = "members_only"
BODY_MISSING_PAYWALLED = "paywalled"
BODY_MISSING_ROUTE_API = "route=api"
BODY_MISSING_UNEXPECTED = "unexpected"

# 차원이 없는 지표의 자리. `NULL` 이 아니라 빈 문자열인 이유는 PK 에 들어가기 때문이다 —
# PostgreSQL 에서 `NULL` 은 서로 같지 않아 같은 지표가 여러 행이 된다.
NO_DIMENSION = ""

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    -- 생산자의 `run_id` 가 아니라 이 Job 의 실행 식별자다 ([01 §3]).
    ingest_run_id text             NOT NULL,
    job           text             NOT NULL,
    metric        text             NOT NULL,
    -- 사유 · 언어 · route 같은 분해축. 없는 지표는 빈 문자열이다.
    dimension     text             NOT NULL,
    value_num     double precision NOT NULL,
    recorded_at   timestamptz      NOT NULL,
    PRIMARY KEY (ingest_run_id, job, metric, dimension)
);

-- "지난 2주 생존율이 어떻게 움직였나" 를 보는 조회가 쓴다.
CREATE INDEX IF NOT EXISTS pl_batch_stat_metric_idx ON {TABLE} (job, metric, recorded_at);
"""

# 같은 실행을 다시 돌리면 그 실행의 행을 **통째로** 갈아치운다. upsert 로 덮기만 하면 재처리에서
# 사라진 `(metric, dimension)` 행이 옛 값으로 남는다 — 첫 실행에서 `SHORT_BODY=3` 이었다가
# 재처리에서 0 건이 되면 그 행이 그대로 3 으로 보인다. 더하지 않는 이유는 `--force` 재처리가
# 같은 `ingest_run_id` 로 같은 문서를 다시 세기 때문이다.
DELETE_RUN_SQL = f"DELETE FROM {TABLE} WHERE ingest_run_id = %s AND job = %s"
INSERT_SQL = f"""
INSERT INTO {TABLE} (ingest_run_id, job, metric, dimension, value_num, recorded_at)
VALUES (%s, %s, %s, %s, %s, now())
"""


@dataclass(frozen=True, slots=True)
class Stat:
    """지표 한 줄."""

    metric: str
    dimension: str
    value: float


class BatchStats:
    """`pl_batch_stat` 한 곳."""

    def __init__(self, config: Config, *, job: str) -> None:
        self._config = config
        self._job = safe_job(job)

    def ensure_schema(self) -> None:
        jdbc.execute(self._config, DDL)
        log.info("배치 통계 스키마 확인: %s", TABLE)

    def replace(self, stats: Iterable[Stat], *, ingest_run_id: str) -> int:
        """이 실행의 통계를 통째로 갈아치운다 — 한 트랜잭션. 넣은 행 수를 돌려준다.

        실행 끝에 한 번 부른다 (`spark/jobs/ingest.py`). 배치마다 부르면 뒤 배치가 앞 배치를
        지운다 — 배치 누적은 `RunStats` 의 일이다.
        """
        rows = [
            (ingest_run_id, self._job, stat.metric, stat.dimension, float(stat.value))
            for stat in stats
        ]
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(DELETE_RUN_SQL, (ingest_run_id, self._job))
            if rows:
                cur.executemany(INSERT_SQL, rows)
        log.info("배치 통계 기록: run=%s %d개", ingest_run_id, len(rows))
        return len(rows)


def _counts_by(frame: "DataFrame", column: str) -> dict[str, int]:
    from pyspark.sql import functions as F

    rows = frame.groupBy(column).agg(F.count(F.lit(1)).alias("n")).collect()
    return {("" if row[column] is None else str(row[column])): int(row["n"]) for row in rows}


def count_stats(judged: "DataFrame") -> list[Stat]:
    """배치 하나의 **더할 수 있는** 지표 — 건수만. 비율과 분포는 여기 없다.

    입력은 **필터로 떨어뜨리기 전** 프레임이다 — `filter_reason` 이 채워져 있고 버려질 행도
    아직 들어 있다. 떨어뜨린 뒤에 세면 분모(입력 건수)가 사라져 생존율을 계산할 수 없다.

    **집계를 몇 번으로 나눈다.** 지표가 서로 다른 축을 쓰므로(사유 · 언어 · route) 한 번의
    `groupBy` 로는 안 되고, 그렇다고 지표마다 훑으면 배치를 열 번 넘게 읽는다. 부른 쪽이
    프레임을 캐시해 두는 것을 전제한다 (`ingest/normalize.py` 가 그렇게 한다).
    """
    from pyspark.sql import functions as F

    stats: list[Stat] = []

    reasons = _counts_by(judged, "filter_reason")
    received = sum(reasons.values())
    kept = reasons.get("", 0)
    stats.append(Stat(INPUT, NO_DIMENSION, received))
    stats.append(Stat(KEPT, NO_DIMENSION, kept))
    for reason, count in sorted(reasons.items()):
        if reason:
            stats.append(Stat(EXCLUDED, reason, count))

    survivors = judged.where(F.col("filter_reason") == "")

    # 3 단계는 행을 버리지 않으므로 `filter_reason` 에 안 잡힌다. 따로 센다.
    stats.append(
        Stat(NEAR_DUPLICATE, NO_DIMENSION, survivors.where(F.col("dup_of").isNotNull()).count())
    )

    stats.append(
        Stat(
            PUBLISHED_AT_CORRECTED,
            NO_DIMENSION,
            judged.where(F.col("published_at_corrected")).count(),
        )
    )

    # 본문 없는 문서 — [03 §7] 이 "이 목록에서 가장 값진 지표" 로 꼽은 것이다. 회원 전용
    # 판별은 `div.membershipLine` 이라는 CSS 선택자 하나에 달려 있고, 매체가 템플릿을 바꾸면
    # 조용히 깨진다. 깨지는 방향이 둘인데 둘 다 나쁘고, 하나는 법적 문제다(불변식 2).
    # 비율이 7.4% 에서 튀면 즉시 담당 1 에게 알린다.
    bodyless = judged.where(F.col("basis") != BASIS_BODY).withColumn(
        "_kind",
        F.when(F.col("members_only"), F.lit(BODY_MISSING_MEMBERS_ONLY))
        .when(F.col("paywalled"), F.lit(BODY_MISSING_PAYWALLED))
        .when(F.col("route") == "api", F.lit(BODY_MISSING_ROUTE_API))
        # 본문이 오기를 기대한 경로인데 없다. 위 둘 중 어느 쪽도 아니면 설명되지 않는 결손이고,
        # 그게 판별이 깨진 신호다.
        .otherwise(F.lit(BODY_MISSING_UNEXPECTED)),
    )
    for kind, count in sorted(_counts_by(bodyless, "_kind").items()):
        stats.append(Stat(BODY_MISSING, kind, count))

    # 토크나이저 선택이 맞는지 ([04 §2]).
    for lang, count in sorted(_counts_by(survivors, "lang").items()):
        stats.append(Stat(LANG, lang, count))

    return stats


def body_lengths(judged: "DataFrame") -> dict[str, list[int]]:
    """route 별 본문 길이 원자료 — 생존한, 본문 있는 문서만.

    분포는 배치 간에 더할 수 없어서 값 자체를 모은다. 하루 수백 건이라([00 §3]) 정수 목록
    하나가 드라이버 메모리에 드는 값은 무시할 만하다. `listing` 소스는 기사 페이지 HTML 을
    파싱한 결과라 마스크·관련기사가 섞여 들어올 수 있고, 생산자가 걷어낸 것이 계속 듣고
    있는지를 이 분포가 본다.
    """
    from pyspark.sql import functions as F

    rows = (
        judged.where((F.col("filter_reason") == "") & (F.col("basis") == BASIS_BODY))
        .select("route", "content_len")
        .collect()
    )
    lengths: dict[str, list[int]] = {}
    for row in rows:
        route = "" if row["route"] is None else str(row["route"])
        lengths.setdefault(route, []).append(int(row["content_len"] or 0))
    return lengths


def _percentile(sorted_values: list[int], fraction: float) -> float:
    """nearest-rank. `percentile_approx` 와 같이 실제 값 중 하나를 돌려준다."""
    if not sorted_values:
        return 0.0
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return float(sorted_values[rank - 1])


def length_stats(route: str, lengths: list[int]) -> list[Stat]:
    """한 route 의 본문 길이 분포 넷 — 평균 · p50 · p90 · 최대."""
    if not lengths:
        return []
    ordered = sorted(lengths)
    return [
        Stat(BODY_LEN_AVG, route, sum(ordered) / len(ordered)),
        Stat(BODY_LEN_P50, route, _percentile(ordered, 0.5)),
        Stat(BODY_LEN_P90, route, _percentile(ordered, 0.9)),
        Stat(BODY_LEN_MAX, route, float(ordered[-1])),
    ]


class RunStats:
    """실행 하나의 통계 누적기. 배치마다 `add_batch`, 끝에 `finalize` 한 번.

    건수는 더하고, 본문 길이는 값을 모으고, 비율은 `finalize` 에서 누적 건수로 다시 계산한다.
    백필처럼 정제 프레임 밖에서 이미 아는 것(`backfill_listed` 등)은 `add` 로 얹는다.

    `INPUT` · `KEPT` 는 배치가 하나도 없어도 0 으로 남는다 — "안 셌음" 과 "0 건" 을 가르는 것이
    좁은 표의 규약이고, 이 둘은 실행이 돌았다면 늘 셌다고 봐야 한다.
    """

    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], float] = {
            (INPUT, NO_DIMENSION): 0.0,
            (KEPT, NO_DIMENSION): 0.0,
        }
        self._lengths: dict[str, list[int]] = {}
        self._extra: list[Stat] = []
        self.batches = 0

    def add_counts(self, stats: Iterable[Stat]) -> "RunStats":
        for stat in stats:
            key = (stat.metric, stat.dimension)
            self._counts[key] = self._counts.get(key, 0.0) + float(stat.value)
        return self

    def add_lengths(self, route: str, lengths: Iterable[int]) -> "RunStats":
        self._lengths.setdefault(route, []).extend(int(value) for value in lengths)
        return self

    def add_batch(self, judged: "DataFrame") -> "RunStats":
        """정제를 마친(필터로 떨어뜨리기 전) 배치 프레임 하나를 누적한다."""
        self.add_counts(count_stats(judged))
        for route, lengths in body_lengths(judged).items():
            self.add_lengths(route, lengths)
        self.batches += 1
        return self

    def add(self, stats: Iterable[Stat]) -> "RunStats":
        """정제 프레임 밖에서 온 지표. 그대로 실린다."""
        self._extra.extend(stats)
        return self

    def finalize(self) -> list[Stat]:
        stats = [
            Stat(metric, dimension, value)
            for (metric, dimension), value in sorted(self._counts.items())
        ]
        received = self._counts[(INPUT, NO_DIMENSION)]
        kept = self._counts[(KEPT, NO_DIMENSION)]
        # 전체 건강도. 0으로 나누지 않는다 — 빈 실행도 정상적으로 온다.
        stats.append(Stat(SURVIVAL_RATE, NO_DIMENSION, (kept / received) if received else 0.0))
        for route, lengths in sorted(self._lengths.items()):
            stats.extend(length_stats(route, lengths))
        stats.extend(self._extra)
        return stats


def collect_stats(judged: "DataFrame") -> list[Stat]:
    """프레임 하나를 실행 전체로 보고 [03 §7] 의 지표를 전부 뽑는다. 테스트와 단발 조회용."""
    return RunStats().add_batch(judged).finalize()
