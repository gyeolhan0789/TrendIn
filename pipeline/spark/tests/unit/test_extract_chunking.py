"""토막 분할 (`extract/chunking.py`)과 그 뒤처리 (`extract/entities.py`). 층 1 ([09 §4]).

**모델 없이 전량을 검증할 수 있는 것이 이 설계의 값어치다.** 분할은 문자열 연산이고
오프셋 복원과 중복 접기는 순수 함수라, GLiNER 를 올리지 않고도 경계가 맞는지 확인된다.
"""

from __future__ import annotations

import pytest

from trendin.spark.extract import chunking as ck
from trendin.spark.extract.entities import Span, _dedupe, _packed


def words(count: int, *, period_every: int = 0) -> str:
    """어절 `count` 개짜리 본문. `period_every` 마다 마침표를 찍는다."""
    parts = []
    for index in range(count):
        token = f"w{index}"
        if period_every and (index + 1) % period_every == 0:
            token += "."
        parts.append(token)
    return " ".join(parts)


def split(text: str, *, budget: int = 256, overlap: int = 24, max_chunks: int = 3):
    return ck.split(text, budget=budget, overlap=overlap, max_chunks=max_chunks)


# --- 분할 ---------------------------------------------------------------------------


def test_short_text_is_one_chunk():
    """예산 안에 들어가면 자르지 않는다. 자르면 겹침 중복만 생긴다."""
    text = words(100)
    chunks = split(text)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].offset == 0


@pytest.mark.parametrize("text", ["", "   ", "\n\n"])
def test_empty_text_yields_nothing(text):
    """빈 문서는 토막이 없다. 빈 문자열을 모델에 넣으면 경고만 쌓인다."""
    assert split(text) == []


def test_offsets_point_into_the_original():
    """**이 테스트가 이 모듈의 핵심이다.** 오프셋이 어긋나면 제목 가산과 조사 제거가 함께
    무너지는데, 증상은 "후보가 좀 이상하다" 로만 나타난다."""
    text = words(600)
    for chunk in split(text):
        assert text[chunk.offset : chunk.offset + len(chunk.text)] == chunk.text


def test_chunks_cover_the_text_in_order():
    """토막이 앞에서 뒤로 이어진다. 겹침 때문에 뒤 토막의 시작이 앞 토막의 끝보다 앞이다."""
    text = words(600)
    chunks = split(text)
    assert len(chunks) > 1
    offsets = [chunk.offset for chunk in chunks]
    assert offsets == sorted(offsets)
    for before, after in zip(chunks, chunks[1:]):
        assert after.offset < before.offset + len(before.text)


def test_max_chunks_caps_the_cost():
    """상한을 넘는 뒷부분은 버린다. 옛 `max_chars` 가 하려던 일이다."""
    text = words(2000)
    assert len(split(text, max_chunks=3)) == 3
    assert len(split(text, max_chunks=1)) == 1


def test_overlap_zero_still_advances():
    """겹침이 0 이어도 토막이 앞으로 나아간다 — 무한 루프가 되지 않는다."""
    chunks = split(words(600), overlap=0)
    assert len(chunks) == 3
    assert chunks[0].offset < chunks[1].offset < chunks[2].offset


def test_cut_prefers_a_sentence_end():
    """문장이 끝나는 자리에서 끊는다. 예산 경계에서 기계적으로 자르면 `2026 봄/여름
    컬렉션` 같은 다어절 실체가 반으로 갈린다."""
    text = words(600, period_every=50)
    first = split(text)[0]
    assert first.text.endswith(".")
    # 예산(256)보다는 짧고, 되짚는 범위(예산의 1/4)를 벗어나지 않는다.
    assert 192 <= ck.count_tokens(first.text) <= 256


def test_cut_falls_back_when_no_sentence_end():
    """문장부호가 없으면 예산 자리에서 그냥 끊는다. 끝없이 되짚으면 토막이 짧아져 문맥이
    줄고, 그러면 유형 판정이 나빠진다."""
    first = split(words(600))[0]
    assert ck.count_tokens(first.text) == 256


# --- 배치 구성 ----------------------------------------------------------------------


def chunks_of(*lengths: int) -> list[tuple[ck.Chunk, int]]:
    return [(ck.Chunk(words(n), 0), i) for i, n in enumerate(lengths)]


