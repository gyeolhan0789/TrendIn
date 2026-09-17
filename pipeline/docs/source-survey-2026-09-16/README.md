# 다국가 패션 소스 조사·실측 (2026-09-16)

S15P21A102-282 의 근거 자료다. 291(1차 46곳 등록)의 PR 이 이 측정 표를 붙인다. 결정은 여기가 아니라 282 스토리와 개정될 `web-collect.md` · `source-discovery.md`(283)에 있다.

## 파일

| 파일 | 내용 |
|---|---|
| `survey.md` | 유형 9가지 × 국가 조사. 대상 사이트를 치지 않고 검색·공식 문서만 봤다(② 출처 / ③ 추정) |
| `probe/results.csv` | 81곳 실측, 사이트당 한 줄. `conclusion` 이 최종 판정, `conclusion_auto` 는 자동 판정 |
| `probe/results_raw.csv` | 사람이 고치기 전 자동 결과. 고친 이유는 `finalize.py` |
| `probe/ccnews.json` | CC-NEWS 하루 파일 수·크기, 파일 하나의 후보 도메인 적중 수 |
| `probe/retail_anchors.json` | 리테일러 목록 페이지의 링크 주소·제목 |
| `probe/*.py` | `sites.py` 후보 목록, `probe.py` 피드·기사 측정, `ccnews.py`, `finalize.py` |
| `probe/requirements.lock.txt` | trafilatura 2.2.0 · feedparser 6.0.14 · warcio 1.8.1 |
| `probe/run.log` · `ccnews.log` | 실행 로그. 경로는 실행 당시 세션 scratchpad 다 |

## 측정 규칙

UA `TrendInBot/0.1 (non-profit student project; trend analysis)`, 같은 호스트 직렬 3초, 사이트당 피드 1장 + 기사 최대 3장, 재시도 없음. 403·429 면 그 호스트를 멈췄다. robots.txt 는 기록만 했다. 본문은 길이만 재고 버렸고 파일에 남은 텍스트는 제목뿐이다.

판정 기준:

- **전문 피드**: 피드 본문 길이 ÷ 같은 기사의 trafilatura 추출 길이, 중앙값 0.7 이상.
- **기사 추출 가능**: 3건 중 2건 이상이 300자(일·중·한 150자) 초과.

## 결과

| 결론 | 수 |
|---|---|
| 요약 피드 + 기사 페이지 추출 | 24 (ld+json 만으로 11, trafilatura 필요 13) |
| 전문 피드 | 22 |
| 피드 없음 (리테일러 5곳 포함) | 19 |
| 차단 (전부 첫 요청 403) | 9 |
| 측정 실패 (네트워크·TLS·DNS·타임아웃) | 5 |
| 요약 피드인데 추출 실패 (네이버 블로그, 브런치) | 2 |
| 이미지뿐 / CC-NEWS 후보 | 0 / 0 |

| 국가 | 전문 | 요약+추출 | 추출 실패 | 피드 없음 | 차단 | 측정 실패 |
|---|---|---|---|---|---|---|
| 미국 | 3 | 7 | 0 | 1 | 3 | 0 |
| 영국 | 3 | 4 | 0 | 2 | 2 | 0 |
| 일본 | 9 | 5 | 0 | 3 | 0 | 2 |
| 프랑스 | 2 | 2 | 0 | 1 | 2 | 0 |
| 이탈리아 | 3 | 2 | 0 | 0 | 1 | 1 |
| 중국 | 1 | 1 | 0 | 3 | 1 | 1 |
| 한국 | 0 | 2 | 2 | 6 | 0 | 1 |
| 기타 | 1 | 1 | 0 | 3 | 0 | 0 |

`survey.md` 와 어긋난 곳: Condé Nast `/feed/rss` 7곳은 모두 요약 피드지만 기사 ld+json `articleBody` 에 전문이 있다. Fashionista 의 `.rss/excerpt/` 는 이름과 달리 전문이다. i-D · L'Officiel · Numéro · CanCam · Madame Figaro JP · ELLE China · 繊研新聞은 조사에서 못 찾았는데 피드가 있었다.

CC-NEWS 는 하루 9~15파일(파일당 약 1.07GB, 하루 13~16GB)이고 URL 인덱스가 없다. 09-15 파일 하나(response 21,528건)에서 후보 도메인 적중 0건, 후보 17곳이 CCBot 을 루트부터 막는다. 그래서 보류했다(289).

## 확인 못 한 것

- 페이월 사이트(BoF · WWD · Drapers · 繊研 · note · Journal du Textile)의 추출분이 전문인지 티저인지.
- 측정 실패 5곳: FashionNetwork JP(unreachable), 时尚芭莎 · MF Fashion(TLS 인증서 만료 — 측정 환경 문제일 수도), BEAMS(타임아웃), 패션인사이트(DNS). 291 에서 다시 잰다.
- PR TIMES · 뉴스와이어 · 美通社의 패션 분류 피드 주소.
- 블로그 대표 선정이 약하다(수년째 글 없음, 티스토리 미측정). 288 에서 다시 고른다.
- 하루 발행 수는 피드 1장의 날짜 폭 추정이라 섹션 피드와 사이트 전체 피드를 그대로 비교하면 안 된다.
