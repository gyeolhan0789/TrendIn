"""문서 하나 → 후보 묶음. `extract/batch.py` 의 UDF 본체이고 **pyspark 를 import 하지 않는다.**

[04 §1] 의 파이프라인 중 문서 하나 안에서 끝나는 단계가 여기 있다 —
토큰화 → 후보 생성 → 비교키 → 문서 안 필터(형태·길이·불용어·노이즈). 코퍼스를 봐야 하는
DF 필터 · 대표 표기 · 스코어링은 `batch.py` 가 Spark 로 한다.

**후보를 문서 안에서 비교키로 합친다.** 출현마다 행을 내면 UDF 결과가 문서 길이에 비례해
커지고, 어차피 점수는 문서 × 후보 단위다. 대신 문서 안 빈도(`tf`) · 제목 빈도(`tf_title`) ·
포함 관계(`parents`)를 합쳐 든다.

**버린 후보도 센다.** 사유별 건수가 [04 §9] 의 모니터링이다 — "문서당 평균 후보 수" 가
급변하면 정제 실패나 필터 오작동이고, 그 숫자가 없으면 알 수 없다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from trendin.spark.extract import candidates as cand
from trendin.spark.extract import filters
from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.lexicon import Lexicon


@dataclass(frozen=True, slots=True)
class ExtractionOptions:
    """문서 하나를 처리하는 데 필요한 설정 전부. UDF 클로저에 통째로 들어간다."""

    lexicon: Lexicon
    ngram_max: int = 3
    limits: filters.CandidateLimits = field(default_factory=filters.CandidateLimits)
    tokenize: tk.TokenizeOptions = field(default_factory=tk.TokenizeOptions)


@dataclass(frozen=True, slots=True)
class DocumentCandidate:
    """문서 안에서 합쳐진 후보 하나."""

    key: str
    # 문서 안 최다 표기. 코퍼스 대표 표기는 `batch.py` 가 다시 고른다 ([04 §4]).
    surface: str
    kind: str
    ntokens: int
    tf: int
    tf_title: int
    parents: tuple[str, ...]
    # 이 문서의 어느 출현에서든 고유명사 태그를 받았나 ([04 §6]).
    is_proper: bool = False

    def as_row(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "surface": self.surface,
            "kind": self.kind,
            "ntokens": self.ntokens,
            "tf": self.tf,
            "tf_title": self.tf_title,
            "parents": list(self.parents),
            "is_proper": self.is_proper,
        }


@dataclass(frozen=True, slots=True)
class DocumentExtraction:
    candidates: tuple[DocumentCandidate, ...]
    abbreviations: tuple[cand.AbbreviationPair, ...]
    # BM25 의 문서 길이 — 제목 + 본문 토큰 수, 불용어 포함.
    doc_len: int
    # 문서 안 필터가 버린 비교키 수, 사유별.
    dropped: dict[str, int]

    def as_row(self) -> dict[str, Any]:
        """UDF 반환값. 칸 이름은 `batch.EXTRACTION_SCHEMA` 와 한 쌍이다."""
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


def extract_document(
    title: str | None, body: str | None, lang: str | None, *, options: ExtractionOptions
) -> DocumentExtraction:
    """제목 + 본문 → 문서 안 후보. 본문이 없는 문서(`hn` · `members_only`)는 제목만으로 돈다 —
    [03 §2] 가 그런 문서를 살려 보낸 이유가 이것이다.

    `body_code` 는 읽지 않는다. [03 §4] 가 코드를 본문에서 떼어 둔 이유가 DF 통계 오염이고,
    여기서 다시 합치면 그 결정이 무효가 된다. 코드 안의 진짜 키워드(`kubectl`)는 대개 본문
    문장에도 나온다.
    """
    title_tokens = tk.tokenize(title, lang, lexicon=options.lexicon, options=options.tokenize)
    body_tokens = tk.tokenize(body, lang, lexicon=options.lexicon, options=options.tokenize)

    occurrences = cand.ngram_candidates(
        cand.spans(title_tokens), ngram_max=options.ngram_max, in_title=True
    )
    occurrences += cand.ngram_candidates(
        cand.spans(body_tokens), ngram_max=options.ngram_max, in_title=False
    )

    merged = _merge(occurrences)
    kept: list[DocumentCandidate] = []
    dropped: Counter[str] = Counter()
    for item in merged:
        reason = filters.rejection_reason(item.key, lexicon=options.lexicon, limits=options.limits)
        if reason is None:
            kept.append(item)
        else:
            dropped[reason] += 1

    text = "\n".join(part for part in (title, body) if part)
    return DocumentExtraction(
        candidates=tuple(kept),
        abbreviations=tuple(_dedupe_pairs(cand.abbreviation_pairs(text))),
        doc_len=tk.doc_length(title_tokens) + tk.doc_length(body_tokens),
        dropped=dict(dropped),
    )


def _merge(occurrences: list[cand.Occurrence]) -> list[DocumentCandidate]:
    """출현 → 비교키별 하나. 등장 순서를 유지한다 — 결정적이어야 스냅샷이 선다 ([04 §9])."""
    order: list[str] = []
    surfaces: dict[str, Counter[str]] = {}
    kinds: dict[str, str] = {}
    ntokens: dict[str, int] = {}
    tf: Counter[str] = Counter()
    tf_title: Counter[str] = Counter()
    parents: dict[str, set[str]] = {}
    proper: dict[str, bool] = {}
    for occ in occurrences:
        if occ.key not in kinds:
            order.append(occ.key)
            kinds[occ.key] = occ.kind
            ntokens[occ.key] = occ.ntokens
            surfaces[occ.key] = Counter()
            parents[occ.key] = set()
            proper[occ.key] = False
        proper[occ.key] = proper[occ.key] or occ.is_proper
        surfaces[occ.key][occ.surface] += 1
        tf[occ.key] += 1
        if occ.in_title:
            tf_title[occ.key] += 1
        parents[occ.key].update(occ.parents)

    result: list[DocumentCandidate] = []
    for key in order:
        # 최다 표기. 동률이면 먼저 나온 것 — `Counter.most_common` 은 삽입 순서를 지킨다.
        surface = surfaces[key].most_common(1)[0][0]
        result.append(
            DocumentCandidate(
                key=key,
                surface=surface,
                kind=kinds[key],
                ntokens=ntokens[key],
                tf=tf[key],
                tf_title=tf_title[key],
                parents=tuple(sorted(parents[key])),
                is_proper=proper[key],
            )
        )
    return result


def _dedupe_pairs(pairs: list[cand.AbbreviationPair]) -> list[cand.AbbreviationPair]:
    seen: set[tuple[str, str]] = set()
    result: list[cand.AbbreviationPair] = []
    for pair in pairs:
        marker = (pair.abbreviation_key, pair.expansion_key)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(pair)
    return result
