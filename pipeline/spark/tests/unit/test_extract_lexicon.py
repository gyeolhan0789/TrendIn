"""사전 파일 로드 ([04 §5·§8]). 층 1.

보호어(`protected-*.txt`)는 **없어졌다** — 2026-09-09 형태소 분석기 도입으로 조사 규칙이
고유명사를 자르는 일이 없어졌다. 분석기에게 모르는 고유명사를 알려 주는 사용자 사전은
성격이 달라 `extract/morphology.py` 로 옮겼고, 그 시험은
`test_extract_tokenize.py::test_사용자_사전_*` 이다.
"""

from __future__ import annotations

import pathlib

import pytest

from trendin.spark.extract.lexicon import Lexicon, load_lexicon, read_terms

CONF_LEXICON = pathlib.Path(__file__).resolve().parents[2] / "conf" / "lexicon"


def test_공백으로_나뉜_항목과_주석(tmp_path):
    path = tmp_path / "stopwords-en.txt"
    path.write_text("# 머리말\nthe of  and   # 뒤 주석\n\n  OR\n", encoding="utf-8")

    assert read_terms(path, required=True) == ["the", "of", "and", "OR"]


def test_없는_파일은_필수면_죽고_아니면_빈_목록(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_terms(tmp_path / "없다.txt", required=True)
    assert read_terms(tmp_path / "없다.txt", required=False) == []


def test_언어_불용어는_필수_도메인_파일은_선택(tmp_path):
    (tmp_path / "stopwords-ko.txt").write_text("것 수", encoding="utf-8")
    (tmp_path / "stopwords-en.txt").write_text("the", encoding="utf-8")

    lexicon = load_lexicon(tmp_path, domain="newdomain")

    assert lexicon.is_stopword("것") and lexicon.is_stopword("the")
    assert not lexicon.noise


def test_언어_불용어가_없으면_죽는다(tmp_path):
    """없으면 문장 전체가 한 구간이 되어 후보가 조합적으로 늘고 조용히 잡음이 된다."""
    (tmp_path / "stopwords-ko.txt").write_text("것", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_lexicon(tmp_path, domain="dev")


def test_항목은_비교키로_저장된다():
    """파일에 `Code` · `multi-agent` 로 적어도 `code` · `multi agent` 와 맞는다."""
    lexicon = Lexicon.of(stopwords=["Code", "multi-agent"], noise=["TMP"])

    assert lexicon.is_stopword("code") and lexicon.is_stopword("multi agent")
    assert lexicon.is_noise("tmp")


@pytest.mark.parametrize("domain", ["dev", "fashion"])
def test_저장소의_씨앗_사전이_읽힌다(domain):
    """`spark/conf/lexicon/` 의 실제 파일. 형식이 깨지면 Job 이 시작할 때 죽으므로 여기서
    먼저 잡는다."""
    lexicon = load_lexicon(CONF_LEXICON, domain=domain)

    assert lexicon.is_stopword("the") and lexicon.is_stopword("것")
    assert lexicon.noise
