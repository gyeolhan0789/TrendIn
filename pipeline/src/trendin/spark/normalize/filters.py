"""품질 필터 ([03 §6](../../../../spark/docs/03-normalization-spec.md)).

**본문 유무로 분기한다.** 규격의 필터 표는 `body` 가 있는 문서에 적용되고, 애초에 본문이
없는 문서(`members_only` · `hn`)는 **제목 길이 하한만** 본다. 그 분기를 놓치면 회원 전용
7.4% 와 dev 도메인 전량이 통째로 사라진다 ([03 §2]).

**버린 문서를 조용히 넘기지 않는다.** 어느 필터가 물었는지를 `reason` 으로 남기고
[03 §7] 의 집계가 그걸 센다. 생존율이 갑자기 떨어지면 소스가 HTML 구조를 바꿨거나 생산자
어댑터가 깨진 것이고, 이 숫자가 없으면 "왜 이번 주 언급량이 줄었지" 에 답할 수 없다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass

from trendin.spark.normalize.adapters.protocol import BASIS_BODY
from trendin.spark.normalize.documents import Document
from trendin.spark.normalize.lang import UNKNOWN, unsupported
from trendin.spark.normalize.urls import too_long

# 제외 사유. [03 §7] 이 사유별 건수를 세므로 값이 곧 집계 키다 — 이름을 바꾸면 옛 배치
# 통계와 이어지지 않는다.
NO_URL = "NO_URL"
URL_TOO_LONG = "URL_TOO_LONG"
EMPTY_BODY = "EMPTY_BODY"
SHORT_BODY = "SHORT_BODY"
UNKNOWN_LANG = "UNKNOWN_LANG"
# 알아봤지만 키워드 추출이 다루지 않는 언어(`lang.LANGUAGES`). `UNKNOWN_LANG` 과 나누는 이유는
# 대응이 달라서다 — 이쪽은 소스가 그 언어를 낸다는 확실한 신호고, 저쪽은 근거 부족이다.
UNSUPPORTED_LANG = "UNSUPPORTED_LANG"
SHORT_TITLE = "SHORT_TITLE"
# 발행일을 못 정한 문서. 계약 판별(`io/contract.check_article`)이 먼저 막으므로 여기 오면 배선이
# 깨진 것이다 — 그래도 두는 이유는 이 문서가 `published_date` 없는 파티션에 쓰이는 것을 마지막에
# 막는 자리가 여기밖에 없기 때문이다.
INVALID_PUBLISHED_AT = "INVALID_PUBLISHED_AT"

KEPT = ""


@dataclass(frozen=True, slots=True)
class FilterThresholds:
    """필터 문턱. `conf/*.yaml` 의 `ingest.normalize.filters` 에서 온다.

    **기본값은 잠정이다.** [S6](../../../../spark/docs/10-delivery-plan.md) 이 실데이터의
    문서 길이 분포를 재고 확정하며, 그때 `pl_config_history` 에 초기값이 기록된다
    ([09 §7] 항목 5). 여기 숫자를 코드에 박지 않고 설정으로 뺀 이유가 그것이다 — 지금 값은
    "기사라기엔 너무 짧다" 의 대략적인 선이고 근거로 삼을 측정이 아직 없다.
    """

    # 정제 후 본문 길이 하한. 이보다 짧으면 키워드를 뽑을 것이 없다.
    min_body_len: int = 100
    # 제목 길이 하한. 제목은 필수 필드라 비어 있을 수 없지만(불변식 9) 한두 글자짜리는 버린다.
    min_title_len: int = 5

    @classmethod
    def from_section(cls, section: dict) -> "FilterThresholds":
        # 기본값을 인스턴스에서 읽는 이유는 `lang.LangThresholds.from_section` 과 같다 —
        # `slots=True` 에서 `cls.min_body_len` 은 슬롯 서술자다.
        default = cls()
        return cls(
            min_body_len=int(section.get("min_body_len", default.min_body_len)),
            min_title_len=int(section.get("min_title_len", default.min_title_len)),
        )


def exclusion_reason(document: Document, thresholds: FilterThresholds | None = None) -> str:
    """제외 사유. 통과면 빈 문자열.

    순서가 의미를 갖는다:

    1. **URL** — 없거나 너무 길면 `contents` 에 넣을 수 없으므로 다른 검사가 무의미하다.
    2. **정제 후 빈 본문** — 본문이 *있었는데* 정제가 다 걷어낸 경우. 링크만 있던 기사가
       여기 걸린다. `basis` 만 보면 이 문서가 요약·제목 경로로 떨어져 통과해버린다.
    3. **추출하지 않는 언어** — 본문 유무와 무관하다. 제목만 있는 문서도 토크나이저로 가므로,
       여기서 안 빼면 일본어 제목이 한국어 분석기를 탄다.
    4. **본문 있는 문서** — 길이 하한과 `lang`.
    5. **본문 없는 문서** — 제목 길이만.

    **2 가 4·5 보다 먼저여야 하는 이유** — 정제 후 빈 본문은 `basis` 가 이미 `summary` 나
    `title` 로 떨어져 있어서, 4 의 조건에 걸리지 않고 5 의 관대한 검사를 통과한다. 그러면
    [03 §6] 이 "제외" 라고 적은 두 줄("빈 본문", "링크만 있고 텍스트가 없음")이 영영 발동하지
    않고, **아무 증상도 없다.**

    `author` 상한은 여기서 보지 않는다 — 규격이 "제외하지 않고 표시" 로 정했고, 그 표시는
    [07 §7] 의 기여 상한이 쓴다. 게다가 이 소스 셋에서는 저자 기반 봇 방어가 거의 의미가
    없다 ([03 §6] ⚠️) — 매체 기사의 저자는 소속 기자라 문서 수가 원래 많고 `hn` 의 `author`
    는 투고자다. 정상 기자를 봇으로 누르지 않으려면 실제 분포를 재기 전까지 끄는 것이 맞다.
    """
    limits = thresholds or FilterThresholds()

    if document.url is None:
        return NO_URL
    if too_long(document.url):
        # `contents.url` 이 varchar UNIQUE 라 인덱스 항목 상한을 넘으면 INSERT 가 죽고
        # 배치 하나가 통째로 실패한다 ([03 §8]). 드물지만 드물게 전체를 죽이는 종류다.
        return URL_TOO_LONG

    if document.published_date is None:
        # 파티션 키가 없다. `curated` 의 날짜 파티션 계약([01 §3])을 깨는 문서는 살리지 않는다.
        return INVALID_PUBLISHED_AT

    if document.had_raw_body and document.basis != BASIS_BODY:
        return EMPTY_BODY

    if unsupported(document.lang):
        return UNSUPPORTED_LANG

    if document.basis == BASIS_BODY:
        if document.content_len < limits.min_body_len:
            return SHORT_BODY
        if document.lang == UNKNOWN:
            # 토크나이저를 고를 수 없다 ([04 §2]). 없는 근거로 고르면 그 문서의 후보가
            # 전부 잡음이 된다.
            return UNKNOWN_LANG
        return KEPT

    # 본문이 애초에 없는 문서 — 회원 전용(fashion 7.4%)과 `hn`(dev 전량).
    #
    # 추출하지 않는 언어는 위에서 이미 뺐다. 남은 `unknown` 을 보지 않는 이유는 제목만으로는
    # 글자 수 하한에 걸려 대개 `unknown` 이 되기 때문이다. 여기서 `unknown` 을 걸면 dev 도메인이
    # 통째로 사라진다. 그 문서들의 토크나이저를
    # 무엇으로 고를지는 [00 §7] 한계 19번의 결론이 정한다.
    if len(document.title) < limits.min_title_len:
        return SHORT_TITLE
    return KEPT
