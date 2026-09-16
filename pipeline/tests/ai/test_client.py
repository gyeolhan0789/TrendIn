"""GMS OpenAI 클라이언트 단위 테스트. 실제 네트워크와 키를 사용하지 않는다."""

import json

import httpx
import pytest

from trendin.ai.client import GMS_ENDPOINT, GMS_MODEL, GmsOpenAIClient, GmsOpenAIError


def test_환경변수의_키와_고정_모델로_GMS를_호출한다(monkeypatch):
    monkeypatch.setenv("GMS_KEY", "test-key")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})

    client = GmsOpenAIClient(transport=httpx.MockTransport(handler))
    content = client.create_chat_completion(
        [{"role": "user", "content": "테스트"}], response_format={"type": "json_object"}
    )

    assert content == '{"ok":true}'
    assert seen["url"] == GMS_ENDPOINT
    assert seen["authorization"] == "Bearer test-key"
    assert seen["body"]["model"] == GMS_MODEL
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_키가_없으면_호출_전에_실패한다(monkeypatch):
    monkeypatch.delenv("GMS_KEY", raising=False)
    with pytest.raises(GmsOpenAIError, match="GMS_KEY"):
        GmsOpenAIClient()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, text="unavailable"),
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"choices": []}),
    ],
)
def test_호출_실패나_잘못된_응답을_예외로_바꾼다(response):
    client = GmsOpenAIClient(
        api_key="test-key", transport=httpx.MockTransport(lambda request: response)
    )
    with pytest.raises(GmsOpenAIError):
        client.create_chat_completion([{"role": "user", "content": "테스트"}])
