#!/usr/bin/env python
"""위키데이터에서 패션 브랜드·디자이너의 다국어 이름을 받아 개념 초기 사전 파일을 만든다.

```sh
.venv/Scripts/python scripts/seed-concepts-wikidata.py            # spark/conf/concepts/ 에 쓴다
.venv/Scripts/python scripts/seed-concepts-wikidata.py --min-langs 4
```

같은 항목에 붙은 언어별 라벨은 **사람이 확인해 같다고 적어 둔 것**이라 그대로 사전에 넣을 수
있다. 저작권을 포기한(CC0) 데이터라 출처 표시 의무도 없다.

## 두 파일로 나눈다

| 파일 | 조건 | 분류 |
| --- | --- | --- |
| `wikidata-brands.json` | 패션 하우스(P31/P279* Q1941779) 또는 산업이 패션(P452 Q12684) | brand |
| `wikidata-designers.json` | 직업이 패션 디자이너(P106 Q3501317) | designer |

한 항목이 둘 다면 브랜드다 — 기사에서 세는 대상이 회사 쪽이다.

## ⚠️ 잡음이 섞인다

2026-09-16 실측: 항목 7,192 중 언어 셋 이상이 2,902 — 영어 쌍으로 ko 641 · ja 861 · ar 759 ·
fr 2,855 · it 2,605.
같은 이름의 사람과 회사가 따로 있고(Tory Burch), 라벨이 틀린 항목도 있다(켈리 오스본의 영어
라벨이 다른 사람 이름). `--min-langs` 를 올리면 줄지만 없어지지 않는다. **결과 파일은 사람이
한 번 훑고 커밋한다.** 이 스크립트는 저장소 밖 실험 폴더의 `fetch_wikidata.py` 를 옮겨 온 것이다.

한 달에 한 번쯤 다시 돌린다. 초기 사전 적재(`concept/seed.py`)는 있는 것을 덮지 않으므로 안전하다.
"""

from __future__ import annotations

import argparse
import collections
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "trendin-concept-seed/0.1 (S15P21A102)"
LANGS = ("en", "ko", "ja", "ar", "fr", "it")
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "spark" / "conf" / "concepts"

# `?kind` 로 어느 갈래에서 왔는지 같이 받는다. 갈래가 분류가 된다.
#
# 별칭(skos:altLabel)은 여기서 받지 않는다. OPTIONAL 로 붙였더니 행이 라벨 × 별칭으로 불어
# SPARQL 끝점이 504 를 냈다 (2026-09-17). 라벨로 항목을 고른 뒤 별칭은 엔티티 API 로 50개씩
# 따로 받는다 — 남긴 항목만 물으니 호출이 60번 안쪽이다.
# 갈래 × 언어로 **작게 여러 번** 묻는다 (3 × 6 = 18번). 한 번에 다 받으면 1만 6천 행이 넘어
# 끝점이 청크 전송 중에 끊는다 (2026-09-17 두 번 겪었다). 작은 질의는 각각 수백~수천 행이다.
BRANCHES = {
    "brand": "{ ?item wdt:P31/wdt:P279* wd:Q1941779 } UNION { ?item wdt:P452 wd:Q12684 }",
    "designer": "?item wdt:P106 wd:Q3501317 .",
}
QUERY = """
SELECT ?item ?label WHERE {
  %s
  ?item rdfs:label ?label . FILTER(LANG(?label) = "%s")
}
"""

ENTITY_API = "https://www.wikidata.org/w/api.php"
ENTITY_BATCH = 50  # wbgetentities 의 상한


RETRIES = 4


def _get(url: str, *, what: str) -> dict:
    """JSON 을 받는다. 5xx · 끊긴 응답은 잠깐 기다려 다시 시도한다.

    위키데이터 끝점이 가끔 504 를 내거나 본문을 중간에 끊는다 (2026-09-17 에 둘 다 겪었다 —
    끊긴 쪽은 `JSONDecodeError` 로 나타난다). 재시도 없이 죽으면 1시간짜리 수집이 마지막
    호출 하나에서 날아간다. 마지막 실패는 어느 단계(`what`)였는지와 본문 앞뒤를 붙여 올린다.
    """
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                body = response.read()
            return json.loads(body)
        except urllib.error.HTTPError as error:
            last = error
            # 429 는 "천천히 해라" 다. Retry-After 를 주면 그만큼, 아니면 아래 대기.
            # 그 밖의 4xx 는 우리 질의가 틀린 것이라 다시 해도 같다 — 바로 올린다.
            if error.code == 429:
                retry_after = error.headers.get("Retry-After") if error.headers else None
                if retry_after and retry_after.isdigit():
                    time.sleep(int(retry_after))
            elif error.code < 500:
                raise
        # `ValueError` 가 여기 있는 이유 — 서버가 청크 전송 중에 끊으면 http.client 가 빈 청크
        # 길이를 16진수로 읽다 `invalid literal for int() with base 16: b''` 를 낸다 (2026-09-17).
        except (
            urllib.error.URLError,
            json.JSONDecodeError,
            TimeoutError,
            ConnectionError,
            http.client.HTTPException,
            ValueError,
        ) as error:
            last = error
            if isinstance(error, json.JSONDecodeError):
                snippet = error.doc[max(0, error.pos - 120) : error.pos + 120]
                print(f"  {what}: 본문이 JSON 이 아니다 — …{snippet!r}…", file=sys.stderr)
        wait = 5 * attempt
        print(f"  {what}: {attempt}/{RETRIES} 실패 ({type(last).__name__}) — {wait}초 뒤 재시도",
              file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"{what}: {RETRIES}번 실패") from last


