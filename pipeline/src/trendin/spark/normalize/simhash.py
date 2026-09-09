"""SimHash — 근사 중복 판별의 지문 ([03 §6](../../../../spark/docs/03-normalization-spec.md) 3단계).

**SimHash 를 쓰는 이유** — 단일 노드에서 MinHash + LSH 를 돌리는 것보다 단순하고, 실행당
수백 건 규모([00 §3])에서는 밴딩 없이 전량 비교해도 감당된다. 규모가 커지면 밴딩을 넣는다.

**무엇을 잡으려고 두는가** — 두산매거진 4곳(`vogue`·`gqkorea`·`wkorea`·`allure`)이 같은
WordPress 템플릿을 쓰는 계열사라, 같은 보도자료를 각각 올리는 경우가 있다. 그건 `article_id`
도 URL 도 달라서 이것 말고는 잡히지 않는다. 반대로 같은 매체 안 섹션 중복은 `article_id` 가
같아 1단계에서 잡히므로 여기까지 오지 않는다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import hashlib
import re

BITS = 64
_MASK = (1 << BITS) - 1

# 토큰 — 한글·라틴·숫자의 연속. 기호를 버리는 이유는 같은 문서를 옮겨 실으면서 따옴표나
# 대시만 바뀌는 일이 흔해서, 그게 지문에 들어가면 같은 글이 다른 지문을 갖는다.
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")

# 몇 개를 묶어 하나의 특징으로 볼지. 단어 하나씩 세면 어휘만 겹치는 다른 글이 가까워지고,
# 너무 길게 묶으면 한 단어만 바뀐 같은 글이 멀어진다. 3 은 문서 유사도의 통상 기본값이다.
SHINGLE = 3


def tokenize(text: str) -> list[str]:
    """지문용 토큰. [04] 의 키워드 토큰화와 다른 것이다.

    여기 토큰은 **문서가 같은지만** 판단하는 데 쓰고 키워드 후보가 되지 않는다. 그래서
    소문자로 접어도 되고(표기 차이를 무시해야 같은 글로 보인다) 조사·어미를 끊을 이유가 없다.
    """
    return _TOKEN.findall(text.lower())


def shingles(tokens: list[str], size: int = SHINGLE) -> list[str]:
    """겹치는 n-gram. 토큰이 `size` 보다 적으면 전체를 하나로 본다."""
    if len(tokens) < size:
        return [" ".join(tokens)] if tokens else []
    return [" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)]


def simhash(text: str | None, *, size: int = SHINGLE) -> int | None:
    """64비트 지문. 특징이 하나도 없으면 `None`.

    `md5` 를 쓰는 이유는 **암호학적 용도가 아니기 때문이다** — 필요한 것은 비트가 고르게
    퍼지는 것뿐이고, 이 함수는 배치의 모든 shingle 마다 불린다. `sha256` 은 여기서 값 없이
    느리다. (`url_hash` 는 정체성이라 sha256 이다 — 거기서는 충돌이 곧 문서 유실이다.)
    """
    features = shingles(tokenize(text or ""), size)
    if not features:
        return None

    weights = [0] * BITS
    for feature in features:
        digest = hashlib.md5(feature.encode("utf-8"), usedforsecurity=False).digest()
        value = int.from_bytes(digest[: BITS // 8], "big")
        for bit in range(BITS):
            # 비트가 서 있으면 +1, 누워 있으면 -1. 부호가 최종 지문의 그 비트를 정한다.
            weights[bit] += 1 if value >> bit & 1 else -1

    fingerprint = 0
    for bit, weight in enumerate(weights):
        if weight > 0:
            fingerprint |= 1 << bit
    return fingerprint


def to_signed64(value: int | None) -> int | None:
    """부호 없는 64비트 지문을 `bigint` 에 담을 수 있는 부호 있는 값으로.

    **Spark 의 `LongType` 은 부호 있는 64비트다.** 지문은 부호 없는 64비트라 절반이
    상한을 넘고, 그대로 넣으면 조용히 `null` 이 되거나 배치가 죽는다.

    `hamming` 은 변환된 값을 그대로 받아도 맞다 — 2의 보수 표현의 비트 패턴이 같고,
    그 함수가 XOR 결과를 `_MASK` 로 자르기 때문이다. 되돌릴 필요가 없다.
    """
    if value is None:
        return None
    return value - (1 << BITS) if value >= (1 << (BITS - 1)) else value


def hamming(left: int | None, right: int | None) -> int:
    """두 지문의 다른 비트 수. 한쪽이 없으면 최대값 — "안 닮았다" 로 본다.

    `None` 을 0(완전 동일)으로 접으면 지문 없는 문서끼리 서로 중복으로 판별된다. 본문 없는
    문서가 dev 도메인 전량이라([03 §2]) 그 실수는 도메인 하나를 통째로 지운다.
    """
    if left is None or right is None:
        return BITS
    # `& _MASK` 가 부호 있는 값(음수)도 올바른 64비트 패턴으로 되돌린다. 그래서
    # `to_signed64` 를 거친 지문을 그대로 넣어도 결과가 같다.
    return ((left ^ right) & _MASK).bit_count()
