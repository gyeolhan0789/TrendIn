"""연관 키워드 ([06]) — 같은 문서에 함께 나온 정도를 잰다.

`aggregate` 의 다른 지표가 `pl_keyword_daily_stat` 을 읽는 것과 달리, 연관은
**`keyword_contents` 를 읽는다.** 원자료는 (도메인, 비교키, 날짜) 단위라 문서 정체성이
없어서 "같은 문서에 함께 나왔다" 를 물을 수 없다. `keyword_contents (content_id,
keyword_id)` 는 승격된 키워드의 문서별 출현이라 그 질문에 바로 답한다.

## 자카드를 쓰는 이유

`함께 나온 문서 수 ÷ 둘 중 하나라도 나온 문서 수` 이고 100 을 곱해 싣는다.

- **범위가 저절로 맞는다.** `relation_score` 는 `numeric(5,2)` 에 `BETWEEN 0 AND 100`
  제약이 걸려 있고, 자카드는 0~1 이라 100 을 곱하면 그대로 들어간다.
- **흔한 키워드가 상위를 먹지 않는다.** 단순 공기 문서 수로 재면 `드레스` 처럼 어디에나
  나오는 말이 모든 키워드의 1위가 된다.
- **대칭이다.** 표의 PK 가 `(source, target)` 이라 양방향으로 두 행을 넣는데, 비대칭
  산식이면 방향마다 값이 달라 조회하는 쪽이 어느 방향을 봐야 하는지 알아야 한다.

정규화 PMI 도 후보였다. 드문 쌍을 잘 드러내지만 관측이 적을 때 값이 튀어서 하한 관측 수를
따로 둬야 하고, 그 값을 정하려면 코퍼스가 차야 한다.

## 포함 관계를 빼는 이유

**옛 측정에서 연관 1위의 24% 가 자기 표기의 조각이었다** — `샤넬` 과 `샤넬 백` 은 늘 같은
문서에 나오므로 자카드가 1 에 가깝고, 그래서 어떤 키워드를 눌러도 자기 자신의 변형이 먼저
나온다. 코퍼스가 커지면 더 나빠진다. 비교 이름이 서로를 포함하는 쌍을 아예 뺀다.

이것은 병합([05])이 못 잡은 쌍을 연관에서 다시 막는 것이라 **두더지잡기가 아니라 같은
결함의 두 번째 방어선**이다. 병합이 좋아지면 이 규칙에 걸리는 쌍이 줄어든다.

**`pyspark` 를 import 하지 않는다** ([09 §4] 층 1). SQL 문자열과 설정만 만든다.
"""

from __future__ import annotations

from dataclasses import dataclass

from trendin.spark.common.config import Config, ConfigError

SECTION = "aggregate.relations"

# 서비스 표 ([08 §4]). 백엔드가 소유하고 우리가 채운다.
RELATIONS = "keyword_relations"
RELATION_COLUMNS = (
    "source_keyword_id",
    "target_keyword_id",
    "relation_score",
    "co_occurrence_count",
    "updated_at",
)


@dataclass(frozen=True, slots=True)
class RelationThresholds:
    """[06] 의 숫자. **코퍼스가 차기를 기다릴 값이 아니다** — 창 길이는 기획이 정했고
    나머지 둘은 표 크기를 묶는 값이라 분포를 보고 정할 성질이 아니다."""

    # 동시출현을 세는 창. 지표의 가장 긴 기간(`30D`)과 맞춘다 — 연관만 다른 기간을 보면
    # 화면에서 "30일 지표" 와 "연관" 이 서로 다른 시기를 말하게 된다.
    window_days: int = 30
    # 쌍이 관측된 문서 수의 하한. **1 을 허용하면 안 된다** — 문서 한 건에만 함께 나온 쌍도
    # 둘 다 그 문서에만 있으면 자카드가 100 이 되어 상위를 차지한다.
    min_co_occurrence: int = 2
    # 키워드 하나가 갖는 연관의 수. 표가 쌍의 제곱으로 커지는 것을 여기서 묶는다.
    top_n: int = 20

    @classmethod
    def from_config(cls, config: Config) -> "RelationThresholds":
        section = config.section(SECTION)
        default = cls()
        thresholds = cls(
            window_days=int(section.get("window_days", default.window_days)),
            min_co_occurrence=int(section.get("min_co_occurrence", default.min_co_occurrence)),
            top_n=int(section.get("top_n", default.top_n)),
        )
        if thresholds.window_days < 1:
            raise ConfigError("aggregate.relations.window_days 는 1 이상이어야 한다")
        if thresholds.min_co_occurrence < 2:
            raise ConfigError(
                "aggregate.relations.min_co_occurrence 는 2 이상이어야 한다 — "
                "1 이면 한 문서에만 함께 나온 쌍이 자카드 100 으로 상위를 먹는다"
            )
        if thresholds.top_n < 1:
            raise ConfigError("aggregate.relations.top_n 은 1 이상이어야 한다")
        return thresholds


