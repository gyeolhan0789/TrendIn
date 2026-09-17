# ruff: noqa — 2026-09-16 일회성 실측 기록. 실행한 그대로 보존한다.
"""자동 판정(conclusion_auto) 위에 요청 로그를 읽고 사람이 고친 판정(conclusion)과 이유(note)를 얹는다."""
import collections, csv, json

rows = {r["key"]: r for r in csv.DictReader(open("results_raw.csv", encoding="utf-8"))}
for r in csv.DictReader(open("results_partial.csv", encoding="utf-8")):  # globenewswire 재실행분
    r["note"] = (r.get("note") or "") + " 1차 실행: rss/list 에서 Atom 주소를 찾았으나 공백 미인코딩으로 요청 전 예외 → 인코딩해 재실행(이 호스트 총 8요청)"
    rows[r["key"]] = r

OV = {
    "fashionista": ("전문피드로 수집", "경로 이름은 excerpt 지만 content:encoded 중앙값 4169자. 첫 기사 페이지가 403 → 호스트 중단, 피드·기사 비교 못 함(절대 기준으로 판정)"),
    "wwdjapan": ("전문피드로 수집", "content:encoded 중앙값 1179자(ja, 절대 기준 400 넘음). 첫 기사 페이지 403 → 호스트 중단. 회원 한정 기사가 피드에서 잘리는지는 못 봄"),
    "medium_tag": ("차단", "태그 피드는 200(요약, 10건이 1.4시간). 기사(작성자 서브도메인 *.medium.com) 첫 요청 403"),
    "popeye": ("피드 없음", "홈에서 찾은 피드가 /feed/podcast(팟캐스트, 최신 69일 전). 기사 피드는 못 찾음. trafilatura 532자 고정 → 팟캐스트 페이지 틀"),
    "fashionunited": ("피드 없음", "rss-news 는 살아 있으나 최신 항목 2026-04-23, 항목이 FashionUnited 회사 공지 → 뉴스 피드 아님"),
    "another": ("피드 없음", "Substack 피드 200 이지만 항목 1건, 240일 전 → 휴면"),
    "substack_opulent": ("피드 없음", "피드 200 인데 항목 0 — 발행물 ID 추정이 틀렸을 수 있음"),
    "bof": (None, "per_day 추정 불가(항목 날짜가 2014~2026 섞임). ld articleBody 37~209자(티저), isAccessibleForFree=false. trafilatura 1.6~2.0천 자가 전문인지 페이월 앞부분인지 확인 못 함"),
    "wwd": (None, "ld articleBody 63~138자(티저), piano·isAccessibleForFree=false 흔적. trafilatura 2~3천 자는 받음"),
    "lofficiel": (None, "피드 전문(중앙 3560자). 기사 페이지는 trafilatura 663자로 3건 동일 → 페이지 틀만 뽑힘(JS 렌더 추정). 피드만 쓰면 됨"),
    "prtimes": (None, "fashion 카테고리 피드를 못 찾아 사이트 전체 index.rdf 를 잼 — per_day·건수는 전체 기준, 패션 분류 아님"),
    "senken": (None, "trafilatura 315~712자로 짧음 — 유료 잘림 가능(확인 못 함). 피드는 홈에서 찾은 posts/feed.xml"),
    "hatena": (None, "플랫폼 동작(전문 RSS)은 확인. 고른 블로그는 최신 글 2094일 전 → 대표로 부적절"),
    "naver_blog": ("요약피드, 기사 추출 실패", "고른 블로그 최신 글 2104일 전. 글 페이지는 iframe 틀이라 trafilatura 0자. robots 가 * 에 금지"),
    "brunch": ("요약피드, 기사 추출 실패", "비공식 /rss/@@id 는 200 이나 본문 필드 없음(제목만). 글 페이지 trafilatura 70~91자 → JS 렌더 추정. 고른 작가 최신 글 1586일 전"),
    "ameba": (None, "robots.txt 요청만 403(rssblog.ameba.jp). 피드·글 페이지는 200"),
    "fashionnetwork_jp": ("측정 실패", "jp.fashionnetwork.com/rss/ 요청이 Network unreachable(재시도 안 함). robots 는 200"),
    "bazaar_cn": ("측정 실패", "TLS 인증서 만료 오류(검증 끄지 않음)"),
    "mffashion": ("측정 실패", "TLS 인증서 만료 오류(검증 끄지 않음)"),
    "beams": ("측정 실패", "목록·robots 둘 다 20초 타임아웃"),
    "fashioninsight": ("측정 실패", "도메인 DNS 해석 실패(allArticle.xml·홈 모두)"),
    "032c": (None, "/feed 요청은 DNS 오류, 이어서 홈은 200 이었고 피드 링크 없음"),
    "ssense": (None, "목록 판정은 1차 휴리스틱(패턴 앵커 중 15자 이상 19개, 첫 것이 'Product Curation' — 메뉴일 수 있음). 반반"),
    "end": (None, "슬러그형 기사 앵커 18개(제목 텍스트 있음) + __NEXT_DATA__ 1.4MB → JS 없이 목록 있음"),
    "musinsa": (None, "보이는 텍스트 7자, __NEXT_DATA__ 2.8KB(목록을 담기엔 작음) → JS 렌더링 필요. robots 가 * 금지"),
    "29cm": (None, "보이는 텍스트 56자, __NEXT_DATA__ 5.4KB → JS 렌더링 필요(또는 URL 추정 오류)"),
    "wconcept": (None, "콘텐츠 목록 URL 을 몰라 홈을 잼. 기사 앵커 0, 보이는 텍스트 864자 → 판정 약함"),
}
RETAIL_VERDICT = {
    "ssense": "HTML 에 있음(반반)", "end": "HTML 에 있음", "musinsa": "JS 렌더링 필요", "29cm": "JS 렌더링 필요(URL 반반)",
    "wconcept": "판정 못 함(홈만 잼)", "mrporter": "차단(403)", "beams": "타임아웃",
}

