# 영국 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. hypebeast 도 같은 날 같은 명령으로 쟀다.

## 명령

```
python -m trendin.fashion.collect.probe <key> --check --header --page-param paged
python -m trendin.fashion.collect.probe <key> --check --samples 0 --page-param page
```

첫 줄은 피드 1페이지, 표본 기사 3건, 2페이지, 999페이지를 친다. 둘째 줄은 기사를 받지 않고 `page` 만 잰다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다. 403·429 를 받은 표본은 없다.

섹션 피드 추측은 같은 세션으로 주소마다 한 번씩 쳤다(#고른 것).

## 측정 표

표본을 받은 실행의 줄을 그대로 옮겼다. 2p·끝 페이지 칸은 그 실행의 `--page-param` 값으로 잰 것이다 — vogue_uk 는 `page`, 나머지는 `paged`. 파라미터별 결과는 #페이지 넘김에 있다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| hypebeast | HK | rss20 | 19 | 1.6 | trafilatura,trafilatura,trafilatura | 2134 | 0/3 | 0/3 | 0/3 | same_page | items |
| glamour_uk | GB | rss20 | 30 | 7.0 | ld_json,ld_json,ld_json | 8502 | 0/3 | 0/3 | 3/3 | same_page | items |
| vogue_uk | GB | rss20 | 50 | 2.6 | ld_json,ld_json,ld_json | 7383 | 0/3 | 0/3 | 3/3 | ok | 400 |
| marieclaire_uk | GB | rss20 | 50 | 56.2 | trafilatura,trafilatura,trafilatura | 3709 | 0/3 | 0/3 | 3/3 | same_page | items |
| dazed | GB | atom | 15 | 1.2 | trafilatura,trafilatura,trafilatura | 3116 | 0/3 | 0/3 | 3/3 | same_page | items |
| id | GB | rss20 | 10 | 51.9 | trafilatura,trafilatura,feed | 4723 | 0/3 | 0/3 | 3/3 | ok | 404 |
| theindustry | GB | rss20 | 20 | 1.9 | trafilatura,trafilatura,trafilatura | 2207 | 0/3 | 0/3 | 3/3 | ok | items |
| drapers | GB | rss20 | 10 | 0.6 | 유료,유료,유료 | - | 3/3 | 0/3 | 3/3 | ok | items |

hypebeast 의 저자 0/3 은 옮기며 고친 값이다. 잴 때는 `<author>` 를 읽게 해서 3/3 이었지만 그 값은 발행처 주소다(#고른 것).

## 제외

| key | 이유 |
|---|---|
| drapers | 표본 3건이 전부 유료 표시(`isAccessibleForFree=false`)다. 제외 규칙(전부 유료면 뺀다)에 걸린다 |

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다. 2p 가 `ok` 인 파라미터만 프로필에 적었다.

| key | `paged` | `page` | 프로필 |
|---|---|---|---|
| hypebeast | same_page / items | 안 잼 | 없음 |
| glamour_uk | same_page / items | ok / 400 | `page` |
| vogue_uk | 안 잼 — glamour_uk 와 같은 Condé Nast 피드 | ok / 400 | `page` |
| marieclaire_uk | same_page / items | empty_or_404 / empty | 없음 |
| dazed | same_page / items | same_page / items | 없음 |
| id | ok / 404 | 안 잼 | `paged` |
| theindustry | ok / items | 안 잼 | `paged` |

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| hypebeast | `hypebeast.com/fashion/feed` | `guid_query_param` `post` | guid 가 `https://hypebeast.com/?post=6785282` 꼴이다 |
| glamour_uk | `/feed/rss` (전체) | `guid_hash` | 섹션 피드 추측 셋(`/feed/fashion/rss`, `/feed/category/fashion/latest/rss`, `/fashion/feed/rss`)이 전부 404 다. guid 는 24자리 16진 객체 id 다 |
| vogue_uk | `/feed/rss` (전체) | `guid_hash` | 추측 둘(`/feed/fashion/rss`, `/feed/category/fashion/latest/rss`)이 404 다. guid 는 glamour_uk 와 같은 모양이다 |
| marieclaire_uk | `/feeds/tag/fashion` | `guid_hash` | 실측 주소가 이미 패션 태그 피드다. guid 는 `uybywogWjM5sEAeDExREC8` 같은 불투명 문자열이다 |
| dazed | `/rss` (전체, Atom) | `url_path_segment` `2` | `/fashion/rss` 는 200 이지만 피드가 아니라 HTML 섹션 페이지다. link 가 `/<섹션>/article/70981/1/<슬러그>` 라 셋째 조각이 숫자 id 다. 표본 셋(70981·70931·70978)이 섹션이 달라도 같은 자리였다 |
| id | `/category/fashion/feed/` | `guid_query_param` `p` | 워드프레스 카테고리 피드가 있다. guid 가 `?p=441560` 꼴이다 |
| theindustry | `www.theindustry.fashion/feed/` (전체) | `guid_hash` | `/category/fashion/feed/` 는 404 다. 999페이지의 옛 글은 guid 가 `?p=` 가 아니라 퍼머링크라서 `guid_query_param` 이 20건 전부 실패했다. `guid_hash` 는 두 모양을 다 받는다 |

- **hypebeast 는 저자 칸을 적지 않았다.** `dc:creator` 가 없고, `<author>` 는 모든 item 이 `info@hypebeast.com (Hypebeast)` 다. 발행처 주소라 저자로 싣지 않는다.
- **theindustry 는 `www.` 를 붙였다.** 실측 주소 `theindustry.fashion/feed/` 는 `www.` 로 리다이렉트한다. 세션은 리다이렉트를 따라가지 않는다.
- **country 는 발행 법인의 소재지다.** Condé Nast 두 곳과 Future plc·Dazed Media 는 알려진 영국 법인 이름으로 적었다. 이번에 사이트 표기로 다시 확인하지는 않았다. i-D·TheIndustry.fashion 은 런던 발행처라는 것만 보고 `GB` 로 적었고, 법인 이름은 모른다.

## 남은 확인 거리

- **Condé Nast 두 곳의 `?page=999` 는 400 이다.** 백필은 404·410·빈 피드만 피드 끝으로 본다. 6개월에 닿기 전에 피드가 끝나면 백필이 오류로 멈춘다. 과거분 채움 하위 작업에서 본다.
- **dazed 는 패션만 주는 피드가 없다.** 음악·뷰티 기사도 들어온다. 15건이 1.2일 치라 1시간 수집 주기로는 넉넉하다.
- **theindustry 는 999페이지에도 기사를 준다.** 백필은 발행일로 멈춘다.
