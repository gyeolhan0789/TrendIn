"""트렌드 분석 프롬프트와 구조화 응답 검증."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trendin.ai.client import GmsOpenAIClient, GmsOpenAIError

# 화면에 들어갈 전체 분량은 글자 수로 제한하고, 읽기 쉬운 호흡은 문장 수로 안내한다.
# 문장 수만 정하면 한 문장이 지나치게 길어질 수 있으므로 글자 수 상한도 함께 유지한다.
#
# **`summary` 와 `reason` 은 계약에서 검증하지 않는다.** 두 칸 다 `text` 라 넘쳐도 저장이
# 깨지지 않고, 여기서 막으면 조금 긴 응답 하나가 그 키워드의 분석을 통째로 날린다 — 분량은
# 취향이고 `description` 의 255자는 `varchar` 가 강제하는 사실이라, 둘을 같이 다루지 않는다.
SUMMARY_MAX_CHARS = 300
REASON_MAX_CHARS = 250
PROMPT_VERSION = "trend-analysis-v6"

# `trend_analyses.description` 이 `varchar(255)` 다. **프롬프트에 적는 수와 계약이 받는 수가
# 다르다** — 200 으로 부탁하고 255 까지 받는다. 모델이 조금 넘겨도 버리지 않되, 칸을 넘기면
# 저장 전에 멈춘다.
DESCRIPTION_PROMPT_CHARS = 200
DESCRIPTION_MAX_CHARS = 255

DEVELOPER_PROMPT = f"""당신은 한국어 트렌드 분석가다.
입력으로 제공된 자료만 사용해 트렌드를 분석한다.
반드시 JSON 객체 하나만 반환하고 마크다운 코드 블록이나 부가 설명을 쓰지 않는다.
JSON에는 description, summary, reason 문자열 필드만 포함한다.
입력의 기간별 트렌드 유형과 지표를 해석하되, 원인과 배경은 기사 근거로만 설명한다.
기사 게시일과 기사 속 사건 발생일을 구분한다. 분석 기간에 게시된 기사라도 과거 사건을
다룰 수 있으므로, 과거 사건을 해당 기간의 관심 상승 원인으로 연결하지 않는다.
해당 기간에 다시 소개되거나 활용된 사실이 확인되면 그 사실만 설명한다.
NEW, RISING, CURRENT는 내부 분석 관점일 뿐이며 출력 문장에는 직접 쓰지 않는다.
description은 정의, summary는 최근 기사에서 보이는 양상, reason은 그 배경과 원인을 맡는다.
세 필드에서 같은 사실이나 표현을 반복하지 않는다.
서비스 화면에 바로 노출되는 문장으로 작성하고, 분석 과정이나 자료의 한계를 설명하지 않는다.
모든 필드는 존댓말을 쓰지 않는 간결한 설명체로 작성한다. 문장 끝은 주로 "~다", "~된다",
"~이어진다", "~보인다"처럼 마무리한다. "~합니다", "~됩니다", "~있습니다", "~했습니다",
"~합니다." 같은 합니다체 표현을 쓰지 않는다.
어색한 번역체와 수동태를 피한다. "끌어올려진다", "집중된다", "추정된다"보다
"관심을 끌었다", "주목도를 높였다", "확산됐다", "흐름을 만들었다"처럼 자연스러운
한국어 표현을 쓴다.
자연스러운 표현보다 사실성이 우선이다. 함께 보도됐다는 사실이나 언급량 증가만으로
"관심을 끌었다", "주목도를 높였다" 같은 인과관계를 만들지 않는다.
- description: 트렌드가 무엇인지 핵심 특징을 간결한 1문장으로 정의한다. summary나 reason을
  반복하지 않는다. 공백을 포함해 {DESCRIPTION_PROMPT_CHARS}자를 넘기지 않는다.
- summary: 기사에 공통으로 나타나는 스타일, 아이템, 활용 방식과 흐름을 3~4문장으로 설명한다.
  첫 문장은 트렌드의 모습이나 대표 아이템으로 바로 시작한다. "최근 기사들에서",
  "제공된 자료에서는", "자료에 따르면", "기사 범위에서", "입력 자료에서",
  "지난 N시간/일 동안 언급이 N%" 같은 출처 설명형
  또는 지표 설명형 도입으로 시작하지 않는다. 언급량이나 증가율은 필요한 경우에만 근거로
  활용한다. 한 문장에 여러 사실을 나열하거나 "~하고, ~하며, ~되고"처럼 길게 잇지 말고
  짧고 읽기 쉬운 문장으로 나눈다. description을 늘여 쓰거나 reason의 원인을 미리 반복하지 않는다.
  분량은 공백을 포함해
  {SUMMARY_MAX_CHARS}자를 넘기지 않는다.