cc = json.load(open("ccnews.json"))
for k, r in rows.items():
    r["conclusion_auto"] = r["conclusion"]
    if k in OV:
        c, n = OV[k]
        if c:
            r["conclusion"] = c
        r["note"] = ((r.get("note") or "").strip() + " " + n).strip()
    if r["kind"] == "retail":
        r["listing_verdict"] = RETAIL_VERDICT.get(k, r.get("listing_verdict", ""))
        if r["conclusion"] not in ("차단", "측정 실패"):
            r["conclusion"] = "피드 없음"
    r["cc_news_hits_1file"] = 0  # 후보 도메인 전부 0 (ccnews.json)
    r["ld_or_traf"] = ""
    if r["conclusion"] == "요약피드+기사페이지 추출":
        r["ld_or_traf"] = "ld+json 만으로" if int(r.get("ld_ok") or 0) >= 2 else "trafilatura 필요"

from probe import COLS
cols = ["key", "name", "country", "kind", "added", "conclusion", "conclusion_auto", "ld_or_traf", "cc_news_hits_1file"] + [c for c in COLS if c not in ("key", "name", "country", "kind", "added", "conclusion")]
cols.insert(cols.index("listing_verdict"), "listing_verdict") if "listing_verdict" not in cols else None
order = [s["key"] for s in __import__("sites").SITES]
with open("results.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for k in order:
        w.writerow(rows[k])

# 집계
C = collections.Counter(r["conclusion"] for r in rows.values())
print("결론별", dict(C))
X = collections.defaultdict(collections.Counter)
for r in rows.values():
    X[r["country"]][r["conclusion"]] += 1
for c in sorted(X):
    print(c, dict(X[c]))
print("ld/traf", collections.Counter(r["ld_or_traf"] for r in rows.values() if r["ld_or_traf"]))
print("요약피드 추출 사이트:", [(k, r["ld_or_traf"]) for k, r in rows.items() if r["ld_or_traf"]])
print("CCBot robots 금지(루트):", [k for k, r in rows.items() if r.get("robots_ccbot_root") == "False"])
print("robots * 금지(대상):", [k for k, r in rows.items() if "*=False" in (r.get("robots_feed_ok") or "")])
print("paywall isAccessibleForFree=false:", [k for k, r in rows.items() if "isAccessibleForFree=false" in (r.get("paywall_hints") or "")])
print("title bad:", [(k, r["title_bad"]) for k, r in rows.items() if r.get("title_bad") and not r["title_bad"].startswith("0/")])
print("per_day:", [(k, r["per_day"]) for k, r in rows.items() if r.get("per_day")])
print("items:", [(k, r["items"]) for k, r in rows.items() if r.get("items")])
print("added:", [k for k, r in rows.items() if r["added"] == "True"])
