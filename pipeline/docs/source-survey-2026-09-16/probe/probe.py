# ruff: noqa — 2026-09-16 일회성 실측 기록. 실행한 그대로 보존한다.
"""패션 소스 후보 일회성 실측. 결과는 CSV 한 줄씩, 본문은 저장하지 않는다(길이·언어·제목만)."""
import csv, gzip, json, re, statistics, sys, threading, time, traceback, zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib import robotparser

import feedparser, trafilatura
from sites import SITES

UA = "TrendInBot/0.1 (non-profit student project; trend analysis)"
TIMEOUT = 20
GAP = 3.0
MAXREQ = 10
MAXBYTES = 15 * 1024 * 1024
OUT = "results.csv"

_host_locks: dict = {}
_host_last: dict = {}
_host_blocked: dict = {}
_glock = threading.Lock()

BLOCK_MARKERS = [r"cf-chl", r"Just a moment\.\.\.", r"captcha-delivery", r"px-captcha", r"g-recaptcha", r"h-captcha",
                 r"Pardon Our Interruption", r"Access Denied", r"Request unsuccessful\. Incapsula", r"_Incapsula_Resource",
                 r"Attention Required! \| Cloudflare", r"安全验证", r"人机验证"]
LOGIN_RE = re.compile(r"/(login|signin|sign-in|auth|account/login)\b", re.I)


class Blocked(Exception):
    pass


def host_of(url):
    return urlsplit(url).hostname or ""


class Fetcher:
    def __init__(self, key):
        self.key = key
        self.n = 0
        self.log = []

    def get(self, url):
        h = host_of(url)
        with _glock:
            lock = _host_locks.setdefault(h, threading.Lock())
        with lock:
            if h in _host_blocked:
                raise Blocked(f"{h} 이미 차단: {_host_blocked[h]}")
            if self.n >= MAXREQ:
                raise RuntimeError("요청 상한 10")
            wait = _host_last.get(h, 0) + GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            self.n += 1
            t0 = time.time()
            status, final, body, ctype, err = None, url, b"", "", None
            try:
                req = Request(url, headers={"User-Agent": UA})
                with build_opener().open(req, timeout=TIMEOUT) as r:
                    status, final, ctype = r.status, r.geturl(), r.headers.get("Content-Type", "")
                    body = r.read(MAXBYTES)
                    enc = r.headers.get("Content-Encoding", "")
                    if enc == "gzip":
                        body = gzip.decompress(body)
            except HTTPError as e:
                status, final = e.code, e.geturl() or url
                try:
                    body = e.read(200000)
                except Exception:
                    body = b""
            except (URLError, TimeoutError, OSError) as e:
                err = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
            finally:
                _host_last[h] = time.time()
            self.log.append((url, status, round(time.time() - t0, 1), err))
            reason = None
            if status in (403, 429):
                reason = f"HTTP {status}"
            elif final and LOGIN_RE.search(urlsplit(final).path) and not LOGIN_RE.search(urlsplit(url).path):
                reason = f"로그인 리다이렉트 {final}"
            elif body and (status != 200 or len(body) < 30000):
                txt = body[:30000].decode("utf-8", "ignore")
                for m in BLOCK_MARKERS:
                    if re.search(m, txt):
                        reason = f"챌린지 표지 '{m}' (HTTP {status}, {len(body)}B)"
                        break
            if reason:
                _host_blocked[h] = reason
                fh = host_of(final)
                if fh and fh != h:
                    _host_blocked[fh] = reason
                raise Blocked(f"{h}: {reason}")
            return dict(status=status, final=final, body=body, ctype=ctype, err=err)


# ---------- 텍스트 도구
TAG_RE = re.compile(r"<[^>]+>")


def strip_html(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s or "")
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", s))).strip()


