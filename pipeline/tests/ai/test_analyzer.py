"""트렌드 분석 JSON 계약 단위 테스트."""

import json

import pytest

from trendin.ai.analyzer import TrendAnalyzer
from trendin.ai.client import GmsOpenAIError


class StubClient:
    def __init__(self, content):
        self.content = content
        self.messages = None
        self.response_format = None

    def create_chat_completion(self, messages, *, response_format=None):
        self.messages = messages
        self.response_format = response_format
        return self.content


def test_description_summary_reason_JSON을_파싱한다():
    expected = {
        "description": (
            "발레코어는 리본, 플랫슈즈, 레그워머 등 발레복의 요소를 일상 패션에 "
            "접목한 스타일이다."
        ),
        "summary": (
            "발레코어는 발레에서 영감을 받은 아이템을 일상복과 조합하는 모습으로 "
            "나타나고 있다. 최근 브랜드 컬렉션과 신제품에 리본과 플랫슈즈가 반복적으로 "
            "등장하고, 패션 콘텐츠에서도 관련 스타일링이 지속적으로 소개되고 있다."
        ),
        "reason": (
            "여러 브랜드가 리본 디테일의 플랫슈즈와 발레 슈즈에서 영감을 받은 제품을 "
            "연이어 선보인 것이 관심 증가의 주요 요인으로 나타난다. 관련 제품이 패션 "
            "매체에 반복적으로 소개되고 셀럽의 스타일링까지 노출되면서 관심이 확대되고 있다."
        ),
    }
    client = StubClient(json.dumps(expected, ensure_ascii=False))

    result = TrendAnalyzer(client).analyze("발레코어 관련 테스트 자료")

    assert result.model_dump() == expected
    assert client.response_format == {"type": "json_object"}
    assert [message["role"] for message in client.messages] == ["developer", "user"]
    prompt = client.messages[0]["content"]
    assert all(kind in prompt for kind in ("NEW", "RISING", "CURRENT"))
    assert "유형이 여러 개면" in prompt
    reason_instruction = prompt.split("- reason:", 1)[1]
    assert "NEW는 새롭게 등장한 배경" in reason_instruction
    assert "RISING은 관심이 갑자기 또는 다시 상승한 이유" in reason_instruction
    assert "CURRENT는 현재 유행하는 배경" in reason_instruction
    assert "모든 관점" in reason_instruction


@pytest.mark.parametrize(
    "content",
    [
        "JSON이 아닌 응답",
        '{"description":"설명","summary":"요약"}',
        '{"description":"설명","summary":"요약","reason":""}',
        '{"description":"설명","summary":"요약","reason":"이유","extra":"값"}',
    ],
)
def test_잘못된_JSON_응답을_거부한다(content):
    with pytest.raises(GmsOpenAIError, match="JSON 계약"):
        TrendAnalyzer(StubClient(content)).analyze("테스트 자료")


def test_입력이_비면_GMS를_호출하지_않는다():
    client = StubClient("호출되면 안 됨")
    with pytest.raises(ValueError, match="입력"):
        TrendAnalyzer(client).analyze("  ")
    assert client.messages is None
