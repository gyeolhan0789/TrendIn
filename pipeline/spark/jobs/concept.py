#!/usr/bin/env python
"""concept — 승격된 키워드를 언어 무관 개념 번호에 붙인다.

```sh
spark/scripts/submit.sh concept --profile local --domain fashion            # 최근 창 전부
spark/scripts/submit.sh concept --profile local --domain fashion --dry-run  # 개념을 쓰지 않는다
```

**하는 것** — `src/trendin/spark/concept/` 전부. 저장소의 초기 사전을 표에 반영하고, 표에서
사전을 읽고, 최근 `concept.window_days` 일의 선별 후보를 기사별로 모아 붙이고, `article_concept`
에 쓰고, 못 붙인 표기를 `pl_unmapped_expression` 에 쌓는다. 기본은 여기까지다. 자동 연결을
명시적으로 켜면 영어 이름·통합 후보·LLM 검증을 거쳐 확실한 기존 개념만 같은 실행에서 붙인다.

**초기 사전은 매 실행이 넣는다.** 플래그로 두면 순서를 사람이 기억해야 한다 — 사전이 빈 채로
켜면 승격 키워드 전부가 미등록으로 쌓인다. 나중에 사전을 넣으면 창 안에서 실제로 붙은
표현은 검수 대기에서 내려가지만 기사 이력은 남는다. 다시 넣는 것은 싸고 안전하다:
개념은 비어 있는 칸만 채우고 표현은
이미 있으면 건드리지 않아 검수가 내린 쌍이 되살아나지 않는다 (`concept/seed.py`).

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
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.exit_codes import NOTHING_NEW
from trendin.spark.common.logging import get_logger
from trendin.spark.concept.mapping import map_article
from trendin.spark.concept.seed import apply_seed, apply_seed_in_memory, load_seed_dir
from trendin.spark.concept.thresholds import ConceptThresholds
from trendin.spark.concept.workflow import AutomationPolicy
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
    parser.add_argument(
        "--auto-link",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="미등록 표현 자동 연결. 없으면 concept.automation.enabled 설정을 따른다",
    )
    parser.add_argument(
        "--seed-in-memory",
        action="store_true",
        help="초기 사전을 DB 에 쓰지 않고 메모리에만 얹는다. --dry-run 과 함께만 쓴다",
    )
    parser.add_argument(
        "--seed-dir",
        type=Path,
        default=None,
        help="초기 사전을 여기서 읽는다. --dry-run 과 함께만 쓴다. 없으면 concept.seed_dir",
    )
    parser.add_argument(
        "--dump",
        type=Path,
        default=None,
        help="기사별 결과를 JSON Lines 로 떨군다. 사전을 바꾸기 전후를 맞댈 때",
    )


def run(spark: SparkSession | None, config: Config, args: argparse.Namespace) -> int | None:
    """세션을 받지만 쓰지 않는다 — 조회는 PostgreSQL, 붙이기는 순수 파이썬이다.
    그래서 `None` 도 받는다: `scripts/concept-run.py` 가 Spark 없이 노트북에서 이 함수를 부른다.

    규모가 그렇다: 창 30일에 승격 키워드 발생이 수천 행이고 사전이 수만 행이다. 드라이버 메모리
    안이고, Spark 로 흩으면 사전을 executor 마다 실어야 한다. `aggregate` 와 같은 판단이다.
    """
    if args.seed_in_memory and not args.dry_run:
        # 메모리 사전의 새 개념은 음수 번호다 — `pl_article_concept` 의 외래키를 못 만족한다.
        # DB 를 건드리기 전에 세운다.
        raise ConfigError("--seed-in-memory 는 --dry-run 과 함께만 쓴다")
    if args.seed_dir is not None and not args.dry_run:
        # **운영에 들어가는 사전은 저장소에 커밋된 것뿐이다.** 검수를 거치지 않은 폴더를
        # 명령줄 한 줄로 적재할 수 있으면 git 이 승인 계층인 것이 무너진다. 실험은 여기서
        # 읽고, 통과한 파일만 `spark/conf/concepts/` 로 옮겨 커밋한다. 운영에서 사전 위치를
        # 바꿔야 하면 그것은 설정(`concept.seed_dir`)이 할 일이다.
        raise ConfigError("--seed-dir 는 --dry-run 과 함께만 쓴다 — 적재는 커밋된 사전만 한다")
    thresholds = ConceptThresholds.from_config(config)
    automation = AutomationPolicy.from_config(config)
    window_days = args.window_days or thresholds.window_days
    if window_days < 1:
        raise ConfigError("--window-days 는 1 이상이어야 한다")
    # `--domain` 의 허용값만 DOMAIN_VALUES 로 검사한다(argparse choices). 조회에는 슬러그를 그대로
    # 넘긴다 — pl_ 표가 슬러그로 저장한다 (`ConceptSink.occurrences`).
    sink = ConceptSink(config)
    sink.ensure_schema()

    dry_run = bool(args.dry_run)
    seed_in_memory = bool(args.seed_in_memory)

    # 초기 사전을 먼저 반영한다. dry-run 도 반영한다 — dry-run 이 막는 것은 기사별 개념 쓰기이고,
    # 사전 없이 돌리면 전부 미등록이 되어 확인할 것이 없다. **사전 변경 자체를 되돌려 가며
    # 비교할 때만** `--seed-in-memory` 로 적재를 건너뛴다. 그 경우 이 실행은 DB 를 읽기만 한다.
    seed_dir = Path(args.seed_dir or thresholds.seed_dir)
    if not seed_dir.is_absolute():
        seed_dir = _repo_root() / seed_dir
    if args.seed_dir is not None:
        log.info("초기 사전을 %s 에서 읽는다 — 이 실행에만 쓴다", seed_dir)
    concepts = load_seed_dir(seed_dir)
    if not concepts:
        # `Path.glob` 은 없는 디렉터리에서도 조용히 빈 결과를 준다. 그대로 두면 사전이 빈 채로
        # 돌아 승격 키워드 전부가 미등록으로 쌓이므로 여기서 세운다.
        raise ConfigError(f"초기 사전을 읽지 못했다 — concept.seed_dir 를 확인한다: {seed_dir}")
    if seed_in_memory:
        dictionary, seeded = apply_seed_in_memory(
            sink.load_dictionary(),
            concepts,
            rejected=sink.rejected_expression_keys(),
        )
    else:
        seeded = apply_seed(config, concepts)
        if seeded.concepts_new or seeded.expressions_new or seeded.parents_set:
            log.info(
                "사전 버전 %d",
                sink.bump_version(
                    note=(
                        f"초기 사전 적재: 개념 {seeded.concepts_new} · "
                        f"표현 {seeded.expressions_new} · 상위 {seeded.parents_set}"
                    ),
                    changed_by="seed",
                ),
            )
        dictionary = sink.load_dictionary()
    version = sink.current_version()

    grouped = sink.occurrences(domain=args.domain, window_days=window_days)
    if not grouped:
        log.info("[%s] 최근 %d일에 선별된 후보가 없다 — 붙일 것이 없다", args.domain, window_days)
        return NOTHING_NEW

    rows, unmapped, deferred = [], [], []
    resolved_keys: set[tuple[str, str]] = set()
    # 덤프는 기사별로 "무엇이 붙었나" 를 알아야 한다 — 합친 집합으로는 기사 단위가 사라진다.
    resolved_by_article: dict[int, tuple[tuple[str, str], ...]] = {}
    context_by_article: dict[int, tuple[tuple[str, str], ...]] = {}
    for article_id, keywords in grouped.items():
        result = map_article(article_id, None, keywords, dictionary)
        rows.extend(result.rows)
        unmapped.extend(result.unmapped)
        deferred.extend(result.deferred)
        resolved_keys.update(result.resolved_keys)
        if args.dump:
            resolved_by_article[article_id] = result.resolved_keys
            context_by_article[article_id] = result.context_keys

    # 문맥을 그 낱말이 실제로 나온 문장으로 바꾼다. 기사 제목을 그대로 쓰던 자리인데, 운영
    # 미등록의 91%가 제목에 그 낱말이 없었다 — 가릴 근거가 되기는커녕 엉뚱한 쪽으로 끌고 간다
    # (`concept/context.py`). 본문은 미등록이 나온 기사만 읽는다.
    # `--dry-run` 에서는 건너뛴다. 쓰지 않을 문맥 때문에 본문을 읽을 이유가 없고, 회귀 검사
    # (`--dump --seed-in-memory --dry-run`)가 그 비용을 매번 치르게 된다. 덤프는 표기가 어디로
    # 갔는지만 적지 문맥을 적지 않는다.
    if not dry_run:
        unmapped = _with_sentences(
            spark, config, unmapped, thresholds, _stored_contexts(sink, thresholds)
        )

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

    if args.dump:
        written = _dump(
            args.dump,
            domain=args.domain,
            window_days=window_days,
            dictionary_version=version,
            seed_in_memory=seed_in_memory,
            seed_dir=seed_dir,
            dictionary=dictionary,
            rows=rows,
            unmapped=unmapped,
            deferred=deferred,
            resolved=resolved_by_article,
            context=context_by_article,
        )
        log.info("덤프 %d줄 → %s", written, args.dump)

    if dry_run:
        log.info("dry-run — 쓰지 않는다")
        return None

    sink.write(
        rows=rows,
        processed_article_ids=grouped.keys(),
        unmapped=unmapped,
        resolved_keys=resolved_keys,
        dictionary_version=version,
        context_samples=thresholds.context_samples,
    )
    enabled = automation.enabled if args.auto_link is None else bool(args.auto_link)
    if enabled and unmapped:
        _run_automatic_linking(
            config=config,
            sink=sink,
            dictionary=dictionary,
            automation=replace(automation, enabled=True),
            thresholds=thresholds,
            grouped=grouped,
            unmapped=unmapped,
            dictionary_version=version,
            domain=args.domain,
            window_days=window_days,
        )
    return None


def _mint_new_concepts(
    *, sink, automation, result, questions, dictionary, domain: str, window_days: int,
    run_id: str,
) -> None:
    """판정이 "새 개념" 이라고 한 것 중 근거가 선 것만 사전에 넣는다.

    세는 개념으로 넣는다 — 그 표기는 사전에 없던 동안에도 키워드로 순위에 셌다. 숨길 분류는
    `concept.automation.mint_uncounted` 에 적는다.
    """
    from trendin.spark.concept import minting, workflow

    if not automation.create_concepts:
        return
    wanted = {
        item.key for item in result.decisions if item.decision == workflow.NEW_CONCEPT
    }
    if not wanted:
        return
    by_key = {question.key: question for question in questions}
    proposals = []
    for key in sorted(wanted):
        decision = next(d for d in result.decisions if d.key == key and d.decision == "NEW_CONCEPT")
        english = decision.evidence.get("english_name")
        category = decision.evidence.get("category")
        question = by_key.get(key)
        if not english or not category or question is None:
            continue
        proposals.append(
            (key[0], key[1], question.surface or key[1], str(english), str(category))
        )
    if not proposals:
        return
    try:
        evidence = {
            key: minting.Evidence(articles, sources)
            for key, (articles, sources) in sink.expression_evidence(
                domain=domain, window_days=window_days
            ).items()
        }
    except Exception:
        log.exception("근거를 읽지 못했다 — 새 개념을 만들지 않는다")
        return
    mints = minting.select(
        proposals,
        evidence,
        [concept.canonical_name for concept in dictionary.concepts()],
        minting.MintPolicy(automation.min_create_articles, automation.min_create_sources),
    )
    if not mints:
        log.info("새 개념 후보 %d건 중 근거가 선 것이 없다", len(proposals))
        return
    try:
        made = sink.mint_concepts(
            mints, decided_by=minting.AUTO_SOURCE, run_id=run_id,
            uncounted=automation.mint_uncounted,
        )
        log.info("새 개념 %d건을 넣었다 — 후보 %d건 중", made, len(proposals))
    except Exception:
        log.exception("새 개념 적재 실패 — 이번 회차 연결 결과는 그대로 둔다")


def _stored_contexts(sink, thresholds) -> dict:
    """이미 쌓인 문맥 표본. 읽지 못하면 빈 사전 — 예전처럼 본문을 다 읽는다."""
    try:
        return sink.stored_contexts(min_articles=thresholds.min_articles)
    except Exception:
        log.exception("쌓인 문맥을 읽지 못했다 — 본문을 전부 읽는다")
        return {}


def _with_sentences(spark, config: Config, unmapped: list, thresholds, stored) -> list:
    """미등록 발생의 문맥을 기사 본문의 문장으로 채운다. 못 읽으면 그대로 둔다.

    **판정 대상이 될 표현의 기사만 읽는다.** 창 안의 미등록 발생 전부를 읽으면 parquet 을 수천
    개 열게 되고, 원래 DB 만 쓰던 이 Job 이 갑자기 무거워진다. 문맥이 필요한 것은 기사 수
    문턱을 넘어 실제로 판정에 오르는 표현뿐이다 — 나머지는 어차피 묻지 않는다.

    **표본이 이미 찬 표기는 본문을 읽지 않는다.** 저장은 표현당 상한이 있어서
    (`io/concepts.UNMAPPED_MERGE_SQL`), 찬 표기의 기사를 또 읽어 봐야 뽑은 문장이 그대로
    버려진다. 이것이 시간의 거의 전부다 — 본문은 발행일 폴더로 나뉘어 있고 읽을 기사 목록의
    처음부터 끝까지가 통째로 스캔되므로, 30일에 흩어진 목록 하나가 30일치를 다 읽게 만든다.
    빼고 나면 남는 것이 새로 올라온 표기뿐이라 범위가 최근 며칠로 좁아진다.

    건너뛴 표기에는 저장해 둔 문장을 그대로 얹는다. 비우거나 제목으로 되돌리면 판정이 문맥
    없는 표기가 되어 유보로 떨어진다 (`concept/judge.usable_context`).
    """
    from dataclasses import replace as _replace

    from trendin.spark.concept.context import find_sentence
    from trendin.spark.concept.context import plan as context_plan
    from trendin.spark.io.article_bodies import load_bodies
    from trendin.spark.normalize.curated import curated_root

    if not unmapped:
        return unmapped
    counts: dict[tuple[str, str], set[int]] = {}
    for item in unmapped:
        counts.setdefault((item.lang, item.normalized), set()).add(item.article_id)
    chosen = context_plan(
        {key: len(ids) for key, ids in counts.items()},
        min_articles=thresholds.min_articles,
        context_samples=thresholds.context_samples,
        stored=stored,
    )
    wanted, kept = chosen.wanted, chosen.kept

    def _apply(item, sentence: str | None):
        return item if item.context == sentence else _replace(item, context=sentence)

    def _reuse(items: list) -> list:
        """본문을 읽지 못했을 때도 저장된 문장은 쓴다."""
        if not kept:
            return items
        return [_apply(item, kept.get(item.key, item.context)) for item in items]

    if not wanted:
        if kept:
            log.info("문맥 표본이 이미 찬 표현 %d개 — 본문을 읽지 않는다", len(kept))
        return _reuse(unmapped)
    try:
        root = curated_root(config)
    except Exception:
        log.warning("curated 경로를 읽지 못했다 — 문맥은 제목 그대로 둔다")
        return _reuse(unmapped)
    needed = {
        item.article_id for item in unmapped if (item.lang, item.normalized) in wanted
    }
    log.info(
        "문맥용 본문 %d개 기사를 읽는다 (문장이 필요한 표현 %d개 · 표본이 찬 표현 %d개 건너뜀 "
        "· 미등록 발생 %d)",
        len(needed), len(wanted), len(kept), len(unmapped),
    )
    bodies = load_bodies(spark, config, needed, curated_root=root)
    if not bodies:
        log.info("본문을 읽지 못했다 — 문맥은 제목 그대로 둔다")
        return _reuse(unmapped)

    filled = 0
    out = []
    for item in unmapped:
        key = item.key
        if key in kept:
            # 저장해 둔 문장이 있다. 같은 것을 다시 뽑을 이유가 없다.
            out.append(_apply(item, kept[key]))
            continue
        if key not in wanted:
            # 판정에 오르지 않을 표현이다. 본문을 읽지 않았으니 있던 값을 그대로 둔다.
            out.append(item)
            continue
        body = bodies.get(item.article_id)
        sentence = find_sentence(body, item.context, item.surface) if body else None
        if sentence is None:
            # 본문에도 제목에도 없으면 비운다. 엉뚱한 제목을 문맥이라고 넘기지 않는다.
            out.append(_replace(item, context=None))
            continue
        filled += 1
        out.append(_replace(item, context=sentence))
    log.info(
        "등장 문장을 붙인 미등록 발생 %d건 (새로 뽑은 표현 %d개 · 저장분을 쓴 표현 %d개)",
        filled, len(wanted), len(kept),
    )
    return out


def _run_automatic_linking(
    *, config: Config, sink: ConceptSink, dictionary, automation: AutomationPolicy,
    thresholds: ConceptThresholds, grouped, unmapped, dictionary_version: int,
    domain: str, window_days: int,
) -> None:
    """Run the optional paid path after legacy output has safely been persisted."""
    from trendin.spark.concept import workflow
    from trendin.spark.concept.auto_link import apply_links
    from trendin.spark.concept.candidates import CandidateIndex
    from trendin.spark.concept.judge import PROMPT_VERSION
    from trendin.spark.concept.retrieval import CandidateRetriever, RetrievalPolicy
    from trendin.spark.io.concepts import new_run_id
    from trendin.spark.io.llm import GmsClient

    questions = _questions(unmapped, min_articles=thresholds.min_articles)
    if not questions:
        log.info("자동 연결 대상 없음: 기사 수 문턱 %d", thresholds.min_articles)
        return
    try:
        client = GmsClient(model=automation.model)
    except Exception:
        log.exception("자동 연결 LLM 초기화 실패 — 기존 사전 매핑 결과는 유지한다")
        return

    retriever = CandidateRetriever(
        dictionary, CandidateIndex(dictionary), RetrievalPolicy.from_config(config)
    )
    vector_search = (
        _vector_search(config, retriever.policy.top_k) if automation.vector_enabled else None
    )
    # 지난 회차에 이미 결론이 난 표현은 다시 묻지 않는다. 같은 `Getty Images` 를 매달 LLM 에게
    # 되묻는 것을 막는 자리다. 무엇을 아직 믿을지는 사전 버전과 프롬프트 버전이 정한다.
    settled = sink.settled_decisions(
        prompt_version=PROMPT_VERSION, dictionary_version=dictionary_version
    )
    result = workflow.run_workflow(
        questions,
        client=client,
        cache=sink,
        retriever=retriever,
        policy=automation,
        vector_search=vector_search,
        settled=settled,
    )
    if result.reused:
        log.info("이미 판정된 표현 %d건은 건너뛴다", len(result.reused))
    counts = Counter(item.decision for item in result.decisions)
    log.info(
        "판정 갈래: LINK %d · NEW %d · EXCLUDE %d · DEFER %d — 질문 %d · 호출 시도 %d",
        counts.get(workflow.LINK, 0),
        counts.get(workflow.NEW_CONCEPT, 0),
        counts.get(workflow.EXCLUDE, 0),
        counts.get(workflow.DEFER, 0),
        len(questions),
        result.attempted_calls,
    )

    if not automation.apply_links:
        # **관찰 모드.** 판정은 돌되 사전에는 아무것도 넣지 않는다. 결과는 검수 대기의
        # 제안으로만 남고, 사전은 사람이 `scripts/concept-review.py apply` 로 승인한 것만
        # 받는다. 판정을 `pl_mapping_decision` 에도 적지 않는다 — 거기 적으면 굳어서
        # 나중에 반영을 켜도 그 표현은 다시 보지 않는다 (`io/concepts.record_proposals`).
        try:
            recorded = sink.record_proposals(
                result.decisions,
                model=automation.model,
                prompt_version=PROMPT_VERSION,
                dictionary_version=dictionary_version,
            )
            log.info("제안 %d건을 검수 대기에 남겼다 — 사전 반영 없음", recorded)
        except Exception:
            log.exception("제안 기록 실패 — 이번 회차 연결 결과는 그대로 둔다")
        return

    # **이 회차가 바꾼 것은 전부 이 번호로 묶인다.** 판정 표·연결·새 개념 세 자리가 같은 번호로
    # 원장(`io/concepts.CHANGE`)에 남고, 되돌릴 때 이 번호 하나로 한꺼번에 내린다.
    run_id = new_run_id()
    log.info("자동 반영 회차 %s 시작", run_id)
    try:
        # `LINK` 는 여기 적지 않는다. 연결이 실제로 들어갔을 때 `apply_links` 가 같은 트랜잭션에서
        # 적는다 — 여기서도 적으면 한 연결이 판정 표에 두 번 남고, 막혀서 안 들어간 연결도
        # "이었다" 로 남는다.
        recorded = sink.record_decisions(
            [item for item in result.decisions if item.decision != workflow.LINK],
            decided_by="auto:llm",
            model=automation.model,
            prompt_version=PROMPT_VERSION,
            dictionary_version=dictionary_version,
            run_id=run_id,
        )
        log.info("판정 %d건을 기록했다", recorded)
    except Exception:
        log.exception("판정 기록 실패 — 이번 회차 연결 결과는 그대로 둔다")

    _mint_new_concepts(
        sink=sink, automation=automation, result=result, questions=questions,
        dictionary=dictionary, domain=domain, window_days=window_days, run_id=run_id,
    )

    applied: tuple = ()
    try:
        applied = apply_links(
            config, tuple(result.links), model=automation.model,
            prompt_version=workflow.VERIFY_PROMPT_VERSION, run_id=run_id,
        )
    except Exception:
        log.exception("자동 연결 적재 실패 — 이번 회차 연결은 하나도 들어가지 않았다")
    # 유보 목록에는 제외·새 개념으로 결론 난 표기도 섞여 있다(`workflow.run_workflow` 가 사유를
    # 남기려고 같이 담는다). 그 표기에 유보를 또 적으면 최신 결정이 유보가 되어 결론이 지워진다.
    decided = {item.key for item in result.decisions}
    for item in result.deferred:
        try:
            sink.record_auto_defer(
                lang=item.lang,
                normalized=item.normalized,
                evidence=item.evidence,
                model=automation.model,
                prompt_version=(
                    PROMPT_VERSION if item.reason == "NAME_FAILED"
                    else workflow.VERIFY_PROMPT_VERSION
                ),
                dictionary_version=dictionary_version,
                run_id=run_id,
                write_decision=(item.lang, item.normalized) not in decided,
            )
        except Exception:
            log.exception("자동 유보 기록 실패: %s/%s", item.lang, item.normalized)
    log.info(
        "자동 반영 회차 %s: 질문 %d · 호출 시도 %d · LINK %d · DEFER %d — 되돌리려면 "
        "scripts/concept-review.py rollback --run %s --by human:<이름>",
        run_id, len(questions), result.attempted_calls, len(applied), len(result.deferred),
        run_id,
    )
    if not applied:
        return

    # Newly inserted aliases must affect article_concept in this same run, not thirty minutes later.
    refreshed = sink.load_dictionary()
    new_version = sink.current_version()
    auto_pairs = {
        (item.article_id, link.concept_id)
        for item in unmapped
        for link in applied
        if (item.lang, item.normalized) == (link.verdict.lang, link.verdict.normalized)
    }
    rows, still_unmapped = [], []
    resolved_keys: set[tuple[str, str]] = set()
    for article_id, keywords in grouped.items():
        mapped = map_article(article_id, None, keywords, refreshed)
        rows.extend(
            replace(row, method="AUTO_LLM")
            if (row.article_id, row.concept_id) in auto_pairs else row
            for row in mapped.rows
        )
        still_unmapped.extend(mapped.unmapped)
        resolved_keys.update(mapped.resolved_keys)
    sink.write(
        rows=rows,
        processed_article_ids=grouped.keys(),
        unmapped=still_unmapped,
        resolved_keys=resolved_keys,
        dictionary_version=new_version,
        context_samples=thresholds.context_samples,
    )


def _dump(
    path: Path,
    *,
    domain: str,
    window_days: int,
    dictionary_version: int,
    seed_in_memory: bool,
    seed_dir: Path,
    dictionary,
    rows,
    unmapped,
    deferred,
    resolved: dict[int, tuple[tuple[str, str], ...]],
    context: dict[int, tuple[tuple[str, str], ...]],
) -> int:
    """기사별 결과를 JSON Lines 로 떨군다 — 사전을 바꾸기 전후를 맞대기 위한 것.

    **표기 단위로 맞댄다.** `resolved` · `context` · `deferred` · `unmapped` 한 줄이 각각
    `(article_id, lang, normalized)` 하나의 결과이고, 한 표기는 **넷 중 정확히 하나**다.
    그래서 두 덤프를 맞대면 `resolved → deferred` 같은 이동이 바로 세어진다 — 사전을
    늘렸을 때 **원래 붙던 것이 모호해져 밀려난** 건수가 그 회귀 지표다.

    `context` 를 따로 두는 이유는 그것이 셋과 다른 상태이기 때문이다. 모호했지만 문맥 규칙이
    갈라 붙인 표기라 기사에는 개념이 남는데, 검수 대기에서는 안 내려간다. 넷으로 나누지 않으면
    이 표기들이 덤프에서 아예 빠져 "말뭉치가 달라졌다" 로 잘못 세어진다.

    개념 번호로 맞대면 안 된다. `--seed-in-memory` 의 새 개념은 음수이고 두 실행에서 같은
    번호라는 보장이 없다. `row` 줄은 "어느 개념이 몇 기사에 붙었나" 를 따로 세기 위한 것이고,
    번호가 양수인 실행끼리만 비교한다.

    줄을 전부 정렬해 쓴다 — `diff` 로도 읽히고, 읽어서 세는 쪽도 순서에 기대지 않는다.
    """
    lines: list[dict] = [
        {
            "t": "meta",
            "domain": domain,
            "window_days": window_days,
            "dictionary_version": dictionary_version,
            "seed_in_memory": seed_in_memory,
            "seed_dir": str(seed_dir),
            "concepts": len(dictionary.concepts()),
            "expressions": len(dictionary),
            "articles": len(resolved),
            "rows": len(rows),
            "context": sum(len(keys) for keys in context.values()),
            "deferred": len(deferred),
            "unmapped": len(unmapped),
        }
    ]
    for kind, per_article in (("resolved", resolved), ("context", context)):
        for article_id in sorted(per_article):
            for lang, normalized in sorted(per_article[article_id]):
                lines.append(
                    {
                        "t": kind,
                        "article_id": article_id,
                        "lang": lang,
                        "normalized": normalized,
                    }
                )
    for item in sorted(deferred, key=lambda d: (d.article_id, d.lang, d.normalized)):
        lines.append(
            {
                "t": "deferred",
                "article_id": item.article_id,
                "lang": item.lang,
                "normalized": item.normalized,
                "concept_ids": sorted(item.concept_ids),
            }
        )
    for item in sorted(unmapped, key=lambda u: (u.article_id, u.lang, u.normalized)):
        lines.append(
            {
                "t": "unmapped",
                "article_id": item.article_id,
                "lang": item.lang,
                "normalized": item.normalized,
            }
        )
    for row in sorted(rows, key=lambda r: (r.article_id, r.concept_id)):
        lines.append(
            {
                "t": "row",
                "article_id": row.article_id,
                "concept_id": row.concept_id,
                "method": row.method,
            }
        )

    path = Path(path)
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for line in lines:
            out.write(json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            out.write("\n")
    return len(lines)


def _questions(unmapped, *, min_articles: int):
    from trendin.spark.concept.judge import Question

    articles: dict[tuple[str, str], set[int]] = {}
    contexts: dict[tuple[str, str], str | None] = {}
    surfaces: dict[tuple[str, str], str] = {}
    for item in unmapped:
        key = (item.lang, item.normalized)
        articles.setdefault(key, set()).add(item.article_id)
        surfaces.setdefault(key, item.surface)
        if key not in contexts or (contexts[key] is None and item.context):
            contexts[key] = item.context
    eligible = [
        (key, ids) for key, ids in articles.items() if len(ids) >= min_articles
    ]
    eligible.sort(key=lambda pair: (-len(pair[1]), pair[0]))
    return [
        Question(
            index,
            lang,
            normalized,
            len(ids),
            contexts[(lang, normalized)],
            surfaces[(lang, normalized)],
        )
        for index, ((lang, normalized), ids) in enumerate(eligible, start=1)
    ]


def _vector_search(config: Config, limit: int):
    """Return a lazy vector search callback, or None when model/vector state is unavailable."""
    try:
        from trendin.spark.concept.embedding import MODEL_ID, MODEL_REVISION, E5Encoder, model_key
        from trendin.spark.io.concept_vectors import ConceptVectorStore

        store = ConceptVectorStore(config)
        total, embedded = store.coverage(model_key(MODEL_ID, MODEL_REVISION))
        if not total or embedded != total:
            log.warning(
                "개념 벡터가 불완전하다(%d/%d) — 문자·음가 후보로 계속한다",
                embedded,
                total,
            )
            return None
        encoder = E5Encoder(MODEL_ID, MODEL_REVISION)
    except Exception:
        log.exception("벡터 검색 초기화 실패 — 문자·음가 후보로 계속한다")
        return None

    def search(original: str, english_name: str):
        vectors = encoder.encode([original, english_name], query=True)
        return {
            "original": store.search(vectors[0], model_id=encoder.model_id, limit=limit),
            "english": store.search(vectors[1], model_id=encoder.model_id, limit=limit),
        }

    return search


def _repo_root() -> Path:
    # spark/jobs/concept.py → pipeline/
    return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