- reason: 트렌드 유형에 따라 새롭게 등장한 배경, 관심이 갑자기 또는 다시 상승한 이유,
  현재 유행하는 배경을 정확히 2문장으로 설명한다. 유형이 여러 개면 모든 관점을 검토하되,
  기사로 뒷받침되는 공통 배경을 중심으로 2문장에 통합한다. 유형별로 문장을 하나씩
  만들거나, 모든 유형을 설명하려고 근거 없는 원인을 추가하지 않는다.
  "NEW는", "RISING은", "CURRENT는"처럼 내부 유형명으로 문장을 시작하지 않는다.
  자료의 제품 출시, 컬렉션, 셀럽 노출, 행사 등 구체적인 사건과 연결하고, 해당 유형의
  원인이나 배경을 설명한다. "최근 기사들에서", "제공된 자료에서는", "자료에 따르면",
  "기사 범위에서", "입력 자료에서", "지난 N시간/일 동안", "직전 대비", "N건에서 N건으로"
  같은 리포트식 도입으로 시작하지 않는다. "다만", "단", "그러나", "하지만"으로 시작하는
  반박·한계 문장을 쓰지 않는다. "근거가 부족하다", "확인하기 어렵다", "단정하기 어렵다",
  "확정하기 어렵다", "특정하기 어렵다", "제한적이다", "추정된다", "확인되지 않는다",
  "단일 원인", "직접 원인", "자료만으로는", "기사만으로는" 같은 메타 분석 표현을 쓰지 않는다.
  원인을 특정할 수 없다는 말을 덧붙이지 않는다.
  인과관계가 확인되지 않으면 출시, 착용, 공개, 반복 소개 등 관찰된 사실만 설명한다.
  "~때문에 관심이 늘었다"나 "~계기로 보인다"처럼 단정 또는 완곡한 추측으로 바꾸지 않는다.
  공백을 포함해 {REASON_MAX_CHARS}자를 넘기지 않는다.
모든 필드는 입력 자료에서 확인되는 내용만 사용하며, 확인할 수 없는 내용은 추측하지 않는다.
읽는 사람은 입력 자료를 보지 못한다. NEW·RISING·CURRENT 같은 유형 이름과 "기사1",
"기사2·3" 같은 자료 번호를 어느 필드에도 쓰지 않고, 근거는 매체 이름이나 사건 자체로
가리킨다. 입력의 라벨은 분석에만 사용하고 화면 문장으로 옮기지 않는다."""


class TrendAnalysis(BaseModel):
    """AI 트렌드 분석 결과의 확정 JSON 계약.

    `description` 에만 길이 상한이 있다. 없이 두면 긴 응답이 `StringDataRightTruncation`
    으로 **저장 단계에서** 죽고, 러너의 포괄 `except` 가 그 키워드 하나를 삼킨다 — summary 와
    reason 까지 함께 사라지는데 증상은 "일부 트렌드만 분석이 비어 있다" 로만 보인다. 계약에서
    막으면 같은 실패가 `GmsOpenAIError` 로 원인 자리에 남는다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_CHARS)
    summary: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class TrendAnalyzer:
    """간단한 입력 자료를 GMS에 보내고 확정된 JSON 계약으로 검증한다."""

    def __init__(self, client: GmsOpenAIClient | None = None) -> None:
        self.client = client or GmsOpenAIClient()

    def analyze(self, input_text: str) -> TrendAnalysis:
        if not input_text.strip():
            raise ValueError("분석 입력이 비어 있다")

        content = self.client.create_chat_completion(
            [
                {"role": "developer", "content": DEVELOPER_PROMPT},
                {"role": "user", "content": input_text},
            ],
            response_format={"type": "json_object"},
        )
        try:
            return TrendAnalysis.model_validate_json(content)
        except ValidationError as exc:
            raise GmsOpenAIError("GMS OpenAI 응답이 트렌드 분석 JSON 계약과 맞지 않는다") from exc
