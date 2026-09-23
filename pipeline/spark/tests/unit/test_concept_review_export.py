"""검수지가 관찰 모드의 제안을 어떻게 옮기는가.

사람이 훑고 넣는 흐름이라 **비우는 자리가 채우는 자리만큼 중요하다** — 판정이 스스로 못
고르겠다고 한 것을 미리 채우면 그대로 반영된다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "_concept_review", ROOT / "scripts" / "concept-review.py"
)
_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_review)

suggestion = _review._suggestion


def test_연결_제안은_개념_번호를_채운다():
    decision, concept, why = suggestion(
        {"decision": "LINK", "concept_id": 42, "english_name": "vest", "category": "apparel"}
    )
    assert (decision, concept) == ("LINK", "42")
    assert "vest/apparel" in why


def test_새_개념_제안은_이름과_분류를_채운다():
    """`apply` 가 `이름/분류` 모양을 요구한다."""
    assert suggestion(
        {"decision": "NEW_CONCEPT", "english_name": "balletcore", "category": "style"}
    )[:2] == ("NEW", "balletcore/style")


def test_세지_않을_것은_개념_열을_비운다():
    """`EXCLUDE` 는 `apply` 가 표기 자체로 개념을 만든다 — 번호를 줄 것이 없다."""
    assert suggestion({"decision": "EXCLUDE", "english_name": "summer"})[:2] == ("EXCLUDE", "")


def test_유보와_모양이_어긋난_제안은_비운다():
    """사람이 채워야 할 자리다. 미리 채우면 훑지 않고 반영된다."""
    assert suggestion({"decision": "DEFER", "reason": "COMPETING_REFERENT"})[:2] == ("", "")
    # 개념 번호 없는 LINK, 분류 없는 NEW — 둘 다 그대로 넣을 수 없다.
    assert suggestion({"decision": "LINK", "english_name": "coach"})[:2] == ("", "")
    assert suggestion({"decision": "NEW_CONCEPT", "english_name": "balletcore"})[:2] == ("", "")


def test_제안이_없으면_세_칸_모두_빈다():
    assert suggestion(None) == ("", "", "")


def test_왜_그렇게_봤는지를_남긴다():
    """`why` 는 `apply` 가 읽지 않는다. 사람이 판단을 되짚는 자리다."""
    why = suggestion(
        {"decision": "DEFER", "english_name": "Dior", "category": "brand",
         "reason": "COMPETING_REFERENT", "outcome": "STRONG"}
    )[2]
    assert "Dior/brand" in why and "COMPETING_REFERENT" in why