def lang_guess(text):
    t = text[:5000]
    if not t:
        return ""
    kana = len(re.findall(r"[぀-ヿ]", t))
    hangul = len(re.findall(r"[가-힣]", t))
    han = len(re.findall(r"[一-鿿]", t))
    letters = len(re.findall(r"[A-Za-zÀ-ÿ]", t))
    tot = kana + hangul + han + letters or 1
    if hangul / tot > 0.2:
        return "ko"
    if kana / tot > 0.05:
        return "ja"
    if han / tot > 0.3:
        return "zh"
    words = re.findall(r"[a-zà-ÿ']+", t.lower())
    sc = {
        "en": sum(w in {"the", "and", "of", "to", "is", "with", "for", "this"} for w in words),
        "fr": sum(w in {"le", "la", "les", "et", "des", "est", "une", "pour", "du"} for w in words),
        "it": sum(w in {"il", "di", "che", "e", "la", "per", "una", "della", "sono", "gli"} for w in words),
        "de": sum(w in {"der", "die", "und", "das", "ist", "mit", "nicht", "ein"} for w in words),
    }
    best = max(sc, key=sc.get)
    return best if sc[best] > 2 else "?"


CJK = {"ja", "zh", "ko"}
BAD_TITLE = re.compile(r"^\s*$|^[\W\d_]+$|\.(jpe?g|png|gif|webp|heic)$|^(IMG|DSC|PXL)[_-]?\d+", re.I)


