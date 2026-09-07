# 웹 수집 설계 — 패션 매거진 7곳 · Hacker News

패션 매거진 7곳과 Hacker News 에서 새 글을 주기적으로 모아 MinIO 에 쌓고, 저장이 확인된 건마다 Kafka 이벤트를 낸다.
이 문서는 **무엇을 지켜야 하는지**(결정·불변식·계약)를 적는다. 어떻게 만드는지는 구현할 때 정한다.

- 실측일: 2026-09-03. 사이트 구조는 바뀌므로 #2 의 표는 그날의 사실이다.
- 근거 등급 표기: ① 실행 결과 ② 출처 ③ 감. 표기가 없는 줄은 이 문서의 결정이다.
- 잠정값은 **(잠정)** 으로 표시한다. 확정처럼 적힌 값은 바꾸려면 이 문서를 고친다.

## 1. 범위

| | 안에 있다 | 밖에 있다 |
|---|---|---|
| 대상 | 아래 8개 소스의 새 글 | 댓글, 이미지·영상 바이너리, 검색 결과 페이지, Hacker News 의 HTML 페이지, **hypebeast 전체**(#3.2 · 확정 2-1) |
| 항목 | 제목·URL·발행일·요약·본문 텍스트·카테고리·저자 | 회원 전용 본문(#3), Hacker News 가 링크한 외부 원문(⚠️ #12) |
| 저장 | MinIO 원문 + 정규화 JSON, 앱 DB 장부 | 검색 색인, 키워드 추출 |
| 이벤트 | "기사 하나가 저장됐다" 알림 | 소비자 쪽 처리, 재처리 큐(DLQ) |
| 시간 | 지금부터의 새 글 + 피드가 허용하는 만큼의 과거분 | 아카이브 전량 백필 |

소스 목록. **도메인**은 `fashion` / `dev` 둘이다. hypebeast 는 약관 때문에 뺐다(확정 2-1).

| 소스 키 | 도메인 | 시작 URL |
|---|---|---|
| `harpersbazaar` | fashion | https://www.harpersbazaar.co.kr/fashion |
| `vogue` | fashion | https://www.vogue.co.kr/fashion/ |
| `gqkorea` | fashion | https://www.gqkorea.co.kr/style/ |
| `wkorea` | fashion | https://www.wkorea.com/fashion/ |
| `allure` | fashion | https://www.allurekorea.com/style/ |
| `marieclaire` | fashion | https://www.marieclairekorea.com/category/fashion/ |
| `cosmopolitan` | fashion | https://www.cosmopolitan.co.kr/fashion |
| `hn` | dev | https://news.ycombinator.com/newest |

## 2. 소스 조사 결과 (① 실측 2026-09-03)

브라우저 UA 와 curl 기본 UA 둘 다로 목록 페이지를 받았고, 아홉 곳 모두 200 이었다. 차단은 없다. 대신 이름을 지정한 봇 차단이 있다(아래 robots 열).

| 소스 | 플랫폼 | robots.txt `User-agent: *` | 새 글 발견 경로 | 회당 건수 | 본문 위치 | 기사 ID | 발행일 | 과거분 |
|---|---|---|---|---|---|---|---|---|
| vogue | WordPress (두산매거진 공통 템플릿) | `/wp-admin/ /search/ /preview/ /auth/` 금지. Scrapy·CCBot·GPTBot·ClaudeBot 등 이름 지정 봇은 전면 금지 | `/category/fashion/feed/` | 10 | 피드 `content:encoded` 에 전문 | guid `?p=854414` 의 숫자 | pubDate (UTC) | `?paged=N` 동작. 30페이지가 약 6주 전 |
| gqkorea | 위와 같음 | 위와 같음 | `/category/style/feed/` | 10 | 위와 같음 | 위와 같음 | 위와 같음 | 위와 같음 |
| wkorea | 위와 같음 | 위와 같음 | `/category/fashion/feed/` | 10 | 위와 같음 | 위와 같음 | 위와 같음 | 위와 같음 |
| allure | 위와 같음 | 위와 같음 | `/category/style/feed/` | 10 | 위와 같음 | 위와 같음 | 위와 같음 | 위와 같음 |
| marieclaire | WordPress (자체) | `/wp-admin/` 만 금지 | `/category/fashion/feed/` | 10 | 피드 `content:encoded` 전문. 기사 페이지 ld+json `NewsArticle.articleBody` 도 있다 | guid `?p=558420` 의 숫자 | pubDate (UTC) | `?paged=N` 동작 |
| ~~hypebeast~~ (제외) | 자체 CMS (CloudFront) | `/api /_ajax /post-content /search-suggest` 등 금지, 그 외 `Allow: /` | `/fashion/feed` | 20 | 피드 `content:encoded` 전문 | guid `?post=705465` 의 숫자 | pubDate (UTC) | 없음. `?paged=2` 가 같은 20건 |
| harpersbazaar | 자체 플랫폼 (cosmopolitan 과 동일 템플릿) | `/event/notice` 만 금지. GPTBot·CCBot 전면 금지 | 목록 HTML `/fashion` + 하위 섹션 `/fashion/{news,style,trend,sports,watchnjewelry}` | 목록 36건 (섹션별 `?offset=N` 동작) | 기사 페이지 `div.atc_body_cont`. 그 안에 로그인 마스크(`atc_mask_login`)와 관련기사(`ab_related_article`)가 섞여 있어 둘은 걷어낸다. 바깥 `atc_body` 는 크레딧·태그·추천까지 감싸서 넓다. ld+json `NewsArticle` 에 headline·datePublished·description·author 는 있고 articleBody 는 없다 | URL `/article/{숫자}` | `article:published_time` (+09:00) | 섹션 페이지 offset 으로 일부 |
| cosmopolitan | 위와 같음 | `/event/notice` 와 기사 1건 금지. GPTBot·CCBot 전면 금지 | 목록 HTML `/fashion` + 하위 섹션 `/fashion/{trends,item,howto,celebstyle,watchandjewelry}` | 목록 49건 (`?offset=20` 에서 10건 추가 후 멈춤) | 위와 같음 | 위와 같음 | 위와 같음 | 위와 같음 |
| hn | 공식 API | HTML 은 `Crawl-delay: 30`. API 는 robots 대상이 아니다 | Algolia HN Search `search_by_date?tags=story&numericFilters=created_at_i>{커서}` | 시간당 약 26건 (1회 요청 최대 1000건) | 없음. 제목·URL·점수·댓글수·작성자만 | `objectID` | `created_at_i` (epoch) | 커서로 무제한. 대안 Firebase `newstories` 는 500건 ≈ 10시간 |

특이사항.

- **harpersbazaar·cosmopolitan 의 `/rss`** 는 살아 있지만 사이트 전체 피드이고 `?category=` 파라미터를 무시한다. 카테고리는 항목 안 `cate_depth1` 태그로만 구분된다. 건수가 2건(bazaar)·10건(cosmo)이라 발견 경로로 쓰기엔 얕다. 그래서 목록 HTML 을 발견 경로로 삼는다.
- **harpersbazaar·cosmopolitan 에 회원 전용 기사가 있다.** 판정 신호는 **기사 페이지의 `div.membershipLine`** 이다 (① 재실측 2026-09-03, 표본 8/8 정확히 갈랐다). 목록 6장 기준 회원 전용은 217건 중 16건(7.4%)이다. 처리 규칙은 #7 불변식 2.
  - ⚠️ **판정에 쓰면 안 되는 것 둘.** (1) 목록 HTML 의 `membersYn` 은 **추천 위젯 JSON** 의 필드다. 그 JSON 은 페이지당 20건인데 앵커 36건 중 34건이 거기 없다 — 목록이 아니다. 목록 앵커 쪽 신호는 `div.memmark` 이고 둘은 다른 집합이다. (2) 기사 페이지의 "전체 페이지를 읽으시려면…" **마스크 문구는 8/8 전부에 있다**(숨은 모달 템플릿). 일반 기사에도 있으므로 구분자가 못 된다. `memmark` 역시 기사 페이지의 관련기사 위젯에 1~3개 나타난다.
- **두산매거진 4곳의 피드는 10건뿐**이고 vogue 는 하루치가 10건을 넘길 때가 있다(09-02 ~ 09-03 사이 10건). 주기가 길면 놓친다. #9 의 주기가 이 관찰에서 나왔다.
- **두산매거진 4곳은 WordPress REST(`/wp-json/wp/v2/posts`) 가 401** 이다. 피드가 유일한 구조화 경로다.
- **hypebeast 는 이 표에 실측 기록으로만 남는다.** 약관 8조 문언이 피드를 예외로 두지 않아 소스에서 뺐다(#3.2 · 확정 2-1). 위 행은 2026-09-03 에 실제로 잰 값이고, 다시 넣기로 하면 출발점이 된다.
- 모든 소스가 curl 기본 UA 에도 200 을 줬다. 즉 우리를 막는 건 없고, 우리가 스스로 지킬 규칙만 있다.

## 3. 법적 검토 (② 출처, 2026-09-03 조사)

전제: 비영리 학생 프로젝트. 원문은 내부 저장소에만 두고 외부에 재게시하지 않는다. 법령 조문은 국가법령정보센터(law.go.kr) 원문, 약관은 각 사이트의 약관 페이지, 판례는 판결 요지를 확인했다.

**결론.** 공개 페이지를 정상 접근으로 읽는 것 자체는 문제가 없다. 위법은 **차단 우회**와 **재게시**에서 갈린다. 야놀자 대 여기어때(대법원 2022.5.12. 선고 2021도1533)는 회원가입 없이 열린 API 를 읽은 행위를 전부 무죄로 봤다. 접근권한 제한 여부는 "보호조치나 이용약관 등 객관적으로 드러난 사정을 종합"해 본다. 잡코리아 대 사람인(대법원 2017.8.24. 선고 2017다224395)은 VPN 으로 정체를 숨기고 출처를 지운 뒤 경쟁 서비스에 재게시한 행위를 부정경쟁행위로 봤다. 이 두 사건 사이가 우리 기준선이다.

### 3.1 법령

| 법령·조문 | 우리에게 | 지키는 방법 |
|---|---|---|
| 저작권법 제16조 복제권 | **걸린다.** 본문을 MinIO 에 저장하는 것은 복제다. 제목·URL·발행일만이면 대체로 안 걸린다(제호는 독립 저작물이 아니라는 판례 법리) | 본문 보존 기간을 둔다(#9). 재게시하지 않는다(불변식 3) |
| 제30조 사적이용 | **못 쓴다.** "개인 또는 가정 및 이에 준하는 한정된 범위"가 요건이라 팀 프로젝트는 밖이다 | 기대지 않는다 |
| 제35조의5 공정이용 | **여기에 기댄다.** 비영리·비공개·키워드 추출이라는 변형적 목적. 재게시하지 않는 것이 4호(시장 영향)에 결정적이다 | 이 문서가 목적을 기록한다. 불변식 3 |
| 제37조 출처 명시 | **걸린다.** 공정이용(제35조의5)은 면제 목록에 없다 | 저장 레코드마다 URL·매체·발행일이 있다(불변식 11) |
| 제93조 데이터베이스제작자 권리 | 제2항이 "반복적이거나 특정 목적을 위해 체계적으로" 하는 소량 복제도 상당한 부분으로 본다. 매번 전체 목록을 다시 저장하면 닿는다 | 신규분만 증분 저장한다(불변식 12) |
| 텍스트·데이터마이닝(TDM) 면책 | **2026년 9월 현재 없다.** 시행 2026-08-11 저작권법(법률 제21336호) 조문 전수에서 제35조의6 부재를 확인했다. 개정안은 21대 국회에서 발의됐고 이후 상태는 미확인(#3.5) | 기대지 않는다 |
| 정보통신망법 제48조 제1항, 제4항(2024.1 신설) | **차단을 우회하지 않으면 안 걸린다.** 위반은 5년 이하 징역 또는 5천만원 이하 벌금, 미수도 처벌. 제4항은 보호·인증 절차 우회 프로그램 사용을 금지한다 | 로그인·페이월·캡차·IP 차단을 우회하지 않는다(불변식 2) |
| 부정경쟁방지법 제2조 제1호 카목·파목 | **덜 걸린다.** 카목은 부정접속·보호조치 무력화가 요건, 파목은 "자신의 영업을 위하여"가 요건이라 비영리 내부 이용은 약하다 | 정상 접근만 한다. 서비스로 수익화하는 순간 요건이 생긴다 |

### 3.2 사이트별 약관

| 사이트 | 운영 법인 | 자동 수집 금지 조항 | 그 외 | robots.txt |
|---|---|---|---|---|
| harpersbazaar.co.kr | 허스트중앙(유) | **없음** ([약관](https://www.hjmembers.co.kr/etc/term)) | **제10조 3항** "회원은 서비스를 이용하여 얻은 정보를 회사의 사전승낙 없이 복사, 복제, 변경, 번역, 출판, 방송 기타의 방법으로 사용하거나 이를 타인에게 제공할 수 없습니다" — **영리 목적 요건이 없다.** 제13조 4항은 영리목적 이용을 따로 금지. **제5조 2항** 이 회원가입 시 '동의함' 클릭을 약관 동의 의사표시로 본다 | GPTBot·CCBot 만 차단 |
| cosmopolitan.co.kr | 허스트중앙(유) | **없음** (같은 약관, 1조가 코스모폴리탄 명시) | 위와 같음 | 위와 같음 |
| ~~hypebeast.kr~~ (제외) | Hypebeast Limited (홍콩법 준거) | **있음.** [약관](https://hypebeast.kr/terms) 8조 원문: *"Use any **automated or non-automated** means to access, copy or distribute **any portion of the website** or collect any information from the website, including without limitation, the use of so-called 'robots', 'spiders', 'offline readers', etc."* 10조가 aggregating 을 따로 금지한다 | 문언이 수단도 자동·수동도 가리지 않고 대상이 "website 의 어느 부분"이라 **RSS 피드가 예외로 빠질 자리가 없다.** 사이트가 피드를 공개 광고하는 것과는 별개다 | 사실상 전부 허용 |
| vogue · gqkorea · wkorea · allure | 두산매거진 | 없음. 자체 약관은 못 찾았고 [법적 고지](https://www.doosanmagazine.com/etc/legal-notice)가 "사적·비상업 열람 외 복제 금지" | 고지의 적용 범위가 각 매체 도메인까지인지 문언상 불분명 | **Scrapy 를 이름으로 차단.** GPTBot·ClaudeBot·CCBot 등도 |
| marieclairekorea.com | (주)엠씨케이퍼블리싱 | 없음 ([약관](https://www.marieclairekorea.com/%ec%9d%b4%ec%9a%a9%ec%95%bd%ea%b4%80/)) | 11조 "사전 승낙 없이 복제" 금지 | `/wp-admin/` 만 차단 |

hypebeast 만 약관 문언으로 자동 수집을 금지하고, 그 문언에 피드 예외가 없다. **그래서 소스에서 뺐다(확정 2-1).** 피드만 읽는 안은 요청 수와 우회 위험은 줄이지만 약관 위반 자체는 줄이지 않는다 — "안전"이 아니라 "어차피 할 거면 가장 방어 가능한 형태"였다.

**로그인해서 수집하는 것은 익명 열람과 다른 자리다.** 허스트중앙 제5조 2항이 회원가입을 약관 동의로 보므로, 계정을 만드는 순간 우리가 계약 당사자가 되고 **영리 목적 요건이 없는** 제10조 3항이 직접 붙는다. 익명 열람이면 "약관에 동의한 적 없다"가 다툼거리로 남지만(#3 의 야놀자 판례가 그 방향), 가입하면 그 주장이 사라진다. 그래서 회원 전용 기사는 로그인 없이 판정만 하고 본문을 저장하지 않으며(확정 8, 불변식 2), 수집기는 `Cookie`·`Authorization` 헤더를 실을 자리 자체를 두지 않는다. 로그인 수집을 하려면 어댑터 추가가 아니라 이 문서의 불변식 2 개정과 공통 기반 수정이 함께 필요하다.

### 3.3 Hacker News

| 항목 | 내용 |
|---|---|
| 사이트 약관 | [YC 이용약관](https://www.ycombinator.com/legal)이 data mining·robots·scraping 을 명문으로 금지한다. robots.txt 는 `Crawl-delay: 30` 으로 열어 둔다. 서로 어긋난다 |
| 공식 API ([HackerNews/API](https://github.com/HackerNews/API)) | Firebase. 인증 불필요, "There is currently no rate limit". 저장소 라이선스는 MIT 이나 게시물 콘텐츠의 라이선스로 읽기는 어렵다 |
| Algolia HN Search ([문서](https://hn.algolia.com/api)) | 인증 불필요. **IP 당 시간당 10,000 요청** 상한. 별도 귀속 조항 없음 |
| 결론 | **HN 의 HTML 페이지는 요청하지 않는다.** 공식 API 만 쓴다. 우리 사용량은 시간당 몇 건이라 상한과 멀다 |
| 링크된 외부 원문 | HN 의 허용은 HN 도메인까지다. 외부 도메인은 각자 robots·약관이 있다. v1 은 URL 과 HN 메타데이터만 저장한다. 본문을 받으려면 robots 를 미리 확인한 도메인 화이트리스트가 필요하다(⚠️ #12) |

### 3.4 화면에 낼 수 있는 것

제목·URL·매체명·발행일은 화면에 내도 된다. 제호는 저작물이 아니고 링크는 복제가 아니다. **본문과 리드 문장은 화면에 내지 않는다.** 키워드와 집계는 우리 산출물이다.

### 3.5 확인 못 한 것

- 제호 비저작물성 판례의 사건번호. 법리만 확인했다.
- TDM 면책 개정안의 22대 국회 현재 상태. 현행법에 없다는 사실만 확정이다.
- 두산매거진 법적 고지가 vogue 등 매체 도메인에 그대로 적용되는지. 실무상 robots.txt 를 기준으로 삼는다.
- ~~hypebeast 약관이 자사 공개 RSS 를 읽는 것까지 금지하는지~~ → 2026-09-03 약관 원문 확인. 8조가 "any portion of the website" 를 "automated or non-automated means" 로 접근·수집하는 것을 금지하고 RSS 예외가 없다. 소스에서 뺐다(확정 2-1).

## 4. 구조 — 다섯 단계와 장부

```
[발견] ─후보─▶ [취득] ─원문─▶ [정규화] ─article.json─▶ [저장] ─장부 행─▶ [발급]
  소스별          소스별          공통                 MinIO+장부           Kafka
```

| 단계 | 하는 일 | 입력 | 출력 |
|---|---|---|---|
| 발견 | 소스에서 새 글 후보 목록을 얻는다 | 소스 정의, 마지막 커서 | 후보 `{article_id, url, published_at?}` 목록. 피드 소스는 원문(item XML)도 함께 |
| 취득 | 후보의 원문 바이트를 얻는다 | 후보 | raw 바이트 + 받은 시각. 피드 소스는 발견에서 받은 item 이 곧 raw 라 이 단계가 빈다 |
| 정규화 | raw 에서 공통 스키마를 만든다 | raw | `article.json` (#5.3) |
| 저장 | MinIO 에 raw 와 article.json 을 쓰고 있음을 확인한 뒤 장부에 적는다 | raw, article.json | 장부 행 (#5.4) |
| 발급 | 장부에서 아직 이벤트가 안 나간 행을 골라 Kafka 에 낸다 | 장부 | 이벤트 (#6), 장부 `event_emitted_at` |

**발견과 취득은 소스마다 다르고, 정규화 이후는 소스와 무관하다.** 소스 어댑터의 책임은 "후보 → raw → article.json" 까지다. 저장·발급은 어댑터를 모른다.

**장부(`collected_article`)를 두는 이유.** "저장이 확인된 뒤에 발급한다"를 재시도에도 성립하게 만드는 자리다. 저장 태스크가 장부에 적고, 발급 태스크가 장부를 읽어 낸다. 둘 사이에서 죽어도 장부에 `event_emitted_at` 이 비어 있으니 다음 실행이 이어 낸다. 같은 기사를 다시 발견했을 때 건너뛰는 판정도 장부로 한다. (대안: 장부 없이 MinIO 객체 존재 확인만으로 판정 — ⚠️ #12)

## 5. 저장 구조

### 5.1 버킷과 키

버킷 하나. 도메인·소스·경로·날짜는 키 접두어다.

```
{bucket}/{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/raw.{ext}
{bucket}/{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/article.json
```

| 자리 | 값 | 규칙 |
|---|---|---|
| `bucket` | `trendin-raw` (잠정) | 하나 |
| `domain` | `fashion` \| `dev` | #1 의 표 |
| `source` | #1 의 소스 키 | 소문자·숫자·하이픈 |
| `route` | `rss` \| `listing` \| `api` | **소스당 하나로 고정**한다. 경로를 바꾸면 소스 정의를 바꾸는 것이고 이 문서를 고친다. 소스 하나가 두 경로를 가지지 않으므로 같은 기사가 두 키에 생기지 않는다 |
| `yyyy/mm/dd` | **발행일**, Asia/Seoul 기준 | 수집일이 아니다. 같은 기사를 언제 다시 받아도 같은 키에 간다. 수집 시각은 article.json 과 객체 메타데이터에 |
| `article_id` | 소스 안에서 유일하고 바뀌지 않는 값 | #2 표의 "기사 ID" 열. URL 슬러그는 쓰지 않는다(제목이 바뀌면 슬러그도 바뀐다) |
| `ext` | `xml` \| `html` \| `json` | 피드 소스 `xml`(item 조각), 목록 소스 `html`(기사 페이지), API 소스 `json`(응답 그대로) |

객체 메타데이터(잠정): `collected-at`(UTC ISO-8601), `run-id`, `content-sha256`.

### 5.2 raw

받은 바이트 그대로. 인코딩 변환·정리·압축을 하지 않는다. 정규화가 틀렸을 때 raw 에서 다시 만들 수 있어야 한다.

### 5.3 article.json

| 필드 | 필수 | 내용 |
|---|---|---|
| `schema_version` | ✓ | `1` |
| `domain` `source` `route` `article_id` | ✓ | 키와 같은 값 |
| `url` | ✓ | 기사 정식 URL. 추적 파라미터 제거. 피드의 `link` 또는 `og:url` |
| `title` | ✓ | 제목. HTML 엔티티 풀고 앞뒤 공백 제거 |
| `published_at` | ✓ | ISO-8601, 소스가 준 오프셋 그대로 (UTC 로 바꾸지 않는다) |
| `collected_at` | ✓ | ISO-8601 UTC. 원문을 받은 시각 |
| `raw_key` | ✓ | raw 객체 키 |
| `content_sha256` | ✓ | raw 바이트의 해시 |
| `modified_at` | | 소스가 주면 |
| `summary` | | description / og:description / 리드 |
| `body_text` | | 본문. HTML 태그를 벗긴 평문. 문단 경계는 빈 줄 |
| `categories` | | 소스가 붙인 분류 문자열 배열. 피드 소스는 `<category>`. 목록 소스는 **그 기사를 발견한 하위 섹션 슬러그**다 — `article:section` 은 8/8 상수 `"FASHION"` 이라 `domain` 필드의 사본이고, `cate_depth1/2` 는 `/rss` 에만 있고 기사 페이지엔 없다 (① 재실측). 루트 목록(`/fashion`)은 분류가 아니라 목록이므로 라벨로 치지 않는다 |
| `author` | | |
| `members_only` | | harpersbazaar·cosmopolitan 회원 전용이면 `true`. 이때 `body_text` 는 없다 |
| `extra` | | 소스 고유 값. hn 은 `score` `descendants` `by` |

### 5.4 장부 `collected_article` (앱 DB)

| 컬럼 | 내용 |
|---|---|
| `source` `article_id` | 유일키 |
| `domain` `route` `url` `title` `published_at` | article.json 과 같은 값 |
| `raw_key` `article_key` `content_sha256` | 저장 결과 |
| `collected_at` | |
| `event_emitted_at` | 발급 성공 시각. NULL 이면 아직 안 나갔다 |

v1 은 장부에 있는 `(source, article_id)` 는 다시 취득하지 않는다. 수정 기사 추적은 범위 밖이다.

장부는 지우지 않는다. MinIO 객체가 보존 기간(#9)을 넘겨 사라진 뒤에도 "언제 어디서 무엇을 받았나"는 장부에 남는다. 그래서 장부의 `url` `title` `published_at` 은 article.json 의 사본이지 참조가 아니다.

## 6. 이벤트 (Kafka)

메시지 형식은 팀이 아직 안 정했다. 아래는 **전부 (잠정)** 이고, 확정되면 이 절을 고친다.

| 항목 | 값 (잠정) |
|---|---|
| 토픽 | `article.collected` 하나. 도메인은 메시지 필드로 구분 |
| 키 | `{source}:{article_id}` — 같은 기사는 같은 파티션 |
| 값 | 아래 JSON |
| 발급 조건 | MinIO `stat` 이 raw·article.json 둘 다 성공한 뒤. 장부에 행이 있어야 한다 |
| 전달 보장 | at-least-once. 소비자는 `(source, article_id)` 로 멱등 처리한다 |

```json
{
  "schema": "article.collected.v1",
  "event_id": "uuid4",
  "occurred_at": "2026-09-03T02:10:00Z",
  "domain": "fashion",
  "source": "vogue",
  "route": "rss",
  "article_id": "854414",
  "url": "https://www.vogue.co.kr/2026/09/03/...",
  "title": "...",
  "published_at": "2026-09-03T01:00:00+00:00",
  "bucket": "trendin-raw",
  "raw_key": "fashion/vogue/rss/2026/09/03/854414/raw.xml",
  "article_key": "fashion/vogue/rss/2026/09/03/854414/article.json",
  "content_sha256": "..."
}
```

**본문은 이벤트에 싣지 않는다.** 소비자는 `article_key` 로 MinIO 에서 읽는다. 이건 잠정이 아니라 결정이다(#7 불변식 6).

## 7. 불변식

| # | 불변식 | 왜 |
|---|---|---|
| 1 | robots.txt 의 `User-agent: *` 규칙이 금지한 경로는 요청하지 않는다. 이름 지정 차단 목록에 오른 UA 문자열(Scrapy 기본 UA 등)을 쓰지 않는다. Hacker News 는 HTML 을 요청하지 않고 공식 API 만 쓴다 | #3. 우리 UA 는 별도 문자열이라 `*` 규칙을 따른다. HN 약관이 사이트 스크래핑을 금지한다 |
| 2 | 접근 제한을 우회하지 않는다. 로그인·회원 전용·페이월·캡차·IP 차단 전부다. 403·429 를 받으면 그 실행에서 그 호스트를 멈추고, IP 나 UA 를 바꿔 다시 시도하지 않는다. `members_only` 기사는 제목·URL·발행일·요약만 저장하고 본문을 저장하지 않는다. HTML 에 텍스트가 실려 있어도 마찬가지다 | 정보통신망법 제48조는 형사 조항이다. 판례가 위법을 가른 지점이 차단 우회다 |
| 3 | 본문과 리드는 내부 저장소에만 둔다. 외부 재게시·전송·화면 표시를 하지 않는다. 화면에는 제목·URL·매체명·발행일까지만 낸다 | 공정이용 4호와 부정경쟁방지법 파목을 동시에 지키는 지점이다 |
| 4 | 같은 호스트에 대한 요청은 직렬이고 간격을 둔다 (#9) | 부하를 주지 않는다. `crawler_pool` 은 전체 동시성만 막고 호스트별 간격은 수집기 몫이다 |
| 5 | 이벤트는 MinIO 에 raw·article.json 이 있음을 `stat` 으로 확인한 뒤에만 낸다 | 소비자가 키로 읽었을 때 반드시 있어야 한다 |
| 6 | 이벤트에 본문이 없다. 키만 있다 | 메시지 크기와 재사용. 본문의 단일 출처는 MinIO |
| 7 | `(source, article_id)` 하나는 MinIO 키 하나, 장부 행 하나. 재실행해도 늘지 않는다 | 파이프라인 규약 "모든 태스크는 멱등" |
| 8 | raw 는 받은 바이트 그대로다 | 정규화를 다시 할 수 있어야 한다 |
| 9 | article.json 필수 필드가 하나라도 비면 그 기사는 저장하지 않고 실패로 남긴다 | 반쪽 기사가 이벤트로 나가면 소비자가 판정할 수 없다 |
| 10 | 발행일 키(`yyyy/mm/dd`)는 Asia/Seoul 로 계산한다 | 팀 스케줄과 트렌드 집계가 KST 다 |
| 11 | article.json·장부·이벤트에 `url` `source` `published_at` 이 항상 있다 | 저작권법 제37조 출처 명시. 공정이용은 면제가 아니다 |
| 12 | 장부에 있는 `(source, article_id)` 는 다시 받지도 저장하지도 않는다. 과거분 백필은 소스당 한 번이다. 목록·피드 요청은 주기마다 하되 저장은 신규분만이다 | 저작권법 제93조 제2항. 반복적·체계적 전량 복제가 되지 않게 |
| 13 | MinIO 객체는 보존 기간(#9)을 넘기면 지운다. 장부 행은 남는다 | 복제권 부담을 기간으로 자른다. 메타데이터는 저작물이 아니라 남겨도 된다 |

## 8. 확정 사항

| # | 결정 | 대안과 버린 이유 |
|---|---|---|
| 1 | 발견 경로는 #2 표대로. 두산 4곳·marieclaire 는 카테고리 피드, harpersbazaar·cosmopolitan 은 목록 HTML + 기사 페이지, hn 은 Algolia API | bazaar·cosmo `/rss` 는 카테고리 필터가 없고 2~10건. hn 은 약관이 사이트 스크래핑을 금지하고 API 를 공식 제공한다 |
| 2 | 피드 소스는 피드의 `content:encoded` 를 본문으로 쓰고 기사 페이지를 따로 받지 않는다 | 요청 수를 1/10 로 줄인다. 잘림이 확인되면 그 소스만 기사 페이지로 바꾼다 |
| 2-1 | **hypebeast 를 소스에서 뺀다.** 피드를 포함해 어떤 요청도 보내지 않는다. #1 표에 줄이 없고 어댑터도 만들지 않는다. #2 표의 행은 실측 기록으로만 남는다 | 약관 8조가 "automated or non-automated means" 로 "any portion of the website" 에 접근·수집하는 것을 금지하고 **RSS 예외가 없다**(#3.2 원문). 피드만 읽는 안은 우회 위험은 0으로 만들지만 약관 위반은 그대로 남긴다. 2026-09-03 팀 확정 |
| 3 | hn 은 API 메타데이터만 저장한다. 링크된 외부 원문은 v1 에서 받지 않는다 | 외부 도메인마다 robots·약관이 다르다. 제목·점수만으로 dev 트렌드 1차 판정은 된다 (⚠️ #12) |
| 4 | 저장소는 MinIO 버킷 하나, 키 구조 #5.1 | 도메인별 버킷은 권한·수명주기 정책이 둘로 갈린다. 접두어면 충분하다 |
| 5 | 날짜 파티션은 발행일 KST | 수집일이면 재수집마다 키가 늘어 불변식 7 이 깨진다 |
| 6 | 장부는 앱 DB `collected_article` | 파이프라인 규약 "XCom 엔 ID·건수만, 본문은 DB" 와 같은 방향 |
| 7 | 이벤트는 저장 확인 뒤, 본문 없이, 키 `{source}:{article_id}` | #6 |
| 8 | 회원 전용 기사는 본문 제외 (불변식 2) | 우회 없음이 원칙. ⚠️ #12 에서 팀 확인 |
| 9 | 과거분은 피드가 `?paged=N` 을 주는 소스(두산 4곳, marieclaire)만, 파라미터 #9 깊이까지. 나머지는 없음 | 아카이브 백필은 범위 밖 |
| 10 | UA 는 자체 문자열에 팀명·연락처·목적을 넣는다 (#9) | 잡코리아 사건에서 정체를 숨긴 점이 불리하게 작용했다. 운영자가 연락할 수 있어야 한다 |
| 11 | MinIO 객체(raw·article.json)는 보존 기간이 지나면 지운다. 장부는 영구다 | 무기한 보존은 복제권·제93조 부담을 키운다. 재처리가 필요하면 기간 안에 한다 (⚠️ #12) |

## 9. 파라미터 (전부 잠정)

| 파라미터 | 잠정값 | 근거 |
|---|---|---|
| 수집 주기 — fashion 소스 | 1시간 | ① vogue 카테고리 피드 10건이 딱 24시간을 덮었다. 발행이 몰리는 날엔 피드가 더 빨리 넘어가므로 여유를 둔다 |
| 수집 주기 — hn | 30분 | ① 시간당 26건, Algolia 1회 1000건. 사실 6시간도 되지만 "새 글" 체감을 위해 |
| 같은 호스트 요청 간격 | 3초 | ③ 법정 기준은 없다. hn robots 의 30초는 HTML 에만 해당하고 우리는 HTML 을 안 받는다 |
| Algolia 요청 상한 | 시간당 10,000 (문서 명시). 우리는 시간당 2건 안팎 | ② 출처 |
| 요청 타임아웃 | 20초 | ③ |
| 재시도 | 2회, 1분 간격. 403·429 는 재시도하지 않는다(불변식 2) | 파이프라인 예제 DAG 의 값 |
| 과거분 깊이 | 피드 30페이지 (≈ 300건, vogue 기준 6주), 소스당 한 번. **2페이지부터** 돈다 | ① `?paged=30` 확인. ① `?paged=1` 은 파라미터 없는 요청과 같은 10건이라 주기 수집과 겹친다. ① `?paged=999` 도 404 가 아니라 200 에 오래된 10건을 주므로 "빈 응답이면 멈춘다" 는 종료 조건이 없다 — 페이지 상한이 유일한 브레이크다 |
| 버킷 이름 | `trendin-raw` | |
| 토픽 이름 | `article.collected` | |
| UA 문자열 (확정) | `TrendInBot/0.1 (non-profit student project; trend analysis)` | ① `lab.ssafy.com` 은 익명 접근이 로그인으로 302 라 연락처 구실을 못 한다. ① HTTP 헤더는 latin-1 이라 한글이 못 들어간다(`UnicodeEncodeError`). 봇임을 밝히는 이름이 핵심이고 연락처 부재는 정체 숨김이 아니다(#3 의 잡코리아 사건은 VPN·출처 삭제·재게시의 조합이었다). 브라우저 UA 위장은 하지 않는다 |
| MinIO 객체 보존 기간 | 90일. 지나면 raw·article.json 삭제, 장부는 유지 | ③ 재처리 여유와 복제권 부담 사이. 팀이 정한다(⚠️ #12) |

## 10. 교체 지점 (seam)

| 교체 지점 | 계약 — 어디에 무엇이 고정되나 | 바꿀 때 건드리는 것 |
|---|---|---|
| 소스 어댑터 (소스당 하나, 8개) | 입력: 소스 정의(#1 표의 한 행)와 마지막 커서. 출력: `article.json` (#5.3) 과 raw. 발견·취득은 어댑터 안에서 끝난다 | 그 어댑터 하나. 정규화 이후는 모른다 |
| 저장소 | #5.1 키 규칙, raw·article.json 두 객체, 쓰고 나서 `stat` 확인 | 저장 모듈과 이 문서의 #5.1 |
| 장부 | #5.4 컬럼과 `(source, article_id)` 유일키, `event_emitted_at` 의 의미 | DDL 과 저장·발급 둘 |
| 이벤트 | #6 토픽·키·메시지 스키마 v1 | 발급기와 모든 소비자. 스키마 버전을 올린다 |
| 실행 주기·간격 | #9 파라미터 | 설정값만 |
| 소스 목록 | #1 표 | 어댑터 추가 + 표 한 줄. 다른 부품은 모른다 |

## 11. 순서

설계가 못 박는 순서만 적는다. 나머지는 병렬이다.

1. **MinIO 가 있어야 저장 부품이 검증된다.** 어댑터는 고정 자료(저장한 피드·HTML)로 저장소 없이 검증한다.
2. **Kafka 가 있어야 발급 부품이 검증된다.**
3. **저장 부품(장부 포함)이 있어야 발급 부품이 읽을 행이 있다.**
4. 어댑터 8개는 서로 독립이고 저장 부품과도 독립이다.

```
[MinIO 구축] ──▶ [저장 + 장부] ──▶ [발급] ◀── [Kafka 구축]
[어댑터 ×9] ──────────────────────────┘ (합류는 실행 DAG 에서)
```

## 12. 열린 질문 ⚠️ (팀이 정한다)

| # | 질문 | 이 문서의 잠정 답 |
|---|---|---|
| 1 | MinIO 보존 기간. 90일이면 그 뒤로는 새 추출 모델로 옛 기사를 다시 못 돌린다. 무기한이면 복제권·제93조 부담이 쌓인다 | 90일 |
| 2 | harpersbazaar·cosmopolitan 회원 전용 기사: 본문 제외(보수) vs 로그인 없이 HTML 에 실린 만큼 저장. **로그인해서 받는 안은 여기 없다** — 제5조 2항·제10조 3항 때문에 별개 결정이다(#3.2). 재실측으로 자리가 하나 늘었다: 기사 페이지 HTML 자체에 본문이 실려 오므로 **raw 를 저장하면 본문을 저장하는 것**이다 | 본문 제외 + **raw 도 저장하지 않음**. 164 가 이걸 구현했지만 **확정이 아니라 가역적 기본값**이다 — 뒤집어 저장하려면 `Article` 의 검증 하나를 지우면 되고, 반대로 저장해 둔 뒤 뒤집으면 MinIO 에서 골라 지우고 이미 나간 이벤트를 좇아야 한다. 되돌림 비용이 싼 쪽을 기본으로 뒀다. 잃는 것은 7.4% 의 본문이고 제목·URL·발행일·요약은 남는다 |
| 3 | hn 외부 원문 본문을 받을 것인가 | v1 안 받음. 받는다면 robots 를 미리 확인한 도메인 화이트리스트를 가진 별도 부품 |
| 4 | Kafka 메시지: #6 잠정안 승인 여부. 토픽 하나 vs 도메인별 둘 | 하나 |
| 5 | 장부를 앱 DB 에 둘지, 장부 없이 MinIO 존재 확인만으로 갈지 | 앱 DB 장부 |
| 6 | 날짜 파티션: 발행일 vs 수집일 | 발행일 |
| 7 | 저장·이벤트 단위: 기사 하나당 객체 둘과 이벤트 하나(이 문서) vs 실행 한 번당 배치 파일 하나와 이벤트 하나(팀 문서, #14) | 기사별 |

## 13. 실행 방법 참고 (결정이 아니다)

파이프라인 규약(`pipeline/README.md`)에 맞춘 한 가지 방법이다. 수행자가 바꿔도 이 문서의 결정은 그대로다.

- 도메인당 DAG 하나(`fashion_collect`, `dev_collect`), 소스별 동적 매핑. 외부 요청 태스크는 `pool="crawler_pool"`. 호스트별 간격은 어댑터 안에서.
- MinIO 는 S3 호환이라 Airflow 의 S3 훅(`endpoint_url` 지정)으로 쓴다. Kafka 는 Airflow 의 Kafka provider 또는 `confluent-kafka` 직접.
- MinIO·Kafka 는 `infra/compose.yaml` 의 `s15p21a102-shared` 네트워크에 붙는다. 포트는 `127.0.0.1` 바인드, 접근은 SSH 터널.
- 커서: 피드 소스는 커서가 없다(매번 10~20건 받고 장부로 거른다). hn 은 마지막 `created_at_i` 를 Airflow 데이터 구간에서 계산한다.
- 보존 기간은 MinIO 버킷 수명주기 규칙(ILM)으로 건다. 코드가 지우지 않는다.
- 호스트별 3초 간격은 어댑터 안의 단일 세션에서 지킨다. 같은 호스트를 두 태스크가 동시에 치지 않도록 소스당 태스크 하나로 매핑한다.

## 14. 팀 파이프라인 문서와의 차이

`pipeline/docs/data-pipeline-design.md`(2026-09-03, 팀 전체 구조)와 이 문서는 같은 자리를 다르게 그린다. 어느 쪽이 맞는지는 이벤트 계약 이슈(S15P21A102-155)가 정한다. 이 문서의 #5·#6 은 그 입력이다.

| 자리 | 팀 문서 | 이 문서 |
|---|---|---|
| 저장 단위 | 실행(run) 하나당 `part-000.jsonl.gz` + `metadata.json` | 기사 하나당 `raw` + `article.json` |
| 키 파티션 | `domain=…/collected_date=…/source=…/run_id=…` (수집일) | `domain/source/route/yyyy/mm/dd/article_id` (발행일 KST) |
| 버킷 | `raw-data` | `trendin-raw` (잠정) |
| 이벤트 | 파일 하나당 `raw-file-ready` (건수·크기·체크섬) | 기사 하나당 `article.collected` (잠정) |
| 중복·멱등 | Spark 단계에서 중복 제거 | 장부와 기사별 키로 수집 단계에서 |
| dev 소스 | reddit · github · stackoverflow 를 예시로 | Hacker News 만 (이 문서의 범위) |

기사별을 고른 이유는 #8 확정 5·7 이다. 배치 파일이면 같은 기사를 다시 받았을 때 새 run_id 밑에 또 생겨 불변식 7 이 성립하지 않고, 소비자가 기사 하나를 다시 읽으려면 파일 전체를 열어야 한다. 반대로 배치 파일은 객체 수와 이벤트 수가 적다. 규모는 하루 700건 안팎이라(① HN 시간당 26건, 패션 7곳 합쳐 하루 100건 안팎 관찰) 둘 다 감당된다. 팀이 배치 파일로 정하면 이 문서의 #5·#6·#7·#12 를 고친다.

## 부록 A. 실측 요약 (2026-09-03)

| 확인 | 결과 |
|---|---|
| 목록 페이지 접근 (curl UA / 브라우저 UA) | 9곳 전부 200 / 200 |
| 두산 4곳 `/wp-json/wp/v2/posts` | 401 |
| 두산 4곳 `/category/{slug}/feed/` | 200, 10건, `content:encoded` 있음, `?paged=30` 까지 확인 |
| marieclaire `/category/fashion/feed/` | 200, 10건, `?paged=2` 확인, 기사 ld+json 에 articleBody 2449자 |
| hypebeast `/fashion/feed` | 200, 20건, `?paged=2` 는 같은 내용 |
| harpersbazaar `/rss` | 200, 2건, `cate_depth1/2` 커스텀 태그, 본문 없음 |
| cosmopolitan `/rss` | 200, 10건, 위와 같음 |
| harpersbazaar `/fashion` 목록 | 기사 링크 36건. `/fashion/news?offset=20` 에서 새 링크 21건 |
| cosmopolitan `/fashion` 목록 | 기사 링크 49건. `?offset=20` 에서 10건 추가, `offset=40` 이후 동일 |
| bazaar·cosmo 기사 페이지 | ld+json `NewsArticle`(headline·datePublished·copyrightHolder, articleBody 없음), 본문 컨테이너 `atc_body`, 회원 전용 마스크 |
| **재실측 (같은 날, 목록 12장·기사 8건)** | |
| 목록 응답 | 12/12 가 200. 장당 190~250 KB |
| 앵커 `/article/{숫자}` | bazaar 루트 36 · 섹션 32씩 (6장 합쳐 고유 110건), cosmo 루트 49 · 섹션 32씩 (고유 107건) |
| 목록 안 JSON 페이로드 | 페이지당 고유 20건. **앵커 36건 중 34건이 여기 없다** — 추천 위젯이지 목록이 아니다 |
| 회원 전용 비중 | 217건 중 16건 (7.4%). bazaar 9/110, cosmo 7/107 |
| `div.membershipLine` | 기사 8건에서 회원 전용에만 1개, 일반엔 0개 (8/8) |
| 마스크 문구 | 기사 8건 **전부**에 존재 — 판정 불가 |
| ld+json ↔ meta 태그 | 발행일·url·요약이 8/8 완전 일치. `author` 는 ld+json 에만 있다 |
| 회원 전용 기사 페이지 | 본문이 HTML 에 통째로 실려 온다. `membershipLine` 은 유료 구간 시작 표시일 뿐 본문을 자르지 않는다 |
| hn Algolia `search_by_date` + `numericFilters=created_at_i>` | 200, 최근 1시간 26건 |
| hn Firebase `newstories` | 200, 500건이 약 9.7시간 |
