# ruff: noqa — 2026-09-16 일회성 실측 기록. 실행한 그대로 보존한다.
"""CC-NEWS: 최근 월 warc.paths.gz → 날짜별 파일 수·크기, 최근 날 WARC 1개를 스트리밍으로 훑어 후보 도메인 레코드 수."""
import collections, gzip, io, json, re, sys, time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from warcio.archiveiterator import ArchiveIterator
from sites import SITES

UA = "TrendInBot/0.1 (non-profit student project; trend analysis)"
BASE = "https://data.commoncrawl.org/"


def req(url, method="GET"):
    return urlopen(Request(url, headers={"User-Agent": UA}, method=method), timeout=60)


def domain_of(url):
    h = urlsplit(url).hostname or ""
    return h[4:] if h.startswith("www.") else h


CANDS = {}
for s in SITES:
    for u in s["feeds"] + [s.get("discover") or "", s.get("retail") or ""]:
        if u:
            d = domain_of(u)
            d = {"rssblog.ameba.jp": "ameblo.jp", "rss.blog.naver.com": "blog.naver.com", "fashionunited.info": "fashionunited.com"}.get(d, d)
            CANDS.setdefault(d, s["key"])
# 도메인 뿌리 기준으로도 맞춘다 (us.fashionnetwork.com → fashionnetwork.com 도 따로 셈)
ROOTS = {".".join(d.split(".")[-2:]) if not re.search(r"\.(co|com)\.(uk|jp|kr|cn)$", d) else ".".join(d.split(".")[-3:]) for d in CANDS}
ROOTS -= {"naver.com", "substack.com", "medium.com", "note.com", "hatenablog.com", "ameblo.jp", "lefigaro.fr", "brunch.co.kr"}
FASHION_PATH = re.compile(r"/(fashion|style|mode|moda|runway|fashion-week|luxury|apparel|streetwear)(/|-|$)", re.I)


def main():
    out = {}
    ym = time.strftime("%Y/%m")
    paths = None
    for cand in [ym, time.strftime("%Y/%m", time.gmtime(time.time() - 20 * 86400))]:
        try:
            with req(f"{BASE}crawl-data/CC-NEWS/{cand}/warc.paths.gz") as r:
                paths = gzip.decompress(r.read()).decode().split()
                out["month"] = cand
                break
        except Exception as e:
            out.setdefault("paths_errors", []).append(f"{cand}: {e}")
    by_day = collections.defaultdict(list)
    for p in paths:
        m = re.search(r"CC-NEWS-(\d{8})\d{6}-\d+\.warc\.gz", p)
        if m:
            by_day[m.group(1)].append(p)
    out["files_per_day"] = {d: len(v) for d, v in sorted(by_day.items())}
    days = sorted(by_day)
    # 마지막 날은 아직 채워지는 중일 수 있어 그 전날을 "최근 하루"로 본다
    day = days[-2] if len(days) >= 2 else days[-1]
    out["day"] = day
    sizes = {}
    for p in by_day[day]:
        with req(BASE + p, "HEAD") as r:
            sizes[p] = int(r.headers["Content-Length"])
        time.sleep(0.5)
    out["day_sizes_bytes"] = sizes
    out["day_total_bytes"] = sum(sizes.values())
    # 가운데 파일 하나를 스트리밍으로
    target = by_day[day][len(by_day[day]) // 2]
    out["sampled_file"] = target
    t0 = time.time()
    total = 0
    resp_n = 0
    host_hits = collections.Counter()
    root_hits = collections.Counter()
    hit_bytes = collections.Counter()
    fashion_path = 0
    lang_hosts = collections.Counter()
    with req(BASE + target) as r:
        for rec in ArchiveIterator(r):
            total += 1
            if rec.rec_type != "response":
                continue
            resp_n += 1
            url = rec.rec_headers.get_header("WARC-Target-URI") or ""
            d = domain_of(url)
            if FASHION_PATH.search(urlsplit(url).path):
                fashion_path += 1
            clen = int(rec.rec_headers.get_header("Content-Length") or 0)
            if d in CANDS:
                host_hits[d] += 1
                hit_bytes[d] += clen
            root = ".".join(d.split(".")[-3:]) if re.search(r"\.(co|com)\.(uk|jp|kr|cn)$", d) else ".".join(d.split(".")[-2:])
            if root in ROOTS:
                root_hits[root] += 1
            # 본문은 읽지 않고 흘려보낸다
            rec.content_stream().read()
    out["sample_seconds"] = round(time.time() - t0)
    out["sample_records_total"] = total
    out["sample_responses"] = resp_n
    out["sample_host_hits"] = dict(host_hits.most_common())
    out["sample_host_hit_bytes"] = dict(hit_bytes)
    out["sample_root_hits"] = dict(root_hits.most_common())
    out["sample_fashion_path_urls"] = fashion_path
    out["candidates_checked"] = sorted(CANDS)
    json.dump(out, open("ccnews.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k not in ("day_sizes_bytes", "candidates_checked")}, indent=1, ensure_ascii=False))


main()
