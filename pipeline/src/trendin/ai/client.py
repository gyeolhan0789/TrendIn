"""GMS OpenAI Chat Completions 클라이언트."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import httpx

GMS_ENDPOINT = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
GMS_MODEL = "gpt-5.4-nano"


class GmsOpenAIError(RuntimeError):
    """GMS 호출 또는 Chat Completions 응답이 유효하지 않을 때 발생한다."""


class GmsOpenAIClient:
    """환경변수의 키로 GMS Chat Completions API를 호출한다."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str = GMS_ENDPOINT,
        model: str = GMS_MODEL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get("GMS_KEY", "")).strip()
        if not self.api_key:
            raise GmsOpenAIError("GMS_KEY가 비어 있다. pipeline/.env를 채운다")
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout
        self.transport = transport

    def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: Mapping[str, str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if response_format is not None:
            payload["response_format"] = dict(response_format)

        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GmsOpenAIError("GMS OpenAI 호출에 실패했다") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GmsOpenAIError("GMS OpenAI 응답에 message content가 없다") from exc
        if not isinstance(content, str) or not content.strip():
            raise GmsOpenAIError("GMS OpenAI 응답의 message content가 비어 있다")
        return content
