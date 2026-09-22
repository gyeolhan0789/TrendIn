#!/usr/bin/env python
"""위키데이터에서 패션 개념의 다국어 이름을 받아 개념 초기 사전 파일을 만든다.

```sh
# 새 갈래만 받아 검수용 폴더에 쓴다 — 저장소에 바로 넣지 않는다
BR="apparel footwear accessory material color"
.venv/Scripts/python scripts/seed-concepts-wikidata.py --branches $BR --out-dir /tmp/wd
.venv/Scripts/python scripts/seed-concepts-wikidata.py --min-langs 4   # 전부, 저장소에 쓴다
```

**받은 파일을 그대로 커밋하지 않는다.** `--out-dir` 로 따로 뽑아 사람이 훑고, `concept
--dry-run --seed-in-memory --dump` 를 전후로 떠서 `scripts/concept-dump-diff.py` 로 맞대
**원래 붙던 표기가 밀려나지 않았는지** 확인한 뒤에 옮긴다. 표현을 늘리면 같은 표기가 두
개념에 걸려 매핑이 되레 줄 수 있다.

같은 항목에 붙은 언어별 라벨은 **사람이 확인해 같다고 적어 둔 것**이라 그대로 사전에 넣을 수
있다. 저작권을 포기한(CC0) 데이터라 출처 표시 의무도 없다.

## 두 파일로 나눈다

| 파일 | 조건 | 분류 |
| --- | --- | --- |
| `wikidata-brands.json` | 패션 하우스(P31/P279* Q1941779) 또는 산업이 패션(P452 Q12684) | brand |
| `wikidata-designers.json` | 직업이 패션 디자이너(P106 Q3501317) | designer |
| `wikidata-footwear.json` | 신발(P279* Q161928)의 하위 | footwear |
| `wikidata-accessory.json` | 패션 액세서리(P279* Q1065579)의 하위 | accessory |
| `wikidata-material.json` | 직물(P279* Q28823)의 하위 | material |
| `wikidata-color.json` | 색(P279* Q1075)의 하위 | color |
| `wikidata-apparel.json` | 옷(P279* Q11460)의 하위 | apparel |

한 항목이 여러 갈래에 걸리면 **표의 위쪽이 이긴다.** 브랜드와 디자이너가 겹치면 브랜드다 —
기사에서 세는 대상이 회사 쪽이다. 신발·액세서리는 위키데이터에서 옷의 하위이기도 해서, 옷을
먼저 두면 전부 옷이 된다. 그래서 좁은 갈래를 위에 둔다.

**일반명사는 브랜드와 성질이 다르다.** 고유명사는 라벨이 곧 표기지만, `상의` · `아우터` 처럼
분류 이름에 가까운 말은 개념으로 두되 세면 안 된다 (`countable: false`). 위키데이터는 그것을
알려주지 않으므로 전부 `true` 로 나온다 — 검수에서 손으로 내린다.

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
#
# 갈래는 **좁은 것부터** 적는다. 한 항목이 여러 갈래에 걸리면 먼저 나온 갈래가 이긴다 —
# 위키데이터에서 신발과 액세서리는 옷의 하위이기도 해서, 옷을 먼저 두면 전부 옷이 된다.
#
# 뿌리 QID 는 2026-09-21 에 확인했다: 옷 Q11460 · 신발 Q161928 · 액세서리 Q1065579 ·
# 직물 Q28823 · 색 Q1075. 일반명사는 `P279*` 로 하위 갈래를 재귀로 받는다 (고유명사 쪽은
# `P31/P279*` — 그쪽은 개체이고 이쪽은 종류다). 깊이를 제한하지 않는 이유는 한국어 라벨이
# 있는 하위가 갈래마다 100~900개뿐이라 (2026-09-21 실측) 제한해서 얻는 것보다 잃는 것이
# 많아서다. 잡음은 `--min-langs` 와 사람 검수가 거른다.
BRANCHES: dict[str, tuple[str, str]] = {
    # 갈래: (SPARQL 조건, 내보낼 파일 이름)
    "brand": (
        "{ ?item wdt:P31/wdt:P279* wd:Q1941779 } UNION { ?item wdt:P452 wd:Q12684 }",
        "wikidata-brands.json",
    ),
    "designer": ("?item wdt:P106 wd:Q3501317 .", "wikidata-designers.json"),
    "footwear": ("?item wdt:P279* wd:Q161928 .", "wikidata-footwear.json"),
    "accessory": ("?item wdt:P279* wd:Q1065579 .", "wikidata-accessory.json"),
    "material": ("?item wdt:P279* wd:Q28823 .", "wikidata-material.json"),
    "color": ("?item wdt:P279* wd:Q1075 .", "wikidata-color.json"),
    "apparel": ("?item wdt:P279* wd:Q11460 .", "wikidata-apparel.json"),
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


def fetch(branches: dict[str, tuple[str, str]]) -> list[tuple[str, str, str, str]]:
    """`(qid, kind, lang, label)` 전부. 갈래 × 언어마다 한 번씩 묻는다."""
    rows: list[tuple[str, str, str, str]] = []
    for kind, (pattern, _) in branches.items():
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
    parser.add_argument(
        "--branches",
        nargs="+",
        choices=sorted(BRANCHES),
        default=sorted(BRANCHES),
        help="받을 갈래. 브랜드 1.4만 건을 다시 받지 않고 새 갈래만 뽑을 때 쓴다",
    )
    args = parser.parse_args()
    if args.min_langs < 1:
        parser.error("--min-langs 는 1 이상이어야 한다")
    # 우선순위는 BRANCHES 의 선언 순서다. 고른 갈래만 남기되 순서는 그대로 둔다.
    branches = {name: BRANCHES[name] for name in BRANCHES if name in set(args.branches)}

    items = group(fetch(branches))
    kept = {
        qid: item
        for qid, item in items.items()
        if "en" in item["labels"] and len(item["labels"]) >= args.min_langs
    }
    aliases = fetch_aliases(sorted(kept))
    by_kind: dict[str, list[dict]] = {name: [] for name in branches}
    for qid in sorted(kept):
        item = kept[qid]
        # 선언 순서가 우선순위다 — 신발이 옷보다 먼저라 `스니커` 는 신발로 간다.
        kind = next(name for name in branches if name in item["kinds"])
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
            "license": "CC0-1.0",
            "category": kind,
            "fetched_at": date.today().isoformat(),
            "query": {"min_langs": args.min_langs, "langs": list(LANGS)},
            "items": rows,
        }
        path = args.out_dir / branches[kind][1]
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
