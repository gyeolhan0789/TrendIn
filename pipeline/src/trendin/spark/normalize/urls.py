"""URL 정규화와 `url_hash` ([03 §6](../../../../spark/docs/03-normalization-spec.md)).

**이 모듈의 출력이 곧 유일성 기준이다.** `contents.url` 에 UNIQUE 가 직접 걸려 있고
([03 §8]) 중복 제거 2단계가 `url_hash` 로 대표를 고른다. 그래서 규칙을 바꾸면 이미 들어간
행과 새로 들어올 행의 기준이 갈리고, 같은 기사가 두 행이 된다. **규칙을 고칠 때는 기존
행을 다시 계산할 계획이 함께 있어야 한다.**

**pyspark 를 import 하지 않는다.** 문자열 하나에 대한 순수 함수라 SparkSession 없이 검사할
수 있다 ([09 §4] 층 1).
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlsplit, urlunsplit

# 스킴별 기본 포트. 명시돼 있으면 지운다 — `https://a.com:443/x` 와 `https://a.com/x` 는
# 같은 문서인데 문자열로는 다르다.
_DEFAULT_PORTS = {"http": "80", "https": "443"}

# 추적 파라미터. 접두어로 지우는 것과 이름으로 지우는 것을 나눈다.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_NAMES = frozenset({"fbclid", "gclid", "ref", "source"})

# PostgreSQL B-tree 인덱스 항목 상한이 약 2704바이트다 ([03 §8]). `contents.url` 이 varchar
# UNIQUE 라 이걸 넘는 URL 은 INSERT 가 오류로 죽고, 배치 하나가 통째로 실패한다. 여유를
# 두는 이유는 인덱스 항목에 URL 바이트만 들어가는 것이 아니기 때문이다.
URL_MAX_BYTES = 2600


def _drop_tracking(query: str) -> str:
    """추적 파라미터를 지우고 남은 키를 정렬한다.

    `keep_blank_values=True` 인 이유는 `?page=` 같은 빈 값이 소스에서 의미를 갖는 경우가
    있어서다. 지우면 서로 다른 URL 이 같은 값으로 접힌다.

    정렬을 마지막에 하는 이유는 순서만 다른 같은 질의를 같은 문자열로 만들기 위해서다.
    소스가 목록 페이지마다 파라미터 순서를 바꿔 내는 일이 실제로 있다.
    """
    kept = [
        (name, value)
        for name, value in parse_qsl(query, keep_blank_values=True)
        if name.lower() not in _TRACKING_NAMES
        and not any(name.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ]
    kept.sort()
    # `urlencode` 를 쓰지 않는다. 그쪽은 이미 인코딩된 값을 다시 인코딩해(`%2F` → `%252F`)
    # 원본과 다른 URL 을 만든다. `parse_qsl` 이 디코딩한 값을 그대로 되붙인다.
    return "&".join(f"{name}={value}" if value else name for name, value in kept)


def normalize_url(raw: str | None) -> str | None:
    """정규화된 URL. 입력이 비어 있거나 형태가 아니면 `None`.

    순서는 [03 §6] 그대로다 — 스킴·호스트 소문자 → 기본 포트 제거 → 추적 파라미터 제거
    → 프래그먼트 제거 → 후행 슬래시 정리 → 질의 키 정렬.

    **`None` 을 돌려주는 것이 정상 경로다.** 생산자가 URL 없는 기사를 저장하지 않으므로
    (불변식 11) 실제로는 거의 오지 않지만, 여기서 예외를 올리면 그 한 건이 배치를 죽인다.
    거른 건수는 [03 §7] 에서 센다.
    """
    if raw is None or not raw.strip():
        return None

    try:
        parts = urlsplit(raw.strip())
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        # 스킴 없는 상대 경로는 정체성을 만들 수 없다. 어느 호스트인지 모른다.
        return None

    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not host:
        return None

    # 자격이 든 URL 은 오지 않지만, 오면 정체성에 넣지 않는다 — 같은 문서가 자격에 따라
    # 여러 행이 된다. 그리고 비밀이 `contents.url` 로 새어 나간다.
    netloc = host
    port = parts.port
    if port is not None and str(port) != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{port}"

    # 루트는 빈 문자열이 아니라 "/" 로 둔다. 빈 경로와 "/" 를 가르면 같은 문서가 둘이 된다.
    path = parts.path.rstrip("/") or "/"
    # 프래그먼트는 통째로 버린다 — 서버에 전달되지 않으므로 다른 문서일 수 없다.
    return urlunsplit((scheme, netloc, path, _drop_tracking(parts.query), ""))


def url_hash(normalized: str | None) -> bytes | None:
    """`sha256(normalized_url)` 32바이트. 파이프라인 내부에서의 문서 정체성 ([03 §1]).

    **정규화된 URL 을 받는다.** 원본을 넣으면 같은 문서가 다른 해시를 갖는다. 함수 안에서
    정규화하지 않는 이유는 호출부가 정규화 결과 자체도 필요하기 때문이고(표준 문서의 `url`),
    두 번 계산하면 두 값이 갈릴 수 있다.
    """
    if normalized is None:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).digest()


def too_long(normalized: str | None) -> bool:
    """`contents.url` 의 인덱스 항목 상한을 넘는지 ([03 §8]).

    문자 수가 아니라 **바이트 수**로 센다. 한글이 섞인 URL 은 문자 하나가 3바이트라
    문자 수로 재면 통과하고 삽입에서 죽는다.
    """
    if normalized is None:
        return False
    return len(normalized.encode("utf-8")) > URL_MAX_BYTES
