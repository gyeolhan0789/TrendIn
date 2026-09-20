"""GMS(SSAFY LLM 프록시) 호출 — 크레딧이 드는 유일한 자리.

```python
client = GmsClient(model="gpt-4o-mini")
content = client.chat(messages)
```

**크레딧이 드는 코드를 한 파일에만 둔다.** 어디서 돈이 나가는지 찾으려고 저장소를 뒤지지
않아도 되게 하려는 것이고, 부르기 전에 세는 자리(`scripts/concept-judge.py --estimate`)를
따로 두기 위해서다.

`trendin/ai/client.py` 도 같은 프록시를 부르지만 그 파일은 트렌드 분석 담당의 것이다. 모델과
재시도 규칙이 서로 다르고, 한쪽을 고치면 다른 쪽이 깨지므로 합치지 않는다.

**키가 없으면 시작하지 않는다.** 절반쯤 돌다 죽으면 어디까지 물었는지 세어야 한다.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
KEY_ENV = "GMS_KEY"
RETRIES = 3


class LlmError(RuntimeError):
    """호출이 실패했거나 답이 쓸 수 없는 모양일 때."""


class GmsClient:
    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        endpoint: str = ENDPOINT,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get(KEY_ENV, "")).strip()
        if not self.api_key:
            raise LlmError(f"{KEY_ENV} 가 비어 있다 — 호출하기 전에 환경변수로 넣는다")
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 1200) -> str:
        """답 본문 하나. 쓴 토큰은 객체에 쌓아 두어 실행이 끝나고 합계를 볼 수 있게 한다."""
        payload = {
            "model": self.model,
            "messages": messages,
            # 같은 질문에 같은 답이 나와야 판정 캐시가 뜻을 갖는다.
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        last: Exception | None = None
        for attempt in range(1, RETRIES + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    answer = json.loads(response.read())
                break
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", "replace")[:400]
                # 4xx 는 우리 요청이 틀린 것이라 다시 해도 같다 — 429 만 기다렸다 다시 한다.
                if error.code != 429 and error.code < 500:
                    raise LlmError(f"GMS 가 거절했다 ({error.code}): {detail}") from error
                last = error
                time.sleep(2 * attempt)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                last = error
                time.sleep(2 * attempt)
        else:
            raise LlmError(f"GMS 호출이 {RETRIES}번 다 실패했다: {last}")

        self.calls += 1
        usage = answer.get("usage") or {}
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        try:
            content = answer["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LlmError(f"답에 본문이 없다: {str(answer)[:300]}") from error
        if not isinstance(content, str) or not content.strip():
            raise LlmError("답 본문이 비어 있다")
        return content
