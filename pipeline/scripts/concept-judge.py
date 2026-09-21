#!/usr/bin/env python
"""미등록 표기에 영어 이름과 분류를 붙인다 — LLM 을 부르는 유일한 진입점.

```sh
# 부르지 않고 견적만 본다. 프롬프트 전문과 어림 토큰을 찍는다.
.venv/Scripts/python scripts/concept-judge.py --profile local --limit 30 --estimate

# 실제로 부른다. GMS_KEY 가 있어야 하고 크레딧이 든다.
GMS_KEY=... .venv/Scripts/python scripts/concept-judge.py --profile local --limit 30

# 기존 개념과 이름·분류가 정확히 맞는 결과만 자동 반영한다.
GMS_KEY=... .venv/Scripts/python scripts/concept-judge.py --profile dev --limit 30 --apply-links
```

**기본은 견적이 아니라 호출이지만, 부르기 전에 반드시 한도를 본다.** `--max-calls` 를 넘으면
그 회차는 거기서 멈춘다. 기사 수가 많은 것부터 물어서, 예산이 모자라면 영향이 큰 것만 하고
나머지는 다음으로 넘어간다.

기본은 TSV 출력만 한다. `--apply-links` 를 주면 기존 개념의 영어 이름과 분류가
유일하게 정확히 일치한 표기만 사전에 자동 연결한다. 새 개념과 애매한 이름은 검수 대상으로 남긴다.
`--vector-top-k`를 켜면 문자·음가·벡터 후보를 합쳐 재정렬하고 별도 LLM 호출로 검증한다.
자동 반영 관문은 `concept.retrieval` 설정을 따르며 `--min-vector-similarity`로 한 회차만
덮어쓸 수 있다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.concept import vector_judge  # noqa: E402
from trendin.spark.concept.auto_link import Link, apply_links, select_links  # noqa: E402
from trendin.spark.concept.candidates import CandidateIndex  # noqa: E402
from trendin.spark.concept.embedding import (  # noqa: E402
    MODEL_ID,
    MODEL_REVISION,
    E5Encoder,
    model_key,
)
from trendin.spark.concept.judge import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    NameIndex,
    Question,
    batches,
    estimate_tokens,
    messages,
    parse,
    user_prompt,
)
from trendin.spark.concept.retrieval import (  # noqa: E402
    CandidateRetriever,
    RankedCandidate,
    RetrievalPolicy,
)
from trendin.spark.concept.vector_judge import (  # noqa: E402
    eligible_choice,
    parse_choice,
    verification_slot_available,
)
from trendin.spark.io import jdbc  # noqa: E402
from trendin.spark.io.concept_vectors import ConceptVectorStore, VectorHit  # noqa: E402
from trendin.spark.io.concepts import UNMAPPED, UNMAPPED_CONTEXT, ConceptSink  # noqa: E402
from trendin.spark.io.llm import DEFAULT_MODEL, GmsClient  # noqa: E402

# 답 하나에 드는 출력 토큰 어림. `{"i":1,"en":"vintage","cat":"style"}` 가 스무 남짓이다.
OUTPUT_TOKENS_PER_ITEM = 22

UNMAPPED_SQL = f"""
SELECT u.lang, u.normalized, u.article_count,
       (SELECT c.snippet FROM {UNMAPPED_CONTEXT} c WHERE c.unmapped_id = u.id
         ORDER BY c.article_id LIMIT 1) AS context
  FROM {UNMAPPED} u
 WHERE u.status IN ('PENDING', 'QUEUED')
   AND u.article_count >= %s
 ORDER BY u.article_count DESC, u.lang, u.normalized
