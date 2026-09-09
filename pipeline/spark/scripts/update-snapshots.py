#!/usr/bin/env python
"""회귀 스냅샷 갱신 ([04 §9](../docs/04-keyword-extraction-spec.md) · [09 §4]).

    pipeline/.venv/bin/python spark/scripts/update-snapshots.py

`tests/fixtures/corpus/` 30건에 **정제와 문서 안 추출을 실제 코드로** 돌려
`tests/fixtures/snapshots/` 에 결과를 쓴다. `tests/unit/test_extract_snapshots.py` 가 같은
계산을 다시 해서 파일과 대조하므로, 코드를 고쳐 결과가 바뀌면 그 테스트가 먼저 빨개진다.

**의도한 변경이면 이 스크립트를 돌려 갱신하고 diff 를 커밋에 남긴다.** 목적은 변경을 막는
것이 아니라 **의도하지 않은 변경을 드러내는 것**이다 ([09 §4]).

**코퍼스 통계가 필요한 것은 스냅샷에 없다.** DF · 대표 표기 · C-value · BM25 · 점수 ·
순위는 코퍼스 전체를 봐야 나오고(`extract/batch.py`), 그 값들은 S6 가 임계값을 확정하면
바뀐다. 지금 고정하면 임계값을 만질 때마다 30건이 통째로 흔들려 스냅샷이 경보가 아니라
잡음이 된다. 그래서 **문서 하나 안에서 결정되는 것까지만** 고정한다 — 토큰화 · 구간 ·
n-gram · 비교키 · 문서 안 필터, 그리고 그 앞의 정제. 방금 고친 결함 셋이 전부 그 범위다.

pyspark 를 import 하지 않는다 ([09 §4] 층 1).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SPARK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPARK_DIR.parent / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.extract import morphology  # noqa: E402
from trendin.spark.extract.document import ExtractionOptions, extract_document  # noqa: E402
from trendin.spark.extract.filters import CandidateLimits  # noqa: E402
from trendin.spark.extract.lexicon import load_lexicon  # noqa: E402
from trendin.spark.extract.thresholds import lexicon_dir  # noqa: E402
from trendin.spark.extract.tokenize import TokenizeOptions  # noqa: E402
from trendin.spark.normalize.documents import build_document  # noqa: E402

# **파일 하나에 30건을 담는다.** 문서마다 파일을 두면 픽스처만 60개가 되어 변경 목록이
# 그것으로 덮이고, 정작 읽어야 할 구현·테스트가 묻힌다. 한 파일 안의 diff 는 git 이
# 지역적으로 보여 주므로 눈으로 보는 데 지장이 없다 — 키를 이름으로 정렬해 둔 이유다.
CORPUS = SPARK_DIR / "tests" / "fixtures" / "corpus.json"
SNAPSHOTS = SPARK_DIR / "tests" / "fixtures" / "snapshots.json"

# 스냅샷에 적는 후보 수. 전부 적으면 문서당 200줄이 되어 눈으로 diff 를 볼 수 없다.
# 꼬리의 변화는 `digest` 가 잡는다.
TOP_N = 15

RUN_ID = "snapshot"


def options_for(config, domain: str) -> ExtractionOptions:
    """문서 하나에 필요한 설정만. **`base.yaml` 의 값만 쓴다** — `local.yaml` 의 잠정
    임계값(DF 비율 · 가중치 · top_k)은 문서 안 계산에 들어가지 않으므로, 그 값이 바뀌어도
    스냅샷은 흔들리지 않는다."""
    section = f"extract.domains.{domain}"
    directory = SPARK_DIR.parent / lexicon_dir(config)
    return ExtractionOptions(
        lexicon=load_lexicon(directory, domain=domain),
        ngram_max=int(config.get("extract.ngram_max", 3)),
        limits=CandidateLimits(
            min_chars=int(config.get("extract.candidate.min_chars", 2)),
            max_chars=int(config.get("extract.candidate.max_chars", 40)),
        ),
        tokenize=TokenizeOptions(
            code_identifiers=bool(config.get(f"{section}.code_identifiers", True)),
            surface_policy=str(
                config.get(f"{section}.surface_policy", morphology.SURFACE_PREFIXED)
            ),
            analyzer=morphology.AnalyzerSpec(
                user_words=morphology.load_user_words(directory, domain=domain)
            ),
        ),
    )


def _row(item) -> str:
    """후보 하나 → 한 줄. **칸마다 줄을 쓰지 않는 이유** — 후보 15개 × 문서 30건을 7줄짜리
    JSON 객체로 적으면 그것만 2,750줄이고 스냅샷 파일의 68%가 된다. 담은 정보는 같고
    diff 는 오히려 읽기 쉽다 — 후보 하나가 바뀌면 한 줄이 바뀐다.

    사람이 읽는 값이고 무엇도 파싱하지 않는다. 표기가 비교키와 다를 때가 눈에 걸려야
    해서 둘을 늘 함께 적는다 (`코트 | 코트` vs `mcp | MCP`).
    """
    return (
        f"{item.key} | {item.surface} | {item.kind} | "
        f"n{item.ntokens} tf{item.tf} t{item.tf_title}"
    )


def snapshot_for(article: dict[str, Any], config) -> dict[str, Any]:
    """`article.json` 하나 → 스냅샷 하나. 실제 정제·추출 경로를 그대로 태운다."""
    document = build_document(article, {}, ingest_run_id=RUN_ID)
    domain = str(article.get("domain") or "fashion")
    extraction = extract_document(
        document.title, document.body, document.lang, options=options_for(config, domain)
    )

    keys = sorted(item.key for item in extraction.candidates)
    digest = hashlib.sha256("\n".join(keys).encode()).hexdigest()[:16]
    ordered = sorted(extraction.candidates, key=lambda c: (-c.tf, c.key))

    return {
        # 출처 표시 — 발췌본을 저장소에 두는 근거다 (저작권법 제37조, [09 §4]).
        "source": {
            "domain": document.domain,
            "source_id": document.source_id,
            "route": document.route,
            "article_id": article.get("article_id"),
            "url": document.url,
            "published_date": str(document.published_date),
        },
        "normalize": {
            "lang": document.lang,
            "basis": document.basis,
            "title": document.title,
            "body_chars": len(document.body or ""),
            "body_lines": len((document.body or "").split("\n")) if document.body else 0,
            "summary_chars": len(document.summary or ""),
            "body_head": (document.body or "")[:120],
        },
        "extract": {
            "doc_len": extraction.doc_len,
            "candidates": len(extraction.candidates),
            "dropped": dict(sorted(extraction.dropped.items())),
            "keys_digest": digest,
            "top": [_row(item) for item in ordered[:TOP_N]],
            "abbreviations": [
                {
                    "abbreviation": pair.abbreviation,
                    "expansion": pair.expansion,
                    "initials_match": pair.initials_match,
                }
                for pair in extraction.abbreviations
            ],
        },
    }


def load_corpus() -> dict[str, dict[str, Any]]:
    """`{이름: article.json}`. 없으면 빈 사전 — 코퍼스를 두지 않은 체크아웃도 있다."""
    if not CORPUS.exists():
        return {}
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def build_all() -> dict[str, dict[str, Any]]:
    """`{이름: 스냅샷}`. 테스트가 이 함수를 불러 파일과 대조한다."""
    config = load_config("local")
    corpus = sorted(load_corpus().items())
    return {name: snapshot_for(article, config) for name, article in corpus}


def render(snapshots: dict[str, Any]) -> str:
    return json.dumps(snapshots, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    snapshots = build_all()
    if not snapshots:
        print(f"코퍼스가 없거나 비어 있다: {CORPUS}", file=sys.stderr)
        return 1

    before = json.loads(SNAPSHOTS.read_text(encoding="utf-8")) if SNAPSHOTS.exists() else {}
    changed = [name for name in snapshots if before.get(name) != snapshots[name]]
    gone = [name for name in before if name not in snapshots]

    SNAPSHOTS.write_text(render(snapshots), encoding="utf-8")
    for name in changed:
        print(f"  {'갱신' if name in before else '생성'} {name}")
    for name in gone:
        print(f"  삭제 {name}")
    print(f"{len(snapshots)}건 중 {len(changed)}건 바뀌었다 → {SNAPSHOTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
