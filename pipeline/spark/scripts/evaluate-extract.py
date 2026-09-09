#!/usr/bin/env python
"""추출 품질 전후 비교 — [04 §9](../docs/04-keyword-extraction-spec.md) 의 수동 검수·분포 모니터링.

    pipeline/.venv/Scripts/python.exe spark/scripts/evaluate-extract.py \
        --before 20260909T160000 --after 20260909T173000

`pl_document_candidate` 의 **두 `extract_run_id` 를 같은 방식으로** 재서 마크다운 보고서를
낸다. 토큰화나 임계값을 바꿨을 때 "나아졌나" 를 답하는 것이 목적이고, 그 답은 절대 수치가
아니라 전후 차이다 ([04 §9]).

## 왜 스냅샷과 따로 있나

스냅샷(`update-snapshots.py`)은 **재현성**을 지킨다 — 결과가 바뀌면 빨개진다. 이쪽은
**품질**을 본다 — 결과가 바뀌는 것이 전제이고, 바뀐 방향을 묻는다. 그래서 CI 에 넣지 않고
사람이 부른다.

## 표기 정책 진단은 없앴다 (2026-09-09)

`core`/`prefixed`/`word` 셋 중 하나를 고르려고 복수형·파생형 갈림과 접두사 온전 여부를
재는 절이 있었다. **그 결정은 끝났고 수치는 문서에 박혔다** ([04 §2] · 그날 검수 문서
§6). 한 번 쓰고 끝난 진단을 도구에 남겨 두면 다음 사람이 그 절을 다시 읽고 판단을 다시
할지 고민한다. 되돌릴 일이 생기면 그 문서의 수치가 출발점이다.

## 무엇을 재나

| # | 산출물 | 왜 |
| --- | --- | --- |
| 1 | 요약 수치 | 후보 행 수 · 비교키 수 · 문서당 후보 · 선별 수. 급변은 필터 오작동 신호 |
| 2 | 상위 100 후보 분류 | [04 §9] "상위 100 을 눈으로 훑는다" 의 자동화 가능한 절반 |
| 3 | **문서당 top-10 매핑** | 코퍼스 순위만 보면 안 보이는 결함이 있다 (아래) |
| 4 | 사라진 것 · 새로 생긴 것 | 개선인지 그냥 다른지를 가른다 |

**3번이 없으면 안 된다.** 코퍼스 집계 상위 100 은 DF 가 큰 것만 올라오므로 `스커트보` ·
`19만9천원` 처럼 **문서 하나에서만 상위인 결함**이 통계에 묻힌다. 2026-09-09 검수 시트에서
`퍼의` · `체크의` · `조합이에요` · `10만9천원` 이 전부 그런 경우였다.

## 분류는 기계가 절반만 한다

조사 잔재 · 서술어 활용형 · 숫자·가격 · 토큰화 오류는 **형태소 분석기 자신에게 후보 표기를
다시 물어** 판정한다 — 후보 문자열만 보고 되는 일이라 전후 두 실행에 **같은 잣대**가 적용되고,
그게 비교의 전제다. 사람 눈이 필요한 것(패션 신호 / 스타일 수식어 / 무정보어)은 가르지 않고
`명사 — 사람이 가른다` 로 모아 채워 넣을 표를 낸다. 어느 쪽인지 적는 것이 검수다.

**⚠️ 손으로 센 옛 수치와 이 스크립트의 수치는 다를 수 있다.** 그럴 때 옳은 것은 **양쪽을 이
스크립트로 다시 센 값**이다 — 잣대가 같아야 차이가 뜻을 갖는다.

## ⚠️ `pl_document_candidate` 에는 실행 하나만 남는다

`CandidateSink.write` 가 처리한 문서의 옛 행을 지우고 새로 넣는다 (`io/candidates.py`).
같은 373건을 두 번 돌리면 **먼저 것이 없어진다** — `extract_run_id` 로 두 실행이 공존하지
않는다. 그래서 전후 비교는 **실행마다 바로 떠 두고** 그 파일들을 비교해야 한다:

    # 돌린 직후에 뜬다
    python spark/scripts/evaluate-extract.py --dump runs/rules.jsonl.gz
    # ... 코드를 바꾸고 다시 돌린 뒤
    python spark/scripts/evaluate-extract.py --dump runs/morphology.jsonl.gz
    # 두 파일을 비교한다
    python spark/scripts/evaluate-extract.py --before rules.gz --after morphology.gz

`--before`/`--after` 는 **파일 경로이거나 `extract_run_id`** 다. 경로가 있으면 파일에서
읽고, 없으면 DB 에서 그 run_id 를 찾는다. 뜬 파일은 저장소에 넣지 않는다 — 검수 결과인
마크다운만 남긴다.

pyspark 를 import 하지 않는다 ([09 §4] 층 1).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SPARK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPARK_DIR.parent / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.extract import morphology as mp  # noqa: E402
from trendin.spark.extract.lexicon import load_lexicon  # noqa: E402
from trendin.spark.extract.thresholds import lexicon_dir  # noqa: E402
from trendin.spark.extract.tokenize import TokenizeOptions, tokenize  # noqa: E402
from trendin.spark.normalize.documents import build_document  # noqa: E402

CORPUS = SPARK_DIR / "tests" / "fixtures" / "corpus.json"

# 상위 몇 개를 분류하나. [04 §9] 가 정한 수다 — 한 사람이 30초에 훑는 규모.
TOP_N = 100
# 문서당 몇 개를 시트에 적나. `per_document_top_k` 와 같은 값이어야 검수의 뜻이 맞는다.
PER_DOC = 10

# --- 분류 --------------------------------------------------------------------

JOSA = "조사 잔재"
CONJUGATED = "서술어 활용형"
NUMERIC = "숫자·가격"
WEB = "웹 요소"
CUT = "토큰화 오류"
NOUN = "명사 — 사람이 가른다"

# 사람이 채우는 칸. 위 기계 판정에 걸리지 않은 것을 여기 셋 중 하나로 적는다.
MANUAL = ("패션 신호", "스타일 수식어", "무정보어")

ORDER = (JOSA, CONJUGATED, NUMERIC, WEB, CUT, NOUN)

# 웹·플랫폼 잔재. [03 §4] 단계 8 이 지우기로 한 것들의 낱말 형태다 — 정제가 새면 여기 뜬다.
# 짧게 유지한다. 이 목록이 길어지면 정제 쪽을 고칠 일이다 (`normalize/boilerplate.py`).
WEB_TERMS = frozenset(
    {
        "관련기사",
        "인스타그램",
        "유튜브",
        "페이스북",
        "트위터",
        "카카오톡",
        "홈페이지",
        "사이트",
        "이미지",
        "클릭",
        "링크",
        "팔로우",
        "구독",
        "댓글",
        "무단전재",
        "재배포",
    }
)

# 가격·수량 표기. **전체가 숫자+단위여야 한다.** 처음에는 "숫자로 시작하면" 으로 뒀는데
# `18K 로즈 골드` · `29CM` · `17세기` 처럼 **옳은 낱말**을 결함으로 셌다. 결함율을 부풀리는
# 잣대는 전후 비교를 무의미하게 만든다.
_NUMERIC_SURFACE = re.compile(
    r"^[\d,.]+$|^[\d,.]+(만|천|억)?[\d,.]*(만|천|억)?\s*(원|달러|유로|엔|%)$"
)

_HANGUL = re.compile(r"[가-힣]")

# 후보 표기를 끼워 넣는 자리. 관형사 하나 — `Classifier._tags` 를 본다.
_FRAME = "그 "



@dataclass(frozen=True, slots=True)
class Candidate:
    """`pl_document_candidate` 한 행에서 쓰는 칸만."""

    # 16진 문자열. DB 는 bytea 지만 `_rows` 가 접는다.
    url_hash: str
    key: str
    surface: str
    kind: str
    ntokens: int
    tf: int
    df: int
    score: float
    rank: int
    selected: bool


class Classifier:
    """후보 표기 하나 → 부류. **형태소 분석기에게 표기를 다시 물어본다.**

    후보가 어떻게 만들어졌는지는 보지 않는다 — 문자열만 본다. 그래야 규칙 기반 실행과
    형태소 기반 실행에 같은 잣대가 적용된다.
    """

    def __init__(self, surfaces_by_df: dict[str, int]) -> None:
        self._analyzer = mp.analyzer_for(mp.AnalyzerSpec())
        # 토큰화 오류 판정에 쓴다 — `스커트보` 는 `스커트` 의 접두인데 DF 가 훨씬 낮다.
        self._df = surfaces_by_df

    def classify(self, surface: str) -> str:
        if surface in WEB_TERMS:
            return WEB
        if _NUMERIC_SURFACE.match(surface):
            return NUMERIC
        if self._is_cut(surface):
            return CUT
        tags = self._tags(surface)
        if not tags:
            return NOUN
        if tags[-1].startswith("J"):
            return JOSA
        if any(tag.startswith(("VV", "VA", "VX", "VC", "E", "XSV", "XSA")) for tag in tags):
            return CONJUGATED
        return NOUN

    def _tags(self, surface: str) -> list[str]:
        """후보 표기의 품사 열. **명사가 올 자리에 끼워 넣고 분석한다.**

        낱말 하나를 문맥 없이 분석하면 분석기가 엉뚱한 길을 고른다 — `치마` 를 `하`(VV)
        `지`(EC) `말`(VX) `어`(EF) 로 읽는다. 이 잣대의 첫 판에서 `치마` 가 아홉 번 활용형으로
        걸렸고, `알로`(브랜드)와 `찢청` 도 같은 이유로 걸렸다. **잣대가 결함을 부풀리면
        개선이 실제보다 커 보인다.**

        그래서 `그 ` 를 앞에 붙여 **명사구가 기대되는 자리**로 만든다. `그` 는 관형사(MM)라
        뒤에 오는 것의 분석을 명사 쪽으로 이끌지만, 조사·어미가 실제로 붙어 있으면 그대로
        갈린다 — `그 퍼의` 는 `퍼`+`의` 이고 `그 부드러운` 은 `부드럽`+`은` 이다. 프레임의
        형태소는 시작 위치로 걸러 낸다.
        """
        morphs = self._analyzer.analyze([_FRAME + surface])[0]
        return [morph.tag for morph in morphs if morph.start >= len(_FRAME)]

    def _is_cut(self, surface: str) -> bool:
        """**잘린 낱말인가** — 다른 후보 표기의 접두이면서 그쪽 DF 가 압도적인가.

        `스커트보`(DF 2) 대 `스커트`(DF 60) · `발렌시아`(DF 4) 대 `발렌시아가`(DF 30).
        접두 관계와 DF 격차 둘을 함께 보는 이유는 접두 관계만으로는 `데님`/`데님룩` 처럼
        **둘 다 옳은** 쌍을 잘못 잡기 때문이다 — 그 경우 DF 가 압도하지 않는다.
        """
        if len(surface) < 2 or not _HANGUL.search(surface):
            return False
        mine = self._df.get(surface, 0)
        for extra in (1, 2):
            longer = None
            for other, other_df in self._df.items():
                if len(other) == len(surface) + extra and other.startswith(surface):
                    if longer is None or other_df > longer:
                        longer = other_df
            if longer is not None and longer >= max(5, mine * 5):
                return True
        return False

    # **반대 방향은 보지 않는다.** 처음에는 "내가 더 긴 쪽인데 짧은 쪽 DF 가 압도하면 잘린
    # 것" 도 봤는데, `여성복`(`여성`) · `바람막이`(`바람`) · `스니커`(`스니커즈`) 처럼 **둘 다
    # 옳은 낱말**을 74가지나 결함으로 셌다. 그 방향이 노렸던 `퍼의` · `체크의` 는 조사 판정이
    # 이미 잡으므로 없어도 된다.



# --- DB ----------------------------------------------------------------------


def connect():
    """`APP_DB_*` 환경변수 또는 로컬 컴포즈 기본값. 호스트에서 돈다 — 컨테이너의 5432 가
    `127.0.0.1:55432` 로 나와 있다 (`datastore/compose.yaml`)."""
    import psycopg2

    return psycopg2.connect(
        host=os.environ.get("APP_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_DB_PORT", "55432")),
        dbname=os.environ.get("APP_DB_NAME", "trendin"),
        user=os.environ.get("APP_DB_USER", "trendin"),
        password=os.environ.get("APP_DB_PASSWORD") or _password_from_env_file(),
    )


def _password_from_env_file() -> str:
    """`pipeline/.env` 의 `APP_DB_PASSWORD`. 비밀을 인자로 받지 않으려는 것이다 — 셸 히스토리에
    남는다."""
    path = SPARK_DIR.parent / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("APP_DB_PASSWORD="):
                return line.split("=", 1)[1].strip()
    return ""


_SELECT = """
    select url_hash, normalized_key, surface, kind, ntokens, tf, df, score, rank, selected
      from pl_document_candidate
     where domain = %s
