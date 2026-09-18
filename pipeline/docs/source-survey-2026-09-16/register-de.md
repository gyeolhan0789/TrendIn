# 독일 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. 소스는 highsnobiety 한 곳이다. 09-16 실측의 국가 칸은 `DE/INTL` 이었다.

## 명령

```
python -m trendin.fashion.collect.probe highsnobiety --check --header --page-param paged
python -m trendin.fashion.collect.probe highsnobiety --check --samples 0 --page-param page
```

첫 줄은 피드 1페이지, 표본 기사 3건, 2페이지, 999페이지를 친다. 둘째 줄은 기사를 받지 않고 `page` 만 잰다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다. 표본 기사에서 403·429 를 받은 것은 없다.

guid 모양을 보려고 피드 1페이지를 같은 세션으로 한 번 더 받았다. 섹션 피드 추측은 첫 주소에서 403 을 받아 멈췄다(#고른 것).

## 측정 표

표본을 받은 실행(`paged`)의 줄을 그대로 옮겼다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| highsnobiety | DE | rss20 | 16 | 0.5 | trafilatura,trafilatura,trafilatura | 2687 | 0/3 | 0/3 | 0/3 | same_page | items |

## 제외

없다.

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다.

| key | `paged` | `page` | 프로필 |
|---|---|---|---|
| highsnobiety | same_page / items | same_page / items | 없음 |

두 파라미터 모두 1페이지와 같은 16건을 준다. 그래서 백필 대상이 아니다.

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| highsnobiety | `/feeds/rss` (전체) | `guid_hash` | guid 가 `https://www.highsnobiety.com/p/<슬러그>/` 꼴의 퍼머링크다. 숫자 id 가 없다 |

- **섹션 피드는 없다고 보고 전체 피드를 적었다.** 추측 셋 중 첫 주소 `/feeds/rss/style` 이 403 이었다. 세션은 403 을 받으면 그 호스트를 멈춘다. 그래서 나머지 둘(`/feeds/rss?category=style`, `/style/feed`)은 치지 않았다. 403 뒤에는 다시 치지 않는다는 규칙에 따랐다.
- **저자는 0/3 이다.** 피드에 `dc:creator` 도 `<author>` 도 없다. 기자 이름은 `content:encoded` 본문 첫 줄(`By ...`)에만 있다.
- **피드 응답의 Content-Type 은 `application/octet-stream` 이다.** 파서는 그대로 읽었다(16건, 실패 0건).
- **country 는 발행 법인의 소재지다.** 사이트 Imprint 의 발행 법인은 Titel Media GmbH(베를린, Amtsgericht Charlottenburg HRB 125489 B)다. 이 값은 웹 검색 결과의 Imprint 요약과 기업 등기 요약 사이트로 확인했다. Imprint 페이지를 직접 열지는 않았다. 2022년 Zalando 가 인수했지만 발행 법인은 그대로 베를린이다.
- 호스트 `www.highsnobiety.com` 을 쓰는 다른 등록·후보 소스는 없다.

## 남은 확인 거리

- **피드가 16건 0.5일 치다.** 1시간 주기로는 넉넉하다. 수집이 반나절 넘게 멈추면 그 사이 기사를 잃는다. 페이지 넘김이 없어서 백필로 메울 수도 없다.
- **없는 경로에 404 가 아니라 403 을 준다.** `/feeds/rss/style` 한 번만 봤다. 이 호스트는 없는 주소를 403 으로 답하는 것으로 보인다. 그렇다면 주기 수집 중 기사가 지워졌을 때도 403 이 나고 세션이 그 실행에서 호스트를 멈출 수 있다. 수집 로그에서 403 이 나오는지 본다.
- **패션만 주는 피드가 아니다.** 전체 피드라 채널 설명대로 스니커·스트리트웨어 밖의 라이프스타일 기사도 섞일 수 있다. 표본 셋은 모두 패션·스니커 기사였다.
