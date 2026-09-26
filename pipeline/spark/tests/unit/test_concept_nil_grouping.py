"""미등록 표기 덩이 판정 → 기존 개념에 잇기 (`concept/nil_grouping.py`, S15P21A102-394)."""

from __future__ import annotations

import argparse
import json

import pytest

from trendin.spark.concept import nil_grouping
from trendin.spark.concept.cluster_judge import Cluster, Judgement, Member
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.mapping import Keyword, Unmapped

LONDON = Concept(11, "London Fashion Week", "event")
PARIS = Concept(12, "Paris Fashion Week", "event")
VOGUE = Concept(21, "Vogue World 2026", "event")
TWIN = Concept(31, "coach", "brand")
COACH = Concept(32, "coach", "person")

DICTIONARY = Dictionary(
    concepts=[LONDON, PARIS, VOGUE, TWIN, COACH],
    expressions=[
        Expression(1, 11, "en", "london fashion week"),
        Expression(2, 12, "en", "paris fashion week"),
        Expression(3, 21, "en", "vogue world 2026"),
        Expression(4, 31, "en", "coach", ambiguous=True),
        Expression(5, 32, "en", "coach", ambiguous=True),
    ],
)


def grouped(**articles: list[str]) -> dict[int, list[Keyword]]:
    """`a1=["LFW", ...]` → 기사 번호 1 에 그 표기들. 문맥은 표기가 든 문장으로 채운다."""
    return {
        int(name[1:]): [Keyword(surface, f"At {surface} today") for surface in surfaces]
        for name, surfaces in articles.items()
    }


LFW_ARTICLES = grouped(
    a1=["LFW", "London Fashion Week"],
    a2=["LFW", "London Fashion Week"],
    a3=["LFW"],
    a4=["Vogue World 2026", "Vogue World 2026: Milano"],
    a5=["Vogue World 2026: Milano"],
    a6=["Vogue World 2026: Milano"],
)


# --- 관찰 · 덩이 고르기 ---------------------------------------------------------


def test_표기마다_등장_기사와_개념을_모은다():
    observed = nil_grouping.observe(LFW_ARTICLES, DICTIONARY)
    assert observed["lfw"].docs == {1, 2, 3}
    assert observed["lfw"].unmapped
    assert observed["london fashion week"].concept_id == 11
    assert observed["vogue world 2026 milano"].surface == "Vogue World 2026: Milano"


def test_사전에서_모호한_표기는_미등록이_아니다():
    observed = nil_grouping.observe(grouped(a1=["Coach"]), DICTIONARY)
    assert observed["coach"].ambiguous
    assert not observed["coach"].unmapped


def test_본문_문장을_제목보다_앞에_둔다():
    sentences = {("la", "lfw"): ["Day three of LFW opened with Burberry."]}
    observed = nil_grouping.observe(LFW_ARTICLES, DICTIONARY, sentences)
    assert observed["lfw"].contexts[0] == "Day three of LFW opened with Burberry."


def test_기존_개념이_있고_미등록이_문턱을_넘는_덩이만_고른다():
    observed = nil_grouping.observe(LFW_ARTICLES, DICTIONARY)
    targets = nil_grouping.select_clusters(observed, min_articles=3)
    keys = [tuple(m.key for m in cluster.members) for cluster in targets]
    assert keys == [("lfw", "london fashion week"), ("vogue world 2026", "vogue world 2026 milano")]
    assert targets[0].pairs == (("lfw", "london fashion week", 2),)


def test_미등록이_문턱_아래면_묻지_않는다():
    observed = nil_grouping.observe(LFW_ARTICLES, DICTIONARY)
    assert nil_grouping.select_clusters(observed, min_articles=4) == []


def test_미등록끼리만_있는_덩이는_묻지_않는다():
    """잇을 개념이 없다 — 새 개념 만들기는 범위 밖이다."""
    articles = grouped(
        a1=["White Lotus", "The White Lotus"],
        a2=["White Lotus", "The White Lotus"],
        a3=["White Lotus"],
    )
    observed = nil_grouping.observe(articles, DICTIONARY)
    assert nil_grouping.select_clusters(observed, min_articles=1) == []


# --- 캐시 열쇠 ------------------------------------------------------------------


def test_구성원과_쌍이_같으면_문장이_달라도_같은_열쇠다():
    one = Cluster((Member("a", "A", None, ("x",)), Member("a b", "A B")), (("a", "a b", 1),))
    two = Cluster((Member("a b", "A B", None, ("y",)), Member("a", "A")), (("a", "a b", 5),))
    assert nil_grouping.cache_key(one) == nil_grouping.cache_key(two)


def test_쌍이_다르면_다른_열쇠다():
    one = Cluster((Member("a", "A"), Member("a b", "A B")), (("a", "a b", 1),))
    two = Cluster((Member("a", "A"), Member("a b", "A B")), ())
    assert nil_grouping.cache_key(one) != nil_grouping.cache_key(two)


