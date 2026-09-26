"""[05] 의 단계 배선 — `extract` Job 의 후반부.

```
1. 관측 읽기        후보별 누적 (문서·일수·소스·저자). 별칭을 접지 않은 원표기 단위
2. 병합 쌍          층 1 복수형 · 층 2 약어 · 기존 별칭(변형 제외) · 검수 승인
                    표기 변형(오타)은 세기만 하고 병합 근거에 넣지 않는다 (아래)
3. 해소             union-find → 대표 하나. 승격된 것이 얽히거나 덩이가 너무 크면 보류
4. 별칭 적재        pl_alias · pl_merge_log + 영향받은 날짜 재집계 (한 트랜잭션)
5. 대표별 관측       별칭을 접은 뒤 다시 읽는다 — 문서 수는 합이 아니라 합집합
6. 승격 심사        registry/promote.judge. 통과한 것만 keywords 로
7. 층 3             임베딩 유사도 → 검수 큐 (자동 병합 없음)
8. 승격             keywords upsert → RETURNING id → pl_keyword_id_map
9. 연결             keyword_contents
```

**Spark 를 쓰지 않는다.** [04] 는 문서 × 후보 규모(실측 70,886행)라 Spark 가 필요했지만
[05] 의 입력은 이미 접힌 내부 테이블이다. 집계는 PostgreSQL 이 인덱스로 하고, 판정은 순수
파이썬이 후보 수천~수만 개에 대해 한다 — 그 사이에 셔플이 들 자리가 없다. `jobs/extract.py`
가 세션을 들고 있지만 이 단계는 쓰지 않고, 그래서 층 2 테스트가 세션 없이 돈다.

**순서가 정확성 조건인 자리가 둘이다.**

| 순서 | 왜 |
| --- | --- |
| 4 → 5 | 대표별 관측은 별칭이 반영된 뒤에야 맞다. 먼저 읽으면 병합 전 값으로 심사한다 |
| 3 → 6 | **병합은 승격 전에만 한다** ([05 §1]). 한 번 들어가면 되돌릴 수 없다 |

**층 3 은 순서에 자유롭다.** 자동 병합을 하지 않고 검수 큐만 채우기 때문이다 ([05 §4]).
그래서 심사 결과를 보고 **사용자에게 보이게 될 표기**로 대상을 좁힌다 — 보이지 않는 후보끼리의
동의어는 아직 아무 화면에도 영향이 없고, 승격되면 그때 다시 걸린다.

⚠️ 그 대가 하나 — 같은 회차에 양쪽이 승격되면 그 쌍의 승인은 다음 실행에서 **사후 병합**이
된다. [05 §7] 이 이미 그 경우를 "큐에 남겨두고 백엔드와 함께 처리" 로 정해 뒀다.

## 표기 변형(오타)은 병합 근거가 아니다 (S15P21A102-398)

편집 거리는 "같다" 를 판정하지 못한다. 쌍 하나하나가 규칙을 지켜도 `bindi → fendi`,
`ezra watson → emma watson` 처럼 딴 낱말이 흔했고, **오타 관계는 전이적이지 않은데 union-find
가 전이성을 강제한다.** 2026-09-20 운영에서 `chanel ← camel ← bagel → bague → vogue` 같은
사슬로 6,461개가 한 덩이가 되어 브랜드가 매체 `vogue` 로 사라졌다. 남는 쌍의 70% 는 흡수되는
쪽이 문서 1건이라 합쳐서 얻는 것도 거의 없다.

그래서 `merge.variant_pairs` 는 **건수 지표로만** 남고 `_pairs` 가 돌려주는 병합 쌍에 들어가지
않는다. 같은 이유로 **`rule = variant` 인 기존 별칭은 되먹이지 않는다** — 추론이 저장되었다가
다음 실행의 증거로 돌아오면, 틀린 추론이 사실처럼 굳는다.

⚠️ 되먹임을 끊어도 이미 적재된 variant 별칭은 `pl_alias` 에 남는다 (**지우지 않는다**,
`io/keywords.ALIAS_MERGE_SQL`). 그 별칭의 대표가 새 덩이에서 다른 대표로 흡수되면 두 홉
사슬이 생길 수 있어, 운영의 variant 별칭 정리가 이 변경 뒤에 따라와야 한다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from trendin.spark.common.logging import get_logger
from trendin.spark.io.keywords import KeywordSink, RegistrySink
from trendin.spark.io.stats import Stat
from trendin.spark.registry import alias as alias_rules
from trendin.spark.registry import embedding as embedding_rules
from trendin.spark.registry import merge as merge_rules
from trendin.spark.registry import normalize as normalize_rules
from trendin.spark.registry import promote as promote_rules
from trendin.spark.registry import review as review_rules
from trendin.spark.registry.merge import AbbreviationEvidence, MergePair, signal_of
from trendin.spark.registry.thresholds import RegistryThresholds

log = get_logger(__name__)

# --- 분포 모니터링 지표. **값이 곧 집계 키다** — 바꾸면 옛 실행과 이어지지 않는다. --------
CANDIDATES = "registry_candidates"  # 심사 대상 대표 수
MERGE_PAIRS = "merge_pairs"  # 차원: {domain}/{규칙}
ALIASES = "aliases"  # 적용된 별칭 수 (누적 표의 이번 회차 반영분)
MERGES_NEW = "merges_new"  # 이번에 새로 기록된 병합 ([05 §8] 의 "적용 시점")
MERGES_PARKED = "merges_parked"  # 자동 적용하지 않고 큐로 보낸 쌍
# 크기 상한을 넘어 통째로 보류한 덩이 수. 큐로 가지 않으므로 여기와 로그가 유일한 흔적이다.
# 0 이 정상이다 — 1 이상이면 병합 규칙 어딘가가 전이성으로 폭주하고 있다.
MERGES_OVERSIZED = "merges_oversized"
RECOUNTED_DATES = "recounted_dates"  # 병합 반영으로 다시 센 (domain, stat_date) 수
PROMOTED = "promoted"  # 이번 회차에 keywords 로 들어간 수 (재승격 포함)
HELD = "held"  # 차원: {domain}/{사유}. registry/promote 의 HELD_* 상수
# 조건마다 **단독으로** 막은 수. 차원은 `HELD` 와 같지만 세는 방식이 다르다 — 위는 후보당
# 사유 하나라 앞선 조건이 뒤를 가리고(`registry/promote.Verdict`), 이쪽은 조건마다 따로 세어
# **합이 보류 수를 넘는다.** 승격 문턱은 위 표로 정할 수 없어서 있는 지표다 ([10 §4] S6).
#
# **이미 승격된 후보는 세지 않는다.** 그것은 심사 결과와 무관하게 통과하므로([05 §1])
# 분포에 섞으면 "이 조건이 지금 무엇을 막고 있나" 가 흐려진다 — 알고 싶은 것은 아직
# 올라오지 못한 쪽이다.
HELD_BY_CONDITION = "held_by_condition"  # 차원: {domain}/{사유}
REVIEW_ENQUEUED = "review_enqueued"
EMBEDDING_ENCODED = "embedding_encoded"  # 캐시에 없어 새로 계산한 표기 수
KEYWORD_CONTENTS_LINKED = "keyword_contents_linked"
# 승격이 막혀 건너뛴 회차. 0/1 이다 — 값이 1 인 실행이 있으면 그 회차의 keywords 가 비어 있다.
PROMOTION_SKIPPED = "promotion_skipped"
# 층 2 변형 탐색을 **상한 때문에 건너뛴** 회차. 0/1 이다 — 쌍이 하나도 안 나온 정상
# 회차와 구분된다 (`merge.VariantScan.skipped`). 둘이 같은 값이면 경보가 아니다.
VARIANT_SCAN_SKIPPED = "variant_scan_skipped"


@dataclass(frozen=True, slots=True)
class Observation:
    """후보 하나의 누적 관측 — **원표기 단위**. `io/keywords.observations` 의 한 행."""

    key: str
    surface: str
    status: str
    keyword_id: int | None
    doc_count: int
    observed_days: int
    source_count: int
    author_count: int


@dataclass
class RegistryResult:
    promoted: tuple[str, ...] = ()
    aliases: int = 0
    parked: int = 0
    review_enqueued: int = 0
    linked_contents: int = 0
    promotion_skipped: bool = False
    stats: list[Stat] = field(default_factory=list)


def registry_batch(
    *,
    domain: str,
    domain_enum: str,
    thresholds: RegistryThresholds,
    registry: RegistrySink,
    keywords: KeywordSink | None,
    extract_run_id: str,
) -> RegistryResult:
    """도메인 하나의 정규화·통합·승격.

    `keywords` 가 `None` 이면 **승격만 건너뛴다** — 병합·검수 큐·이력은 전부 `pl_` 이라
    백엔드 선행 조건과 무관하게 돈다 ([08 §1], `io/keywords.py` 의 차단 절). 그 자리는 둘이
    쓴다: 선행 조건이 없어 **막힌** 회차와, 후보 분포를 보려고 `--skip-promotion` 으로
    **일부러 끈** 회차다. 심사는 어느 쪽에서도 그대로 돌아 보류 분포가 남는다 — 그것이
    문턱을 정하는 자료다 ([10 §4] S6). **이유를 로그에 남기는 것은 호출부다.**
    """
    observations = _observations(registry, domain=domain)
    if not observations:
        log.info("[%s] 후보가 없다 — 레지스트리 단계를 건너뛴다", domain)
        # **빈손으로 돌아가지 않는다.** 좁은 표에서는 행이 없는 것이 곧 "안 셌음" 이라
        # (`io/stats.py`), 여기서 통계를 빼면 그 도메인만 `promotion_skipped` 가 0 도 1 도
        # 아닌 상태가 된다 — 상수 주석이 약속한 0/1 이 깨진다.
        return RegistryResult(
            promotion_skipped=keywords is None,
            stats=[
                Stat(CANDIDATES, domain, 0),
                Stat(PROMOTION_SKIPPED, domain, 1 if keywords is None else 0),
            ],
        )
    df = {item.key: item.doc_count for item in observations.values()}
    promoted_keys = {item.key for item in observations.values() if item.keyword_id is not None}

    pairs, pair_stats = _pairs(registry, domain=domain, df=df, thresholds=thresholds)
    resolution = alias_rules.resolve(
        pairs, df=df, max_group_size=thresholds.alias_max_group_size, promoted=promoted_keys
    )

    stats: list[Stat] = [Stat(CANDIDATES, domain, len(observations)), *pair_stats]
    stats.append(Stat(MERGES_PARKED, domain, len(resolution.parked)))
    stats.append(Stat(MERGES_OVERSIZED, domain, len(resolution.oversized)))
    if resolution.oversized:
        log.warning(
            "[%s] 덩이 %d개가 크기 상한 %d 를 넘어 통째로 보류했다 — 별칭도 검수 큐도 없다. "
            "큰 순서로 (DF 최대 구성원, 크기): %s",
            domain,
            len(resolution.oversized),
            thresholds.alias_max_group_size,
            sorted(resolution.oversized, key=lambda item: -item[1])[:10],
        )

    applied = 0
    if resolution.aliases:
        result = registry.apply_aliases(
            [
                (
                    item.domain,
                    item.alias_key,
                    item.canonical_key,
                    item.layer,
                    item.rule,
                    item.confidence,
                    item.signal,
                    extract_run_id,
                )
                for item in resolution.aliases
            ],
            domain=domain,
        )
        applied = result.aliases
        stats.append(Stat(MERGES_NEW, domain, result.new_or_changed))
        stats.append(Stat(RECOUNTED_DATES, domain, result.recounted_dates))
    stats.append(Stat(ALIASES, domain, applied))

    # 5 — 별칭이 반영된 뒤의 대표별 관측. 이 순서가 정확성 조건이다 (위 표).
    groups = {row[0]: row[1:] for row in registry.group_observations(domain=domain)}
    canonical_of = {item.alias_key: item.canonical_key for item in resolution.aliases}

    judged = _judge_all(
        observations,
        domain=domain,
        groups=groups,
        canonical_of=canonical_of,
        thresholds=thresholds,
    )
    verdicts = judged.verdicts
    passed = tuple(key for key, verdict in verdicts.items() if verdict.promoted)
    for reason in promote_rules.HELD_REASONS:
        held = sum(1 for verdict in verdicts.values() if verdict.reason == reason)
        stats.append(Stat(HELD, f"{domain}/{reason}", held))
        stats.append(
            Stat(HELD_BY_CONDITION, f"{domain}/{reason}", judged.condition_failures[reason])
        )

    # 7 — 층 3. 대상은 심사를 통과한 것 ∪ 이미 승격된 것 (위 docstring).
    visible = tuple(sorted(set(passed) | promoted_keys))
    review_pairs, encoded = _layer3(
        registry, domain=domain, keys=visible, observations=observations, thresholds=thresholds
    )
    stats.append(Stat(EMBEDDING_ENCODED, domain, encoded))

    enqueued = _enqueue(
        registry, domain=domain, parked=resolution.parked, embedding=review_pairs, df=df
    )
    stats.append(Stat(REVIEW_ENQUEUED, domain, enqueued))

    result = RegistryResult(
        promoted=passed,
        aliases=applied,
        parked=len(resolution.parked),
        review_enqueued=enqueued,
        stats=stats,
    )
    if keywords is None:
        result.promotion_skipped = True
        stats.append(Stat(PROMOTION_SKIPPED, domain, 1))
        stats.append(Stat(PROMOTED, domain, 0))
        log.warning(
            "[%s] 승격을 건너뛴다 — 심사를 통과한 후보 %d개가 keywords 에 들어가지 않는다. "
            "이유는 호출부가 이미 남겼다 (선행 조건 부재 또는 --skip-promotion)",
            domain,
            len(passed),
        )
        return result

    stats.append(Stat(PROMOTION_SKIPPED, domain, 0))
    keywords.promote(
        [
            (domain, domain_enum, key, observations[key].surface)
            for key in passed
            if key in observations
        ]
    )
    stats.append(Stat(PROMOTED, domain, len(passed)))
    linked = keywords.stage_and_link_contents(domain=domain, extract_run_id=extract_run_id)
    stats.append(Stat(KEYWORD_CONTENTS_LINKED, domain, linked))
    result.linked_contents = linked
    log.info(
        "[%s] 승격 %d · 별칭 %d · 보류 %d · 검수 큐 %d · 연결 %d",
        domain,
        len(passed),
        applied,
        len(resolution.parked),
        enqueued,
        linked,
    )
    return result


def _observations(registry: RegistrySink, *, domain: str) -> dict[str, Observation]:
    return {
        row[0]: Observation(
            key=row[0],
            surface=row[1],
            status=row[2],
            keyword_id=None if row[3] is None else int(row[3]),
            doc_count=int(row[4]),
            observed_days=int(row[5]),
            source_count=int(row[6]),
            author_count=int(row[7]),
        )
        for row in registry.observations(domain=domain)
    }


def _pairs(
    registry: RegistrySink,
    *,
    domain: str,
    df: dict[str, int],
    thresholds: RegistryThresholds,
) -> tuple[tuple[MergePair, ...], list[Stat]]:
    """병합 쌍 전부와 규칙별 건수.

    **기존 별칭과 검수 승인도 쌍으로 넣는다.** 매 실행 전체 닫힘을 다시 계산해야 사슬이
    생기지 않는다 (`io/keywords.ALIAS_MERGE_SQL` 의 주석).

    **표기 변형은 세기만 한다** (모듈 docstring). 탐색은 돌려서 쌍 수와 건너뜀 여부를 지표로
    남기지만, 그 쌍은 돌려주는 값에 없다 — 계산했다고 병합 후보로 다시 넣지 않는다.
    기존 별칭 중 `rule = variant` 도 같은 이유로 빠진다.
    """
    plural = normalize_rules.plural_pairs(df, domain=domain, thresholds=thresholds)
    abbreviation = merge_rules.abbreviation_pairs(
        (
            AbbreviationEvidence(
                abbreviation_key=row[0],
                expansion_key=row[1],
                initials_match=bool(row[2]),
                document_count=int(row[3]),
                source_count=int(row[4]),
            )
            for row in registry.abbreviation_evidence(domain=domain)
        ),
        domain=domain,
        df=df,
        thresholds=thresholds,
    )
    # 지표 전용. 아래 반환값에 `scan.pairs` 를 넣지 않는다 (위 docstring).
    scan = merge_rules.variant_pairs(df, domain=domain, thresholds=thresholds)
    existing = tuple(
        MergePair(
            domain=domain,
            representative=row[1],
            absorbed=row[0],
            layer=int(row[2]),
            rule=row[3],
            confidence=float(row[4]),
            # 원래 근거를 그대로 들고 온다. 잃으면 처음 병합한 이유가 지워진다 ([05 §8]).
            signal=row[5] or signal_of(),
            )
        for row in registry.aliases(domain=domain)
        if row[3] != merge_rules.RULE_VARIANT
    )
    approved = review_rules.approved_pairs(registry.approved_pairs(domain=domain))

    stats = [
        Stat(MERGE_PAIRS, f"{domain}/{merge_rules.RULE_PLURAL}", len(plural)),
        Stat(MERGE_PAIRS, f"{domain}/{merge_rules.RULE_ABBREVIATION}", len(abbreviation)),
        # 찾은 쌍 수다 — **병합한 수가 아니다** (위 docstring). 키 이름은 옛 실행과 이으려고 둔다.
        Stat(MERGE_PAIRS, f"{domain}/{merge_rules.RULE_VARIANT}", len(scan.pairs)),
        Stat(MERGE_PAIRS, f"{domain}/{review_rules.RULE_REVIEW}", len(approved)),
        # **상한 초과에서만 1 이다.** 쌍이 안 나온 정상 회차에도 1 이면 지표가 정상 상태와
        # 같은 값을 내고, 그러면 "조용히 건너뛴 것을 크게 남긴다" 가 성립하지 않는다.
        Stat(VARIANT_SCAN_SKIPPED, domain, 1 if scan.skipped else 0),
    ]
    return (*plural, *abbreviation, *existing, *approved), stats


@dataclass(frozen=True, slots=True)
class Judged:
    """심사 결과와 조건별 분포. 한 번의 순회에서 둘 다 나온다."""

    verdicts: dict[str, promote_rules.Verdict]
    # 사유 → 그 조건이 **단독으로** 막은 수 (`HELD_BY_CONDITION`). 사유 전부에 대해 키가
    # 있다 — 0 인 조건도 행을 남겨야 "안 막았다" 와 "안 셌다" 가 구분된다 (`io/stats.py`).
    condition_failures: dict[str, int]


def _judge_all(
    observations: dict[str, Observation],
    *,
    domain: str,
    groups: dict[str, tuple],
    canonical_of: dict[str, str],
    thresholds: RegistryThresholds,
) -> Judged:
    """대표마다 심사 한 번. **별칭은 심사하지 않는다** — 그 관측은 대표에 합산돼 있다.

    이미 승격된 것도 다시 심사한다. 통과하면 대표 표기를 갱신하고([05 §5] "`name` 은 바뀔
    수 있다"), 떨어져도 **되돌리지 않는다** ([05 §1]) — 그래서 아래에서 `keyword_id` 가 있는
    것은 무조건 통과로 본다.
    """
    verdicts: dict[str, promote_rules.Verdict] = {}
    condition_failures = {reason: 0 for reason in promote_rules.HELD_REASONS}
    for key, item in sorted(observations.items()):
        if key in canonical_of:
            continue
        group = groups.get(key)
        if group is None:
            continue
        doc_count, observed_days, source_count, author_count = (int(value) for value in group)
        evidence = promote_rules.PromotionEvidence(
            domain=domain,
            key=key,
            surface=item.surface,
            doc_count=doc_count,
            observed_days=observed_days,
            source_count=source_count,
            author_count=author_count,
            # 그룹 문서 수 중 대표 후보의 몫 ([05 §5] 해석은 `registry/promote.py`).
            representative_ratio=(item.doc_count / doc_count) if doc_count else 0.0,
        )
        verdict = promote_rules.judge(evidence, thresholds)
        if item.keyword_id is None:
            for reason in verdict.failed:
                condition_failures[reason] += 1
        elif not verdict.promoted:
            # 이미 승격된 것은 되돌리지 않는다. 사유는 남기지 않는다 — 보류가 아니기 때문이다.
            verdict = promote_rules.Verdict(promoted=True, reason=promote_rules.PROMOTED)
        verdicts[key] = verdict
    return Judged(verdicts=verdicts, condition_failures=condition_failures)


def _layer3(
    registry: RegistrySink,
    *,
    domain: str,
    keys: tuple[str, ...],
    observations: dict[str, Observation],
    thresholds: RegistryThresholds,
) -> tuple[tuple[MergePair, ...], int]:
    """임베딩 유사도 후보와 새로 인코딩한 표기 수. 층 3 이 꺼져 있으면 `((), 0)`."""
    if not thresholds.layer3_enabled or len(keys) < 2:
        return (), 0
    model = thresholds.embedding_model or ""
    spec = embedding_rules.EmbeddingSpec(
        model=model, dim=thresholds.embedding_dim, batch_size=thresholds.embedding_batch_size
    )
    keys_by_surface = {
        observations[key].surface: key for key in keys if key in observations
    }
    raw = registry.cached_vectors(model=model)
    cached = {
        surface: vector
        for surface, text in raw.items()
        if (vector := embedding_rules.vector_from_json(text)) is not None
    }
    fresh = embedding_rules.encode_missing(keys_by_surface, cached=cached, spec=spec)
    if fresh:
        registry.cache_vectors(
            [
                (model, surface, embedding_rules.vector_to_json(vector), len(vector))
                for surface, vector in sorted(fresh.items())
            ]
        )
    vectors = {**cached, **fresh}
    pairs = embedding_rules.similar_pairs(
        vectors,
        domain=domain,
        keys_by_surface=keys_by_surface,
        floor=float(thresholds.review_similarity_floor or 0.0),
        npmi=None,
        npmi_ceiling=thresholds.review_npmi_ceiling,
    )
    return pairs, len(fresh)


def _enqueue(
    registry: RegistrySink,
    *,
    domain: str,
    parked: tuple[MergePair, ...],
    embedding: tuple[MergePair, ...],
    df: dict[str, int],
) -> int:
    items = review_rules.review_items(
        parked=parked,
        embedding_pairs=embedding,
        doc_counts=df,
        decided=registry.decided_pairs(domain=domain),
    )
    if not items:
        return 0
    return registry.enqueue_review(
        [
            (
                item.domain,
                item.representative_key,
                item.absorbed_key,
                item.origin,
                item.layer,
                item.similarity,
                item.npmi,
                item.has_layer2_signal,
                item.priority,
                item.signal,
            )
            for item in items
        ]
    )
