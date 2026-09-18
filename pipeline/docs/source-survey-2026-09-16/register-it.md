# 이탈리아 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. 09-16 에 측정이 실패한 mffashion 도 같은 날 다시 쟀다.

## 명령

```
python -m trendin.fashion.collect.probe <key> --check --header --page-param paged
python -m trendin.fashion.collect.probe <key> --check --samples 0 --page-param page
```

첫 줄은 피드 1페이지, 표본 기사 3건, 2페이지, 999페이지를 친다. 둘째 줄은 기사를 받지 않고 `page` 만 잰다.
vogue_it 는 첫 줄을 `--page-param page` 로 한 번만 돌렸다. vogue_uk 와 같은 Condé Nast 피드라서 `paged` 는 재지 않았다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다.

섹션 피드 추측은 같은 세션으로 주소마다 한 번씩 쳤다(#고른 것). pambianco 는 그 첫 추측에서 403 을 받았고, 그 뒤로 그 호스트를 치지 않았다(#제외).

## 측정 표

표본을 받은 실행의 줄을 그대로 옮겼다. 2p·끝 페이지 칸은 그 실행의 `--page-param` 값으로 잰 것이다. vogue_it 는 `page`, 나머지는 `paged` 다. 파라미터별 결과는 #페이지 넘김에 있다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| vogue_it | IT | rss20 | 50 | 1.8 | ld_json,ld_json,ld_json | 1995 | 0/3 | 0/3 | 3/3 | ok | 400 |
| grazia_it | IT | rss20 | 10 | 1.2 | feed,feed,feed | 2570 | 0/3 | 0/3 | 3/3 | not_older | items |
| iodonna | IT | rss20 | 10 | 1.9 | feed,feed,feed | 3093 | 0/3 | 0/3 | 3/3 | ok | items |
| elle_it | IT | rss20 | 50 | 7.4 | ld_json,ld_json,ld_json | 2154 | 0/3 | 0/3 | 0/3 | same_page | items |

grazia_it 줄은 등록하지 않은 초안 프로필(`article_id` = `url_path_segment` `-1`)로 잰 것이다(#제외).
elle_it 의 저자 0/3 은 피드에 `dc:creator` 가 없어서다.

## 제외

| key | 이유 |
|---|---|
| pambianco | 이번 첫 요청(섹션 피드 추측 `/category/moda/feed/`)이 403 이다. 첫 요청이 403 인 곳은 자동 탈락이다(`source-discovery.md` #4). 09-16 에는 피드·기사 모두 200 이었다 |
| mffashion | 재측정도 실패했다. 세션의 첫 요청(`https://www.mffashion.com/`)이 인증서 검증에서 끊겼다. `openssl s_client` 로 본 서버 인증서가 2026-03-31 에 만료됐다(`CN=mffashion.com`, RapidSSL 발급). 우리 환경 문제가 아니라 서버 쪽이다. TLS 검증은 끄지 않았다 |
| grazia_it | 보류. 피드의 guid 가 전부 빈 값이다. id 는 link 끝 조각의 꼬리(`…-fiocco-997998`)에만 있다. 지금 규칙으로는 슬러그째 받는 `url_path_segment` `-1` 뿐이고, 그러면 제목이 바뀔 때 같은 기사가 두 번 들어온다(`web-collect.md` #5.1 `article_id`) |

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다. 2p 가 `ok` 인 파라미터만 프로필에 적었다.

| key | `paged` | `page` | 프로필 |
|---|---|---|---|
| vogue_it | 안 잼 — vogue_uk 와 같은 Condé Nast 피드 | ok / 400 | `page` |
| grazia_it | not_older / items | not_older / items | 없음(보류) |
| iodonna | ok / items | 안 잼 | `paged` |
| elle_it | same_page / items | same_page / items | 없음 |

grazia_it 의 `paged` 2페이지는 1페이지와 1건이 겹쳤다. `page` 2페이지는 9건이 겹쳤다. `page` 는 무시되고, 두 실행 사이에 새 글이 하나 끼어든 것으로 보인다. 그렇다면 `paged` 는 실제로 넘어가는데 새 글 때문에 not_older 로 잰 것일 수 있다(#남은 확인 거리).

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| vogue_it | `/feed/rss` (전체) | `guid_hash` | 추측 둘(`/feed/moda/rss`, `/feed/category/moda/latest/rss`)이 404 다. guid 는 vogue_uk 와 같은 24자리 16진 객체 id 다 |
| iodonna | `/moda/feed/` | `guid_query_param` `p` | 워드프레스 섹션 피드가 있다. guid 가 `https://www.iodonna.it/?p=2843743` 꼴이다. 999페이지에서도 발견 실패가 없었다 |
| elle_it | `www.elle.com/it/rss/moda.xml` | `url_path_segment` `-2` | 실측 주소 `/it/rss/all.xml` 옆에 moda 피드가 있다. link 가 `/it/moda/<하위 섹션>/a73755883/<슬러그>/` 꼴이다. 표본 셋(a73755883·g73521464·a73768470)이 하위 섹션이 달라도 같은 자리였다. 1페이지 50건 전부 끝에서 둘째 조각이 `a<숫자>` 36건, `g<숫자>`(갤러리) 14건이다 |
| grazia_it (보류) | `/moda/feed` | - | 섹션 피드가 있다. 전체 `/feed` 는 살림·별자리 기사도 섞인다 |

- **elle_it 는 elle_us 와 호스트를 같이 쓴다.** 둘 다 `www.elle.com` 이다. 허용 범위를 `https://www.elle.com/it/` 로 좁혔다. 같은 호스트의 호스트 간격은 한 프로세스 안에서만 지켜진다. 두 소스가 다른 태스크로 돌면 `www.elle.com` 을 동시에 칠 수 있다. 겹침은 받아들이기로 이미 정했다.
- **vogue_it 피드의 50건 중 12건이 별자리 운세다.** `/oroscopo/article/oroscopo-oggi-gemelli` 같은 글이 guid 는 그대로 두고 발행일만 매일 바꾼다. `guid_hash` 라 처음 본 날 한 번만 저장되고 그 뒤로는 건너뛴다. 패션 섹션 피드가 없어서 걸러 낼 방법이 없다.
- **iodonna 는 전체 피드가 하루 80건쯤이다(09-16 실측 81.4).** 전체 대신 moda 섹션 피드를 골랐다. 10건이 1.9일 치라 1시간 수집 주기로는 넉넉하다.
- **country 는 발행 법인의 소재지다.** Edizioni Condé Nast S.p.A.·RCS MediaGroup S.p.A.(iO Donna)·Hearst Magazines Italia S.p.A. 는 알려진 이탈리아 법인 이름으로 적었다. 이번에 사이트 표기로 다시 확인하지는 않았다.

## 남은 확인 거리

- **vogue_it 의 `?page=999` 는 400 이다.** vogue_uk 와 같다. 백필은 404·410·빈 피드만 피드 끝으로 본다. 과거분 채움 하위 작업에서 본다.
- **iodonna 는 999페이지에도 기사를 준다.** 백필은 발행일로 멈춘다.
- **grazia_it 는 id 규칙을 정하면 넣을 수 있다.** 본문은 피드 전문으로 받았다. 유료·403 도 없다. 링크 끝 조각의 숫자 꼬리를 뽑는 규칙을 더하거나, 슬러그 id 를 감수하고 `url_path_segment` `-1` 로 넣는 것 중 하나를 정해야 한다. 넣을 때 `paged` 를 다시 잰다.
- **pambianco 의 403 이 봇 UA 차단인지 한때의 것인지 모른다.** 규칙대로 다시 치지 않았다.
