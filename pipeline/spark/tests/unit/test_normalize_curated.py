"""`curated.strip_scheme` — `body_object_key` 를 자르기 전에 양쪽을 같은 모양으로 맞춘다.

`body_object_keys` 자체는 Spark 세션이 필요해 `spark/tests/spark/test_normalize_batch.py`
가 맡는다. 여기서는 그 자르기의 앵커가 되는 부분만 세션 없이 잠근다 — 운영 경로(`s3a://`)
와 로컬 경로가 **같은 규칙**을 타는지가 이 결함의 핵심이었기 때문이다.
"""

from __future__ import annotations

from trendin.spark.normalize.curated import strip_scheme


def test_운영_경로의_스킴을_뗀다():
    assert strip_scheme("s3a://curated") == "curated"


def test_로컬_경로에는_스킴이_없어_그대로다():
    """`root` 는 로컬일 때 스킴이 없고 `input_file_name()` 은 `file://` 를 붙여 준다.

    양쪽에 같은 함수를 걸어야 `^{root}/` 앵커가 맞는다. 이 비대칭이 키에 경로가 통째로
    들어간 원인이었다.
    """
    assert strip_scheme("/tmp/pytest-0/curated") == "/tmp/pytest-0/curated"
    assert strip_scheme("file:///tmp/pytest-0/curated") == "/tmp/pytest-0/curated"


def test_윈도우_드라이브_문자를_스킴으로_먹지_않는다():
    """`//` 를 필수로 둔 이유. `:` 만 옵션이면 `C:` 가 스킴으로 잘려 경로가 망가진다."""
    assert strip_scheme(r"C:\Users\x\curated") == r"C:\Users\x\curated"