def test_packed_groups_similar_lengths():
    """길이가 비슷한 것끼리 담는다. 짧은 토막이 긴 토막 길이로 패딩되는 낭비가 이 배칭의
    표적이고, 표본 138건에서 1.37배를 줬다."""
    units = chunks_of(250, 10, 240, 12)
    # 예산이 넉넉하면 넷이 한 배치에 들어가 정렬 효과가 보이지 않는다. 나뉠 만큼 조인다.
    batches = list(_packed(units, budget=600, size=32))
    grouped = [sorted(batch) for batch in batches]
    # 짧은 둘(인덱스 1·3)이 같은 배치에, 긴 둘(0·2)이 같은 배치에 모인다.
    assert [1, 3] in grouped
    assert [0, 2] in grouped


def test_packed_respects_the_word_budget():
    """배치의 최장 토막 × 토막 수가 예산을 넘지 않는다. **길이는 `count_tokens` 로 센다** —
    분할과 다른 규칙으로 세면 예산이 어긋나 배치가 커지고, 1차 전량 재추출이 그렇게 죽었다."""
    units = chunks_of(*([200] * 20))
    for batch in _packed(units, budget=600, size=32):
        longest = max(ck.count_tokens(units[i][0].text) for i in batch)
        assert longest * len(batch) <= 600


def test_packed_respects_the_count_cap():
    """짧은 토막만 모여도 배치가 무한정 커지지 않는다."""
    units = chunks_of(*([5] * 100))
    for batch in _packed(units, budget=100_000, size=8):
        assert len(batch) <= 8


def test_packed_covers_every_unit_once():
    """하나도 빠지지 않고 하나도 겹치지 않는다. 빠지면 그 토막의 구간이 통째로 사라진다."""
    units = chunks_of(5, 300, 7, 120, 9)
    seen = [i for batch in _packed(units, budget=600, size=3) for i in batch]
    assert sorted(seen) == list(range(len(units)))


def test_packed_is_deterministic():
    """같은 입력이 같은 배치를 낸다 — 아니면 스냅샷이 서지 않는다 ([04 §9])."""
    units = chunks_of(10, 10, 10, 10)
    assert list(_packed(units, budget=100, size=2)) == list(_packed(units, budget=100, size=2))


# --- 중복 접기 ----------------------------------------------------------------------


def span(surface: str, start: int, score: float = 0.5, label: str = "브랜드") -> Span:
    return Span(surface=surface, label=label, score=score, start=start, end=start + len(surface))


def test_dedupe_folds_the_same_position():
    """겹침 구역을 두 토막이 보므로 같은 자리가 두 번 나온다. **접지 않으면 `tf` 가 부풀어
    `REPEAT_BONUS` 가 두 번 붙는다.**"""
    kept = _dedupe([span("샤넬", 10, 0.9), span("샤넬", 10, 0.7)])
    assert len(kept) == 1
    assert kept[0].score == 0.9


def test_dedupe_keeps_distinct_occurrences():
    """같은 표기라도 자리가 다르면 문서 안에서 실제로 두 번 나온 것이다."""
    kept = _dedupe([span("샤넬", 10), span("샤넬", 500)])
    assert [s.start for s in kept] == [10, 500]


def test_dedupe_folds_boundary_drift():
    """경계가 한 어절씩 어긋난 쌍을 접는다. 토막마다 문맥이 달라 끝이 밀리는 일이 있다."""
    kept = _dedupe([span("데님 팬츠", 10, 0.9), span("데님 팬츠가", 10, 0.4)])
    assert [s.surface for s in kept] == ["데님 팬츠"]


def test_dedupe_returns_document_order():
    """등장 순서로 돌려준다 — `document._merge` 가 이 순서로 비교키의 첫 등장을 정한다."""
    kept = _dedupe([span("디올", 300, 0.8), span("샤넬", 10, 0.9), span("구찌", 150, 0.6)])
    assert [s.start for s in kept] == [10, 150, 300]


def test_dedupe_is_deterministic_on_ties():
    """점수가 같아도 결과가 흔들리지 않는다."""
    tied = [span("샤넬", 10, 0.5), span("샤넬의", 10, 0.5)]
    assert _dedupe(tied) == _dedupe(list(reversed(tied)))
