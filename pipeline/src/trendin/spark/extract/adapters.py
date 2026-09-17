"""언어별 후처리 — **언어를 아는 곳은 여기 하나다** ([04 §2]).

모델은 언어와 무관하게 한 번 돈다 (`extract/entities.py`). 언어마다 갈리는 것은 그 뒤에
구간을 어떻게 다듬느냐뿐이고, 그것을 이 파일에 몬다. 옛 경로는 `tokenize.py` ·
`morphology.py` · `lexicon.py` · `filters.py` 넷이 각자 언어를 알고 있었다.

## 언어마다 할 일이 다른 이유

| 언어 | 증상 | 대응 |
| --- | --- | --- |
| `en` | 구간 안에 줄바꿈이 들어온다 (`bias-cut slip\\ndress`) | 공백 접기 |
| `ko` | 조사째 잘린다 (`제니가` · `데님 팬츠가`) | 형태소로 꼬리 제거 |
| `ja` | **절이 통째로 나온다** | 라벨 제한 + 길이 상한 |

**한국어의 꼬리 제거가 성능의 절반이다** (F1 0.293 → 0.464, `scratchpad/kwlab/RESULTS.md`
§2.2). 다국어 모델은 한국어 어절 경계를 모르는데, 분석기가 조사로 태그한 꼬리를 떼면
사라지고 **사전 항목이 하나도 늘지 않는다.**

## 일본어를 반만 켜는 이유

일본어 실기사 3건에서 원본 구간의 32%·36%·60% 가 절이거나 복합 구간이었다
(`MULTILINGUAL.md` §2.3) — `ウールコットンのカーディガン背面やスウェットのフロントには` 처럼
문장의 절반이 한 구간으로 나온다. 일본어에 어절을 가르는 공백이 없어 모델이 경계를 잡을
근거가 더 적기 때문이다.

한국어처럼 형태소로 고치려 해 봤고 **값을 다 치르지 못했다** (같은 문서 §3) — 절을 명사구로
쪼개면 조각들이 절 전체의 점수와 유형을 물려받고, 무엇보다 `Brooks Brothers` 가
`BrooksBrothers` 로 공백을 잃는다. 브랜드는 일본어에서 유일하게 잘 잡히는 것인데 후처리가
바로 그것을 망가뜨린다.

그래서 **브랜드와 인물만 통과시킨다.** 그 둘은 후처리 없이도 0.83~0.99 로 나온다. 품목·
소재·스타일은 일본어 정답을 만들어 재기 전까지 끈다 — 끄는 것은 설정 한 줄이다.

⚠️ **2026-09-17 현재 이 갈래는 돌지 않는다.** 다국가 소스 확장이 들어오면서 정제가
`ja`·`zh`·`fr`·`it` 를 `UNSUPPORTED_LANG` 으로 걸러 `curated` 에 넣지 않는다
(`normalize/filters.py`). 여기까지 오는 문서에 일본어가 없으므로 아래 라벨 제한과 글자 수
상한은 지금 아무 일도 하지 않는다. **지우지 않고 두는 이유** — 그 필터를 여는 순간 그대로
쓰이고, 없으면 절이 통째로 후보가 되는 것을 다시 발견해야 한다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from trendin.spark.extract import morphology as mp
from trendin.spark.extract.entities import Span
from trendin.spark.normalize.lang import EN, JA, KO, MIXED

# 한국어 표기 끝에서 떼는 품사 — 조사(J\*) · 어미(E\*) · 부호(S\*) 와 서술격·용언 파생 접미사.
# 접두 문자로 보는 이유는 세종 태그셋이 `JKS` · `JKO` · `JX` 처럼 갈라져 있고, 그 갈래를
# 전부 적으면 표가 다시 생기기 때문이다.
_TAIL_PREFIXES = ("J", "E", "S")
_TAIL_TAGS = frozenset({"VCP", "XSV", "XSA"})

# 연속 공백과 줄바꿈 → 단일 공백. 구간이 문단을 넘어 잡힐 때 표기에 줄바꿈이 남는다.
_WHITESPACE = re.compile(r"\s+")

# 일본어 표기의 글자 수 상한. **다른 언어보다 낮다** — 공백이 없어 같은 글자 수가 더 많은
# 내용을 담고, 절이 그대로 통과하는 것을 막는 마지막 문턱이 이것이다. 브랜드명과 인물명은
# 거의 전부 이 아래다 (`ケンゾー` 4 · `セルフォード` 6 · `N.ハリウッド コンパイル` 13).
JA_MAX_CHARS = 20

# 기본 라벨 제한 — `(언어, 그 언어에서 통과시킬 라벨)`. 없는 언어는 전부 통과한다.
# **튜플인 이유** — `AdapterSpec` 이 UDF 클로저로 직렬화되고 해시 가능해야 한다.
DEFAULT_LABEL_GATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (JA, ("브랜드", "인물", "회사 또는 조직")),
)


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    """언어별 후처리에 필요한 것 전부. 작고 해시 가능해야 한다."""

    analyzer: mp.AnalyzerSpec = field(default_factory=mp.AnalyzerSpec)
    label_gates: tuple[tuple[str, tuple[str, ...]], ...] = DEFAULT_LABEL_GATES
    ja_max_chars: int = JA_MAX_CHARS

    def allows(self, lang: str | None, label: str) -> bool:
        """그 언어에서 이 라벨을 통과시키나. 제한이 없는 언어는 전부 통과한다."""
        for gate_lang, labels in self.label_gates:
            if gate_lang == lang:
                return label in labels
        return True


def refine(spans: list[Span], lang: str | None, *, spec: AdapterSpec) -> list[Span]:
    """구간 목록 → 다듬은 구간 목록. 라벨 제한에 걸리거나 표기가 비면 빠진다.

    **묶음으로 받는다.** 한국어 경로가 형태소 분석기를 부르는데, 구간마다 부르면 호출
    비용이 구간 수만큼 곱해진다 (`morphology.Analyzer.analyze` 가 줄 목록을 받는 이유와
    같다).

    `start`·`end` 는 다듬은 뒤에도 원문 기준으로 유지한다 — 꼬리를 뗀 만큼 `end` 가 줄고,
    앞은 건드리지 않는다.
    """
    gated = [span for span in spans if spec.allows(lang, span.label)]
    if not gated:
        return []
    if lang == KO or lang == MIXED:
        surfaces = _trim_korean([span.surface for span in gated], spec=spec)
    elif lang == JA:
        surfaces = [_collapse(span.surface) for span in gated]
    else:
        # `en` · `unknown` · 모르는 값. 공백만 접는다 — 영어는 조사가 없고, 모르는 언어에
        # 한국어 문법을 적용하는 것이 아무것도 안 하는 것보다 나쁘다.
        surfaces = [_collapse(span.surface) for span in gated]

    refined: list[Span] = []
    for span, surface in zip(gated, surfaces):
        if not surface:
            continue
        if lang == JA and len(surface) > spec.ja_max_chars:
            continue
        refined.append(
            Span(
                surface=surface,
                label=span.label,
                score=span.score,
                start=span.start,
                end=span.start + len(surface),
            )
        )
    return refined


def _trim_korean(surfaces: list[str], *, spec: AdapterSpec) -> list[str]:
    """표기 끝의 조사·어미를 뗀다. **라틴 문자만으로 된 표기는 건드리지 않는다.**

    `Brooks Brothers` 를 분석기에 넘길 이유가 없고, 일본어 실험에서 확인했듯이 분석기를
    거치면 라틴 표기의 공백이 사라질 위험이 있다 (`MULTILINGUAL.md` §3).
    """
    analyzer = mp.analyzer_for(spec.analyzer)
    collapsed = [_collapse(surface) for surface in surfaces]
    # 분석기에 넘길 것만 고른다. 위치를 기억해 두었다가 제자리에 돌려놓는다.
    indexes = [i for i, surface in enumerate(collapsed) if surface and not _is_latin(surface)]
    if not indexes:
        return collapsed
    analyzed = analyzer.analyze([collapsed[i] for i in indexes])
    result = list(collapsed)
    for i, morphs in zip(indexes, analyzed):
        result[i] = _strip_tail(collapsed[i], morphs)
    return result


def _strip_tail(surface: str, morphs: list[mp.Morph]) -> str:
    """형태소 목록의 끝에서 조사·어미를 걷어낸 뒤 원문을 그만큼 자른다.

    **형태소의 기본형이 아니라 원문 조각을 쓴다** — 표기는 화면에 나가는 값이다
    (`morphology.Morph` 가 `start`·`end` 를 들고 있는 이유).

    **명사 핵이 없으면 버린다.** 꼬리 제거만으로는 걸러지지 않는 것이 둘 있다 — 접속부사
    (`그리고`/MAJ)는 애초에 꼬리가 아니고, 용언 활용형(`부드러운`)은 어간의 구간이 어미를
    품고 있어(`부드럽/VA-I` 0~4) 잘라도 원표기 그대로가 된다. 규칙을 하나 더 두는 대신
    "명사가 하나도 없는 표기는 키워드가 아니다" 로 한 번에 막는다.
    """
    tail = list(morphs)
    while tail and (tail[-1].tag[0] in _TAIL_PREFIXES or tail[-1].tag in _TAIL_TAGS):
        tail.pop()
    if not tail or not any(morph.tag in mp.NOUN_CORE for morph in tail):
        return ""
    return surface[: tail[-1].end].strip()


def _collapse(surface: str) -> str:
    return _WHITESPACE.sub(" ", surface or "").strip()


def _is_latin(surface: str) -> bool:
    """한글·가나·한자가 하나도 없다. 라틴 표기와 기호·숫자로만 이루어진 표기다."""
    return not any(_is_cjk(ch) for ch in surface)


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0xAC00 <= code <= 0xD7A3  # 한글 음절
        or 0x3040 <= code <= 0x30FF  # 히라가나 · 가타카나
        or 0x4E00 <= code <= 0x9FFF  # 한자
    )


__all__ = ["AdapterSpec", "refine", "DEFAULT_LABEL_GATES", "JA_MAX_CHARS", "EN", "JA", "KO"]