"""


def _rows(cursor) -> list[Candidate]:
    # `url_hash` 는 bytea 라 psycopg2 가 memoryview 로 준다. 16진 문자열로 접는다 —
    # `Document.url_hash` 는 bytes 이고(`normalize/documents.py`), 둘을 견주려면 같은
    # 표현이어야 한다. JSON 으로 뜨는 데도 문자열이 필요하다.
    return [
        Candidate(bytes(row[0]).hex(), *row[1:7], float(row[7]), int(row[8]), bool(row[9]))
        for row in cursor.fetchall()
    ]


def fetch(connection, run_id: str, *, domain: str) -> list[Candidate]:
    with connection.cursor() as cursor:
        cursor.execute(_SELECT + " and extract_run_id = %s", (domain, run_id))
        rows = _rows(cursor)
    if not rows:
        raise SystemExit(
            f"{run_id} 의 행이 없다. `pl_document_candidate` 는 실행 하나만 담는다 — "
            "머리말의 `--dump` 절을 본다"
        )
    return rows


def _as_list(row: Candidate) -> list:
    return [getattr(row, name) for name in Candidate.__dataclass_fields__]


def dump(path: Path, *, domain: str) -> int:
    """지금 DB 에 있는 행을 파일로 뜬다. **실행 직후에 부른다** — 다음 실행이 지운다."""
    import gzip

    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(_SELECT, (domain,))
            rows = _rows(cursor)
            cursor.execute(
                "select distinct extract_run_id from pl_document_candidate where domain = %s",
                (domain,),
            )
            run_ids = [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()
    if not rows:
        raise SystemExit(f"{domain} 도메인 행이 없다 — extract 를 먼저 돌린다")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        print(json.dumps({"run_ids": run_ids, "domain": domain}), file=handle)
        for row in rows:
            print(json.dumps(_as_list(row), ensure_ascii=False), file=handle)
    return len(rows)


def load(path: Path) -> tuple[str, list[Candidate]]:
    import gzip

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        head = json.loads(handle.readline())
        rows = [Candidate(*json.loads(line)) for line in handle if line.strip()]
    return ", ".join(head["run_ids"]), rows


def resolve(value: str, *, domain: str) -> tuple[str, list[Candidate]]:
    """`--before`/`--after` 한 개 → `(run_id 표시, 행)`. 파일이 있으면 파일, 없으면 DB."""
    path = Path(value)
    if path.exists():
        return load(path)
    connection = connect()
    try:
        return value, fetch(connection, value, domain=domain)
    finally:
        connection.close()


# --- 집계 --------------------------------------------------------------------


@dataclass
class Run:
    """실행 하나의 측정값."""

    run_id: str
    label: str
    rows: list[Candidate]

    @property
    def documents(self) -> int:
        return len({row.url_hash for row in self.rows})

    @property
    def keys(self) -> int:
        return len({row.key for row in self.rows})

    @property
    def selected(self) -> int:
        return sum(1 for row in self.rows if row.selected)

    def surface_df(self) -> dict[str, int]:
        """표기 → DF. 같은 표기의 여러 비교키가 있으면 큰 쪽을 쓴다."""
        result: dict[str, int] = {}
        for row in self.rows:
            if row.df > result.get(row.surface, 0):
                result[row.surface] = row.df
        return result

    def top_keys(self, limit: int) -> list[tuple[str, str, int, int]]:
        """코퍼스 상위 후보 — `(비교키, 표기, DF, 총 빈도)`. **DF 순**이다.

        점수 순이 아닌 이유 — 점수는 문서 안에서 정규화된 값이라 코퍼스 순위가 아니고,
        [04 §9] 가 "상위 100" 이라 부르는 것은 많은 문서에 나온 것이다.
        """
        df: dict[str, int] = {}
        freq: Counter[str] = Counter()
        surface: dict[str, str] = {}
        for row in self.rows:
            df[row.key] = max(df.get(row.key, 0), row.df)
            freq[row.key] += row.tf
            surface[row.key] = row.surface
        ranked = sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        return [(key, surface[key], value, freq[key]) for key, value in ranked]

    def selected_rows(self) -> list[Candidate]:
        """선별된 행 — **실제로 `keyword_contents` 로 나갈 것** ([04 §7]). 문서당 상위 K 이고
        점수 하한 이상인 것이라, 이 묶음의 결함율이 곧 precision@K 의 기계 판정분이다."""
        return [row for row in self.rows if row.selected]

    def per_document(self, url_hash: str, limit: int) -> list[Candidate]:
        rows = [row for row in self.rows if row.url_hash == url_hash]
        return sorted(rows, key=lambda row: row.rank)[:limit]


def classify_selected(run: Run, classifier: Classifier) -> Counter:
    """선별된 행을 부류별로 센다. 문서당 매핑 품질의 수치다."""
    counts: Counter[str] = Counter()
    for row in run.selected_rows():
        counts[classifier.classify(row.surface)] += 1
    return counts


def classify_top(run: Run, classifier: Classifier, limit: int) -> tuple[Counter, list[tuple]]:
    counts: Counter[str] = Counter()
    detail: list[tuple] = []
    for key, surface, df, freq in run.top_keys(limit):
        bucket = classifier.classify(surface)
        counts[bucket] += 1
        detail.append((key, surface, df, freq, bucket))
    return counts, detail


# --- 불용어 발동 -------------------------------------------------------------


def stopword_hits(policy: str) -> list[tuple[str, int]]:
    """코퍼스 30건에서 **실제로 발동한 불용어 항목**과 횟수.

    `stopwords-ko.txt` 의 절반이 형태소 분석기 도입으로 닿지 않게 됐는데, 어느 항목이
    그런지는 재 봐야 안다. 발동이 0 인 항목을 지우는 것이 사전을 줄이는 유일한 안전한
    방법이다 — 눈으로 고르면 `백`(가방)처럼 살아 있는 항목을 지운다.
    """
    config = load_config("local")
    directory = SPARK_DIR.parent / lexicon_dir(config)
    lex = load_lexicon(directory, domain="fashion")
    options = TokenizeOptions(
        code_identifiers=False,
        surface_policy=policy,
        analyzer=mp.AnalyzerSpec(user_words=mp.load_user_words(directory, domain="fashion")),
    )
    hits: Counter[str] = Counter()
    for article in _corpus().values():
        document = build_document(article, {}, ingest_run_id="evaluate")
        for part in (document.title, document.body):
            for token in tokenize(part, document.lang, lexicon=lex, options=options):
                if token.is_stop:
                    hits[token.surface] += 1
    unused = sorted(lex.stopwords - {surface.lower() for surface in hits})
    return sorted(hits.items(), key=lambda kv: -kv[1]), unused


# --- 코퍼스 문서 매핑 --------------------------------------------------------


def _corpus() -> dict[str, dict[str, Any]]:
    """`{이름: article.json}`. 없으면 빈 사전 — 문서별 나란히 보기만 빠진다."""
    if not CORPUS.exists():
        return {}
    return dict(sorted(json.loads(CORPUS.read_text(encoding="utf-8")).items()))


def corpus_documents() -> list[tuple[str, str, str]]:
    """`(url_hash, 이름, 제목)`. 검수 시트가 이름으로 문서를 부르므로 필요하다."""
    result = []
    for name, article in _corpus().items():
        document = build_document(article, {}, ingest_run_id="evaluate")
        result.append((document.url_hash.hex(), name, document.title or "(제목 없음)"))
    return result


# --- 보고서 ------------------------------------------------------------------


def table(header: Iterable[str], rows: Iterable[Iterable[Any]], align: str = "") -> list[str]:
    header = list(header)
    marks = [
        "---:" if align[i : i + 1] == "r" else ":---:" if align[i : i + 1] == "c" else "---"
        for i in range(len(header))
    ]
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(marks) + " |"]
    for row in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return out


def report(before: Run, after: Run, *, policy: str) -> str:
    classifier = Classifier({**before.surface_df(), **after.surface_df()})
    before_counts, _ = classify_top(before, classifier, TOP_N)
    after_counts, after_detail = classify_top(after, classifier, TOP_N)
    _, before_detail = classify_top(before, classifier, TOP_N)

    lines: list[str] = []
    add = lines.append

    add(f"# 추출 품질 전후 비교 — 규칙 기반 → 형태소 분석기 ({policy})")
    add("")
    add(f"- **전** `{before.run_id}` — {before.label}")
    add(f"- **후** `{after.run_id}` — {after.label}")
    add(
        f"- 잣대는 양쪽 같다 (`spark/scripts/evaluate-extract.py`). "
        f"상위 {TOP_N} · 문서당 {PER_DOC}."
    )
    add("")

    add("## 1. 요약 수치")
    add("")
    add(
        "\n".join(
            table(
                ["지표", "전", "후", "차이"],
                [
                    _row("문서 × 후보 행", len(before.rows), len(after.rows)),
                    _row("서로 다른 비교키", before.keys, after.keys),
                    _row("후보가 있는 문서", before.documents, after.documents),
                    _row(
                        "문서당 후보(평균)",
                        round(len(before.rows) / max(before.documents, 1), 1),
                        round(len(after.rows) / max(after.documents, 1), 1),
                    ),
                    _row("선별된 행 (selected)", before.selected, after.selected),
                ],
                align="lrrr",
            )
        )
    )
    add("")

    add(f"## 2. 상위 {TOP_N} 후보 분류")
    add("")
    add("기계가 가르는 넷(조사 잔재 · 서술어 활용형 · 숫자·가격 · 토큰화 오류)과 웹 요소까지가")
    add("자동이고, 나머지는 `명사 — 사람이 가른다` 에 모인다. §5 가 그 표다.")
    add("")
    add(
        "\n".join(
            table(
                ["부류", "전", "후", "차이"],
                [
                    _row(bucket, before_counts.get(bucket, 0), after_counts.get(bucket, 0))
                    for bucket in ORDER
                ],
                align="lrrr",
            )
        )
    )
    add("")
    for bucket in ORDER:
        if bucket == NOUN:
            continue
        gone = [item for item in before_detail if item[4] == bucket]
        left = [item for item in after_detail if item[4] == bucket]
        if not gone and not left:
            continue
        add(f"**{bucket}** — 전 {len(gone)}개: " + ", ".join(f"`{i[1]}`" for i in gone[:12]))
        add("")
        tail = ": " + ", ".join(f"`{i[1]}`" for i in left[:12]) if left else " (없다)"
        add(f"→ 후 {len(left)}개" + tail)
        add("")

    add("## 3. 문서당 매핑 품질 — 선별된 행의 결함율")
    add("")
    add("**이 절이 §2 보다 무겁다.** 코퍼스 집계 상위 100 은 DF 가 큰 것만 올라오므로 문서")
    add("하나에서만 상위인 결함(`퍼의` · `10만9천원` · `스커트보`)이 통계에 묻힌다. 여기는")
    add(f"**문서당 상위 {PER_DOC} 로 선별된 행 전부**(코퍼스 373건)를 같은 잣대로 센 것이다.")
    add("")
    before_sel = classify_selected(before, classifier)
    after_sel = classify_selected(after, classifier)
    before_total = max(sum(before_sel.values()), 1)
    after_total = max(sum(after_sel.values()), 1)
    before_bad = before_total - before_sel.get(NOUN, 0)
    after_bad = after_total - after_sel.get(NOUN, 0)
    rows = [
        _row("선별된 행", before_total, after_total),
        _row("**기계 판정 결함**", before_bad, after_bad),
    ]
    rows.append(
        (
            "**결함율**",
            f"{before_bad / before_total:.1%}",
            f"{after_bad / after_total:.1%}",
            f"{(after_bad / after_total - before_bad / before_total) * 100:+.1f}%p",
        )
    )
    rows += [
        _row(bucket, before_sel.get(bucket, 0), after_sel.get(bucket, 0))
        for bucket in ORDER
        if bucket != NOUN
    ]
    lines.extend(table(["지표", "전", "후", "차이"], rows, align="lrrr"))
    add("")
    add("### 문서별 나란히 보기 — 코퍼스 30건")
    add("")
    for url_hash, name, title in corpus_documents():
        before_rows = before.per_document(url_hash, PER_DOC)
        after_rows = after.per_document(url_hash, PER_DOC)
        if not before_rows and not after_rows:
            continue
        add(f"### {title}")
        add("")
        add(f"`{name}`")
        add("")
        add(
            "\n".join(
                table(
                    ["#", "전 · 표기", "종류", "DF", "점수", "후 · 표기", "종류", "DF", "점수"],
                    [
                        _pair_row(index, before_rows, after_rows)
                        for index in range(max(len(before_rows), len(after_rows)))
                    ],
                    align="rlrrrlrrr",
                )
            )
        )
        add("")

    add("## 4. 사라진 것 · 새로 생긴 것")
    add("")
    before_keys = {key for key, *_ in before.top_keys(500)}
    after_keys = {key for key, *_ in after.top_keys(500)}
    gone = [item for item in before.top_keys(500) if item[0] not in after_keys][:40]
    born = [item for item in after.top_keys(500) if item[0] not in before_keys][:40]
    add("**사라진 상위 후보** (전 상위 500 에 있고 후 상위 500 에 없다)")
    add("")
    add(
        "\n".join(
            table(
                ["표기", "DF", "부류"],
                [(f"`{s}`", df, classifier.classify(s)) for _, s, df, _ in gone],
                align="lrl",
            )
        )
    )
    add("")
    add("**새로 생긴 상위 후보**")
    add("")
    add(
        "\n".join(
            table(
                ["표기", "DF", "부류"],
                [(f"`{s}`", df, classifier.classify(s)) for _, s, df, _ in born],
                align="lrl",
            )
        )
    )
    add("")

    add(f"## 5. 사람이 가르는 표 — 후 상위 {TOP_N} 중 명사")
    add("")
    add("`" + "` / `".join(MANUAL) + "` 중 하나를 적는다. 빈 칸은 아직 안 매긴 것이다.")
    add("")
    add(
        "\n".join(
            table(
                ["#", "표기", "DF", "빈도", "부류"],
                [
                    (index + 1, f"`{surface}`", df, freq, "")
                    for index, (_, surface, df, freq, bucket) in enumerate(after_detail)
                    if bucket == NOUN
                ],
                align="rlrrc",
            )
        )
    )
    add("")

    hits, unused = stopword_hits(policy)
    add("## 6. 불용어 발동 — 코퍼스 30건")
    add("")
    add("발동이 0 인 항목은 형태소 분석기가 그 품사를 아예 후보로 만들지 않는다는 뜻이다.")
    add("**지우기 전에 이 표를 본다** — `백`(가방)처럼 살아 있는 항목을 눈으로 고르면 지운다.")
    add("")
    add("**발동한 것** " + (", ".join(f"`{s}`×{n}" for s, n in hits[:60]) or "(없다)"))
    add("")
    add(
        f"**한 번도 발동하지 않은 것** {len(unused)}개 — "
        + ", ".join(f"`{s}`" for s in unused[:120])
    )
    add("")
    return "\n".join(lines) + "\n"


def _row(label: str, before: Any, after: Any) -> tuple:
    try:
        delta = after - before
        sign = f"{delta:+,}" if isinstance(delta, int) else f"{delta:+.1f}"
    except TypeError:
        sign = ""
    fmt = "{:,}".format if isinstance(before, int) else str
    return (label, fmt(before), fmt(after), sign)


def _pair_row(index: int, before_rows: list[Candidate], after_rows: list[Candidate]) -> tuple:
    left = before_rows[index] if index < len(before_rows) else None
    right = after_rows[index] if index < len(after_rows) else None
    return (
        index + 1,
        f"`{left.surface}`" if left else "",
        left.kind if left else "",
        left.df if left else "",
        f"{left.score:.3f}" if left else "",
        f"`{right.surface}`" if right else "",
        right.kind if right else "",
        right.df if right else "",
        f"{right.score:.3f}" if right else "",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="추출 품질 전후 비교")
    parser.add_argument("--dump", type=Path, help="지금 DB 의 행을 이 파일로 뜨고 끝낸다")
    parser.add_argument("--before", help="비교 기준 — 뜬 파일 경로 또는 extract_run_id")
    parser.add_argument("--after", help="새 실행 — 뜬 파일 경로 또는 extract_run_id")
    parser.add_argument("--before-label", default="규칙 기반 토큰화 (조사·어미 접미 표)")
    parser.add_argument("--after-label", default="형태소 분석기 (kiwipiepy)")
    parser.add_argument("--domain", default="fashion")
    parser.add_argument("--policy", default=mp.SURFACE_PREFIXED, choices=mp.SURFACE_POLICIES)
    parser.add_argument("--out", type=Path, help="쓸 파일. 없으면 표준출력")
    args = parser.parse_args()

    if args.dump:
        print(f"{dump(args.dump, domain=args.domain):,}행 떴다: {args.dump}")
        return 0
    if not (args.before and args.after):
        parser.error("--before 와 --after 가 함께 필요하다 (또는 --dump)")

    before_id, before_rows = resolve(args.before, domain=args.domain)
    after_id, after_rows = resolve(args.after, domain=args.domain)
    before = Run(before_id, args.before_label, before_rows)
    after = Run(after_id, args.after_label, after_rows)

    text = report(before, after, policy=args.policy)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"썼다: {args.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
