"""문서 하나 → 후보 묶음. `extract/batch.py` 의 UDF 본체이고 **pyspark 를 import 하지 않는다.**

[04 §1] 의 파이프라인 중 문서 하나 안에서 끝나는 단계가 여기 있다 —
구간 다듬기(언어별) → 비교키 → 문서 안 합치기 → 형태·길이 필터.

**모델을 부르지 않는다.** 추론은 `extract/batch.py` 가 파티션 단위로 묶어서 하고
(`entities.Recognizer.predict`), 이 파일은 그 결과를 받아 후보로 만든다. 그렇게 나눈
이유는 둘이다 — 배치 추론이 성능의 전부이고, 층 1 테스트가 모델 없이 돈다.

**제목과 본문을 한 텍스트로 붙여 한 번만 추론한다.** 구간의 시작 위치가 제목 길이 안쪽이면
제목 출현이다 (`tf_title`). 따로 추론하면 문서당 호출이 두 번이 되고, 제목이 짧아 배치
효율도 나빠진다.

**후보를 문서 안에서 비교키로 합친다.** 출현마다 행을 내면 UDF 결과가 문서 길이에 비례해
커지고, 어차피 점수는 문서 × 후보 단위다.

**버린 후보도 센다.** 사유별 건수가 [04 §9] 의 모니터링이다 — "문서당 평균 후보 수" 가
급변하면 정제 실패나 필터 오작동이고, 그 숫자가 없으면 알 수 없다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Sequence

from trendin.spark.extract import abbreviations as abbr
from trendin.spark.extract import adapters, filters
from trendin.spark.extract.entities import Span
from trendin.spark.extract.keys import normalized_key

# 제목과 본문을 잇는 글자. 구간이 이 자리를 넘어 잡히지 않도록 줄바꿈을 쓴다.
JOINER = "\n"


@dataclass(frozen=True, slots=True)
class ExtractionOptions:
    """문서 하나를 처리하는 데 필요한 설정 전부. UDF 클로저에 통째로 들어간다.

    **인식기 자체는 여기 없다** — `entities.RecognizerSpec` 은 `batch.py` 가 들고 있다.
    이 파일은 이미 나온 구간만 다룬다.
    """

    adapter: adapters.AdapterSpec = field(default_factory=adapters.AdapterSpec)
    limits: filters.CandidateLimits = field(default_factory=filters.CandidateLimits)


@dataclass(frozen=True, slots=True)
class DocumentCandidate:
    """문서 안에서 합쳐진 후보 하나."""

    key: str
    # 문서 안 최고 점수 구간의 표기. 코퍼스 대표 표기는 `batch.py` 가 다시 고른다 ([04 §4]).
    surface: str
    # 모델이 붙인 유형. 화면 필터와 유형별 순위표가 쓴다. **병합이나 승격 조건에 쓰지
    # 않는다** — 정답과 맞은 후보 기준으로 유형 정확도가 77.6% 다 (`RANKED.md` §6.1).
    entity_type: str
    # 0~1. 그 문서에서 이 후보가 받은 점수다 (`_score` 참고).
    score: float
    ntokens: int
    tf: int
    tf_title: int
    is_proper: bool

    def as_row(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "surface": self.surface,
            "entity_type": self.entity_type,
            "score": self.score,
            "ntokens": self.ntokens,
            "tf": self.tf,
            "tf_title": self.tf_title,
            "is_proper": self.is_proper,
        }


@dataclass(frozen=True, slots=True)
class DocumentExtraction:
    candidates: tuple[DocumentCandidate, ...]
    abbreviations: tuple[abbr.AbbreviationPair, ...]
    # BM25 의 문서 길이 — **글자 수**다. 옛 경로는 토큰 수였는데, 공백으로 어절을 가르지 않는
    # 일본어에서 그 값이 0 에 가까워져 언어마다 척도가 달라진다. BM25 는 이제 점수에 들어가지
    # 않고 기록만 되므로(`extract/batch.py`), 언어를 가리지 않는 척도를 쓴다.
    doc_len: int
    # 문서 안 필터가 버린 비교키 수, 사유별.
    dropped: dict[str, int]

    def as_row(self) -> dict[str, Any]:
        """UDF 반환값. 칸 이름은 `batch.extraction_schema` 와 한 쌍이다."""
        return {
            "candidates": [item.as_row() for item in self.candidates],
            "abbreviations": [
                {
                    "abbreviation": pair.abbreviation,
                    "expansion": pair.expansion,
                    "abbreviation_key": pair.abbreviation_key,
                    "expansion_key": pair.expansion_key,
                    "initials_match": pair.initials_match,
                }
                for pair in self.abbreviations
            ],
            "doc_len": self.doc_len,
            "dropped": dict(self.dropped),
        }


def document_text(title: str | None, body: str | None) -> tuple[str, int]:
    """`(모델에 넣을 텍스트, 제목 길이)`.

    본문이 없는 문서(`hn` · `members_only`)는 제목만으로 돈다 — [03 §2] 가 그런 문서를 살려
    보낸 이유가 이것이다.

    `body_code` 는 읽지 않는다. [03 §4] 가 코드를 본문에서 떼어 둔 이유가 DF 통계 오염이고,
    여기서 다시 합치면 그 결정이 무효가 된다.
    """
    head = (title or "").strip()
    tail = (body or "").strip()
    if head and tail:
        return f"{head}{JOINER}{tail}", len(head)
    if head:
        return head, len(head)
    return tail, 0


def extract_document(
    title: str | None,
    body: str | None,
    lang: str | None,
    spans: Sequence[Span],
    *,
    options: ExtractionOptions,
) -> DocumentExtraction:
    """인식된 구간 → 문서 안 후보.

    `spans` 는 `document_text` 가 만든 텍스트에 대한 것이어야 한다 — `start` 로 제목 출현을
    가르기 때문이다.
    """
    text, title_len = document_text(title, body)
    dropped: Counter[str] = Counter()

    refined = adapters.refine(list(spans), lang, spec=options.adapter)
    dropped[filters.LABEL] = max(0, len(spans) - len(refined))

    merged = _merge(refined, title_len=title_len)
    kept: list[DocumentCandidate] = []
    for item in merged:
        reason = filters.rejection_reason(item.key, limits=options.limits)
        if reason is None:
            kept.append(item)
        else:
            dropped[reason] += 1

    return DocumentExtraction(
        candidates=tuple(kept),
        abbreviations=tuple(_dedupe_pairs(abbr.abbreviation_pairs(text))),
        doc_len=len(text),
        dropped={reason: n for reason, n in dropped.items() if n},
    )


def _merge(spans: Sequence[Span], *, title_len: int) -> list[DocumentCandidate]:
    """구간 → 비교키별 하나. **등장 순서를 유지한다** — 결정적이어야 스냅샷이 선다 ([04 §9]).

    같은 실체가 여러 번 나오면 최고 점수를 쓰고, 표기는 그 최고 점수 구간의 것을 쓴다.
    최빈 표기가 아니라 최고 점수 표기인 이유는, 모델이 확신한 자리가 경계도 제대로 잡힌
    자리이기 때문이다 (`제니` 0.90 과 `제니가 알려주는` 0.31 중 앞의 것).
    """
    order: list[str] = []
    best: dict[str, Span] = {}
    tf: Counter[str] = Counter()
    tf_title: Counter[str] = Counter()
    proper: dict[str, bool] = {}

    for span in spans:
        key = normalized_key(span.surface)
        if not key:
            continue
        if key not in best:
            order.append(key)
            best[key] = span
            proper[key] = False
        elif span.score > best[key].score:
            best[key] = span
        proper[key] = proper[key] or span.is_proper
        tf[key] += 1
        if span.start < title_len:
            tf_title[key] += 1

    return [
        DocumentCandidate(
            key=key,
            surface=best[key].surface,
            entity_type=best[key].label,
            score=_score(best[key].score, tf[key]),
            ntokens=len(key.split(" ")),
            tf=tf[key],
            tf_title=tf_title[key],
            is_proper=proper[key],
        )
        for key in order
    ]


# 문서 안에서 거듭 나온 후보에 주는 가산. **작게 둔다** — 반복은 약한 신호이고, 크게 주면
# 기사마다 쏟아지는 일반명사가 상위를 먹는다. 0.1 은 `scratchpad/kwlab` 이 F1 0.504 를 낸
# 설정 그대로다.
REPEAT_BONUS = 0.1


def _score(best: float, tf: int) -> float:
    """모델 점수에 반복 가산. **0~1 을 넘지 않는다** — `score_floor` 가 그 척도다."""
    return min(1.0, best * (1.0 + REPEAT_BONUS * (tf - 1)))


def _dedupe_pairs(pairs: list[abbr.AbbreviationPair]) -> list[abbr.AbbreviationPair]:
    seen: set[tuple[str, str]] = set()
    result: list[abbr.AbbreviationPair] = []
    for pair in pairs:
        marker = (pair.abbreviation_key, pair.expansion_key)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(pair)
    return result
