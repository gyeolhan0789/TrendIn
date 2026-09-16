"""GMS 실제 호출 검증. GMS_KEY가 있을 때만 실행한다."""

import os

import pytest

from trendin.ai.analyzer import TrendAnalyzer

pytestmark = pytest.mark.skipif(not os.environ.get("GMS_KEY"), reason="GMS_KEY가 필요하다")


@pytest.mark.allow_network
def test_GMS_gpt_5_4_nano가_트렌드_JSON을_반환한다():
    result = TrendAnalyzer().analyze(
        "트렌드: 발레코어. 리본과 플랫슈즈 콘텐츠가 늘었고, 브랜드 신제품과 "
        "셀럽 스타일링 노출이 최근 증가했다."
    )

    assert result.description
    assert result.summary
    assert result.reason
