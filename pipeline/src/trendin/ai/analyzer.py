"""트렌드 분석 프롬프트와 구조화 응답 검증."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trendin.ai.client import GmsOpenAIClient, GmsOpenAIError

DEVELOPER_PROMPT = """당신은 한국어 트렌드 분석가다.
입력으로 제공된 자료만 사용해 트렌드를 분석한다.
반드시 JSON 객체 하나만 반환하고 마크다운 코드 블록이나 부가 설명을 쓰지 않는다.
JSON에는 description, summary, reason 문자열 필드만 포함한다.
입력의 기간별 트렌드 유형과 지표를 해석하되, 원인과 배경은 기사 근거로만 설명한다.
- description: 트렌드가 무엇인지 핵심 특징을 간결한 1문장으로 정의한다. summary나 reason을
  반복하지 않는다.
- summary: 여러 자료에 공통으로 나타나는 현재 모습과 흐름을 1~5문장으로 종합한다. 자료에
  나온 대표 스타일, 아이템, 브랜드, 현상이 있다면 함께 설명하되 description을 늘여 쓰지 않는다.
- reason: NEW는 새롭게 등장한 배경, RISING은 관심이 갑자기 또는 다시 상승한 이유,
  CURRENT는 현재 유행하는 배경을 2~3문장으로 설명한다. 유형이 여러 개면 모든 관점을
  함께 반영한다. 자료의 제품 출시, 컬렉션, 셀럽 노출, 행사 등 구체적인 사건과 연결하고,
  해당 유형의 원인이나 배경을 뒷받침할 근거가 부족하면 확인하기 어렵다고 명시한다.
모든 필드는 입력 자료에서 확인되는 내용만 사용하며, 확인할 수 없는 내용은 추측하지 않는다."""


class TrendAnalysis(BaseModel):
    """AI 트렌드 분석 결과의 확정 JSON 계약."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(min_length=1)
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
