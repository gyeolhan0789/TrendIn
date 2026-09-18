#!/usr/bin/env python
"""concept — 승격된 키워드를 언어 무관 개념 번호에 붙인다.

```sh
spark/scripts/submit.sh concept --profile local --domain fashion            # 최근 창 전부
spark/scripts/submit.sh concept --profile local --domain fashion --seed     # 초기 사전 넣고 붙인다
spark/scripts/submit.sh concept --profile local --domain fashion --dry-run  # 쓰지 않는다
```

**하는 것** — `src/trendin/spark/concept/` 전부. 서비스 표에서 사전을 읽고, 최근
`concept.window_days` 일의 선별 후보를 기사별로 모아 붙이고, `article_concept` 에 쓰고, 못 붙인
표기를 `pl_unmapped_expression` 에 쌓는다. **LLM 은 없다.**

**매 실행이 창 전체를 다시 붙인다.** `aggregate` 의 소급 재계산과 같은 뜻이다 — 사전이 바뀌면
창 안의 기사는 다음 실행이 저절로 고친다. 결과는 기사·개념 기본키로 upsert 하고, 이번에 처리한
기사에서 더는 안 붙는 개념은 지운다. 그래서 몇 번을 돌려도 행이 늘지 않는다.

**기사 언어는 아직 표기의 문자 체계로 정한다.** `pl_document_candidate` 에 언어 칸이 없다.
한글이면 ko, 가나면 ja, 아랍 문자면 ar, 라틴이면 언어 무관 조회다. 추출이 계약 A 에 `lang` 과
문맥을 실어 주면 그쪽으로 바꾼다 (`docs/concept-layer.md`).

**표는 전부 이 Job 이 만든다.** 개념 표 넷(`pl_concept` · `pl_concept_category` ·
`pl_concept_expression` · `pl_article_concept`)도 서비스 표가 아니라 우리 표다 — 스프링이 읽지
않으므로 Flyway 를 거치지 않는다 (2026-09-17). 백엔드 선행 조건이 없다.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.exit_codes import NOTHING_NEW
from trendin.spark.common.logging import get_logger
from trendin.spark.concept.mapping import Keyword, map_article
from trendin.spark.concept.seed import apply_seed, load_seed_dir
from trendin.spark.concept.thresholds import ConceptThresholds
from trendin.spark.io.concepts import ConceptSink
from trendin.spark.io.contract import DOMAIN_VALUES

# 세션은 받기만 하고 쓰지 않는다. 타입 검사용으로만 들여와야 pyspark 가 없는 곳
# (`scripts/concept-run.py`) 에서도 이 모듈을 import 할 수 있다.
if TYPE_CHECKING:
    from pyspark.sql import SparkSession

log = get_logger("concept")

JOB = "concept"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--domain",
        required=True,
        choices=sorted(DOMAIN_VALUES),
        help="붙일 도메인 슬러그. 개념 표는 지금 fashion 만 있다",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="붙이기 전에 concept.seed_dir 의 초기 사전을 표에 넣는다. 있는 것은 덮지 않는다",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=None,
        help="최근 며칠 분을 다시 붙이나. 없으면 concept.window_days",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="붙이기만 하고 쓰지 않는다. 사전을 바꿔 보며 결과를 확인할 때",
    )


def run(spark: SparkSession | None, config: Config, args: argparse.Namespace) -> int | None:
    """세션을 받지만 쓰지 않는다 — 조회는 PostgreSQL, 붙이기는 순수 파이썬이다.
    그래서 `None` 도 받는다: `scripts/concept-run.py` 가 Spark 없이 노트북에서 이 함수를 부른다.

    규모가 그렇다: 창 30일에 승격 키워드 발생이 수천 행이고 사전이 수만 행이다. 드라이버 메모리
    안이고, Spark 로 흩으면 사전을 executor 마다 실어야 한다. `aggregate` 와 같은 판단이다.
    """
    thresholds = ConceptThresholds.from_config(config)
    window_days = args.window_days or thresholds.window_days
    if window_days < 1:
        raise ConfigError("--window-days 는 1 이상이어야 한다")
    # `--domain` 의 허용값만 DOMAIN_VALUES 로 검사한다(argparse choices). 조회에는 슬러그를 그대로
    # 넘긴다 — pl_ 표가 슬러그로 저장한다 (`ConceptSink.occurrences`).
    sink = ConceptSink(config)
    sink.ensure_schema()

    dry_run = bool(args.dry_run)

    # `--seed` 는 명시적 요청이라 dry-run 이어도 넣는다. dry-run 이 막는 것은 기사별 개념 쓰기다 —
    # 초기 사전 없이 dry-run 을 돌리면 전부 미등록이 되어 아무것도 확인할 수 없다.
    if args.seed:
        seed_dir = Path(thresholds.seed_dir)
        if not seed_dir.is_absolute():
            seed_dir = _repo_root() / seed_dir
        concepts = load_seed_dir(seed_dir)
        result = apply_seed(config, concepts)
        if result.concepts_new or result.expressions_new or result.parents_set:
            version = sink.bump_version(
                note=(
                    f"초기 사전 적재: 개념 {result.concepts_new} · 표현 {result.expressions_new} · "
                    f"상위 {result.parents_set}"
                ),
                changed_by="seed",
            )
            log.info("사전 버전 %d", version)

    dictionary = sink.load_dictionary()
    if len(dictionary) == 0:
        log.warning("사전이 비어 있다 — 전부 미등록이 된다. --seed 로 초기 사전을 먼저 넣는다")
    version = sink.current_version()

    grouped = sink.occurrences(domain=args.domain, window_days=window_days)
    if not grouped:
        log.info("[%s] 최근 %d일에 선별된 후보가 없다 — 붙일 것이 없다", args.domain, window_days)
        return NOTHING_NEW

    rows, unmapped, deferred = [], [], []
    for article_id, surfaces in grouped.items():
        result = map_article(article_id, None, [Keyword(s) for s in surfaces], dictionary)
        rows.extend(result.rows)
        unmapped.extend(result.unmapped)
        deferred.extend(result.deferred)

    distinct_unmapped = {(u.lang, u.normalized) for u in unmapped}
    log.info(
        "[%s] 기사 %d · 개념 행 %d · 미등록 발생 %d (표현 %d) · 유보 %d · 사전 v%d",
        args.domain,
        len(grouped),
        len(rows),
        len(unmapped),
        len(distinct_unmapped),
        len(deferred),
        version,
    )
    for d in deferred[:20]:
        log.info("  유보: 기사 %d · %s → 개념 %s", d.article_id, d.normalized, d.concept_ids)

    if dry_run:
        log.info("dry-run — 쓰지 않는다")
        return None

    sink.write(
        rows=rows,
        processed_article_ids=grouped.keys(),
        unmapped=unmapped,
        dictionary_version=version,
        context_samples=thresholds.context_samples,
    )
    return None


def _repo_root() -> Path:
    # spark/jobs/concept.py → pipeline/
    return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
