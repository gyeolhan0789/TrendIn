"""언어 판별 ([03 §5](../../../../spark/docs/03-normalization-spec.md)).

**문자 비율로 판별하고 언어 판별 라이브러리를 쓰지 않는다.** 규격이 든 이유는 셋이었다 —
(a) 키워드를 뽑는 언어가 사실상 한/영 둘뿐이고 (b) 개발 도메인 텍스트는 코드·식별자가 섞여
있어 일반 판별기가 자주 틀리며 (c) 의존성이 하나 줄어든다.

**(a) 는 2026-09-19 에 없어졌다** — 아래 여섯이 전부 `extractable` 이다. 남은 근거는 (b)·(c)
이고, 판별을 라이브러리로 바꾸려면 `hn` 제목이 프랑스어·이탈리아어로 뒤집히지 않는지를
먼저 재야 한다.

`lang` 이 필요한 이유는 [04 §2] 에서 토크나이저를 고르기 때문이다. `mixed` 는 두
토크나이저를 모두 돌리고, `unknown` 은 [03 §6] 의 품질 필터에서 대개 걸러진다.

**알아보는 언어와 추출하는 언어가 같아졌다** (`LANGUAGES`). 2026-09-19 이전에는 달랐다 —
해외 소스가 늘면서 일본어·중국어가 `unknown` 으로, 프랑스어·이탈리아어가 `en` 으로 떨어지는
것을 막으려고 판별만 넓히고 추출은 넓히지 않았고, 그래서 필터가 그 문서를 이유를 붙여 뺐다
(`filters.UNSUPPORTED_LANG`). 그 상태로 3개월치를 돌리자 **12,553건 중 6,948건이 그 사유로
버려졌다** — 일본 매체 7곳·이탈리아 3곳·프랑스 3곳·중국 2곳이 통째로였다. 사유 상수는
그대로 둔다. 언어를 다시 닫을 자리가 여기 한 칸이라 그때 다시 쓰인다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KO = "ko"
EN = "en"
MIXED = "mixed"
JA = "ja"
ZH = "zh"
FR = "fr"
IT = "it"
UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Language:
    """판별이 낼 수 있는 언어 하나. `unknown` 은 여기 없다 — 언어가 아니라 근거가 없다는 뜻이다."""

    code: str
    # 키워드 추출(`extract/tokenize.py`)이 이 언어를 다루는가. 아니면 필터가 문서를 뺀다.
    extractable: bool
    # 라틴 문자가 우세한 텍스트에서 이 언어를 가리키는 기능어. 비어 있으면 문자 비율로만 알아본다.
    function_words: frozenset[str] = frozenset()


# `de` `la` `le` `per` `con` `come` `non` 은 일부러 뺐다. 영어 제목에도 흔히 나오는 낱말
# (`de facto`, `La Liga`, `cost per token`, `pros and cons`, `non-profit`)이라 `hn` 제목이
# 프랑스어·이탈리아어로 뒤집힌다. 영어 목록에서 `a` `in` `on` `an` 을 뺀 것은 반대 방향이다 —
# 이탈리아어·프랑스어에서도 흔한 낱말이라 영어 표로 세면 진짜 이탈리아어 문단을 누른다.
LANGUAGES: dict[str, Language] = {
    language.code: language
    for language in (
        # 한글이 우세하다.
        Language(KO, extractable=True),
        # 라틴 문자가 우세하고, 다른 라틴 언어의 기능어 근거가 영어보다 강하지 않다.
        Language(
            EN,
            extractable=True,
            function_words=frozenset(
                "the and of to is for with that this from by are how what why you your it "
                "as at be was not we can will has have its into about more than which their "
                "they been were who when".split()
            ),
        ),
        # 한글과 라틴 문자가 둘 다 유의미하다.
        Language(MIXED, extractable=True),
        # 한자·가나가 유의미하고 가나가 섞여 있다.
        Language(JA, extractable=True),
        # 한자가 유의미하고 가나가 (거의) 없다.
        Language(ZH, extractable=True),
        Language(
            FR,
            extractable=True,
            function_words=frozenset(
                "les des du une est et dans avec pour sur qui que pas aux au cette ces sont "
                "ses nous vous mais ont été être très où à leur leurs aussi elle elles ils "
                "ne comme".split()
            ),
        ),
        Language(
            IT,
            extractable=True,
            function_words=frozenset(
                "il di della delle dello dei degli nel nella nelle che sono una uno gli alla "
                "alle anche questo questa più è dalla dal sulla sul tra hanno essere stato "
                "loro suo sua molto ancora dopo ogni cui perché".split()
            ),
        ),
    )
}


def unsupported(lang: str | None) -> bool:
    """알아봤지만 추출하지 않는 언어인지. `unknown` 은 여기 들지 않는다 — 기존 규칙을 따른다."""
    language = LANGUAGES.get(lang or "")
    return language is not None and not language.extractable


# 한글 — 음절(가~힣) · 자모 · 호환 자모. 자모를 넣는 이유는 초성 표기(`ㅋㅋ`)나 분해된
# 형태(NFD 로 온 텍스트)가 실제로 섞여 오기 때문이다. NFKC 를 거쳐도 자모는 합쳐지지 않는다.
_HANGUL_RANGES = (
    (0xAC00, 0xD7A3),  # 음절
    (0x1100, 0x11FF),  # 자모
    (0x3130, 0x318F),  # 호환 자모
    (0xA960, 0xA97F),  # 확장 A
    (0xD7B0, 0xD7FF),  # 확장 B
)

# `・`(U+30FB) 는 가타카나 블록에 있지만 구두점이라 뺀다. 중국어 텍스트의 가운뎃점으로도
# 쓰여서, 세면 한자뿐인 글이 `ja` 가 된다.
_KANA_RANGES = (
    (0x3041, 0x309F),  # 히라가나
    (0x30A0, 0x30FA),  # 가타카나
    (0x30FC, 0x30FF),
    (0x31F0, 0x31FF),  # 가타카나 음성 확장
    (0xFF66, 0xFF9F),  # 반각 가타카나
)

_HAN_RANGES = (
    (0x3400, 0x4DBF),  # 확장 A
    (0x4E00, 0x9FFF),  # 통합 한자
    (0xF900, 0xFAFF),  # 호환 한자
    (0x20000, 0x2FA1F),  # 확장 B 이후
)

_WORD = re.compile(r"[^\W\d_]+")


@dataclass(frozen=True, slots=True)
class LangThresholds:
    """판별 문턱. `conf/*.yaml` 의 `ingest.normalize.lang` 에서 온다.

    **기본값은 잠정이다** ([09 §7] 항목 5). 실데이터의 문자 비율 분포를 재기 전에 정한
    숫자라, [S6](../../../../spark/docs/10-delivery-plan.md) 에서 다시 정한다. 여기 값을
    코드에 박지 않고 설정으로 뺀 이유가 그것이다.
    """

    # 한쪽 문자가 이 비율을 넘으면 그 언어로 본다.
    dominant: float = 0.6
    # 두 언어가 각각 이 비율을 넘으면 `mixed`.
    secondary: float = 0.2
    # 글자(한글+라틴)가 이 개수 미만이면 `unknown`. 제목만 있는 문서가 여기 걸린다.
    min_letters: int = 10
    # 한자·가나가 이 개수 이상이어야 `ja`·`zh` 를 본다. `min_letters` 와 따로 두는 이유는
    # 한 글자가 담는 정보가 많아서다 — 10자 하한이면 일본어 제목 대부분이 `unknown` 이 된다.
    cjk_min_letters: int = 5
    # 전체 글자 중 한자·가나 비율이 이 이상이어야 `ja`·`zh`. 영문 기사에 섞인 회사명 한 줄은
    # 여기 못 미친다.
    cjk_share: float = 0.3
    # 한자·가나 중 가나 비율이 이 이상이면 `ja`, 미만이면 `zh`.
    kana_share: float = 0.05
    # 낱말이 이보다 적으면 기능어를 보지 않고 `en` 이다. 짧은 영어 제목이 뒤집히지 않게 한다.
    latin_min_words: int = 6
    # 영어가 아닌 라틴 언어로 보려면 기능어가 이만큼 나오고 영어 기능어보다 많아야 한다.
    latin_min_hits: int = 3

    @classmethod
    def from_section(cls, section: dict) -> "LangThresholds":
        """설정 구역에서. 빈 구역이면 기본값 그대로다.

        **기본값을 인스턴스에서 읽는다.** `slots=True` 데이터클래스에서 `cls.dominant` 는
        기본값이 아니라 슬롯 서술자라, `float()` 에 넣으면 `TypeError` 로 죽는다 — 설정
        구역이 비어 있는 모든 실행에서.
        """
        default = cls()
        return cls(
            dominant=float(section.get("dominant", default.dominant)),
            secondary=float(section.get("secondary", default.secondary)),
            min_letters=int(section.get("min_letters", default.min_letters)),
            cjk_min_letters=int(section.get("cjk_min_letters", default.cjk_min_letters)),
            cjk_share=float(section.get("cjk_share", default.cjk_share)),
            kana_share=float(section.get("kana_share", default.kana_share)),
            latin_min_words=int(section.get("latin_min_words", default.latin_min_words)),
            latin_min_hits=int(section.get("latin_min_hits", default.latin_min_hits)),
        )


@dataclass(frozen=True, slots=True)
class ScriptCounts:
    """문자 체계별 글자 수.

    **숫자·기호·공백은 세지 않는다.** 비율의 분모에 넣으면 표·수치가 많은 기사가 문자
    비율이 낮아져 `unknown` 으로 떨어진다. 실제로는 한국어 기사인데.
    """

    hangul: int = 0
    latin: int = 0
    kana: int = 0
    han: int = 0


def _within(code: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(low <= code <= high for low, high in ranges)


def count_scripts(text: str) -> ScriptCounts:
    hangul = latin = kana = han = 0
    for ch in text:
        code = ord(ch)
        if _within(code, _HANGUL_RANGES):
            hangul += 1
        elif ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            latin += 1
        elif _within(code, _KANA_RANGES):
            kana += 1
        elif _within(code, _HAN_RANGES):
            han += 1
    return ScriptCounts(hangul=hangul, latin=latin, kana=kana, han=han)


def detect_lang(text: str | None, thresholds: LangThresholds | None = None) -> str:
    """`LANGUAGES` 의 코드 하나, 아니면 `unknown`.

    순서 — 한자·가나(`ja`·`zh`) → 글자 수 하한 → 두 언어가 다 유의미한가(`mixed`) → 한쪽이
    우세한가 → 라틴이 우세하면 기능어로 `en`·`fr`·`it`.

    **한자·가나를 맨 앞에 두되 한글·라틴 판정에는 섞지 않는다.** 섞으면 한자가 몇 자 든 한국어
    기사의 한글 비율이 내려가 `mixed`·`ko` 경계가 움직인다. 그래서 한자·가나가 유의미하지
    않은 텍스트는 이전과 같은 계산을 탄다.

    **`mixed` 를 우세 판정보다 먼저 보는 이유** — 한국 패션 매체 기사는 한글 본문에 브랜드명·
    컬렉션명이 영문으로 잔뜩 섞인다. 우세를 먼저 보면 그 기사가 전부 `ko` 가 되고, [04 §2]
    가 영문 브랜드명을 한국어 토크나이저로 끊는다. 그건 이 소스 셋에서 가장 값진 키워드다.
    """
    limits = thresholds or LangThresholds()
    if not text:
        return UNKNOWN

    counts = count_scripts(text)
    cjk = _cjk_lang(counts, limits)
    if cjk is not None:
        return cjk

    total = counts.hangul + counts.latin
    if total < limits.min_letters:
        # 판별할 근거가 없다. 없는 근거로 토크나이저를 고르면 그 문서의 후보가 전부 잡음이 된다.
        return UNKNOWN

    ko_ratio = counts.hangul / total
    en_ratio = counts.latin / total
    if ko_ratio >= limits.secondary and en_ratio >= limits.secondary:
        return MIXED
    if ko_ratio >= limits.dominant:
        return KO
    if en_ratio >= limits.dominant:
        return _latin_lang(text, limits)
    # 둘 다 우세하지 않고 둘 다 유의미하지도 않다 — 문자가 거의 없는 텍스트다.
    return UNKNOWN


def _cjk_lang(counts: ScriptCounts, limits: LangThresholds) -> str | None:
    cjk = counts.kana + counts.han
    if cjk < limits.cjk_min_letters:
        return None
    letters = counts.hangul + counts.latin + cjk
    # 한자를 괄호로 병기한 한국어 기사가 `zh` 로 가지 않게 한글이 유의미하면 보지 않는다.
    if cjk / letters < limits.cjk_share or counts.hangul / letters >= limits.secondary:
        return None
    return JA if counts.kana / cjk >= limits.kana_share else ZH


def _latin_lang(text: str, limits: LangThresholds) -> str:
    """라틴 문자가 우세한 텍스트의 언어. 근거가 약하면 `en` 이다.

    `en` 으로 기우는 이유는 비용의 비대칭이다. 영어 문서를 프랑스어로 잘못 보면 필터가
    버리고(dev 도메인 `hn` 제목이 통째로 사라질 수 있다), 프랑스어 문서를 영어로 잘못 보면
    영어 토크나이저가 잡음 후보를 조금 낸다.
    """
    words = [word.lower() for word in _WORD.findall(text)]
    if len(words) < limits.latin_min_words:
        return EN
    hits = {
        language.code: sum(word in language.function_words for word in words)
        for language in LANGUAGES.values()
        if language.function_words
    }
    best = max(hits, key=hits.__getitem__)
    runner_up = max(count for code, count in hits.items() if code != best)
    if best == EN or hits[best] < limits.latin_min_hits or hits[best] == runner_up:
        return EN
    return best