def test_판정은_캐시를_거쳐도_같다():
    judgement = Judgement({("lfw", "london fashion week"): "same"})
    payload = json.loads(json.dumps(nil_grouping.to_payload(judgement)))
    assert nil_grouping.from_payload(payload) == judgement
    assert nil_grouping.from_payload(None) is None
    assert nil_grouping.from_payload({"relations": []}) is None


# --- 잇기 계획 ------------------------------------------------------------------


def observed_for(*keys_and_concepts: tuple[str, int | None]) -> dict[str, nil_grouping.Observed]:
    return {
        key: nil_grouping.Observed("la", key, key.title(), concept)
        for key, concept in keys_and_concepts
    }


def test_개념이_하나인_묶음의_미등록_표기를_그_개념에_잇는다():
    observed = observed_for(("lfw", None), ("london fashion week", 11))
    links, skipped = nil_grouping.plan_links(
        Judgement({("lfw", "london fashion week"): "same"}), observed
    )
    assert [(link.normalized, link.concept_id, link.relation) for link in links] == [
        ("lfw", 11, "same")
    ]
    assert skipped == []


def test_series_도_잇는다():
    observed = observed_for(("vogue world 2026", 21), ("vogue world 2026 milano", None))
    links, _ = nil_grouping.plan_links(
        Judgement({("vogue world 2026", "vogue world 2026 milano"): "series"}), observed
    )
    assert [(link.normalized, link.relation) for link in links] == [
        ("vogue world 2026 milano", "series")
    ]


def test_합치지_않는_관계는_잇지_않는다():
    observed = observed_for(("fashion week", None), ("london fashion week", 11))
    links, skipped = nil_grouping.plan_links(
        Judgement({("fashion week", "london fashion week"): "related"}), observed
    )
    assert links == [] and skipped == []


def test_개념이_둘_걸린_묶음은_건너뛴다():
    observed = observed_for(("fw", None), ("london fashion week", 11), ("paris fashion week", 12))
    judgement = Judgement(
        {("fw", "london fashion week"): "same", ("fw", "paris fashion week"): "same"}
    )
    links, skipped = nil_grouping.plan_links(judgement, observed)
    assert links == []
    assert skipped == [(("fw", "london fashion week", "paris fashion week"), "MANY_CONCEPTS")]


def test_미등록끼리의_묶음은_건너뛴다():
    observed = observed_for(("white lotus", None), ("the white lotus", None))
    _, skipped = nil_grouping.plan_links(
        Judgement({("the white lotus", "white lotus"): "same"}), observed
    )
    assert skipped == [(("the white lotus", "white lotus"), "NO_CONCEPT")]


def test_모호한_표기가_끼면_건너뛴다():
    observed = observed_for(("coach", None), ("coach bag", None))
    observed["coach"].ambiguous = True
    _, skipped = nil_grouping.plan_links(Judgement({("coach", "coach bag"): "same"}), observed)
    assert skipped == [(("coach", "coach bag"), "AMBIGUOUS")]


def test_두_덩이가_한_표기를_다른_개념에_이으면_잇지_않는다():
    observed = observed_for(("fw", None), ("london fashion week", 11), ("paris fashion week", 12))
    links, skipped = nil_grouping.plan_all(
        [
            Judgement({("fw", "london fashion week"): "same"}),
            Judgement({("fw", "paris fashion week"): "same"}),
        ],
        observed,
    )
    assert links == []
    assert skipped == [(("fw",), "CONFLICT")]


def test_두_덩이가_같은_개념에_이으면_한_번만_잇는다():
    observed = observed_for(("lfw", None), ("london fashion week", 11))
    judgement = Judgement({("lfw", "london fashion week"): "same"})
    links, _ = nil_grouping.plan_all([judgement, judgement], observed)
    assert len(links) == 1


# --- 묻기 -----------------------------------------------------------------------


class FakeClient:
    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls = 0

    def chat(self, messages, *, max_tokens: int = 1200) -> str:
        self.calls += 1
        return self.answers.pop(0)


PAIR = Cluster(
    (Member("lfw", "LFW"), Member("london fashion week", "London Fashion Week")),
    (("lfw", "london fashion week", 2),),
)


def test_어긋난_답이면_한_번_더_묻는다():
    client = FakeClient("not json", json.dumps({"r": [{"p": 1, "rel": "same"}]}))
    judgement, problems, calls = nil_grouping.ask(client, PAIR)
    assert judgement == Judgement({("lfw", "london fashion week"): "same"})
    assert calls == 2 and problems


def test_두_번_다_어긋나면_판정이_없다():
    client = FakeClient("not json", "{}")
    judgement, _, calls = nil_grouping.ask(client, PAIR)
    assert judgement is None and calls == 2


# --- 설정 -----------------------------------------------------------------------


def test_설정이_없으면_꺼져_있다():
    policy = nil_grouping.Policy.from_mapping({})
    assert not policy.enabled and not policy.apply


def test_호출_상한은_1_이상이다():
    with pytest.raises(ValueError):
        nil_grouping.Policy.from_mapping({"max_calls": 0})


