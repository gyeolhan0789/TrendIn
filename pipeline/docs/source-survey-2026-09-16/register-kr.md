# 한국 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. 09-16 에 측정 실패한 패션인사이트도 같은 날 다시 쟀다.

## 명령

```
python -m trendin.fashion.collect.probe <key> --check --header --page-param page --samples 2
python -m trendin.fashion.collect.probe <key> --check --samples 0 --page-param paged
```

첫 줄은 피드 1페이지, 표본 기사 2건, 2페이지, 999페이지를 친다. 둘째 줄은 기사를 받지 않고 `paged` 만 잰다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다. 표본 기사에서 403·429 를 받은 곳은 없다.

표본이 2건인 이유가 있다. 섹션 피드 주소를 찾으려고 소스마다 기사 페이지 한 건을 먼저 받아 메뉴를 읽었다(#고른 것). 기사 페이지를 소스당 3건 넘게 치지 않으려고 프로브 표본을 2건으로 줄였다.

두 소스는 한국 뉴스 CMS 피드라 기존 규칙으로 읽히지 않았다. guid 가 없고, id 가 link 쿼리(`idxno`)에 있고, pubDate 가 `2026-09-18 15:30:27` 처럼 오프셋 없는 한국 시각이다. 한국섬유신문은 link 가 `http://` 다. 그래서 규칙 둘(`link_query_param`, `rss_pubdate_local`)과 http link 를 https 로 올리는 처리를 먼저 넣었다(`source-discovery.md` #3.2).
pubDate 가 한국 시각이라는 것은 피드를 받은 시각으로 확인했다. 06:31 UTC(15:31 KST)에 받은 피드의 `lastBuildDate` 가 `15:30:43` 이다.

## 측정 표

표본을 받은 실행의 줄을 그대로 옮겼다. 2p·끝 페이지 칸은 `page` 로 잰 것이다. `paged` 결과는 #페이지 넘김에 있다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| ktnews | KR | rss20 | 50 | 1.1 | trafilatura,trafilatura | 1682 | 0/2 | 0/2 | 0/2 | same_page | items |
| itnk | KR | rss20 | 50 | 7.6 | trafilatura,trafilatura | 565 | 0/2 | 0/2 | 0/2 | same_page | items |

표본 본문은 ktnews 1323·2042자, itnk 708·423자다. 09-16 에 쓴 한국어 기사 문턱 150자를 모두 넘는다.

저자는 두 곳 다 0/2 다. 우리는 RSS 2.0 에서 `dc:creator` 만 읽는데 두 피드는 `<author>` 에 싣는다. ktnews 는 `이영희 기자` 같은 기자 이름이고, itnk 는 50건 모두 `국제섬유신문 기자` 다.

## 제외

| key | 이유 |
|---|---|
| fashioninsight | 09-16 에 잰 도메인 `fashioninsight.co.kr` 이 없는 도메인이다. 이번에도 이름 해석이 실패했고, dns.google 조회가 `www.` 유무 모두 NXDOMAIN 이다(권한 서버 `co.kr`). 패션인사이트의 실제 사이트는 `www.fi.co.kr`(제목 `Fashion Insight`)로 보인다. 그 홈을 한 번 받았더니 200 이었지만 `rss` 라는 글자가 한 곳도 없었다. 피드가 없어 프로필로 적을 수 없다 |

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다. 두 곳 다 파라미터를 무시하고 1페이지와 같은 50건을 준다. 프로필에 적지 않았다.

| key | `page` | `paged` | 프로필 |
|---|---|---|---|
| ktnews | same_page / items | same_page / items | 없음 |
| itnk | same_page / items | same_page / items | 없음 |

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| ktnews | `/rss/allArticle.xml` (전체) | `link_query_param` `idxno` | `/rss` 목록 페이지가 403 이다(`/rss` → 301 → `/rss/` 403). 기사 페이지 메뉴에서 패션이 하위 섹션 `S2N29` 인 것을 찾았지만 `/rss/S2N29.xml` 은 404 다. 1페이지 50건이 전부 `?idxno=` 숫자로 읽혔다 |
| itnk | `/rss/allArticle.xml` (전체) | `link_query_param` `idxno` | `/rss/` 목록 페이지가 403 이다. 메뉴의 패션은 하위 섹션 `S2N57` 인데 `/rss/S2N57.xml` 은 404 다. 상위 섹션 `S1N13` 은 `뉴스` 라 패션만 주지 않는다. 1페이지 50건이 전부 읽혔다 |

- **published_at 은 `rss_pubdate_local` `Asia/Seoul` 이다.** 표본의 발행일이 `2026-09-18T15:30:27+09:00` 으로 피드 값과 같다.
- **ktnews link 는 https 로 올려 받는다.** 피드는 https 인데 item link 가 전부 `http://www.ktnews.com/...` 다. 세션은 리다이렉트를 따라가지 않고 허용 범위는 https 만 받는다. https 로 올린 기사 페이지 표본 2건이 200 이었다.
- **country 는 발행 법인의 소재지다.** 사이트 하단 표기로 확인했다. ktnews 는 `㈜한국섬유신문`(서울 중구), itnk 는 `(주)국제섬유신문사`(서울 강남구)다.
- **키가 겹치지 않는다.** 기존 한국 소스(vogue·gqkorea 등)와 이름도 호스트도 다르다.

## 남은 확인 거리

- **두 곳 모두 `/rss/` 목록 페이지가 봇 UA 에 403 이다.** 피드와 기사 페이지는 200 이다. 목록 페이지는 수집하지 않는다. 같은 CMS 가 기사 페이지까지 막기 시작하면 불변식 2 대로 그 실행에서 호스트가 멈춘다.
- **패션만 주는 피드가 없다.** 섬유·유통·뷰티·ESG 기사도 들어온다.
- **과거분을 채울 수 없다.** 페이지 넘김이 없어 백필 대상이 아니다. ktnews 는 50건이 1.1일 치라 1시간 수집 주기로는 넉넉하다.
- **itnk 본문이 짧다.** 표본 중앙값 565자, 짧은 것 423자다. 2건이라 피드 전체의 경향인지는 모른다.
