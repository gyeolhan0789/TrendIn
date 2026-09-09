"""비교키 — 같은 것인지 판별하는 열쇠.

규격은 [04 §4](../../../../spark/docs/04-keyword-extraction-spec.md).

| | 만드는 법 |
| --- | --- |
| 비교키 `normalized_key` | NFKC → 소문자 → 하이픈·언더스코어·공백을 단일 공백 → 앞뒤 구두점 제거 |
| 대표 표기 `surface` | 그 비교키를 가진 원표기 중 코퍼스에서 **가장 빈번한 것**. 화면에 나간다 |

대표 표기는 코퍼스를 봐야 하므로 여기 없다 — `extract/batch.py` 가 Spark 로 고른다. 여기는
문자열 하나에 대한 순수 함수뿐이다.

**영어 복수형은 접지 않는다.** `-s`/`-es` 제거는 `glasses`→`glasse`, `CSS`→`CS` 같은 과교정을
낳는다. [05 §2] 가 빈도 근거를 갖고 조건부로만 처리한다.

이 비교키가 그대로 `keywords.normalized_name` 의 값이 된다 ([05 §5]).

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
import unicodedata

# 하이픈 · 언더스코어 · 연속 공백 → 단일 공백. `multi-agent` = `multi agent` = `multi_agent`
# ([05 §2] 층 1 규칙). 소프트 하이픈 · 전각 하이픈은 NFKC 가 먼저 접는다.
_JOINERS = re.compile(r"[\s\-_‐-―]+")

# 앞뒤에서 떼는 구두점. **`#` 은 뗀다** — 해시태그 `#vibecoding` 과 본문의 `vibecoding` 은
# 같은 것이고, 해시태그였다는 사실은 후보의 `kind` 가 따로 들고 간다 (`extract/candidates.py`).
# `+` 와 `#` 은 **뒤에서는 떼지 않는다** — `C++` · `C#` 은 그 문자가 이름의 일부다.
_LEADING = re.compile(r"^[^\w]+")
_TRAILING = re.compile(r"[^\w+#]+$")

# 소유격. NFKC 가 `’`(U+2019) 를 `'` 로 접지 않아 둘 다 적는다 ([04 §2]).
_POSSESSIVE = re.compile(r"['’]s\b", re.IGNORECASE)


def normalized_key(surface: str | None) -> str:
    """원표기 → 비교키. 비교키가 비면 후보가 아니다 — 부른 쪽이 빈 문자열을 버린다.

    소문자화가 **비교키에서만** 일어난다. 토큰 자체는 대소문자를 유지해 `MCP` 를 화면에
    낼 수 있어야 한다 ([04 §2]). `casefold()` 가 아니라 `lower()` 인 이유는 독일어 `ß` 같은
    특수 접기가 여기서 필요 없고, `lower()` 가 SQL 의 `lower()` 와 같은 결과를 내서
    DB 쪽에서 다시 계산해도 어긋나지 않기 때문이다.
    """
    if not surface:
        return ""
    text = unicodedata.normalize("NFKC", surface)
    text = _POSSESSIVE.sub("", text)
    text = text.lower()
    text = _JOINERS.sub(" ", text).strip()
    # 토큰마다 앞뒤 구두점을 뗀다. 전체에서만 떼면 `react. native` 의 가운데 점이 남는다.
    tokens = [_TRAILING.sub("", _LEADING.sub("", token)) for token in text.split(" ")]
    return " ".join(token for token in tokens if token)