def fetch() -> list[tuple[str, str, str, str]]:
    """`(qid, kind, lang, label)` 전부. 갈래 × 언어마다 한 번씩 묻는다."""
    rows: list[tuple[str, str, str, str]] = []
    for kind, pattern in BRANCHES.items():
        for lang in LANGS:
            query = QUERY % (pattern, lang)
            url = f"{ENDPOINT}?{urllib.parse.urlencode({'query': query})}"
            bindings = _get(url, what=f"SPARQL {kind}/{lang}")["results"]["bindings"]
            for row in bindings:
                qid = row["item"]["value"].rsplit("/", 1)[-1]
                rows.append((qid, kind, lang, row["label"]["value"]))
            print(f"  라벨 {kind}/{lang}: {len(bindings)}행", file=sys.stderr)
    return rows


def fetch_aliases(qids: list[str]) -> dict[str, dict[str, list[str]]]:
    """qid → {lang: [별칭...]}. 50개씩 묶어 엔티티 API 를 친다."""
    out: dict[str, dict[str, list[str]]] = {}
    for start in range(0, len(qids), ENTITY_BATCH):
        chunk = qids[start : start + ENTITY_BATCH]
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": "aliases",
                "languages": "|".join(LANGS),
                "format": "json",
            }
        )
        batch_no = start // ENTITY_BATCH + 1
        if start:
            # 연달아 치면 429 가 온다 (2026-09-17, 11번째에서). 한 박자 쉬는 게 재시도보다 싸다.
            time.sleep(1.0)
        entities = _get(f"{ENTITY_API}?{query}", what=f"별칭 {batch_no}").get("entities", {})
        for qid, entity in entities.items():
            aliases = entity.get("aliases") or {}
            out[qid] = {
                lang: sorted({row["value"] for row in rows})
                for lang, rows in aliases.items()
                if rows
            }
        print(f"  별칭 {min(start + ENTITY_BATCH, len(qids))}/{len(qids)}", file=sys.stderr)
    return out


def group(rows: list[tuple[str, str, str, str]]) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for qid, kind, lang, label in rows:
        entry = items.setdefault(qid, {"id": qid, "kinds": set(), "labels": {}, "aliases": {}})
        entry["kinds"].add(kind)
        entry["labels"][lang] = label
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--min-langs", type=int, default=3, help="이 수 이상의 언어 라벨이 있는 항목만 (영어 포함)"
    )
    args = parser.parse_args()

    items = group(fetch())
    kept = {
        qid: item
        for qid, item in items.items()
        if "en" in item["labels"] and len(item["labels"]) >= args.min_langs
    }
    aliases = fetch_aliases(sorted(kept))
    by_kind = {"brand": [], "designer": []}
    for qid in sorted(kept):
        item = kept[qid]
        kind = "brand" if "brand" in item["kinds"] else "designer"
        by_kind[kind].append(
            {
                "id": item["id"],
                "labels": dict(sorted(item["labels"].items())),
                "aliases": dict(sorted(aliases.get(qid, {}).items())),
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for kind, rows in by_kind.items():
        document = {
            "source": "wikidata",
            "category": kind,
            "fetched_at": date.today().isoformat(),
            "query": {"min_langs": args.min_langs, "langs": list(LANGS)},
            "items": rows,
        }
        path = args.out_dir / f"wikidata-{kind}s.json"
        path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        langs = collections.Counter(lang for row in rows for lang in row["labels"] if lang != "en")
        print(
            f"{path.name}: 항목 {len(rows)} · "
            + " · ".join(f"{lang} {n}" for lang, n in langs.most_common()),
            file=sys.stderr,
        )
    print(f"전체 항목 {len(items)} → 남긴 것 {len(kept)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
