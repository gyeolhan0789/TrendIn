# 프랑스 묶음 등록 측정 (S15P21A102-291)

2026-09-18 에 쟀다. 영국 묶음(`register-uk.md`)과 같은 명령, 같은 세션이다.

## 명령

```
python -m trendin.fashion.collect.probe <key> --check --header --page-param paged
python -m trendin.fashion.collect.probe <key> --check --samples 0 --page-param page
```

첫 줄은 피드 1페이지, 표본 기사 3건, 2페이지, 999페이지를 친다. 둘째 줄은 기사를 받지 않고 `page` 만 잰다.
세션은 기본 봇 UA 이고 호스트 간격 3초를 지킨다. 403·429 를 받은 표본은 없다.

guid 모양과 섹션 피드 추측은 같은 세션으로 주소마다 한 번씩 쳤다(#고른 것).

journaldutextile 은 첫 실행이 999페이지에서 죽었다. 빈 본문의 301 을 피드로 파싱하다 난 오류다. 어댑터를 고친 뒤(커밋 `fix: 피드 페이지가 200 이 아니면 …`) 같은 명령을 한 번 더 돌렸다. 그래서 이 소스만 표본 기사 3건을 두 번 받았다.

## 측정 표

표본을 받은 실행의 줄을 그대로 옮겼다. 2p·끝 페이지 칸은 그 실행의 `--page-param` 값으로 잰 것이다 — vogue_fr 는 `page`, 나머지는 `paged`. 파라미터별 결과는 #페이지 넘김에 있다.

| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 | 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|
| vogue_fr | FR | rss20 | 30 | 0.9 | ld_json,ld_json,ld_json | 4920 | 0/3 | 0/3 | 3/3 | ok | 400 |
| lofficiel | FR | rss20 | 60 | 9.4 | feed,feed,feed | 2162 | 0/3 | 0/3 | 0/3 | same_page | items |
| numero | FR | rss20 | 9 | 4.8 | trafilatura,trafilatura,trafilatura | 11518 | 0/3 | 0/3 | 3/3 | ok | 404 |
| journaldutextile | FR | rss20 | 10 | 36.4 | trafilatura,trafilatura,trafilatura | 6536 | 0/3 | 0/3 | 3/3 | ok | 301 |

numero 의 1p 건수 9 는 `guid_query_param` `p` 로 잰 값이다. 옛 모양 guid 1건이 빠졌다. `guid_hash` 로 바꾼 재실행(`--samples 0`)에서는 1p·2p 모두 10건이고 실패가 없다(#고른 것).

lofficiel 의 본문 경로는 3건 다 `feed` 다. 09-16 실측에서 기사 페이지는 trafilatura 가 3건 모두 663자로 페이지 틀만 뽑았다. 본문 규칙이 더 긴 피드 본문(`content:encoded`)을 골랐다.

lofficiel 의 저자 0/3 은 피드에 `dc:creator` 가 없어서다.

## 제외

없다. 네 곳 모두 표본이 무료이고 403·429 가 없다. journaldutextile 의 최신 글은 측정 당일(09-18) 글이라 오래된 피드도 아니다.

## 페이지 넘김

칸은 `2p 판정 / 999페이지` 다. 2p 가 `ok` 인 파라미터만 프로필에 적었다.

| key | `paged` | `page` | 프로필 |
|---|---|---|---|
| vogue_fr | 안 잼 — vogue_uk 와 같은 Condé Nast 피드 | ok / 400 | `page` |
| lofficiel | same_page / items | same_page / items | 없음 |
| numero | ok / 404 | 안 잼 | `paged` |
| journaldutextile | ok / 301 | 안 잼 | `paged` |

## 고른 것

| key | 피드 주소 | article_id | 근거 |
|---|---|---|---|
| vogue_fr | `/feed/rss` (전체) | `guid_hash` | 추측 둘(`/feed/fashion/rss`, `/feed/mode/rss`)이 404 다. guid 는 vogue_uk 와 같은 24자리 16진 객체 id 다 |
| lofficiel | `/feed.rss` (전체) | `guid_hash` | `/fashion/feed.rss` 는 200 이지만 피드가 아니라 HTML 이다. `/fashion.rss` 는 404 다. guid 는 기사 퍼머링크다 |
| numero | `/category/mode/feed/` | `guid_hash` | 워드프레스 카테고리 피드가 있다. guid 가 `?p=889624` 꼴과 `https://numero.insinio.fr/<섹션>/<슬러그>/` 꼴 둘이다. 2페이지에서 `guid_query_param` 이 10건 중 2건 실패했다(theindustry 와 같은 경우) |
| journaldutextile | `/feed` (전체) | `guid_hash` | 업계지라 전체 피드가 패션·섬유다. guid 는 기사 퍼머링크다 |

- **country 는 발행 법인의 소재지다.** 넷 다 `FR` 이다.
  - vogue_fr 는 알려진 법인 이름(Les Publications Condé Nast SA)으로 적었다. 사이트 표기로 다시 확인하지는 않았다.
  - numero 는 사이트 법적 고지에 Numéro Presse SAS(파리 17구)가 발행처로 적혀 있다.
  - journaldutextile 은 사이트 법적 고지에 Alea Conseil(파리 9구)이 발행처로 적혀 있다.
  - lofficiel 은 사이트 법적 고지를 확인하지 못했다. 파리 등기부에 L'Officiel France Publishing(파리 1구)이 있어 `FR` 로 적었다. 이 법인이 lofficiel.com 을 발행하는지는 확인하지 못했다.
- **numero 의 `/mode/feed/` 는 200 에 빈 본문이다.** 카테고리 피드는 `/category/mode/feed/` 에 있다.
- **호스트 공유는 없다.** 네 호스트 모두 다른 등록 소스와 겹치지 않는다.

## 남은 확인 거리

- **journaldutextile 의 `?paged=999` 는 빈 본문의 301 이다.** 어댑터는 이제 이것을 상태코드 301 의 실패로 낸다. 백필은 404·410·빈 피드만 피드 끝으로 보므로 6개월에 닿기 전에 피드가 끝나면 오류로 멈춘다. 1p 10건이 36일 치라 6개월은 약 5페이지다. 과거분 채움 하위 작업에서 본다.
- **vogue_fr 의 `?page=999` 는 400 이다.** vogue_uk·glamour_uk 와 같은 문제다.
- **lofficiel 은 페이지 넘김이 없다.** 한 피드가 60건·9.4일 치라 1시간 주기 수집에는 넉넉하다. 과거분은 채울 수 없다.
- **lofficiel 은 기사 페이지를 받아도 본문은 피드에서 온다.** raw 로는 페이지 HTML 을 저장한다(285 결정). 페이지에서 본문이 나오지 않는 것은 09-16 실측과 같다.
- **journaldutextile 의 본문 길이가 세 건 다 6.3천~6.5천 자다.** 09-16 에도 7.4천~8.1천 자로 비슷했다. 페이지 틀이 섞였는지 저장 표본으로 확인한다.
- **vogue_fr 에는 패션이 아닌 글도 들어온다.** 표본 셋이 뷰티·점성술 기사였다. 패션만 주는 피드는 찾지 못했다.
