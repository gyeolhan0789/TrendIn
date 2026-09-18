# 중국 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. 09-16 측정 실패였던 bazaar_cn(时尚芭莎)도 같은 날 다시 쟀다.

## 명령

```
python -m trendin.fashion.collect.probe <key> --check --header --page-param paged
python -m trendin.fashion.collect.probe <key> --check --header --page-param page
python -m trendin.fashion.collect.probe <key> --check --samples 0 --page-param paged
```

luxe_co 는 첫 줄만 돌렸다. elle_cn 은 둘째 줄로 표본을 받았고, 셋째 줄로 `paged` 만 쟀다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다. 403·429 를 받은 표본은 없다.

섹션 피드 추측과 발행 법인 확인은 같은 세션으로 주소마다 한 번씩 쳤다(#고른 것).
bazaar_cn 은 같은 세션으로 첫 화면을 한 번 쳤다(#제외).

## 측정 표

최종 피드 주소로 표본을 받은 실행의 줄을 그대로 옮겼다. 2p·끝 페이지 칸은 그 실행의 `--page-param` 값으로 잰 것이다. elle_cn 은 `page`, luxe_co 는 `paged` 다. 파라미터별 결과는 #페이지 넘김에 있다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| elle_cn | CN | rss20 | 43 | 29.4 | ld_json,ld_json,ld_json | 1842 | 0/3 | 0/3 | 0/3 | same_page | items |
| luxe_co | CN | rss20 | 10 | 6.1 | trafilatura,trafilatura,trafilatura | 1721 | 0/3 | 0/3 | 3/3 | ok | items |

- **본문 길이는 한자 기준으로 넉넉하다.** 09-16 조사는 한자 본문의 추출 가능 기준을 150자로 잡았다. 표본 여섯 건 중 가장 짧은 것이 luxe_co 332자, elle_cn 923자다.
- **elle_cn 은 유료 0/3 이다.** 09-16 조사표에는 `paywall` 단서가 찍혀 있었다. 이번 표본 셋의 ld+json 에는 유료 표시가 없고 본문이 ld+json 으로 다 나왔다. 제외 규칙(전부 유료면 뺀다)에 걸리지 않는다.
- **elle_cn 의 저자는 0/3 이다.** 피드 item 에 `dc:creator` 가 없다.

## 제외

| key | 이유 |
|---|---|
| bazaar_cn | 재측정도 실패했다. `https://www.bazaar.com.cn/` 가 TLS 검증에서 `CERTIFICATE_VERIFY_FAILED: certificate has expired` 로 끊긴다. 서버가 내미는 인증서(`*.bazaar.com.cn`, GoDaddy G2)의 만료일이 2020-01-13 이다. 우리 환경 문제가 아니라 사이트 인증서 문제다. 검증은 끄지 않았다 |

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다. 2p 가 `ok` 인 파라미터만 프로필에 적었다.

| key | `paged` | `page` | 프로필 |
|---|---|---|---|
| elle_cn | same_page / items — 전체 피드 `/rss/default.xml` 로 잼 | same_page / items | 없음 |
| luxe_co | ok / items — 전체 피드 `/feed` 와 패션 피드 둘 다 같음 | 안 잼 | `paged` |

elle_cn 의 `paged` 는 섹션 피드로 바꾸기 전에 쟀다. 두 파라미터 모두 1페이지와 같은 바이트 수를 돌려줬다.

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| elle_cn | `www.ellechina.com/rss/fashion.xml` | `url_path_segment` `-2` | 실측 주소 `/rss/default.xml` 은 뷰티 기사도 섞인 전체 피드다. 추측 셋 중 `/rss/fashion.xml` 이 채널 제목 "Fashion - ELLE China" 인 패션 피드다. `/rss/fashion.xml/` 은 같은 피드이고, `/rss/fashion/all.xml` 은 전체 피드("Latest Content")를 준다. link 가 `/<섹션>/<하위섹션>/a73776759/<슬러그>/` 꼴이라 뒤에서 둘째 조각이 id 다. 표본 셋(a73776759·a73776278·a73778026)과 전체 피드 표본(`/beauty/beauty-news/a73782430/…`)이 같은 자리였다 |
| luxe_co | `luxe.co/category/fashion/feed` | `guid_query_param` `p` | 워드프레스 카테고리 피드가 있다. `/tag/fashion/feed` 는 200 이지만 item 이 없다. guid 가 `?p=` 꼴이고 값이 link `/post/482378` 의 숫자와 같다. 999페이지 10건도 실패 0건이라 옛 글의 guid 모양도 같다 |

- **country 는 발행 법인의 소재지다.** 두 곳 모두 사이트 바닥의 저작권·ICP 표기로 확인했다. elle_cn 은 北京赫斯特广告有限公司(첫 화면), luxe_co 는 华丽集（常州）网络科技有限公司(기사 페이지 한 장)다.
- **호스트를 다른 소스와 나눠 쓰지 않는다.** `www.ellechina.com`·`luxe.co` 는 등록했거나 대기 중인 다른 소스에 없다.

## 남은 확인 거리

- **luxe_co 는 999페이지에도 기사를 준다.** 전체 피드와 패션 피드 둘 다 그렇다. 백필은 발행일로 멈춘다.
- **elle_cn 은 페이지 넘김이 없다.** 패션 피드 43건이 29.4일 치라 1시간 수집 주기로는 넉넉하다. 과거분은 이 피드로 채울 수 없다.
- **bazaar_cn 은 인증서가 갱신되면 다시 잴 수 있다.** 291 댓글로 남긴다.
