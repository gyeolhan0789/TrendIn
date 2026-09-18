"""국가 코드 한 벌. 원자료의 국가 칸과 `keyword_country_daily_metrics` 가 함께 쓴다.

**국가는 기사가 아니라 소스의 속성이고, 값은 발행 법인의 소재지다.** 본문 언어도 기사
주제도 아니다 — 한국 매체가 쓴 파리 패션위크 기사는 `KR` 이다. 지금 쓸 수 있는 유일한
정의이고, 화면 문구가 이 뜻과 어긋나면 문구를 고칠 일이다.

값이 오는 길은 이렇다.

```
SourceDef.country → collect_source_country → 장부 뷰 → 봉투 source_country
  → curated (스물세 칸)
  → pl_document_candidate · pl_keyword_daily_stat
  → keyword_country_daily_metrics
```

⚠️ **`UNKNOWN_COUNTRY` 는 세 곳에 같은 리터럴로 있다.** 수집의
`common/collect/contracts.UNKNOWN_COUNTRY` 와 장부 뷰의 `coalesce(country, 'XX')`, 그리고
여기다. 한 벌로 모으지 못하는 이유가 층마다 다르다 — 뷰 쪽은 DDL 이 f-string 이 아니고
(중괄호가 전부 포맷 자리가 된다), 이쪽은 **Spark 층이 수집 층을 import 하지 않는다**는
경계 때문이다. 그 경계는 지금 어디서도 깨지지 않았고 깨뜨릴 값이 없다. 대신
`tests/unit/test_countries.py` 가 세 리터럴이 같은지 본다.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import Column

# 판정할 수 없는 소스의 국가. ISO 3166-1 의 사용자 지정 영역이라 "미지정" 을 뜻하고,
# 서비스 표의 `^[A-Z]{2}$` 제약(`V4__keyword_country_daily_metrics.sql`)을 통과한다.
#
# **`NULL` 을 쓰지 않는다.** "아직 안 붙였다" 와 "붙일 수 없다" 를 구분하지 못하기 때문이고,
# 원자료에서는 이 칸이 기본키에 들어가 `NULL` 이 애초에 허용되지 않는다 — PostgreSQL 에서
# `NULL` 은 서로 같지 않아 같은 키워드의 같은 날짜가 여러 행이 된다.
UNKNOWN_COUNTRY = "XX"

# ISO 3166-1 alpha-2. DB 제약과 같은 규칙이다.
COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")


def normalize_country(value: str | None) -> str:
    """국가 코드를 기본키에 넣을 수 있는 모양으로 접는다. 모르면 `UNKNOWN_COUNTRY`.

    `curated.source_country` 가 nullable 이라 `None` 이 온다. 백필 경로(모드 B)가 옛 객체를
    되읽을 때 그렇고, 국가 칸이 생기기 전에 쓰인 파티션도 그렇다. 소문자로 온 값은 대문자로
    올린다 — 프로필 로더가 이미 막지만, 거기를 통과하지 않는 경로(백필)가 있다.

    **모양이 틀린 값을 그대로 흘리지 않는다.** 흘리면 적재 끝에서
    `ck_keyword_country_daily_metrics_country_code` 위반으로 터지고, 증상이 원인에서 네 층
    떨어진 자리에 나타난다. `UK` 같은 오기는 두 글자 대문자라 이 함수로는 안 걸린다 —
    ISO 화이트리스트는 백엔드에 요청해 두었다.
    """
    if value is None:
        return UNKNOWN_COUNTRY
    folded = value.strip().upper()
    return folded if COUNTRY_CODE.fullmatch(folded) else UNKNOWN_COUNTRY


def country_column(source: "Column") -> "Column":
    """`normalize_country` 와 **같은 규칙**의 Spark 표현식. 추출 배치가 쓴다.

    파이썬 함수를 UDF 로 감싸지 않는 이유는 한 행씩 직렬화할 값이 없기 때문이고, 두 벌로
    가르지 않는 이유는 규칙이 갈리면 원자료와 적재가 다른 나라를 말하게 되기 때문이다.
    `tests/unit/test_countries.py` 가 같은 입력으로 양쪽을 대조한다.
    """
    from pyspark.sql import functions as F

    folded = F.upper(F.trim(source))
    return (
        F.when(folded.rlike(COUNTRY_CODE.pattern), folded)
        .otherwise(F.lit(UNKNOWN_COUNTRY))
        .alias("source_country")
    )
