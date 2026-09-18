# 미국 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. bof 도 이 묶음에서 쟀다. 국가는 `GB` 지만 영국 묶음에서 빠졌다.

## 명령

```
python -m trendin.fashion.collect.probe <key> --check --header --page-param page
python -m trendin.fashion.collect.probe <key> --check --samples 0 --page-param paged
```

첫 줄은 피드 1페이지, 표본 기사 3건, 2페이지, 999페이지를 친다. 둘째 줄은 기사를 받지 않고 `paged` 만 잰다.
whowhatwear·wwd 는 두 파라미터를 바꿔 돌렸다(`paged` 가 첫 줄). bof·fashionista 는 파라미터 없이 첫 줄만 돌렸다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다. 403 을 받은 곳은 fashionista 하나다. 그 뒤로 그 호스트는 치지 않았다.

guid·link 모양은 같은 실행에서 페이지마다 발견 결과를 찍어 봤다. 요청은 늘지 않는다.
섹션 피드 추측은 같은 세션으로 주소마다 한 번씩 쳤다(#고른 것).

## 측정 표

표본을 받은 실행의 줄을 그대로 옮겼다. 2p·끝 페이지 칸은 `page` 로 잰 것이다. bof 는 표본이 전부 유료라 페이지를 재지 않았다. fashionista 는 첫 표본에서 403 을 받아 멈췄다. 파라미터별 결과는 #페이지 넘김에 있다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| vogue_us | US | rss20 | 30 | 2.1 | ld_json,trafilatura,ld_json | 2656 | 0/3 | 0/3 | 3/3 | same_page | items |
| gq_us | US | rss20 | 30 | 2.2 | trafilatura,trafilatura,ld_json | 2468 | 0/3 | 0/3 | 3/3 | ok | 400 |
| harpersbazaar_us | US | rss20 | 50 | 21.1 | ld_json,ld_json,ld_json | 2060 | 0/3 | 0/3 | 0/3 | same_page | items |
| elle_us | US | rss20 | 50 | 7.2 | ld_json,ld_json,ld_json | 3690 | 0/3 | 0/3 | 0/3 | same_page | items |
| whowhatwear | US | rss20 | 50 | 2.9 | trafilatura,feed,trafilatura | 1853 | 0/3 | 0/3 | 3/3 | same_page | items |
| prnewswire | US | rss20 | 20 | 0.6 | trafilatura,trafilatura,trafilatura | 2870 | 0/3 | 0/3 | 0/3 | same_page | items |
| globenewswire | US | atom | 20 | 7.9 | trafilatura,trafilatura,trafilatura | 3911 | 0/3 | 0/3 | 0/3 | same_page | items |
| wwd | US | rss20 | 10 | 0.0 | 유료,유료,유료 | - | 3/3 | 0/3 | 3/3 | not_older | items |
| fashionista | US | rss20 | 50 | 6.5 | 차단 | - | 0/1 | 1/1 | 0/1 | - | - |
| substack_bbsp | US | rss20 | 20 | 51.0 | 유료,유료,유료 | - | 3/3 | 0/3 | 3/3 | same_page | items |
| bof | GB | rss20 | 100 | 4491.0 | 유료,유료,유료 | - | 3/3 | 0/3 | 3/3 | - | - |

whowhatwear·wwd 는 `paged` 로 잰 줄이다. 저자 0/3 은 허스트 두 곳과 보도자료 두 곳이다. 허스트 두 곳은 item 에 `dc:creator`·`<author>` 가 둘 다 없다. bof 의 발행일 폭은 2014년 글이 섞여서다. 09-16 실측과 같다.

## 제외

| key | 이유 |
|---|---|
| wwd | 표본 3건이 전부 유료 표시(`isAccessibleForFree=false`)다. 제외 규칙(전부 유료면 뺀다)에 걸린다 |
| fashionista | 첫 표본 기사 페이지가 403 이다. 제외 규칙(표본에 403 이 하나라도 있으면 차단으로 보고 뺀다)에 걸린다. 09-16 에 이어 두 번째 403 이다 |
| substack_bbsp | 표본 3건이 전부 유료 표시다. 09-16 실측은 "전문피드로 수집" 으로 적었지만 그때도 `isAccessibleForFree=false` 흔적이 있었다 |
| bof | 표본 3건이 전부 유료 표시다 |

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다. 2p 가 `ok` 인 파라미터만 프로필에 적었다.

| key | `page` | `paged` | 프로필 |
|---|---|---|---|
| vogue_us | same_page / items | 안 잼 — 같은 Condé Nast 인 glamour_uk 가 same_page | 없음 |
| gq_us | ok / 400 | 안 잼 — 위와 같음 | `page` |
| harpersbazaar_us | same_page / items | same_page / items | 없음 |
| elle_us | same_page / items | 안 잼 — 같은 허스트 템플릿인 harpersbazaar_us 가 same_page | 없음 |
| whowhatwear | empty_or_404 / empty | same_page / items | 없음 |
| prnewswire | same_page / items | 안 잼 | 없음 |
| globenewswire | same_page / items | 안 잼 | 없음 |
| wwd | 안 잼 | not_older / items | 제외 |
| substack_bbsp | same_page / items | 안 잼 | 제외 |

vogue_us 의 전체 피드 `/feed/rss` 는 `page` 가 not_older / 400 이었다. 2페이지에 1페이지 가장 오래된 글보다 늦은 글이 있다(패션쇼 페이지 `mithridate`, 09-18 06:24 UTC).

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| vogue_us | `/feed/fashion/rss` | `guid_hash` | 패션 피드가 200 이다. 추측 셋 중 나머지(`/feed/category/fashion/latest/rss`, `/feed/tag/fashion/latest/rss`)는 404 다. guid 는 24자리 16진 객체 id 다. link 는 `/article/<슬러그>` 라 id 가 없다 |
| gq_us | `/feed/rss` (전체) | `guid_hash` | 추측 셋(`/feed/style/rss`, `/feed/fashion/rss`, `/feed/category/style/latest/rss`)이 전부 404 다. guid 는 vogue_us 와 같은 모양이다 |
| harpersbazaar_us | `/rss/fashion.xml` | `url_path_segment` `-2` | 실측 주소가 이미 패션 피드다. link 가 `/fashion/trends/a73743894/<슬러그>/` 꼴이다. 표본 셋(a73743894·a73686555·a73656530)에서 id 자리가 끝에서 둘째였다. 셋째 표본은 경로가 한 칸 얕다(`/fashion/a73656530/…`). 그래서 앞에서 세면 안 된다. 1·2·999페이지 50건씩 발견 실패 0 |
| elle_us | `/rss/fashion.xml` | `url_path_segment` `-2` | 추측 하나로 패션 피드를 찾았다. 1페이지 50건 전부 끝에서 둘째가 id 다. 갤러리는 `g71231506` 처럼 `g` 로 시작한다. 기사 `a…` 와 겹치지 않는다 |
| whowhatwear | `/feeds/tag/fashion` | `guid_hash` | Future 템플릿의 태그 피드다(marieclaire_uk 와 같은 꼴). guid 는 `ktv3oBHa62SECBCF4yuUuf` 같은 불투명 문자열이다 |
| prnewswire | 실측 주소 (패션 목록) | `guid_hash` | guid 가 `/news-releases/<슬러그>-302882850.html` 이다. 마지막 조각에 점이 있어서 `url_path_segment` 가 거부한다 |
| globenewswire | 실측 주소 (의류·액세서리 업종, Atom) | `guid_hash` | 경로의 숫자 id 는 언어판끼리 같다. LVMH 공시 영어판과 프랑스어판이 둘 다 `3362481` 이다. 숫자 조각을 id 로 쓰면 둘이 한 건이 된다. `<id>` 는 언어별 전체 URL 이라 갈린다 |

- **allowed_url_prefixes 는 본 호스트 하나씩이다.** 받은 페이지의 link 가 전부 피드와 같은 호스트였다.
- **리다이렉트는 없다.** 등록한 일곱 곳은 피드 주소가 200 을 바로 줬다. fashionista 의 옛 주소 `/.rss/excerpt/` 는 09-16 에 `/.rss/feed/<uuid>.xml` 로 리다이렉트했다. 이번에는 최종 주소로 쟀다.
- **country 는 발행 법인의 소재지다.** Condé Nast(Advance Magazine Publishers Inc.)·허스트(Hearst Communications, Inc.)·PR Newswire Association LLC 는 알려진 미국 법인 이름으로 적었다. 이번에 사이트 표기로 다시 확인하지는 않았다. Who What Wear 와 GlobeNewswire 는 미국 발행처라는 것만 보고 `US` 로 적었다. 법인 이름은 모른다.

## 남은 확인 거리

- **gq_us 의 `?page=999` 는 400 이다.** 영국 Condé Nast 두 곳과 같다. 백필은 404·410·빈 피드만 피드 끝으로 본다. 과거분 채움 하위 작업에서 본다.
- **보도자료 두 곳은 번역본이 따로 들어온다.** prnewswire 1페이지 20건 중 여섯이 보도자료 두 건의 프랑스어·스페인어·독일어판이다. globenewswire 도 영어·프랑스어판이 따로다. id 는 갈리지만 내용은 겹친다. 어디서 거를지는 정하지 않았다.
- **globenewswire 업종 피드에는 패션이 아닌 글도 있다.** 1페이지에 아웃소싱 회사(The Office Gurus) 임원 인사가 있다.
- **vogue_us 패션 피드에 뷰티 글이 섞인다.** 표본 셋 중 하나가 `serum-for-mature-skin` 이다.
- **substack_bbsp 의 유료 표시는 Substack 공통일 수 있다.** 무료 글에도 `isAccessibleForFree=false` 를 붙이는지 이번 표본 셋으로는 가리지 못한다. 다른 Substack 소스를 잴 때 무료로 알려진 글을 표본에 넣어 본다.