"""


def load_questions(config, min_articles: int, limit: int | None) -> list[Question]:
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(UNMAPPED_SQL, (min_articles,))
        rows = cur.fetchall()
    if limit:
        rows = rows[:limit]
    return [
        Question(index=i, lang=lang, normalized=key, article_count=count, context=context)
        for i, (lang, key, count, context) in enumerate(rows, start=1)
    ]


def estimate(groups: list[list[Question]]) -> tuple[int, int]:
    system = estimate_tokens(SYSTEM_PROMPT)
    prompt = sum(system + estimate_tokens(user_prompt(g)) for g in groups)
    output = sum(len(g) * OUTPUT_TOKENS_PER_ITEM for g in groups)
    return prompt, output


def vector_candidate_groups(
    encoder: E5Encoder, store: ConceptVectorStore, english_name: str,
    original: str, *, limit: int,
) -> dict[str, tuple[VectorHit, ...]]:
    """Search both inputs while retaining which query produced each vector score."""
    vectors = encoder.encode([original, english_name], query=True)
    groups = [store.search(values, model_id=encoder.model_id, limit=limit) for values in vectors]
    return {"original": groups[0], "english": groups[1]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="local")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--min-articles", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None, help="영향 큰 것부터 이만큼만")
    parser.add_argument("--max-calls", type=int, default=5,
                        help="영어 이름 판정과 벡터 후보 재판정을 합친 최대 LLM 호출 수")
    parser.add_argument("--estimate", action="store_true", help="부르지 않고 견적만 본다")
    parser.add_argument("--show-prompt", action="store_true", help="프롬프트 전문을 찍는다")
    parser.add_argument(
        "--apply-links", action="store_true", help="확실한 기존 개념 연결만 DB에 반영"
    )
    parser.add_argument("--vector-top-k", type=int, default=0,
                        help="pgvector 후보를 LLM에게 재판정시킬 개수. 0이면 끔")
    parser.add_argument("--embedding-model", default=MODEL_ID)
    parser.add_argument("--embedding-revision", default=MODEL_REVISION)
    parser.add_argument("--min-vector-similarity", type=float, default=None,
                        help="호환용 이름: 설정의 통합 점수 하한을 이번 실행에서 덮어쓴다")
    parser.add_argument("--apply-verified", action="store_true",
                        help="LLM이 고르고 유사도·분류 관문도 넘은 벡터 후보를 DB에 반영")
    args = parser.parse_args(argv)

    if args.vector_top_k < 0:
        parser.error("--vector-top-k must be nonnegative")
    if args.apply_verified and not args.vector_top_k:
        parser.error("--apply-verified requires --vector-top-k")
    if args.min_vector_similarity is not None and not -1 <= args.min_vector_similarity <= 1:
        parser.error("--min-vector-similarity must be between -1 and 1")

    config = load_config(args.profile)
    questions = load_questions(config, args.min_articles, args.limit)
    if not questions:
        print("물을 것이 없다", file=sys.stderr)
        return 0
    groups = batches(questions, args.batch_size)
    prompt_tokens, output_tokens = estimate(groups)

    print(
        f"표현 {len(questions)}개 · 배치 {len(groups)}개(하나에 {args.batch_size}개) · "
        f"모델 {args.model} · 프롬프트 {PROMPT_VERSION}",
        file=sys.stderr,
    )
    print(
        f"어림 토큰 — 입력 {prompt_tokens:,} · 출력 {output_tokens:,}",
        file=sys.stderr,
    )
    if args.show_prompt or args.estimate:
        print("\n--- 지시문 ---\n" + SYSTEM_PROMPT, file=sys.stderr)
        print("\n--- 첫 배치 입력 ---\n" + user_prompt(groups[0]), file=sys.stderr)
    if args.estimate:
        print("\n견적만 냈다. 부르지 않았다.", file=sys.stderr)
        return 0

    if len(groups) > args.max_calls:
        print(
            f"호출 {len(groups)}번이 한도 {args.max_calls}번을 넘는다 — "
            "--max-calls 를 올리거나 --limit 으로 줄인다",
            file=sys.stderr,
        )
        return 1

    client = GmsClient(model=args.model)
    dictionary = ConceptSink(config).load_dictionary()
    names = NameIndex(dictionary)
    encoder = store = retriever = None
    if args.vector_top_k:
        store = ConceptVectorStore(config)
        total, embedded = store.coverage(model_key(args.embedding_model, args.embedding_revision))
        if not total or embedded != total:
            parser.error(
                f"개념 임베딩 {embedded}/{total}개 — "
                "scripts/concept-vectors.py 를 먼저 실행한다"
            )
        encoder = E5Encoder(args.embedding_model, args.embedding_revision)
        policy = RetrievalPolicy.from_config(config)
        if args.vector_top_k != policy.top_k:
            policy = replace(policy, top_k=args.vector_top_k)
        if args.min_vector_similarity is not None:
            policy = replace(policy, min_combined_score=args.min_vector_similarity)
        retriever = CandidateRetriever(dictionary, CandidateIndex(dictionary), policy)
        print(f"벡터 사전 표현 {embedded:,}개 · 통합 Top {policy.top_k}", file=sys.stderr)
    print(f"사전의 영어 이름 {len(names):,}개", file=sys.stderr)
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    columns = ["lang", "normalized", "articles", "en", "category", "결정", "사전", "닮은 이름"]
    if args.vector_top_k:
        columns.extend(("통합 후보", "후보 판정"))
    writer.writerow(columns)
    counts: dict[str, int] = {}
    # 이번 회차 안에서 같은 영어 이름이 여러 번 나오면 개념 하나에 모은다 — `슈즈` 와 `신발` 이
    # 둘 다 `shoes` 로 오는 경우다. 두 번째부터는 새로 만들지 않고 첫 번째에 붙인다.
    minted: set[tuple[str, str]] = set()
    auto_links = []
    verified_links = []
    skipped_verifications = 0
    for group_index, group in enumerate(groups):
        verdicts, problems = parse(client.chat(messages(group)), group)
        for problem in problems:
            print(f"  ! {problem}", file=sys.stderr)
        articles = {q.normalized: q.article_count for q in group}
        batch_links = select_links(verdicts, names)
        auto_links.extend(batch_links)
        link_by_key = {(link.verdict.lang, link.verdict.normalized): link for link in batch_links}
        question_by_key = {(q.lang, q.normalized): q for q in group}
        for verdict in verdicts:
            # 받은 영어 이름으로 **우리가** 사전을 찾는다. 모델에게 고르라고 하지 않는다.
            resolution = names.resolve(verdict.english_name, verdict.category)
            decision = resolution.decision
            auto_link = link_by_key.get((verdict.lang, verdict.normalized))
            if auto_link is not None:
                decision = "AUTO_LINK"
            hits: tuple[RankedCandidate, ...] = ()
            candidate_choice: RankedCandidate | None = None
            if (
                encoder is not None and store is not None and retriever is not None
                and auto_link is None and verdict.category != "generic"
            ):
                vector_hits = vector_candidate_groups(
                    encoder, store, verdict.english_name, verdict.normalized,
                    limit=max(args.vector_top_k, retriever.policy.top_k),
                )
                retrieval = retriever.retrieve(
                    original=verdict.normalized,
                    lang=verdict.lang,
                    english_name=verdict.english_name,
                    category=verdict.category,
                    vector_hits=vector_hits,
                )
                hits = retrieval.candidates
                if retrieval.deferred:
                    decision = "DEFER"
                # Reserve one call for each remaining name-classification batch.
                remaining_groups = len(groups) - group_index - 1
                if not retrieval.deferred and hits and verification_slot_available(
                    client.calls, remaining_groups, args.max_calls
                ):
                    question = question_by_key[(verdict.lang, verdict.normalized)]
                    response = client.chat(
                        vector_judge.messages(verdict, hits, context=question.context)
                    )
                    try:
                        choice = parse_choice(response, hits)
                    except ValueError as error:
                        print(f"  ! {verdict.normalized}: {error}", file=sys.stderr)
                        choice = None
                    if choice is not None:
                        decision = "CANDIDATE_SUGGEST"
                        candidate_choice = next(
                            hit for hit in hits if hit.concept_id == choice
                        )
                        accepted = eligible_choice(
                            verdict,
                            hits,
                            choice,
                            min_similarity=retriever.policy.min_combined_score,
                            context=question.context,
                        )
                        if accepted is not None:
                            decision = "CANDIDATE_LINK"
                            score = next(
                                hit.similarity for hit in hits if hit.concept_id == accepted
                            )
                            verified_links.append(Link(verdict, accepted, "combined", score))
                elif not retrieval.deferred and hits:
                    decision = "CANDIDATE_UNCHECKED"
                    skipped_verifications += 1
            # 이름이 같아도 분류가 다르면 다른 것이다 — `윈터`(사람)와 `겨울`(계절).
            key = (verdict.english_name.lower(), verdict.category)
            if decision == "NEW" and key in minted:
                decision = "SAME_RUN"
            elif decision == "NEW":
                minted.add(key)
            counts[decision] = counts.get(decision, 0) + 1
            row = [
                verdict.lang,
                verdict.normalized,
                articles.get(verdict.normalized, 0),
                verdict.english_name,
                verdict.category,
                decision,
                ", ".join(
                    dictionary.concept(cid).canonical_name for cid in resolution.concept_ids
                ),
                ", ".join(f"{n}({s})" for n, s in resolution.near),
            ]
            if args.vector_top_k:
                row.append(
                    ", ".join(
                        f"{h.name}/{h.category}:{h.score:.3f}"
                        f"[{'+'.join(item.channel for item in h.evidence)}]"
                        for h in hits
                    )
                )
                row.append(
                    ""
                    if candidate_choice is None
                    else (
                        f"{candidate_choice.concept_id}:"
                        f"{candidate_choice.name}/{candidate_choice.category}"
                    )
                )
            writer.writerow(row)

    print(
        f"\n호출 {client.calls}번 · 실제 토큰 입력 {client.prompt_tokens:,} · "
        f"출력 {client.completion_tokens:,}",
        file=sys.stderr,
    )
    if skipped_verifications:
        print(
            f"LLM 호출 한도로 벡터 재판정 {skipped_verifications}건을 건너뛰었다",
            file=sys.stderr,
        )
    applied_total = 0
    if args.apply_links:
        applied_total += apply_links(
            config, tuple(auto_links), model=args.model, prompt_version=PROMPT_VERSION
        )
    if args.apply_verified:
        applied_total += apply_links(
            config, tuple(verified_links), model=args.model, prompt_version="vector-v1"
        )
    if args.apply_links or args.apply_verified:
        target = (len(auto_links) if args.apply_links else 0) + (
            len(verified_links) if args.apply_verified else 0
        )
        print(f"기존 개념 자동 연결 {applied_total}건 / 대상 {target}건", file=sys.stderr)
    else:
        print(f"정확 일치 {len(auto_links)}건 · 검증된 벡터 후보 {len(verified_links)}건 "
              "(반영하려면 --apply-links / --apply-verified)", file=sys.stderr)
    print("결정: " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
