"""미등록 표기 → "이것일 수도 있는 개념" 몇 개.

정확 일치가 없을 때 사전에서 닮은 것을 끌어오는 층이다. **여기서 붙이지 않는다** — 뽑아만 주고
고르는 것은 사람이나 LLM 판정이다. 그래서 규칙마다 정밀도보다 재현율을 택하고, 대신 어느
규칙이 뽑았는지를 `source` 로 남겨 나중에 어느 규칙을 고칠지 알 수 있게 한다.

| 규칙 | 등급 | 찾는 것 | 예 |
| --- | --- | --- | --- |
| `SPACE` | 1 | 띄어쓰기만 다른 표기 | `루이 비통` ↔ `루이비통` |
| `SOUND` | 2 | 소리키가 같은 표기 | `샤넬` ↔ `Chanel` |
| `SOUND_NEAR` | 3 | 소리키가 닮은 표기 | `까르띠에` ↔ `Cartier` |
| `SPELL` | 3 | 같은 언어 안에서 글자가 닮은 표기 | `까르띠에` ↔ `카르티에` |

**띄어쓰기를 비교키에서 접지 않는 결정은 그대로다.** `the ater` 사고를 막으려고 키에서는 접지
않고, 여기서 후보로만 올린다 — 붙이는 것은 판정을 거친 뒤다.

## 왜 소리키에 다시 근사 일치를 거나

음차는 한 벌로 고정되어 있지 않다. `Cartier` 는 `kartir`, `까르띠에` 는 `karti` 라 소리키가 같지
않고, `Gucci`(`kuksi`)와 `구찌`(`kusi`)도 한 글자가 어긋난다. 정확 일치(2등급)와 나누어 세는
이유는 어느 쪽이 실제로 건지는지를 숫자로 보기 위해서다.

## 닮음을 두 단계로 재는 이유

조각(두 글자) 색인으로 **먼저 좁히고**, 남은 것에만 순서를 보는 유사도를 건다. 조각만 보면
`지방시`(`sipanksi`)와 `Jeff Banks`(`sipanks`)가 조각 집합이 같아 1.0 이 된다 — 순서와 길이를
못 본다. 그렇다고 사전 만 개에 순서 비교를 다 돌릴 수는 없어서 두 단계로 나눈다.

문턱 `0.8` 은 알려진 쌍 서른 개를 보고 고른 값이다. 짧은 표기에서는 잡음이 남는다 — `슈즈` 와
`shorts` 가 0.86 이다. 그것까지 규칙으로 막으면 `구찌`(0.89)도 같이 잃어서, 남는 잡음은
후보 다섯 개 제한과 판정이 걸러 내게 두었다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from trendin.spark.concept.dictionary import Dictionary, Expression
from trendin.spark.concept.phonetic import sound_key

SOURCE_SPACE = "SPACE"
SOURCE_SOUND = "SOUND"
SOURCE_SOUND_NEAR = "SOUND_NEAR"
SOURCE_SPELL = "SPELL"

TIER = {SOURCE_SPACE: 1, SOURCE_SOUND: 2, SOURCE_SOUND_NEAR: 3, SOURCE_SPELL: 3}

DEFAULT_LIMIT = 5
# 후보로 받아들이는 문턱. 순서를 보는 유사도에 건다.
DEFAULT_MIN_SIMILARITY = 0.8
# 조각 색인으로 좁힐 때의 문턱. 여기서 너무 조이면 순서 비교까지 가지도 못한다.
BLOCKING_SIMILARITY = 0.4
# 이보다 짧은 표기는 글자 겹침으로 보지 않는다. `백` 하나로 수백 개가 걸린다.
MIN_SPELL_LENGTH = 3


@dataclass(frozen=True, slots=True)
class Candidate:
    concept_id: int
    expression_id: int
    source: str
    score: float

    @property
    def tier(self) -> int:
        return TIER[self.source]


def bigrams(text: str) -> frozenset[str]:
    """두 글자씩. 한 글자짜리는 그 글자 하나를 조각으로 본다."""
    if len(text) < 2:
        return frozenset({text}) if text else frozenset()
    return frozenset(text[i : i + 2] for i in range(len(text) - 1))


def similarity(left: str, right: str) -> float:
    """순서를 보는 닮음. 0 에서 1."""
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


class _NgramIndex:
    """조각 → 그 조각을 가진 항목들. 조각으로 좁힌 뒤 순서를 보는 유사도로 고른다."""

    def __init__(self) -> None:
        self._by_gram: dict[str, list[int]] = defaultdict(list)
        self._text: dict[int, str] = {}
        self._gram_count: dict[int, int] = {}

    def add(self, key: int, text: str) -> None:
        if key in self._text:
            return
        grams = bigrams(text)
        self._text[key] = text
        self._gram_count[key] = len(grams)
        for gram in grams:
            self._by_gram[gram].append(key)

    def search(self, text: str, min_similarity: float) -> dict[int, float]:
        grams = bigrams(text)
        if not grams:
            return {}
        shared: dict[int, int] = defaultdict(int)
        for gram in grams:
            for key in self._by_gram.get(gram, ()):
                shared[key] += 1
        found: dict[int, float] = {}
        for key, count in shared.items():
            blocking = 2 * count / (len(grams) + self._gram_count[key])
            if blocking < BLOCKING_SIMILARITY:
                continue
            score = similarity(text, self._text[key])
            if score >= min_similarity:
                found[key] = score
        return found


class CandidateIndex:
    """사전을 한 번 훑어 색인을 세우고, 그 뒤로는 조회만 한다.

    사전 표현 만 단위에서 색인 넷이 수십 MB 다. 기사마다 세우지 않고 Job 시작에 한 번 세운다.
    """

    def __init__(self, dictionary: Dictionary) -> None:
        self._expressions: dict[int, Expression] = {}
        self._by_spaceless: dict[str, list[int]] = defaultdict(list)
        self._by_sound: dict[str, list[int]] = defaultdict(list)
        self._sound_index = _NgramIndex()
        self._spell_index: dict[str, _NgramIndex] = defaultdict(_NgramIndex)

        for expression in dictionary.expressions():
            eid = expression.expression_id
            self._expressions[eid] = expression
            self._by_spaceless[expression.normalized.replace(" ", "")].append(eid)
            sound = sound_key(expression.normalized)
            if sound:
                self._by_sound[sound].append(eid)
                self._sound_index.add(eid, sound)
            if len(expression.normalized) >= MIN_SPELL_LENGTH:
                self._spell_index[expression.lang].add(eid, expression.normalized)

    def __len__(self) -> int:
        return len(self._expressions)

    def generate(
        self,
        lang: str,
        key: str,
        *,
        limit: int = DEFAULT_LIMIT,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> tuple[Candidate, ...]:
        """이 표기가 가리킬 만한 개념들. 등급이 높은 것부터 `limit` 개에서 끊는다.

        같은 개념이 여러 규칙에 걸리면 가장 높은 등급 하나만 남는다 — LLM 에게 같은 개념을 두
        번 보여 줄 이유가 없다. 같은 글자인 표현은 후보가 아니다: 그건 정확 일치라 이 층까지
        오지 않으며, 왔다면 사전 조회가 이미 걸렀다는 뜻이다.
        """
        if not key:
            return ()
        found: list[Candidate] = []

        for eid in self._by_spaceless.get(key.replace(" ", ""), ()):
            found.append(self._candidate(eid, SOURCE_SPACE, 1.0, key))

        sound = sound_key(key)
        if sound:
            exact = set(self._by_sound.get(sound, ()))
            for eid in exact:
                found.append(self._candidate(eid, SOURCE_SOUND, 1.0, key))
            for eid, score in self._sound_index.search(sound, min_similarity).items():
                if eid not in exact:
                    found.append(self._candidate(eid, SOURCE_SOUND_NEAR, score, key))

        if len(key) >= MIN_SPELL_LENGTH and lang in self._spell_index:
            for eid, score in self._spell_index[lang].search(key, min_similarity).items():
                found.append(self._candidate(eid, SOURCE_SPELL, score, key))

        best: dict[int, Candidate] = {}
        for candidate in found:
            if candidate is None:
                continue
            current = best.get(candidate.concept_id)
            if current is None or (candidate.tier, -candidate.score) < (
                current.tier,
                -current.score,
            ):
                best[candidate.concept_id] = candidate
        ranked = sorted(best.values(), key=lambda c: (c.tier, -c.score, c.concept_id))
        return tuple(ranked[:limit])

    def _candidate(
        self, expression_id: int, source: str, score: float, key: str
    ) -> Candidate | None:
        expression = self._expressions[expression_id]
        if expression.normalized == key:
            return None
        return Candidate(
            concept_id=expression.concept_id,
            expression_id=expression_id,
            source=source,
            score=round(score, 4),
        )
