"""후보 생성 ([04 §3]). 층 1."""

from __future__ import annotations

import pytest

from trendin.spark.extract import candidates as cand
from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.lexicon import Lexicon
from trendin.spark.extract.tokenize import tokenize
from trendin.spark.normalize.lang import EN, KO

LEXICON = Lexicon.of(stopwords=["the", "is", "changing", "how", "we", "for"])


def candidates_of(text, lang=EN, *, ngram_max=3, in_title=False):
    tokens = tokenize(text, lang, lexicon=LEXICON)
    return cand.ngram_candidates(cand.spans(tokens), ngram_max=ngram_max, in_title=in_title)


def keys(occurrences):
    return [occ.key for occ in occurrences]


def test_불용어와_경계로_구간을_자른다():
    tokens = tokenize("the new agentic workflow is changing how we build", EN, lexicon=LEXICON)

    assert [[t.surface for t in span] for span in cand.spans(tokens)] == [
        ["new", "agentic", "workflow"],
        ["build"],
    ]


def test_구간_안의_모든_n_gram_을_낸다():
    """[04 §3] 의 예시 그대로 — 길이 1~3 전부."""
    result = keys(candidates_of("the new agentic workflow is changing how we build"))

    assert sorted(result) == sorted(
        [
            "new",
            "agentic",
            "workflow",
            "new agentic",
            "agentic workflow",
            "new agentic workflow",
            "build",
        ]
    )


def test_길이_상한을_지킨다():
    result = keys(candidates_of("new agentic workflow", ngram_max=2))
    assert "new agentic workflow" not in result and "new agentic" in result


def test_포함_관계를_부모로_든다():
    """C-value 의 T_a — 같은 구간에서 나를 포함하는 더 긴 후보."""
    by_key = {occ.key: occ for occ in candidates_of("new agentic workflow")}

    assert by_key["workflow"].parents == ("agentic workflow", "new agentic workflow")
    assert by_key["agentic workflow"].parents == ("new agentic workflow",)
    assert by_key["new agentic workflow"].parents == ()


def test_숫자_꼴은_꼬리로만():
    """`Python 3.12` 는 되고 `3.12` · `3 tips` 는 안 된다."""
    result = {occ.key: occ for occ in candidates_of("Python 3.12 3 tips")}

    assert "python 3.12" in result and result["python 3.12"].kind == cand.VERSIONED
    assert "3.12" not in result and "3 tips" not in result and "3" not in result
    assert "tips" in result


def test_종류가_붙는다():
    result = {occ.key: occ.kind for occ in candidates_of("MCP useEffect ballet sneakers #newtro")}

    assert result["mcp"] == tk.ACRONYM
    assert result["useeffect"] == tk.CODE
    assert result["ballet"] == cand.TERM
    assert result["ballet sneakers"] == cand.NGRAM
    assert result["newtro"] == tk.HASHTAG


def test_해시태그는_n_gram_에_섞이지_않는다():
    result = keys(candidates_of("new #vibecoding trend"))
    assert "new vibecoding" not in result and "vibecoding trend" not in result


def test_제목_표시가_실린다():
    result = candidates_of("ballet sneakers", in_title=True)
    assert all(occ.in_title for occ in result)


def test_한국어_구간도_같다():
    result = keys(candidates_of("인트레치아토 기법을 재해석한 백과 실루엣", KO))

    assert "인트레치아토 기법" in result and "재해석" in result and "실루엣" in result
    # 조사 뒤는 경계라 `기법 재해석` 은 없다. 한 음절 `백` 은 후보가 못 된다 ([04 §5] 1번).
    assert "기법 재해석" not in result and "백" not in result


# --- 약어-전개형 쌍 ([05 §3] 의 결정적 증거) ---------------------------------------


def test_영문_전개형과_약어의_첫_글자가_맞으면_기록한다():
    (pair,) = cand.abbreviation_pairs("the Model Context Protocol (MCP) is here")

    assert pair.abbreviation == "MCP"
    assert pair.expansion == "Model Context Protocol"  # 앞의 `the` 는 전개형이 아니다
    assert pair.expansion_key == "model context protocol"
    assert pair.initials_match is True


def test_기능어를_건너뛰어_맞춘다():
    (pair,) = cand.abbreviation_pairs("Retrieval of Augmented Generation (RAG)")
    assert pair.expansion == "Retrieval of Augmented Generation" and pair.initials_match


def test_첫_글자가_안_맞으면_기록하지_않는다():
    assert cand.abbreviation_pairs("some random words (XYZ)") == []


def test_한국어_전개형은_대응을_볼_수_없어_표시만_남긴다():
    (pair,) = cand.abbreviation_pairs("MCP는 모델 컨텍스트 프로토콜(MCP)의 약자다")

    assert pair.expansion == "모델 컨텍스트 프로토콜"  # 앞의 `MCP는` 은 빠진다
    assert pair.initials_match is False


@pytest.mark.parametrize("text", [None, "", "no parens here", "(MCP)"])
def test_쌍이_없으면_빈_목록(text):
    assert cand.abbreviation_pairs(text) == []
