"""언어 판별 ([03 §5](../../../../spark/docs/03-normalization-spec.md)).

**문자 비율로 판별하고 언어 판별 라이브러리를 쓰지 않는다.** 이유는 규격 그대로 셋이다 —
(a) 구분해야 하는 것이 사실상 한/영 둘뿐이고 (b) 개발 도메인 텍스트는 코드·식별자가 섞여
있어 일반 판별기가 자주 틀리며 (c) 의존성이 하나 줄어든다.

`lang` 이 필요한 이유는 [04 §2] 에서 토크나이저를 고르기 때문이다. `mixed` 는 두
토크나이저를 모두 돌리고, `unknown` 은 [03 §6] 의 품질 필터에서 대개 걸러진다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass

KO = "ko"
EN = "en"
MIXED = "mixed"
UNKNOWN = "unknown"

# 한글 — 음절(가~힣) · 자모 · 호환 자모. 자모를 넣는 이유는 초성 표기(`ㅋㅋ`)나 분해된
# 형태(NFD 로 온 텍스트)가 실제로 섞여 오기 때문이다. NFKC 를 거쳐도 자모는 합쳐지지 않는다.
_HANGUL_RANGES = (
    (0xAC00, 0xD7A3),  # 음절
    (0x1100, 0x11FF),  # 자모
    (0x3130, 0x318F),  # 호환 자모
    (0xA960, 0xA97F),  # 확장 A
    (0xD7B0, 0xD7FF),  # 확장 B
)


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
        )


def _is_hangul(code: int) -> bool:
    return any(low <= code <= high for low, high in _HANGUL_RANGES)


def count_letters(text: str) -> tuple[int, int]:
    """`(한글 수, 라틴 수)`.

    **숫자·기호·공백은 세지 않는다.** 비율의 분모에 넣으면 표·수치가 많은 기사가 문자
    비율이 낮아져 `unknown` 으로 떨어진다. 실제로는 한국어 기사인데.
    """
    hangul = latin = 0
    for ch in text:
        code = ord(ch)
        if _is_hangul(code):
            hangul += 1
        elif ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            latin += 1
    return hangul, latin


def detect_lang(text: str | None, thresholds: LangThresholds | None = None) -> str:
    """`ko` · `en` · `mixed` · `unknown`.

    순서 — 글자 수 하한 → 두 언어가 다 유의미한가(`mixed`) → 한쪽이 우세한가 → 나머지.

    **`mixed` 를 우세 판정보다 먼저 보는 이유** — 한국 패션 매체 기사는 한글 본문에 브랜드명·
    컬렉션명이 영문으로 잔뜩 섞인다. 우세를 먼저 보면 그 기사가 전부 `ko` 가 되고, [04 §2]
    가 영문 브랜드명을 한국어 토크나이저로 끊는다. 그건 이 소스 셋에서 가장 값진 키워드다.
    """
    limits = thresholds or LangThresholds()
    if not text:
        return UNKNOWN

    hangul, latin = count_letters(text)
    total = hangul + latin
    if total < limits.min_letters:
        # 판별할 근거가 없다. 없는 근거로 토크나이저를 고르면 그 문서의 후보가 전부 잡음이 된다.
        return UNKNOWN

    ko_ratio = hangul / total
    en_ratio = latin / total
    if ko_ratio >= limits.secondary and en_ratio >= limits.secondary:
        return MIXED
    if ko_ratio >= limits.dominant:
        return KO
    if en_ratio >= limits.dominant:
        return EN
    # 둘 다 우세하지 않고 둘 다 유의미하지도 않다 — 문자가 거의 없는 텍스트다.
    return UNKNOWN