def ld_article_bodies(html):
    out = []
    for m in re.finditer(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except Exception:
            try:
                data = json.loads(unescape(raw))
            except Exception:
                continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                for k, v in x.items():
                    if k == "articleBody" and isinstance(v, str):
                        out.append(len(strip_html(v)))
                    else:
                        stack.append(v)
            elif isinstance(x, list):
                stack.extend(x)
    return out


PAYWALL_PATTERNS = {
    "isAccessibleForFree=false": r'"isAccessibleForFree"\s*:\s*"?(false|False)',
    "paywall": r"paywall",
    "piano/tinypass": r"tinypass|piano\.io",
    "subscribe-to-read": r"subscribe to (read|continue)|subscribers? only|members? only|member-only|for members",
    "ja会員限定": r"会員限定|有料会員",
    "fr abonnés": r"réservé aux abonnés",
    "it abbonati": r"riservato agli abbonati",
    "ko 회원전용": r"회원 ?전용|유료 ?회원",
    "zh 会员": r"会员专享|付费阅读",
}


def paywall_hints(html):
    return [k for k, p in PAYWALL_PATTERNS.items() if re.search(p, html, re.I)]


def decode(body, ctype=""):
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', body[:3000], re.I) or re.search(rb'encoding=["\']([\w-]+)', body[:200])
        enc = m.group(1).decode() if m else "utf-8"
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


FEED_LINK_RE = re.compile(r'<link[^>]+type=["\']application/(rss|atom)\+xml["\'][^>]*>', re.I)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def discover_feeds(html, base, kw):
    found = []
    for m in FEED_LINK_RE.finditer(html):
        h = HREF_RE.search(m.group(0))
        if h:
            found.append(urljoin(base, unescape(h.group(1))))
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href = unescape(m.group(1))
        if re.search(r"(rss|feed|atom|\.xml|\.rdf)", href, re.I):
            txt = strip_html(m.group(2))
            if kw is None or kw == "" or kw.lower() in (href + " " + txt).lower():
                found.append(urljoin(base, href))
    seen, out = set(), []
    for f in found:
        if f not in seen and not re.search(r"comments/feed|oembed|wp-json|sitemap", f, re.I):
            seen.add(f)
            out.append(f)
    return out


# ---------- 사이트 1곳
def probe_site(s):
    f = Fetcher(s["key"])
    row = {k: s[k] for k in ("key", "name", "country", "kind", "added")}
    row.update(blocked="", block_reason="", note="")
    try:
        if s["kind"] == "retail":
            probe_retail(s, f, row)
        else:
            probe_feed_site(s, f, row)
    except Blocked as e:
        row["blocked"] = "Y"
        row["block_reason"] = str(e)
    except Exception as e:
        row["note"] += f" 예외 {type(e).__name__}: {e}"
        traceback.print_exc()
    # robots 는 마지막에 (기록만)
    try:
        probe_robots(s, f, row)
    except Blocked as e:
        row["robots_status"] = f"차단 {e}"
    except Exception as e:
        row["robots_status"] = f"예외 {e}"
    row["requests"] = f.n
    row["req_log"] = " | ".join(f"{u} {st} {t}s{(' ' + er) if er else ''}" for u, st, t, er in f.log)
    conclude(row)
    print(f"[{s['key']}] n={f.n} {row.get('conclusion')} {row.get('block_reason','')}", flush=True)
    return row


def probe_feed_site(s, f, row):
    tried = []
    candidates = list(s["feeds"])
    parsed = None
    for url in candidates[:2]:
        r = f.get(url)
        tried.append(f"{url}→{r['status'] or r['err']}")
        if r["status"] == 200 and r["body"]:
            p = feedparser.parse(r["body"])
            if p.entries:
                parsed = (url, r, p)
                break
    if not parsed and s.get("discover"):
        r = f.get(s["discover"])
        tried.append(f"[discover]{s['discover']}→{r['status'] or r['err']}")
        if r["status"] == 200:
            html = decode(r["body"], r["ctype"])
            links = discover_feeds(html, r["final"], s.get("kw"))
            row["discovered_links"] = " ".join(links[:8])
            for url in links[:3]:
                if url in candidates:
                    continue
                rr = f.get(url)
                tried.append(f"{url}→{rr['status'] or rr['err']}")
                if rr["status"] == 200 and rr["body"]:
                    p = feedparser.parse(rr["body"])
                    if p.entries:
                        parsed = (url, rr, p)
                        break
    row["feed_tried"] = " ; ".join(tried)
    if not parsed:
        row["feed_parse"] = "N"
        return
    url, r, p = parsed
    row.update(feed_url=url, feed_status=r["status"], feed_final=r["final"], feed_parse="Y" + (" (bozo)" if p.bozo else ""),
               feed_format=p.version, items=len(p.entries), feed_lang=(p.feed.get("language") or ""))
    dates = []
    for e in p.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        if t:
            dates.append(datetime(*t[:6], tzinfo=timezone.utc))
    if dates:
        newest, oldest = max(dates), min(dates)
        row["newest"], row["oldest"] = newest.isoformat()[:16], oldest.isoformat()[:16]
        span = (newest - oldest).total_seconds() / 86400
        row["span_days"] = round(span, 2)
        row["per_day"] = round((len(dates) - 1) / span, 1) if span > 0 and len(dates) > 1 else ""
        row["age_newest_days"] = round((datetime.now(timezone.utc) - newest).total_seconds() / 86400, 1)
    # 피드 본문 길이
    enc_lens, desc_lens = [], []
    for e in p.entries:
        c = e.get("content")
        enc_lens.append(max((len(strip_html(x.get("value", ""))) for x in c), default=0) if c else 0)
        desc_lens.append(len(strip_html(e.get("summary", ""))))
    row["content_encoded_median"] = int(statistics.median(enc_lens)) if enc_lens else 0
    row["description_median"] = int(statistics.median(desc_lens)) if desc_lens else 0
    titles = [e.get("title", "") or "" for e in p.entries]
    bad = sum(bool(BAD_TITLE.search(t)) for t in titles)
    row["title_bad"] = f"{bad}/{len(titles)}"
    row["title_sample"] = (titles[0] if titles else "")[:80]
    sample_txt = " ".join(titles) + " " + " ".join(strip_html(e.get("summary", ""))[:300] for e in p.entries[:10])
    row["lang_text"] = lang_guess(sample_txt)
    # 기사 3건
    links = []
    for e in p.entries:
        l = e.get("link")
        if l and l not in links:
            links.append(l)
    ld, tr, st, pw, alang, alens = [], [], [], set(), [], []
    for i, link in enumerate(links[:3]):
        try:
            a = f.get(link)
        except Blocked:
            raise
        except RuntimeError:
            break
        st.append(str(a["status"] or a["err"]))
        if a["status"] != 200:
            continue
        html = decode(a["body"], a["ctype"])
        bodies = ld_article_bodies(html)
        ld.append(max(bodies) if bodies else 0)
        txt = trafilatura.extract(html, url=a["final"], favor_recall=False) or ""
        tr.append(len(txt))
        alang.append(lang_guess(txt))
        pw.update(paywall_hints(html))
        # 같은 기사의 피드 본문 길이와 비교
        e = next((x for x in p.entries if x.get("link") == link), None)
        if e is not None:
            c = e.get("content")
            fl = max((len(strip_html(x.get("value", ""))) for x in c), default=0) if c else len(strip_html(e.get("summary", "")))
            alens.append((fl, len(txt)))
    row.update(art_status=",".join(st), ld_body_lens=",".join(map(str, ld)), traf_lens=",".join(map(str, tr)),
               art_lang=",".join(sorted(set(x for x in alang if x))), paywall_hints=",".join(sorted(pw)))
    row["_pairs"] = alens


def probe_retail(s, f, row):
    r = f.get(s["retail"])
    row.update(listing_url=s["retail"], listing_status=r["status"] or r["err"], listing_final=r["final"])
    if r["status"] != 200:
        return
    html = decode(r["body"], r["ctype"])
    vis = strip_html(html)
    row["listing_bytes"] = len(r["body"])
    row["listing_visible_text"] = len(vis)
    pat = re.compile(s["retail_pat"], re.I)
    anchors, dump = [], []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href = unescape(m.group(1))
        if pat.search(href):
            t = strip_html(m.group(2))
            last = urlsplit(urljoin(r["final"], href)).path.rstrip("/").rsplit("/", 1)[-1]
            slugish = last.count("-") >= 2 or re.search(r"\d{3,}", last)
            dump.append((href, t[:100], bool(slugish)))
            if len(t) >= 15 and slugish:
                anchors.append(t)
    row["listing_pattern_anchors_all"] = len(dump)
    with _glock:
        try:
            d = json.load(open("retail_anchors.json"))
        except Exception:
            d = {}
        d[s["key"]] = dump[:80]
        json.dump(d, open("retail_anchors.json", "w"), ensure_ascii=False, indent=0)
    row["listing_article_anchors"] = len(set(anchors))
    row["title_sample"] = anchors[0][:80] if anchors else ""
    nd = re.search(r'(?is)<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html)
    st = re.search(r'(?is)window\.__(INITIAL_STATE|PRELOADED_STATE|APOLLO_STATE|NUXT)__\s*=', html)
    row["listing_state_json"] = (f"__NEXT_DATA__ {len(nd.group(1))}B" if nd else "") + (f" window.__{st.group(1)}__" if st else "")
    row["lang_text"] = lang_guess(vis)
    row["paywall_hints"] = ",".join(paywall_hints(html))
    # 판정
    if len(set(anchors)) >= 5:
        row["listing_verdict"] = "HTML에 기사 제목·링크 있음 (JS 불필요)"
    elif nd or st:
        row["listing_verdict"] = "HTML 앵커엔 없고 상태 JSON 에만 (파싱하면 가능, 렌더링은 불필요)"
    else:
        row["listing_verdict"] = "HTML 에 기사 없음 (JS 렌더링 필요 추정)"


def probe_robots(s, f, row):
    target = s.get("retail") or row.get("feed_final") or row.get("feed_url") or (s["feeds"][0] if s["feeds"] else s.get("discover"))
    if not target:
        return
    base = f"{urlsplit(target).scheme}://{urlsplit(target).netloc}"
    r = f.get(base + "/robots.txt")
    row["robots_status"] = r["status"] or r["err"]
    if r["status"] != 200:
        row["robots_feed_ok"] = "robots 없음(허용 간주)" if r["status"] in (404, 410) else ""
        return
    rp = robotparser.RobotFileParser()
    rp.parse(decode(r["body"]).splitlines())
    row["robots_feed_ok"] = f"TrendInBot={rp.can_fetch('TrendInBot', target)} *={rp.can_fetch('*', target)}"
    arts = [x for x in (row.get("req_log_arts") or [])]
    row["robots_ccbot_root"] = rp.can_fetch("CCBot", base + "/")
    row["robots_ccbot_target"] = rp.can_fetch("CCBot", target)


def conclude(row):
    pairs = row.pop("_pairs", [])
    if row.get("kind") == "retail":
        if row.get("blocked"):
            row["conclusion"] = "차단"
        elif row.get("listing_status") != 200:
            row["conclusion"] = "피드 없음"
            row["note"] += f" 목록 {row.get('listing_status')}"
        else:
            row["conclusion"] = "피드 없음"
            row["note"] += " 리테일러 목록: " + row.get("listing_verdict", "")
        return
    if row.get("blocked") and row.get("feed_parse") != "Y":
        row["conclusion"] = "차단"
        return
    if row.get("feed_parse") != "Y":
        row["conclusion"] = "피드 없음"
        return
    lang = row.get("feed_lang", "")[:2].lower() or row.get("lang_text", "")
    cjk = lang in CJK
    full_abs = 400 if cjk else 1000
    enc, desc = row.get("content_encoded_median", 0), row.get("description_median", 0)
    fb = max(enc, desc)
    ratios = [fl / tl for fl, tl in pairs if tl >= 200]
    row["feed_vs_article_ratio"] = ",".join(f"{x:.2f}" for x in ratios)
    if fb == 0:
        body = "없음"
    elif ratios and statistics.median(ratios) >= 0.7:
        body = "전문"
    elif not ratios and fb >= full_abs:
        body = "전문"
    else:
        body = "요약"
    row["feed_body"] = body
    tb = row.get("title_bad", "0/1").split("/")
    bad_rate = int(tb[0]) / max(int(tb[1]), 1)
    row["title_quality"] = "의미 있음" if bad_rate <= 0.2 else "비었거나 번호·파일명"
    trs = [int(x) for x in row.get("traf_lens", "").split(",") if x]
    lds = [int(x) for x in row.get("ld_body_lens", "").split(",") if x]
    ok_len = 150 if cjk else 300
    row["ld_ok"] = sum(x >= ok_len for x in lds)
    row["traf_ok"] = sum(x >= ok_len for x in trs)
    if bad_rate > 0.5 and fb < 50 and (not trs or max(trs) < ok_len):
        row["conclusion"] = "이미지뿐"
    elif body == "전문":
        row["conclusion"] = "전문피드로 수집"
    elif row.get("blocked"):
        row["conclusion"] = "차단"  # 피드는 됐지만 기사 페이지에서 막힘 → CC-NEWS 후처리에서 다시 봄
        row["note"] += " 피드는 받았고 기사 페이지에서 차단"
    elif row["ld_ok"] >= 2 or row["traf_ok"] >= 2:
        row["conclusion"] = "요약피드+기사페이지 추출"
    else:
        row["conclusion"] = "요약피드(기사 추출 실패)"


COLS = ["key", "name", "country", "kind", "added", "conclusion", "feed_url", "feed_status", "feed_final", "feed_parse", "feed_format",
        "items", "newest", "oldest", "span_days", "per_day", "age_newest_days", "feed_body", "content_encoded_median", "description_median",
        "feed_vs_article_ratio", "feed_lang", "lang_text", "art_lang", "title_bad", "title_quality", "title_sample", "art_status",
        "ld_body_lens", "traf_lens", "ld_ok", "traf_ok", "paywall_hints", "robots_status", "robots_feed_ok", "robots_ccbot_root",
        "robots_ccbot_target", "blocked", "block_reason", "listing_url", "listing_status", "listing_final", "listing_bytes",
        "listing_visible_text", "listing_pattern_anchors_all", "listing_article_anchors", "listing_state_json", "listing_verdict", "discovered_links", "feed_tried",
        "requests", "note", "req_log"]


def main():
    import os
    only = set(sys.argv[1:])
    done = {}
    if not only and os.path.exists("results_partial.csv"):
        done = {r["key"]: r for r in csv.DictReader(open("results_partial.csv", encoding="utf-8"))}
    sites = [s for s in SITES if (not only or s["key"] in only) and s["key"] not in done]
    with ThreadPoolExecutor(max_workers=16) as ex:
        rows = list(ex.map(probe_site, sites))
    rows = list(done.values()) + rows
    out = OUT if not only else "results_partial.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote", out)


if __name__ == "__main__":
    main()
