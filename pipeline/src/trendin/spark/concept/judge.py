"""미등록 표기 → LLM 에게 물을 질문, 그리고 그 답 읽기.

**여기서 부르지 않는다.** 프롬프트를 만들고 답을 읽는 순수 함수만 둔다. 실제 호출은
`io/llm.py`, 진입점은 `scripts/concept-judge.py` 다. 그래야 키 없이 시험할 수 있고, 크레딧이
드는 일이 한 곳에만 있어 눈에 띈다.

## 무엇을 묻나

**첫 판정에는 후보를 보여 주고 고르라고 하지 않는다.** 2026-09-18 실측에서 미등록 475개에
후보를 뽑아 보니 1순위가 거의 다 틀렸다 — 정답 개념이 사전에 아예 없어서다. 틀린 후보를
보여 주면 모델이 거기 끌려간다. 그래서 묻는 것은 하나다:
**"이 말의 영어 이름과 분류가 무엇이냐."**

찾는 일은 우리가 한다. 받은 영어 이름으로 사전을 정확히 조회한다. 벡터 조회를 켜면
정확 일치가 없는 경우에만 별도 프롬프트에서 후보를 보여 주고 같은 대상인지 확인한다.

```
빈티지 → LLM → vintage / style  → 사전 조회 → 있으면 잇고 없으면 새로
제니   → LLM → Jennie / person  → 없음 → 새 개념(인물)
여름   → LLM → summer / generic → 새 개념이되 세지 않음
```

## 토큰을 아끼는 방법

- **표현 종류당 한 번만 묻는다.** 기사마다도 발생마다도 아니다.
- **한 번에 여러 개를 묶는다.** 지시문을 나눠 낸다.
- **답을 짧게 받는다.** gpt-4o-mini 는 출력 단가가 입력의 네 배라 여기가 제일 비싸다.
  설명을 받지 않고 `{"i":1,"en":"vintage","cat":"style"}` 만 받는다.
- **첫 판정에도 문맥을 넣는다 (2026-09-22 에 뒤집었다).** 원래는 토큰을 아끼려고 낱말만
  던졌는데, 그 절약이 다의어 오연결로 돌아왔다. 같은 표기에 뜻이 다른 실제 기사 문맥을 준
  여섯 쌍에서 **여섯 쌍 모두 같은 답**이 나왔다 — 프로그래밍 기사의 `coach` 와 Tapestry 실적
  기사의 `Coach` 가 똑같이 패션 브랜드로 이어졌다. 낱말만 보는 한 구조적으로 못 푼다.
  넣는 것은 기사 제목이 아니라 **그 낱말이 실제로 나온 문장**이다 (`concept/context.py`).

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# v4 (2026-09-22): `event` 를 `media` 에서 떼어냈다. v3 은 첫 판정에 등장 문장을 실었다.
# **올리지 않으면 옛 분류로 내린 판정이 그대로 재사용된다** — 판정 캐시와 `workflow.reusable`
# 이 둘 다 이 값을 열쇠로 쓴다.
PROMPT_VERSION = "name-v4"

# 분류는 `pl_concept_category` 와 같아야 한다 (`io/concepts.py` DDL).
CATEGORIES = (
    "apparel",
    "footwear",
    "accessory",
    "material",
    "color",
    "style",
    "brand",
    "designer",
    "person",
    "media",
    "event",
    "generic",
)

# 세지 않는 분류. 순위에 올릴 대상이 아니므로 개념에 잇지도 않는다.
#
# **`media` 를 따로 둔 이유** — 2026-09-22 안정성 측정에서 같은 입력 두 번에 결정이 어긋난
# 4건이 전부 잡지였다 (`Vogue Italia` · `British Vogue` · `Glamour` · `GQ`). 잡지는 상식적으로
# 브랜드이기도 해서, 칸이 `generic` 과 `brand` 뿐이면 모델이 매번 다르게 고른다. 자기 자리를
# 주면 흔들릴 이유가 없어진다. 순위 51 · 69 · 85 · 101 위라 화면에 바로 보이는 자리였다.
#
# **`event` 는 여기 없다.** 처음에는 패션위크·갈라를 `media` 에 함께 넣었는데 잘못이었다 —
# 잡지는 패션을 **보도하는** 쪽이고 패션위크는 **패션 자체**다. 추출기도 `컬렉션 또는 행사` 를
# 별도 라벨로 갖고 있어 그쪽 구분과도 맞다. 행사를 세기로 한 것은 제품 결정이라, 뒤집을 때는
# 이 집합에 더하지 말고 개념의 `countable` 을 내린다 — 분류는 그대로 두고 세는지만 바꾸는
# 쪽이 되돌리기 쉽다.
UNCOUNTED = frozenset({"generic", "media"})

SYSTEM_PROMPT = """You label keywords taken from fashion media for a trend database.
Each item has "w" (the keyword) and may have "c", one sentence where it actually appeared.
When "c" is present, judge the keyword AS USED IN THAT SENTENCE, not by the word alone.
The same word can be a fashion brand in one article and an everyday word in another.
For each item give "en" (the English name of the thing) and "cat" (one category).
Categories: apparel, footwear, accessory, material, color, style, brand, designer, person, \
media, event, generic.
- person: a real individual (celebrity, model, athlete). Give the usual English name.
- designer: a fashion designer. brand: a label, house or company that makes or sells fashion.
- media: something that REPORTS ON fashion - magazines (Vogue, GQ, Elle), websites, TV networks, \
social platforms, photo agencies. A magazine is a company, but here it is media, never brand.
- event: an occasion fashion HAPPENS AT - fashion weeks, galas, film festivals, award shows, \
runway seasons. Not media: a magazine covers the event, the event is not the magazine.
- generic: not a fashion trend worth counting - everyday words, seasons, emotions, places.
- "en" is ALWAYS a real English word or name, never a category name. Even for generic items: \
yeoreum -> {"en":"summer","cat":"generic"}.
- Use the term fashion media actually uses, in the singular. Common nouns lowercase, \
proper names capitalized.
- If you cannot tell what a word means, still give your best English rendering, cat generic.
Reply with JSON only, no prose: {"r":[{"i":1,"en":"vintage","cat":"style"}]}
One object per input id, same ids, same order."""

DEFAULT_BATCH_SIZE = 10  # 20 이면 묶음 뒤쪽이 뭉개진다 (conf/base.yaml `automation.batch_size`)


def usable_context(context: str | None, *identifiers: str | None) -> bool:
    """이 문맥이 표기 말고 다른 정보를 담고 있나.

    비었거나 표기를 되풀이한 것뿐이면 없는 것으로 친다. 평가 문서의 "문맥 없는 표기는 점수와
    무관하게 유보한다" 를 실제로 지키는 자리다 — 관문이 문맥의 **존재**만 보고 있어서
    `Coach` 의 문맥이 `Coach` 한 낱말이어도 통과했다. 브랜드인지 감독인지 가릴 근거가 하나도
    없는데 자동으로 이어진다.

    **길이로는 자르지 않는다.** 2026-09-22 운영 미등록 6,920건에서 표기를 뺀 나머지가 열 자
    미만인 것이 10건뿐이었고, 그마저 `모델 배윤영의 로맨틱 코어` 처럼 멀쩡한 기사 제목이었다.
    문턱을 세우면 잡는 것보다 버리는 것이 많다. 실제로 갈리는 것은 문맥이 아예 없는 376건이다.
    """
    text = (context or "").strip()
    if not text:
        return False
    folded = text.casefold()
    for item in identifiers:
        key = (item or "").strip().casefold()
        if key and folded == key:
            return False
    return True


@dataclass(frozen=True, slots=True)
class Question:
    """물을 표현 하나. `index` 는 이 배치 안에서만 쓰는 번호다."""

    index: int
    lang: str
    normalized: str
    article_count: int
    context: str | None = None
    surface: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        """판정 기록과 미등록 표를 잇는 열쇠. 두 곳이 같은 쌍을 쓴다."""
        return (self.lang, self.normalized)


@dataclass(frozen=True, slots=True)
class Verdict:
    lang: str
    normalized: str
    english_name: str
    category: str


def batches(questions: list[Question], size: int = DEFAULT_BATCH_SIZE) -> list[list[Question]]:
    return [questions[i : i + size] for i in range(0, len(questions), size)]


# 문맥 한 줄의 길이 상한. 프롬프트에 그대로 실린다.
CONTEXT_CHARS = 200


def user_prompt(batch: list[Question]) -> str:
    """배치 하나의 사용자 메시지. 공백 없는 JSON 이라 토큰이 덜 든다.

    문맥은 **있을 때만** 싣는다. 없는 자리를 빈 문자열로 채우면 토큰만 쓰고, 모델이 문맥이
    있는 항목과 없는 항목을 구분하지 못한다.
    """
    items = []
    for question in batch:
        item = {"i": question.index, "w": question.normalized}
        context = (question.context or "").strip()
        if context and context.casefold() != question.normalized.casefold():
            item["c"] = context[:CONTEXT_CHARS]
        items.append(item)
    return json.dumps({"items": items}, ensure_ascii=False, separators=(",", ":"))


def messages(batch: list[Question]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt(batch)},
    ]


def parse(content: str, batch: list[Question]) -> tuple[list[Verdict], list[str]]:
    """답 → 판정 목록과 문제 목록.

    **못 읽은 항목을 조용히 버리지 않는다.** 배치로 묶으면 모델이 개수를 빠뜨리거나 번호를
    섞을 수 있어서, 어긋난 것은 문제로 올려 부른 쪽이 그 항목만 다시 묻게 한다.
    """
    problems: list[str] = []
    try:
        payload = json.loads(_strip_fence(content))
    except json.JSONDecodeError as error:
        return [], [f"JSON 이 아니다: {error}"]

    rows = payload.get("r") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return [], ["답에 r 목록이 없다"]

    by_index = {q.index: q for q in batch}
    verdicts: list[Verdict] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            problems.append(f"항목이 객체가 아니다: {row!r}")
            continue
        index = row.get("i")
        question = by_index.get(index) if isinstance(index, int) else None
        if question is None:
            problems.append(f"모르는 번호: {index!r}")
            continue
        name = str(row.get("en") or "").strip()
        category = str(row.get("cat") or "").strip().lower()
        if not name:
            problems.append(f"{question.normalized}: 영어 이름이 비었다")
            continue
        if name.lower() == "generic":
            # v1 에서 38건이 이랬다. 그대로 두면 서른여덟 개가 한 개념으로 뭉친다.
            # 다른 분류 이름은 막지 않는다 — `액세서리`→accessory 는 옳은 답이다.
            problems.append(f"{question.normalized}: 영어 이름 자리에 generic 이 왔다")
            continue
        if category not in CATEGORIES:
            problems.append(f"{question.normalized}: 모르는 분류 {category!r}")
            continue
        seen.add(question.index)
        verdicts.append(
            Verdict(
                lang=question.lang,
                normalized=question.normalized,
                english_name=name,
                category=category,
            )
        )
    missing = [by_index[i].normalized for i in sorted(set(by_index) - seen)]
    if missing:
        problems.append("답이 없는 표현: " + ", ".join(missing))
    return verdicts, problems


def estimate_tokens(text: str) -> int:
    """토큰 어림값. **재는 것이 아니라 어림잡는 것이다.**

    `tiktoken` 을 넣으면 정확히 셀 수 있지만 그 의존성은 이 견적 하나 때문에 모두의 환경에
    들어간다. 라틴 글자는 네 글자에 한 토큰, 그 밖(한글·가나·아랍)은 한 글자에 한 토큰으로
    잡는다 — 실제보다 조금 많게 나오는 쪽이라 견적으로는 안전하다.
    """
    latin = sum(1 for ch in text if ch.isascii())
    other = len(text) - latin
    return round(latin / 4 + other) + 4


def _strip_fence(content: str) -> str:
    """```json ... ``` 로 감싸 오는 경우를 벗긴다."""
    text = content.strip()
    if not text.startswith("```"):
        return text
    body = text.split("\n", 1)[1] if "\n" in text else ""
    return body.rsplit("```", 1)[0].strip()


# ---------------------------------------------------------------------------
# 받은 영어 이름으로 사전을 찾는 자리. **모델에게 고르라고 하지 않는다.**


@dataclass(frozen=True, slots=True)
class Resolution:
    """이 영어 이름을 어떻게 할 것인가.

    | 값 | 뜻 |
    | --- | --- |
    | `LINK` | 같은 이름의 개념이 이미 있다. 그 개념의 표현으로 넣는다 |
    | `CHECK` | 아주 닮은 이름이 있다. 같은 것일 수 있으니 **사람이 본다** |
    | `NEW` | 닮은 것도 없다. 새 개념을 만든다 |
    """

    decision: str
    concept_ids: tuple[int, ...]
    near: tuple[tuple[str, float], ...] = ()


DECISION_LINK = "LINK"
DECISION_CHECK = "CHECK"
DECISION_NEW = "NEW"

# 이보다 닮으면 사람이 본다. `polo` 와 `polo shirt` 처럼 한쪽이 다른 쪽을 품는 경우를 잡는다.
NEAR_SIMILARITY = 0.82
NEAR_LIMIT = 3


def name_key(name: str) -> str:
    """영어 이름의 비교키. 소문자 · 앞뒤 구두점 · 연속 공백만 손본다."""
    text = " ".join(name.lower().replace("-", " ").split())
    return text.strip(".,'\"()[]")


def name_variants(key: str) -> tuple[str, ...]:
    """단수·복수 흔들림. `shoes` 와 `shoe`, `flats` 와 `flat` 이 갈리지 않게 한다.

    영어 복수 규칙을 다 담지 않는다 — 여기서 맞히려는 것은 사전에 이미 있는 이름과의 충돌이고,
    빗나가면 `CHECK` 로 떨어져 사람이 본다. 과하게 접으면 `glass` 와 `glasses` 가 합쳐진다.
    """
    out = [key]
    if key.endswith("ies"):
        out.append(key[:-3] + "y")
    elif key.endswith("es"):
        out.append(key[:-2])
        out.append(key[:-1])
    elif key.endswith("s"):
        out.append(key[:-1])
    else:
        out.append(key + "s")
        out.append(key + "es")
    return tuple(dict.fromkeys(out))


class NameIndex:
    """영어 이름 → 개념 번호. 사전의 대표 이름과 라틴 표기에서 세운다.

    조회가 이름 대 이름이라 앞서 실패한 소리·글자 닮음과 다르다 — 양쪽 다 영어라 같은 것을
    같은 글자로 적는다.
    """

    def __init__(self, dictionary) -> None:  # noqa: ANN001 — Dictionary. 층 1 순환 참조를 피한다
        self._by_name: dict[str, set[int]] = {}
        self._category: dict[int, str] = {}
        for concept in dictionary.concepts():
            self._category[concept.concept_id] = concept.category
            self._add(name_key(concept.canonical_name), concept.concept_id)
        for expression in dictionary.expressions():
            if expression.lang in ("en", "la"):
                self._add(name_key(expression.normalized), expression.concept_id)
        self._names = sorted(self._by_name)
        self._blocks: dict[str, list[str]] = {}
        for name in self._names:
            self._blocks.setdefault(name[:1], []).append(name)

    def _add(self, key: str, concept_id: int) -> None:
        if key:
            self._by_name.setdefault(key, set()).add(concept_id)

    def __len__(self) -> int:
        return len(self._by_name)

    def resolve(self, english_name: str, category: str | None = None) -> Resolution:
        """이름으로 찾되 **분류가 맞아야 잇는다.**

        `에스파 윈터`(사람)와 `겨울`(계절)이 둘 다 `Winter` 로 온다. 이름만 보고 합치면 사람과
        계절이 한 개념이 된다. 분류가 다르면 잇지 않고 사람에게 넘긴다.
        """
        key = name_key(english_name)
        if not key:
            return Resolution(DECISION_NEW, ())
        for variant in name_variants(key):
            found = self._by_name.get(variant)
            if not found:
                continue
            if category is None:
                return Resolution(DECISION_LINK, tuple(sorted(found)))
            same = tuple(sorted(c for c in found if self._category.get(c) == category))
            if same:
                return Resolution(DECISION_LINK, same)
            # 같은 이름이 다른 분류로 이미 있다. 사람이 볼 자리다.
            return Resolution(DECISION_CHECK, tuple(sorted(found)), ((variant, 1.0),))
        near = self._near(key)
        if near:
            return Resolution(DECISION_CHECK, (), near)
        return Resolution(DECISION_NEW, ())

    def exact_link(self, english_name: str, category: str) -> int | None:
        """자동 반영용: 이름이 정확히 한 개념에만 걸리고 분류도 맞을 때만 잇는다.

        단복수·유사도 후보는 검수에만 쓴다. 같은 이름이 다른 분류에도 있으면
        LLM 분류 하나만 믿고 고르지 않는다.
        """
        found = self._by_name.get(name_key(english_name), set())
        if len(found) != 1:
            return None
        concept_id = next(iter(found))
        return concept_id if self._category[concept_id] == category else None

    def _near(self, key: str) -> tuple[tuple[str, float], ...]:
        """첫 글자와 길이로 먼저 좁히고 남은 것만 견준다. 사전 전체를 훑지 않는다."""
        from difflib import SequenceMatcher

        found: list[tuple[str, float]] = []
        for name in self._blocks.get(key[:1], ()):
            if abs(len(name) - len(key)) > max(3, len(key) // 2):
                continue
            score = SequenceMatcher(None, key, name).ratio()
            if score >= NEAR_SIMILARITY:
                found.append((name, round(score, 3)))
        found.sort(key=lambda pair: (-pair[1], pair[0]))
        return tuple(found[:NEAR_LIMIT])
