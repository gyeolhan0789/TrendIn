"""소스 레지스트리 (설계 문서 #1 표의 dev 행)."""

import re

import pytest

from trendin.dev.collect import sources


def test_hn_하나다():
    assert sorted(sources.BY_KEY) == ["hn"]


def test_hn_의_국가는_판정할_수_없어_XX_다():
    """hn 은 애그리게이터라 다른 소스의 "발행 법인 소재지" 기준이 붙지 않는다.

    글쓴이는 세계 각국이고 hn 자신은 링크를 모아 둘 뿐이다. `null` 이 아니라 `XX` 인 것은
    "아직 안 붙였다"와 "붙일 수 없다"를 구분하기 위해서다.
    """
    assert sources.get("hn").country == "XX"


def test_국가는_대문자_두_글자다():
    """ISO 3166-1 alpha-2 대문자. `XX` 도 같은 모양이라 판정 불가가 형식을 벗어나지 않는다."""
    assert re.fullmatch(r"[A-Z]{2}", sources.get("hn").country)


def test_모르는_소스는_있는_것을_알려주며_실패한다():
    with pytest.raises(KeyError, match="hn"):
        sources.get("reddit")