# --- 개념 Job 단계 --------------------------------------------------------------


class FakeSink:
    def __init__(self, dictionary: Dictionary, cached: dict | None = None) -> None:
        self.dictionary = dictionary
        self.cache = dict(cached or {})
        self.writes = 0

    def load_dictionary(self):
        return self.dictionary

    def current_version(self):
        return 1

    def cached_judgement(self, **key):
        return self.cache.get((key["normalized"], key["candidate_hash"]))

    def cache_judgement(self, *, verdict, **key):
        self.cache[(key["normalized"], key["candidate_hash"])] = verdict

    def write(self, **_):
        self.writes += 1


def run_step(monkeypatch, sink, client, *, apply: bool, max_calls: int = 10):
    import concept as job

    from trendin.spark.concept import auto_link
    from trendin.spark.io import llm

    applied: list = []

    def fake_apply(config, links, **kwargs):
        applied.extend(links)
        return links

    monkeypatch.setattr(auto_link, "apply_links", fake_apply)
    monkeypatch.setattr(llm, "GmsClient", lambda model: client)
    thresholds = argparse.Namespace(min_articles=3, context_samples=20)
    unmapped = [Unmapped(1, "la", "lfw", "LFW", "At LFW today")]
    job._run_nil_grouping(
        config=None,
        sink=sink,
        policy=nil_grouping.Policy(enabled=True, apply=apply, max_calls=max_calls),
        thresholds=thresholds,
        grouped=LFW_ARTICLES,
        unmapped=unmapped,
    )
    return applied


ANSWER = json.dumps({"r": [{"p": 1, "rel": "same"}]})


def test_판정해서_잇고_캐시에_남긴다(monkeypatch):
    sink = FakeSink(DICTIONARY)
    client = FakeClient(ANSWER, json.dumps({"r": [{"p": 1, "rel": "series"}]}))
    applied = run_step(monkeypatch, sink, client, apply=True)
    assert sorted((link.verdict.normalized, link.concept_id) for link in applied) == [
        ("lfw", 11),
        ("vogue world 2026 milano", 21),
    ]
    assert applied[0].verdict.english_name == "London Fashion Week"
    assert len(sink.cache) == 2 and sink.writes == 1


def test_캐시에_있으면_묻지_않는다(monkeypatch):
    sink = FakeSink(DICTIONARY)
    run_step(monkeypatch, sink, FakeClient(ANSWER, ANSWER), apply=False)
    client = FakeClient()
    run_step(monkeypatch, sink, client, apply=False)
    assert client.calls == 0


def test_apply_가_꺼져_있으면_넣지_않는다(monkeypatch):
    sink = FakeSink(DICTIONARY)
    applied = run_step(monkeypatch, sink, FakeClient(ANSWER, ANSWER), apply=False)
    assert applied == [] and sink.writes == 0


def test_호출_상한을_넘겨_묻지_않는다(monkeypatch):
    sink = FakeSink(DICTIONARY)
    client = FakeClient(ANSWER, ANSWER)
    run_step(monkeypatch, sink, client, apply=False, max_calls=1)
    assert client.calls == 1


def test_LLM_이_죽어도_단계는_조용히_끝난다(monkeypatch):
    class Broken:
        def chat(self, messages, *, max_tokens: int = 1200) -> str:
            raise RuntimeError("GMS down")

    sink = FakeSink(DICTIONARY)
    assert run_step(monkeypatch, sink, Broken(), apply=True) == []


# --- 흔한 머리말 ----------------------------------------------------------------

CITIES = [
    "London",
    "Paris",
    "Milano",
    "New York",
    "Copenhagen",
    "Berlin",
    "Tokyo",
    "Seoul",
    "Madrid",
]


def test_흔한_머리말은_미등록이어도_묻지_않는다():
    """`fashion week` 은 도시마다 붙는다 — 판정이 한 도시와 `same` 이라 하면 일반명사가 합쳐진다."""
    concepts = [Concept(100 + i, f"{city} Fashion Week", "event") for i, city in enumerate(CITIES)]
    dictionary = Dictionary(
        concepts=concepts,
        expressions=[
            Expression(i + 1, concept.concept_id, "en", concept.canonical_name.lower())
            for i, concept in enumerate(concepts)
        ],
    )
    articles = {
        n: [Keyword("Fashion Week", "At Fashion Week today"), Keyword(f"{city} Fashion Week")]
        for n, city in enumerate(CITIES * 2, start=1)
    }
    observed = nil_grouping.observe(articles, dictionary)
    targets = nil_grouping.select_clusters(observed, min_articles=3)
    assert observed["fashion week"].hub
    assert targets == []


def test_흔한_머리말은_판정이_이어도_잇지_않는다():
    observed = observed_for(("fashion week", None), ("london fashion week", 11))
    observed["fashion week"].hub = True
    links, _ = nil_grouping.plan_links(
        Judgement({("fashion week", "london fashion week"): "same"}), observed
    )
    assert links == []