# 창 안의 쌍을 세어 자카드를 매기고 키워드당 상위 N 을 돌려준다.
#
# **집계를 파이썬으로 끌고 오지 않는다.** 쌍은 문서당 후보 수의 제곱으로 늘어 수십만 행이
# 되는데, 그것을 파이썬으로 옮기면 자카드 나눗셈 하나를 하려고 전량을 실어 나르게 된다.
# `aggregate` 가 "집계는 PostgreSQL, 판정은 순수 파이썬" 인 것과 같은 이유다.
#
# `b.keyword_id > a.keyword_id` 로 **쌍을 한 번만 센다.** 자기 자신과의 쌍도 이걸로 빠진다.
RELATION_SQL = """
WITH recent AS (
    SELECT kc.keyword_id, kc.content_id
    FROM keyword_contents kc
    JOIN contents c ON c.id = kc.content_id
    WHERE c.published_at >= %(since)s AND c.published_at < %(until)s
),
df AS (
    SELECT keyword_id, count(*) AS docs
    FROM recent
    GROUP BY keyword_id
),
pairs AS (
    SELECT a.keyword_id AS lo, b.keyword_id AS hi, count(*) AS co
    FROM recent a
    JOIN recent b ON b.content_id = a.content_id AND b.keyword_id > a.keyword_id
    GROUP BY a.keyword_id, b.keyword_id
    HAVING count(*) >= %(min_co)s
),
scored AS (
    SELECT p.lo, p.hi, p.co,
           round(100.0 * p.co / (dlo.docs + dhi.docs - p.co), 2) AS score
    FROM pairs p
    JOIN df dlo ON dlo.keyword_id = p.lo
    JOIN df dhi ON dhi.keyword_id = p.hi
    JOIN keywords klo ON klo.id = p.lo
    JOIN keywords khi ON khi.id = p.hi
    -- 포함 관계 제외 (모듈 주석). `position` 이 0 이면 부분 문자열이 아니다.
    WHERE position(klo.normalized_name IN khi.normalized_name) = 0
      AND position(khi.normalized_name IN klo.normalized_name) = 0
),
-- 양방향으로 편다. 표의 PK 가 `(source, target)` 이고 조회는 `source` 로 들어오므로 쌍
-- 하나가 두 행이 된다. **CTE 이름을 `both` 로 두면 안 된다** — `TRIM(BOTH ...)` 의 예약어라
-- `syntax error at or near "both"` 로 죽는다.
directed AS (
    SELECT lo AS src, hi AS tgt, co, score FROM scored
    UNION ALL
    SELECT hi AS src, lo AS tgt, co, score FROM scored
),
ranked AS (
    SELECT src, tgt, co, score,
           -- 동점에서 `tgt` 까지 보는 이유 — 순서가 흔들리면 같은 입력이 실행마다 다른
           -- 상위 N 을 낸다.
           row_number() OVER (
               PARTITION BY src ORDER BY score DESC, co DESC, tgt
           ) AS rn
    FROM directed
)
SELECT src, tgt, score, co
FROM ranked
WHERE rn <= %(top_n)s
ORDER BY src, rn
"""
