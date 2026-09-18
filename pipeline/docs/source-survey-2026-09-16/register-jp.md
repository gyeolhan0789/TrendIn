# 일본 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. 후보 16곳 중 8곳을 등록했다.

## 명령

```
python -m trendin.fashion.collect.probe <key> --check --header --page-param paged
python -m trendin.fashion.collect.probe <key> --check --samples 0 --page-param page
```

첫 줄은 피드 1페이지, 표본 기사 3건, 2페이지, 999페이지를 친다. 둘째 줄은 기사를 받지 않고 `page` 만 잰다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다.
403 은 세 곳에서 받았다(#제외). 받은 뒤로 그 호스트에는 아무것도 치지 않았다.

섹션 피드 추측은 같은 세션으로 주소마다 한 번씩 쳤다(#고른 것).

houyhnhnm 은 첫 줄을 두 번 돌렸다. 첫 실행은 999페이지가 피드로 읽히지 않아 프로브가 표본 결과를 찍기 전에 예외로 끝났다. 프로브를 고친 뒤(`파싱 실패` 로 찍는다) 한 번 더 돌렸다. 그래서 표본 기사 3건을 두 번 받았다.

## 측정 표

표본을 받은 실행의 줄을 그대로 옮겼다. 2p·끝 페이지 칸은 그 실행의 `--page-param` 값으로 잰 것이다. vogue_jp·note_mb 는 `page`, prtimes 는 파라미터 없이, 나머지는 `paged`. 파라미터별 결과는 #페이지 넘김에 있다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| mensnonno | JP | rss20 | 15 | 1.8 | trafilatura,feed,trafilatura | 959 | 0/3 | 0/3 | 0/3 | ok | 404 |
| fudge | JP | rss20 | 15 | 2.6 | trafilatura,trafilatura,feed | 1383 | 0/3 | 0/3 | 3/3 | ok | 404 |
| oggi | JP | rss20 | 20 | 3.2 | feed,feed,trafilatura | 779 | 0/3 | 0/3 | 0/3 | ok | 404 |
| houyhnhnm | JP | rss20 | 18 | 2.9 | feed,feed,feed | 1087 | 0/3 | 0/3 | 3/3 | ok | 파싱 실패 |
| vogue_jp | JP | rss20 | 30 | 1.8 | ld_json,ld_json,ld_json | 2490 | 0/3 | 0/3 | 3/3 | ok | 400 |
| cancam | JP | rss20 | 15 | 1.6 | feed,feed,feed | 1483 | 0/3 | 0/3 | 3/3 | ok | items |
| fashionsnap | JP | rss20 | 95 | 1.2 | trafilatura,trafilatura,trafilatura | 865 | 0/3 | 0/3 | 0/3 | same_page | items |
| senken | JP | rss20 | 10 | 0.7 | trafilatura,trafilatura,trafilatura | 549 | 0/3 | 0/3 | 0/3 | same_page | items |
| wwdjapan | JP | rss20 | 100 | 3.3 | 차단 | - | 0/1 | 1/1 | 0/1 | - | - |
| note_mb | JP | rss20 | 25 | 137.0 | 유료,유료,유료 | - | 3/3 | 0/3 | 0/3 | same_page | items |
| prtimes | JP | rss10 | 200 | 3.2 | - | - | 0/0 | 0/0 | 0/0 | - | - |
| ameba | JP | - | 0 | - | - | - | 0/0 | 0/0 | 0/0 | discover_failed | items |

houyhnhnm 의 저자 3/3 은 사람 이름이 아니다. `dc:creator` 가 찍어 본 1·2페이지 10건 모두 `HOUYHNHNM` 이다(#남은 확인 거리).

prtimes 는 전체 피드의 모양만 보려고 `--samples 0` 으로 1페이지만 받았다. ameba 는 후보가 0건이라 표본이 없다.

## 제외

| key | 이유 |
|---|---|
| wwdjapan | 첫 표본 기사(`/articles/2501388`)가 403 이다. 09-16 에도 첫 기사가 403 이었다. 제외 규칙(표본에 403 이 하나라도 있으면 뺀다)에 걸린다 |
| figaro_jp | 섹션 피드 추측 `/fashion/feed/` 가 403 이다. 받은 뒤로 이 호스트는 치지 않았다. 표본 기사는 받지 못했다 |
| fashionnetwork_jp | 재측정. 피드 `jp.fashionnetwork.com/rss/` 가 403 이다. 09-16 은 Network unreachable 이었다 |
| beams | 재측정. 목록 `www.beams.co.jp/blog/` 가 20초 읽기 타임아웃을 세 번 냈다(세션 재시도 2회 포함). 09-16 도 같은 타임아웃이었다 |
| note_mb | 표본 3건이 전부 유료 표시다. 제외 규칙(전부 유료면 뺀다)에 걸린다 |
| prtimes | 패션 분류 피드를 찾지 못했다. 실측 주소 `index.rdf` 는 전 업종 보도자료다. 추측 셋은 #고른 것 |
| ameba | 피드 item 에 guid 가 없다. link 끝 조각이 `entry-12979068155.html` 이라 `url_path_segment` 도 못 쓴다(점이 섞인 조각은 받지 않는다). 지금 규칙 셋으로는 id 를 못 뽑는다. 1·2·999페이지 모두 후보 0건, 발견 실패 10건이다 |
| hatena | 고른 블로그의 최신 글이 2,094일 전이다(09-16). 291 경계 밖이라 이번에 재지 않았다 |

- **figaro_jp 는 403 을 차단 신호로 봤다.** 제외 규칙은 기사 페이지 403 만 적는다. 피드 추측 주소의 403 은 규칙에 없다. 불변식 2 가 403 뒤로 그 호스트를 멈추게 하므로 같은 날 다른 주소로 다시 치지 않았다. 다시 잴지는 따로 정한다.
- **ameba 는 `link_hash` 규칙이 생기면 들어올 수 있다.** `source-discovery.md` #3.2 가 필요해지면 따로 더한다고 적어 둔 규칙이다. 이번 묶음에서는 규칙을 더하지 않았다.

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다. 2p 가 `ok` 인 파라미터만 프로필에 적었다.

| key | `paged` | `page` | 프로필 |
|---|---|---|---|
| mensnonno | ok / 404 | 안 잼 | `paged` |
| fudge | ok / 404 | 안 잼 | `paged` |
| oggi | ok / 404 | 안 잼 | `paged` |
| houyhnhnm | ok / 파싱 실패 | 안 잼 | `paged` |
| vogue_jp | 안 잼 — vogue_uk 와 같은 Condé Nast 피드 | ok / 400 | `page` |
| cancam | ok / items | 안 잼 | `paged` |
| fashionsnap | same_page / items | same_page / items | 없음 |
| senken | same_page / items | same_page / items | 없음 |
| note_mb | 안 잼 | same_page / items | 제외 |
| ameba | discover_failed / items | 안 잼 | 제외 |

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| mensnonno | `/fashion/feed/` | `guid_query_param` `p` | 실측 주소 `/blog/feed/` 는 블로그 글이다. `/fashion/feed/` 는 15건을 주고 찍어 본 1·2페이지 10건의 분류가 전부 `最新ファッション` 이다. `/feed/` 도 15건, `/category/fashion/feed/` 는 0건이다. guid 가 `?p=800867` 꼴이다 |
| fudge | `/fashion/feed/` | `guid_query_param` `p` | 실측 주소가 이미 패션 피드다. guid 가 `?p=403164` 꼴이다 |
| oggi | `/fashion/feed` | `guid_query_param` `p` | 실측 주소가 이미 패션 피드다. guid 가 `?p=7943512` 꼴이다 |
| houyhnhnm | `/feed` (전체) | `guid_hash` | `/fashion/feed`·`/fashion/feed/` 는 404 다. `/category/fashion/feed` 는 `/fashion/feed/` 로 301 이다. `/news/feed` 는 18건을 주는 뉴스 피드다. 사이트가 패션 전문이라 전체 피드를 쓴다. guid 는 `https://www.houyhnhnm.jp/news/1170474/` 꼴의 기사 주소다 |
| vogue_jp | `/feed/rss` (전체) | `guid_hash` | `/feed/fashion/rss` 는 200 이지만 0건이다. `/feed/category/fashion/latest/rss` 는 404 다. guid 는 vogue_uk 와 같은 24자리 16진 객체 id 다. 1·2페이지 60건이 전부 그 모양이다 |
| cancam | `/feed` (전체) | `guid_query_param` `p` | `/fashion/feed`·`/category/fashion/feed` 는 200 이지만 0건이다. 1·2·999페이지 45건의 guid 가 전부 `?p=` 꼴이다. 999페이지(2023-03)도 같다 |
| fashionsnap | `/rss.xml` (전체) | `guid_hash` | 업계지라 전체가 패션이다. guid 는 기사 주소다. `/article/2026-09-18/<슬러그>/`, `/article/<슬러그>/`, `/streetstyle/2026-09-18/534137/` 로 모양이 섞여 숫자 id 가 없다 |
| senken | `/posts/feed.xml` (전체) | `guid_hash` | 업계지라 전체가 패션이다. guid 는 `/posts/isseymiyake-260918` 꼴의 슬러그 주소다 |
| prtimes | 제외 | - | `/fashion/` 페이지의 피드 링크는 `index.rdf` 하나다. `/fashion/index.rdf`·`/fashion/rss` 는 404 다 |

- **prtimes 는 첫 실제 RSS 1.0 피드다.** 어댑터가 200건을 실패 없이 읽었다. item 은 `rdf:about` 에 기사 주소를 싣고 `<link>` 와 같다. 발행일은 `dc:date` 에 `2026-09-18T14:00:42+09:00` 꼴로 온다. `content:encoded`·`dc:subject`·`dc:creator` 는 없다. item 은 발행일 순이 아니다 — 1페이지 둘째 item 이 나머지보다 하루 전 글이다.
- **country 는 발행 법인의 소재지다.** 集英社·三栄·小学館·コンデナスト・ジャパン·レコオーランド·繊研新聞社 는 알려진 법인 이름으로 적었다. 이번에 사이트 표기로 다시 확인하지는 않았다. HOUYHNHNM 은 도쿄 발행처라는 것만 보고 `JP` 로 적었고, 법인 이름은 모른다.
- **호스트를 나눠 쓰는 소스는 없다.** 등록한 8곳의 호스트는 다른 등록 소스와 겹치지 않는다.

## 남은 확인 거리

- **houyhnhnm 의 `?paged=999` 는 200 이지만 피드가 아니다.** 103KB 본문이 XML 로 읽히지 않는다. 백필은 404·410·빈 피드만 피드 끝으로 본다. 6개월에 닿기 전에 피드가 끝나면 백필이 파싱 오류로 멈춘다. 1페이지 18건이 2.9일 치라 6개월은 약 60페이지다. 과거분 채움 하위 작업에서 본다.
- **vogue_jp 의 `?page=999` 는 400 이다.** vogue_uk 와 같다. 과거분 채움 하위 작업에서 본다.
- **cancam 은 999페이지에도 기사를 준다(2023-03).** 백필은 발행일로 멈춘다.
- **houyhnhnm 의 저자는 사이트 이름이다.** `dc:creator` 가 찍어 본 10건 모두 `HOUYHNHNM` 이다. 프로필에 저자 칸이 없어서 이 값이 `author` 로 실린다.
- **cancam 전체 피드에는 연예 기사가 많다.** 표본 3건이 전부 `エンタメ` 분류다. 패션 분류 피드 추측 둘은 0건이었다.
- **senken 본문이 짧다(332~1428자).** 표본 3건에 유료 표시는 없다. 비회원에게 앞부분만 주는지는 확인하지 못했다.
- **fashionsnap 은 1.2일에 95건이다.** 페이지 넘김이 없다. 1시간 수집 주기로는 넉넉하다. `/streetstyle/` 글은 사진 위주라 본문이 196자였다.
