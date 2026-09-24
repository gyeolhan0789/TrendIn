# 개념 층 — 다국어 키워드를 하나의 개념으로 세기

`발레코어`(ko) · `balletcore`(en) · `バレエコア`(ja) 는 지금 세 개의 키워드다. 개념 층은 셋에 같은
번호를 달아 "이 개념을 언급한 기사 수" 를 국가를 넘어 셀 수 있게 한다. **키워드를 바꿔치기하지
않고 꼬리표만 단다** — 원표기와 언어는 그대로 남아야 "어느 나라에서 먼저 떴나" 가 보인다.

이 문서는 세 담당(키워드 추출 · 개념 통합 · 랭킹)이 병렬로 일하기 위한 **계약**이다. 설계 근거는
2026-09-17 설계 논의(9절)에 있고, 여기는 그중 코드가 기대는 부분만 적는다.

## 흐름과 책임

```
[키워드 추출]   기사별 키워드 발생을 낸다                      ── 계약 A ──▶
[개념 통합]     표현 → 개념 번호. 못 붙이면 미등록으로 쌓는다   ── 계약 B ──▶
[랭킹]          국가·기간·개념 단위로 기사 수를 센다
```

| 경계 | 정한 것 |
| --- | --- |
| 무엇을 붙이나 | **승격된 키워드만.** 승격 관문(기사 5 · 저자 3 · 관측 2일)이 봇을 거르고 미등록 양을 통제한다 |
| 언어와 국가 | 다른 축이다. 개념 통합은 언어만 보고, 국가는 랭킹이 본다 |
| 중복 기사 | 개념 통합의 일이 아니다. 국가 간 번역·재배포 기사는 기사 단위 근사 중복(별건)이 맡는다 |
| 상하위 집계 | `parent_id` 만 넘긴다. 상위 묶음에서 한 번으로 접는 것은 랭킹의 `count(distinct article_id)` |
| 일반 단어 | `countable = false` 개념으로 **기억**한다. 세지 않는 것은 랭킹이 거른다 |

## 계약 A — 추출 → 개념 통합

기사 하나에 객체 하나. 회차마다 JSONL. 예시: `spark/tests/fixtures/concept/contract-a.jsonl`.

```json
{"article_id": 40213, "lang": "ja", "country": "JP", "source": "vogue_jp",
 "published_at": "2026-09-15T08:30:00+09:00", "extract_run_id": "extract-2026-09-16-0030",
 "keywords": [
   {"surface": "ブーツ", "normalized": "ぶーつ", "count": 3, "in_title": false,
    "context": "今季はロングブーツが主役。ヒールは低めが人気だ。"}
 ]}
```

| 칸 | 뜻 |
| --- | --- |
| `article_id` | `contents.id`. 파이프라인 내부에서는 `url_hash` 로 들고 있다가 적재 때 푼다 |
| `lang` · `country` | **둘 다** 있어야 한다. UAE 매체의 영어 기사는 `lang=en, country=AE` |
| `keywords[].context` | 표기가 나온 문장과 앞뒤 한 문장. 미등록 판정과 검수가 읽는다 |
| `keywords[].normalized` | 추출 쪽 비교키. 개념 통합은 자기 규칙으로 다시 만들되 이 값도 남긴다 — 어긋날 때 추적용 |

**지금(MVP)은 이 파일이 없고 DB 에서 만든다.** `pl_document_candidate ⋈ pl_alias ⋈ pl_keyword_id_map
⋈ pl_content_id_map` 으로 기사별 선별 표기를 읽는다 (`io/concepts.py` `OCCURRENCES_SQL`). 문서 후보는
별칭을 접지 않은 원표기로 저장되고 승격은 대표 키로만 일어나므로, `pl_alias` 를 거쳐 대표로 바꾼 뒤
승격 여부를 본다 — 그 홉이 없으면 별칭으로 흡수된 표기의 기사가 미등록에도 안 남고 사라진다.
조회에 쓰는 표기는 대표가 아니라 원표기다 (개념 사전이 자기 별칭 목록을 따로 갖는다). 그 표에는
`lang` 과 `context` 가 없어서, 언어는 표기의 문자 체계로 정하고 문맥은 비어 있다. **추출이
`lang` 과 `context` 를 실어 주는 것이 계약 A 의 첫 요구다.** 그때 질의를 파일 읽기로 바꾼다.

## 계약 B — 개념 통합 → 랭킹

실제 전달은 표 `pl_article_concept` 하나다. 아래는 같은 내용을 기사 단위로 본 모양.
예시: `spark/tests/fixtures/concept/contract-b.json`.

```json
{"article_id": 40213, "dictionary_version": 42,
 "concepts": [
   {"concept_id": 1201, "canonical_name": "boots", "category": "footwear", "parent_id": null,
    "countable": true, "method": "DICT", "expressions": ["ブーツ"]}
 ],
 "unmapped": [{"surface": "バレエコア", "normalized": "ばれえこあ", "lang": "ja"}]}
```

**"붙은 표기 수" 와 "행 수" 는 다르다.** 같은 기사에서 `Dior` · `디올` 처럼 표기 여럿이 한 개념에 붙어도
`pl_article_concept` 에는 (기사, 개념) 한 행이다. 2026-09-17 실 DB 첫 실행에서 붙은 표기 발생은 504, 행은 478 이었다 —
504 > 478 은 정상이고, 그 차이가 접힌 만큼이다. 커버리지를 말할 때 분모·분자를 발생 수로 셀지 행 수로 셀지 밝혀 적는다.

랭킹이 기대는 규칙 셋:

- **기사·개념 한 쌍에 한 행.** 기본키다. 같은 기사에서 표현이 몇 개든, 몇 번 다시 처리하든 한 행.
- **`countable = false` 는 세지 않는다.** `pl_concept` 을 조인해 거른다.
- **상위 묶음은 자손을 합쳐 `count(distinct article_id)`.** `boots` 와 `ankle boots` 가 한 기사에
  같이 있어도 `boots` 묶음은 1 이다. 세부 순위는 개념 id 그대로(정확 집계), 분류 수준 순위는 묶음.

### 랭킹이 실제로 읽는 것 (2026-09-19)

**`pl_article_concept` 이 아니라 `pl_concept_expression` 이다** (`metrics/concepts.py` ·
`io/metrics.CONCEPT_GROUPS_SQL`). 계약 B 가 기사 단위인데 [07] 은 이미 승격된 키워드 단위로
세기 때문이다 — 기사에서 개념을 다시 세면 `pl_keyword_daily_stat` 과 나란한 두 번째 집계
경로가 생기고, 둘이 어긋나는 날 화면의 숫자와 그래프가 갈린다. 그래서 개념은 **세는 축이
아니라 키워드를 묶는 축**으로만 쓴다:

```
keywords.normalized_name ─(표기 일치)→ pl_concept_expression.normalized → pl_concept
```

그 결과 랭킹에서 일어나는 일은 둘이다.

- **접기** — 같은 개념의 표기를 대표 하나로 합친다. 대표는 지평 전체 언급량이 가장 큰 표기이고
  기간마다 다시 고르지 않는다. 흡수된 표기는 지표 행과 그래프를 그대로 갖되 순위와 배지를
  받지 않는다 (`청바지` 상세 화면이 비지 않게).
- **빼기** — `countable = false` 인 개념에 붙은 키워드는 순위와 배지에서 빠진다. 위 규칙이
  말하던 그것이고, 2026-09-19 까지 집계가 읽지 않고 있었다.

**`lang` 을 보지 않는다.** `keywords` 에 언어 칸이 없고, 애초에 언어를 넘어 접는 것이 목적이다.
그래서 모호 판정도 `normalized` 만으로 센다 — 한 표기가 두 개념에 걸리면(`크리스찬 디올` 이
designer 이자 brand) 어느 쪽으로도 접지 않는다.

fashion 3개월(로컬, D=2026-09-18)에서 **표기 832개가 대표로 접히고 324개가 순위에서 빠졌다.**
접기 전 30D 상위 100 표기는 실제로 82 개념이었다.

| 개념 | 흩어진 표기와 순위 | 합산 |
| --- | --- | --- |
| leather | leather(8위) · pelle(11) · 가죽(34) · cuir(59) | 515 |
| jeans | jeans(3) · 청바지(30) · 데님 팬츠(79) | 426 |
| Vogue | Vogue(4) · Vogue Italia(43) · British Vogue(57) | — (`countable = false`) |

**z 하한으로는 이 일이 안 된다.** 같은 날 재 보고 방향을 바꿨다 — 30D 에서 `샤넬` 이 z=0.00,
`collection` 이 1.59, `suede` 가 2.72 였다. z 는 "흔한 말인가" 가 아니라 "배경 대비 최근에
튀었나" 를 재므로, 꾸준한 진짜 브랜드가 먼저 떨어지고 시즌 따라 늘어나는 배경어가 남는다.

### 연도·시즌만 다른 표기 (2026-09-24, S15P21A102-385)

2026-09-24 24H 인기 순위 1~4위가 한 행사였다 — `Vogue World` · `Vogue World 2026` ·
`Vogue World Milano 2026` · `Vogue World: Milano`. 사전에 없던 새 이름이 여러 변형으로 한꺼번에
들어오면 위의 접기가 아무것도 못 한다. 후보 검색도 사전에 **이미 있는** 개념만 찾으므로 새 표기끼리는
서로 모른다. 문헌에서 NIL clustering(사전 밖 표현끼리 같은 실체를 묶는 일)이라 부르는 자리다.

그중 글자만 보고 확실한 것 — **끝의 연도와 시즌 코드** — 를 `registry/edition.py` 가 뗀다.

| 표기 | 기준형 |
| --- | --- |
| `vogue world 2026` · `2026 met gala` · `멧 갈라 2026년` | `vogue world` · `met gala` · `멧 갈라` |
| `paris fashion week ss27` · `prada menswear ss 2027` | `paris fashion week` · `prada menswear` |
| `milano 2026` · `gucci ss27` · `paris ss27` | 접지 않는다 — 떼고 한 낱말이 남으면 대개 도시·브랜드·일반어다 |
| `air max 90` · `louis vuitton 1854` | 접지 않는다 — 2000~2039 밖이거나 연도 꼴이 아니다 |
| `vogue world milano` → `vogue world`, `vogue` ↔ `vogue world` | 접지 않는다 — 낱말은 떼지 않는다 |

**같은 것이 아니라 같은 집계 단위다.** `Vogue World 2026` 은 시리즈 `Vogue World` 의 한 회차다.
그래서 표기 병합(`pl_alias`)으로 영구히 붙이지 않고 **순위에서만** 합친다 (`metrics/concepts.
build_grouping`, `aggregate.concepts.fold_editions`). 키워드가 그대로라 되돌릴 수 있고, 이미 승격된
키워드에도 걸리며, 기준형 키워드가 없어도 회차끼리 접는다. 층 1 에 같은 규칙을 넣었다가 뺐다 —
회차 정보가 영구히 사라지기 때문이다.

- **합산과 보이는 이름은 다른 문제다.** 합산은 위 문자열 규칙이고, 최신 회차를 이름으로 내는 것은
  **행사(`event`) 개념이 확인된 덩이에만** 한다. `Saint Laurent` + `Saint Laurent SS27` 은 합산해도
  이름이 브랜드여야 하고, 개념이 없는 덩이는 도시인지 행사인지 모른다(사전 분류에 장소가 없다).
  그런 덩이는 개념 접기처럼 무게로 고른다.
- **행사 덩이의 대표** — ① 덩이 전체 언급량의 `aggregate.concepts.representative_min_share`(0.1)
  이상인 회차만 후보다. 예고 기사 한 건(`Vogue World 2027`)이 이름을 가져가지 못한다. ② 연도·시즌이
  가장 늦은 것(`fw26` < `rs27` < `ss27`). ③ 같으면 기준형이 짧은 것 — `vogue world 2026` 이
  `vogue world milano 2026` 을 이긴다. ④ 언급량, ⑤ id. ①~③ 이 이름에서 정해지므로 언급량이
  오르내려도 대표가 흔들리지 않는다. 점유율 경계를 넘는 날 한 번 바뀐다.
- **부딪칠 때의 차례.** ① 한 덩이가 서로 다른 두 개념에 걸리면 접지 않는다 — 사전이 이긴다.
  ② 덩이 안에 세지 않는 표기가 있으면 덩이 전체를 뺀다 — `vogue world` 가 제외됐는데
  `vogue world 2026` 이 순위로 돌아오면 제외 판정을 우회한 것이다. ③ 단 덩이 안에 세는 개념에 붙은
  표기가 있으면 ② 를 하지 않고 접지도 않는다.

2026-09-24 운영 DB 정리 — 09-23 자동 판정이 Milano 두 표기를 각자 새 개념으로 만들어 두 개념에 걸린
덩이가 됐다(① 에 걸려 접히지 않는다). 두 개념을 롤백하고 `Vogue World 2026` 개념에 연결해 네 표기가
한 개념이 됐다. `vogue world` 의 제외 판정은 09-23 에 이미 사람 보류로 풀려 있었다.

⚠️ **알려진 한계** — 두 낱말 장소 + 연도(`Los Angeles 2028`)는 도시에 합산된다. 보이는 이름은 도시
그대로다. 장소 판별과 트렌드 ID 를 대표에서 떼는 일(`rank_group_id` / `display_keyword_id`)은
S15P21A102-386 이다.

개념 사전 10,558 표기에 돌려 보니 떨어지는 것은 11개였고 전부 시즌·회차 표기였다
(`fall winter 2026` → `fall winter`, `miss supranacional 2021` → `miss supranacional`). 브랜드·
디자이너 이름이 잘린 것은 없었다.

**남은 것** — `Vogue World` ↔ `Vogue World Milano` 처럼 낱말이 더 붙은 관계는 의미 판단이 필요하다.
미등록끼리 후보 군집을 만들고(이름 겹침·동시 급등·기사 겹침) 군집 단위로 LLM 에 물어 순위에서만
묶는 단계가 후속이다. 2026-09-24 에 `vogue milano` 를 혼자 물으니 행사 문장에서도 10번 모두 `media`
로 분류됐다 — 개별 판정보다 군집 판정이 필요한 이유다.

**끄는 길** — `aggregate.concepts.fold` · `.drop_uncountable` · `.fold_editions` 다. 사전이 잘못 묶였을 때
사전을 고쳐 다시 붙이는 것보다 빠르다. 개념 표가 없는 환경에서는 값과 무관하게 꺼진다.

### 개념 테이블에 없는 표기끼리 — 후보와 덩이 (2026-09-24, S15P21A102-386)

위 "남은 것" 의 첫 단계다. `registry/nil_candidates.py` 가 문자열로 후보 쌍을 넓게 뽑고, LLM 에 한
번에 물을 덩이로 묶는다. **합치지 않는다** — 판정과 순위 반영은 다음 단계다.

| 규칙 | 예 |
| --- | --- |
| `contain` — 두 낱말 이상이 이어서 들어 있다 | `vogue world` ⊂ `vogue world milano` |
| `prefix` — 앞 두 낱말이 같고 둘 다 세 낱말 이상 | `abito da sera` ~ `abito da sposa` |
| `edition` — 연도·시즌을 떼면 같다 | `met gala` ~ `2026 met gala` |
| `acronym` — 머리글자가 같고 같은 기사에 함께 나온다. 라틴 문자만 | `lfw` ~ `london fashion week` |

한 낱말만 겹치는 것(`vogue` ↔ `vogue world`)은 후보가 아니다. 앞 두 낱말이 같은 표기가 다섯 이상
(`gonna a …` · `t shirt …`)이면 형제 품목이라 그 머리로는 잇지 않고, 후보가 여덟을 넘는 흔한 말
(`fashion week`)은 덩이를 잇지 않고 둘씩 따로 묻는다.

**운영 실측** — 30일 언급이 있는 키워드 8,412 개(개념 없음 6,171)에서 뽑은 문자열 후보 608 쌍을
사람이 검수했다. 기준은 "순위에서 한 줄로 합쳐도 되나" 다 — 같은 대상(S) · 같은 시리즈의 다른
회차(E) 는 합치고, 수식어가 붙어 좁아진 것 · 다른 것(D) 은 합치지 않는다. 라벨은
`spark/tests/fixtures/concept/nil-pairs-gold-2026-09-24.jsonl` 이고, 다음 단계의 LLM 판정을 재는 정답표다.

- 합칠 쌍은 154 (25%, 2026-09-25 재검토 뒤). 나머지 대부분은 `미니 드레스` ↔ `블랙 미니 드레스` 같은
  수식어 변형이다. 아래 신호·후보 수치는 첫 라벨(합칠 쌍 140) 기준이다.
- 등장 패턴은 거를 만큼 갈리지 않는다. 같은 기사 2건 이상 — 정밀도 61% · 재현율 27%. 같은 날 급증
  38% · 30%. 첫 등장 날짜 차이는 구분력이 없고, 날짜별 상관은 새 표기의 날짜가 모자라 69 쌍만
  계산된다. **거르지 않고 판정에 넘기는 근거로만 쓴다.**
- 규칙별로 `edition` 은 19 쌍 모두 맞았고, 머리글자는 조건 없이 141 쌍 중 7 쌍만 맞았다(`dc` =
  `DC Comics` · `Doja Cat` · `dress code` …, 한국어는 `스키` = `스트레이 키즈`).
- 위 규칙으로 뽑으면 368 쌍 · 204 덩이(대부분 두세 표기)이고, 합칠 140 쌍 중 133 쌍이 같은 덩이에
  든다. 놓치는 것은 흔한 머리말 무리 안의 번역(`fashion week de paris` ↔ `fashion week parisienne`)·
  같은 기사가 없는 약어(`jfk`)·띄어쓰기(`빅백` ↔ `빅 백`)다.
- 24H·7D 상위 300 에 걸리고 한쪽이라도 개념이 없는 쌍만 보면 75 쌍 · 46 덩이다(가장 큰 것은
  `vogue world` 계열 9 표기). 덩이째 물으면 하루 수십 번이다.

한 표현에서 겹쳐 뽑힌 두 표기(`Vogue World 2026: Milano` 의 `Vogue World`)는 가장 강한 신호로 봤지만
잴 수 없다 — 추출(`extract/entities._dedupe`)이 겹치는 스팬 중 하나만 남기고 위치도 저장하지 않는다.

### 덩이째 LLM 판정 (2026-09-25, S15P21A102-386)

`concept/cluster_judge.py` 가 덩이를 보여 주고 **후보 쌍마다** 관계를 고르게 한다 — `same` ·
`series` 만 합치고 `narrower` · `related` · `unrelated` · `unsure` 는 합치지 않는다. 합치는 쌍은
이어서 묶음을 만든다. 채점은 `scripts/nil-judge-eval.py` 로 위 라벨에 대고 한다.

**라벨** — 초안은 모델이 이름만 보고 달았고 사람이 두 번 검토했다. 초안에서 52 쌍이 바뀌었다
(정책 미정 41 이 풀림, 초안 `D` → `S` 11). 초안은 합칠 것을 따로 두는 쪽으로 치우쳤다. 파일에
`initial_label`(초안)과 `label`(최종)이 함께 있다. **이 608 쌍은 개발용으로 고정했다** — 모델 답을
보며 고쳤고 프롬프트도 이 쌍들을 보며 만들었으므로 여기 점수는 개발 성능이다. 최종 판단은 다른
시점의 표기로, 모델 답을 보기 전에 사람이 처음부터 단 테스트 라벨로 한다.

**정책** — "순위에서 한 줄로 보여 줘도 되나".
- 합친다: 철자·복수·번역·약어·정식명, 빠진 보완 명사(`white tank` ↔ `white tank top`,
  `폴카 도트` ↔ `폴카 도트 패턴`), 뜻을 좁히지 않는 꾸밈말(`white tee` ↔ `classic white tee`),
  시즌 ↔ 그 시즌의 컬렉션·쇼(`Fall 2026` ↔ `Fall 2026 collection`), 시리즈 ↔ 회차(`Vogue World` ↔
  `Vogue World 2026`), 문장이 같은 대상을 가리키는 것(`Milano 2026` 의 문장이 전부 Vogue World 다).
- 합치지 않는다: 색·핏·길이·소재로 좁아진 것(`tank top` ↔ `white tank top`), 도시가 붙은 행사
  (`Fashion Week` ↔ `London Fashion Week`), 브랜드 ↔ 라인(`Ralph Lauren Collection`), 사람 ↔ 그 이름의
  브랜드(`Francis Kurkdjian` ↔ `Maison Francis Kurkdjian`), 시즌 범위가 다른 것(`Estate 2026` ↔
  `Primavera Estate 2026`).

**실측** (최종 라벨, 지시문 예시 쌍은 뺌. 정밀도 · 재현율 · 나쁜 묶음 비율)

| 판정 | 결과 | |
| --- | --- | --- |
| "합칠 것끼리 묶어라" · gpt-4o-mini | 43% · 67% | 첫 라벨 기준. 수식어 변형을 마구 묶는다 |
| 쌍마다 관계 고르기 · gpt-4o-mini | 64% · 64% · 40% | 표기가 든 문장만 실은 뒤 |
| 〃 · gpt-4.1-mini | 92% · 68% · 13% | |
| 〃 · gpt-4.1 | 98% · 59% · 4% | 거의 안 틀리지만 40% 를 놓친다 |
| + 정책 예시 (`v3`) · gpt-4.1-mini | **90% · 76% · 13%** | 채택 |
| `v3` 를 다섯 덩이씩 묶어 묻기 | 79% · 75% · 21% | 크레딧 45% 절감, 품질이 떨어져 버림 |
| 판정 단계를 나누고 예시 보강 (`v5`) | 77% · 69% · 23% | 규칙끼리 부딪혀 나빠짐 — 버림 |

- **문맥 거르기가 가장 컸다.** 저장된 문맥 절반은 표기가 들어 있지 않은 기사 제목이었다
  (`Vogue World` 의 문맥이 `Wunmi Mosaku Is British Vogue's … Cover Star`). 표기가 든 문장만 싣게
  했다 (`cluster_judge.mentions`). 표기 508 개 중 쓸 문장이 있는 것은 268 개다.
- **"묶어라" 가 아니라 "골라라" 로 물어야 한다.** 안 되는 쪽(`narrower` · `related`)에 칸이 없으면 모델이
  되는 쪽으로 기운다.
- **`v5` 가 나빠진 이유** — "장소가 붙으면 좁아진 것" 이 `Vogue World: Milano` 같은 개최지 회차를
  시리즈에서 떼어 냈고, "보완 명사는 같다" 가 `레더 재킷` ↔ `블랙 레더 재킷` 까지 합쳤다.
- **남은 오류는 두 방향이다.** 문자열이 닮으면 너무 합치고(`black dress` ↔ `little black dress`),
  알아야 풀리는 별칭은 안 합친다(`Cou Cou` ↔ `Cou Cou Intimates`, `De Beers` ↔ `De Beers London`).
- 같은 조건을 두 번 돌리면 2~4%p 흔들린다. 한 번 돌리는 데 gpt-4.1-mini 로 약 520 크레딧이다
  (덩이 198. 크레딧으로 역산하면 약 21만 토큰).

지금 기본값(`cluster-v6`)은 `v3` 규칙에 여러 덩이 문구를 쓰고, 개발 라벨과 어긋나는 예시 하나
(`Milano 2026` 을 올림픽으로 든 것)를 `Los Angeles 2028` 로 바꿨다. 이 문구로는 아직 돌리지 않았다.

**운영 순위로 한 번 돌려 봤다 (2026-09-25 01시, DB 에 쓰지 않음).** 24H · 7D 상위 300 에 걸린 미등록 쌍
83 · 덩이 48 을 `cluster-v6` 로 판정했다. 합쳐지는 묶음은 13 — `Vogue World` 네 표기, `Met Gala` 세 표기,
`LFW` → `London Fashion Week`(7D 116 → 144), `NYFW` → `New York Fashion Week`(7D 15위 → 10위),
`White Lotus` · `Virgin Suicides` 같은 표기 차이다. 애매한 것은 `Barrel-Leg Jeans` + `barrel-leg trousers`
하나다. `MFW` ↔ `Milano Fashion Week` 는 두 번 물어 `same` 과 `related` 로 갈렸다.

처음 돌렸을 때는 `Fashion Week` 이 `London Fashion Week` 에 합쳐져 7D 2위가 116 → 202 로 부풀었고
`Fashion Week de Londres` + `de Milan` 이 한 줄이 됐다. 후보와 흔한 머리말을 순위 표기만으로 셌기
때문이다 — 패션위크 12 표기가 한 덩이로 갔고, 모델은 둘만 물으면 `narrower` 라 하는 쌍을 큰 덩이
안에서는 `same` 이라 했다. 후보는 전체 키워드로 만들고 흔한 머리말도 전체로 세도록 고쳤고, 덩이
상한을 12 에서 9 로 내렸다 (`registry/nil_candidates.py`).

**분류(`pl_concept.category`)로는 아무 유형도 거르지 않는다.** 2026-09-19 에 `RISING` 에서만
소재를 빼는 스위치(`aggregate.thresholds.rising.exclude_categories`)를 두었다 — 24H 다섯 자리를
`flannel` · `cashmere` · `wool` 이 셋 먹어서였다. 같은 날 서버에서는 목록이 굶어 값을 비웠고,
2026-09-21 에 배선째 걷어냈다. `CURRENT` · `RISING` · `NEW` 가 같은 키워드를 두고 서로 다르게
답하면 화면에서 이상하게 보인다는 것이 이유다. `leather` 가 1위인 것도, 가을에 소재가 급상승하는
것도 사실에 맞으니 셋 모두 그대로 보여준다.

**`셔츠` · `바지` 는 분류가 아니라 RISING 조건이 막는다.** 같은 날 후보 59개를 전부 확인했고
하나도 없었다. 늘 흔한 말은 증가율 50% 를 못 넘는다.

분류를 쓰기 전에 다른 축 셋을 나란히 쟀고 전부 안 됐다는 기록은 남긴다 — 다시 거를 일이
생기면 이 셋은 건너뛰어도 된다.

| 축 | 결과 |
| --- | --- |
| 계층(`parent_id`) | 3,584 개념 중 40개만 쓴다. `cigarette jeans` 와 `shirt` 가 둘 다 부모 없음 |
| z 로 정렬 | **더 나빠진다.** `flannel` 2.95 · `cashmere` 3.04 로 소재가 셋으로 는다 |
| 언급량 하한 | 올려도 `trench`(20건) · `wool`(12건)이 남는다 |

## 표

**전부 파이프라인 표다. Flyway 마이그레이션이 없다.** 스프링이 개념 표를 읽지 않으므로 서비스 표로 만들
이유가 없고, 만들면 백엔드 배포와 엮이기만 한다 (2026-09-17 결정). 개념 표 넷도 `pl_` 접두사로
`concept` Job 이 처음 돌 때 만든다 (`io/concepts.py` 의 DDL). 화면이 개념을 읽게 되는 날 서비스
표로 승격한다 — `contents` 가 걸어온 길이다(표가 먼저 있고 Flyway 가 뒤에 baseline 으로 받아들였다).
표는 팀 서비스 DB 한 곳(`SPARK_APP_DB_URL` 이 가리키는 곳, 지금 `pl_document_candidate` 가 있는 DB)에만 생긴다.

| 표 | 키 | 쓰는 쪽 |
| --- | --- | --- |
| `pl_concept_category` | `code` | 분류 목록. Job 이 만들 때 열 개를 넣는다 |
| `pl_concept` | `id` · UNIQUE `(canonical_name, category)` | 정체성은 id. 이름은 전부 고칠 수 있다 |
| `pl_concept_expression` | UNIQUE `(lang, normalized, concept_id)` · 조회 색인 `(lang, normalized)` | 사전 |
| `pl_article_concept` | PK `(article_id, concept_id)` | 랭킹이 읽을 자리. `article_id` 는 `contents.id` 의 논리적 참조(FK 없음 — `pl_` 규약) |

파이프라인 표(`io/concepts.py` 가 만든다):

| 표 | 하는 일 |
| --- | --- |
| `pl_unmapped_expression` | 미등록 표현. `(lang, normalized)` 하나에 한 행. `status` PENDING → QUEUED/RESOLVED |
| `pl_unmapped_article` | (표현, 기사) 쌍 **전부.** `article_count` 의 근거이자 재처리 대상 목록 |
| `pl_unmapped_context` | 문맥 표본, 표현당 `concept.unmapped.context_samples` 건 |
| `pl_mapping_decision` | 누가·무엇으로·왜 붙였나. 되돌릴 때 읽는다 |
| `pl_dictionary_version` | 승인된 변경마다 1 오른다. `pl_article_concept` 행에 찍힌다 |
| `pl_concept_judgement_cache` | LLM 판정 캐시 (다음 단계). 같은 질문을 두 번 하지 않는다 |

## 붙이는 규칙 (`concept/mapping.py` · `normalize.py` · `dictionary.py`)

기사 하나의 표기 목록을 받아 두 번 지난다. 첫 번째로 모호하지 않은 것을 붙이고, 그 결과로 두 번째에
모호한 것을 가른다. 표기마다 순서는 이렇다.

**1. 비교키를 만든다** (`normalize.concept_key`). 기존 규칙(NFKC · 소문자 · 하이픈·밑줄·연속 공백 → 한 공백 ·
앞뒤 문장부호 제거 · 영어 소유격 제거) 위에 문자 체계별 접기를 붙인다.

| 문자 체계 | 접는 것 | 접지 않는 것 |
| --- | --- | --- |
| 아랍 | 발음 부호 · 타트윌 · 알리프 변형(`أ إ آ`→`ا`) · `ة`→`ه` · `ى`→`ي` | 정관사 `ال` (떼면 `Alaïa` 표기까지 잘린다) |
| 일본 | 가운뎃점 `・` `･` · 전각 공백 | 장음 `ー` · 가타카나↔히라가나 |
| 라틴 | (키에서는 없음) | 악센트 — 2차 키 `latin_fold` 로만 본다. 키에서 접으면 프랑스어 단어끼리 충돌 |
| 공통 | — | **띄어쓰기 유무.** `앵클 부츠`≠`앵클부츠`. 접으면 `the ater` 사고. 대신 사전 별칭에 둘 다 넣는다 |

**2. 언어 칸을 정한다** (`normalize.lang_of_surface`). 한글→`ko`, 가나·한자→`ja`, 아랍 문자→`ar`. 라틴은 기사
언어가 라틴 언어(en·fr·it…)면 그 언어, 아니면(한국·일본 기사 안의 `Bottega Veneta`) 언어 무관 `la`.
**지금은 기사 언어를 못 받아** 표기의 문자 체계만으로 정한다 — 계약 A 에 `lang` 이 실리면 바뀐다.

**3. 사전을 찾는다** (`dictionary.lookup`).

| 표기 | 1차 | 2차 |
| --- | --- | --- |
| 한글·가나·아랍 | `(언어, 키)` | `키` 만으로 (언어 칸이 잘못 붙은 경우의 안전망) |
| 라틴 | `키` — **언어 무관** | `latin_fold(키)` — 악센트 접은 것 |

라틴을 언어 무관으로 보는 이유는 브랜드다 — `Gucci` 는 영·불·이 기사와 한국 기사 안에서 같은 글자다.
한 개념에 표현이 여럿 걸려도 결과는 개념당 하나다.

**4. 결과 수에 따라 갈린다.**

| 결과 | 처리 | 기록 |
| --- | --- | --- |
| 개념 하나 | 붙인다 | `method = DICT` |
| 없음 | 미등록으로 쌓는다 (기사 id · 표기 · 문맥) | `pl_unmapped_*` |
| 둘 이상 | 두 번째 지날 때 기사 분류로 가른다 | 아래 |

**5. 모호한 표기를 가른다** (`mapping.disambiguate`). 근거는 그 기사에서 **모호하지 않게 이미 붙은 개념들의 분류**다.
순서대로: 후보 중 그 분류 집합에 드는 것이 딱 하나면 그것 → 둘 이상 들면 진짜 모호한 것이라 **유보** →
아무것도 안 들지만 기사에 패션 개념이 하나라도 있고 패션 분류인 후보가 하나면 그것 → 아니면 유보.
`코트` 가 외투(apparel)·경기장(sports)에 걸렸고 기사에 신발이 있으면 외투다. 가르면 `method = CONTEXT`.
**유보는 세지 않고 `pl_mapping_decision` 성격의 기록만 남긴다** — 세지 않는 쪽이 잘못 세는 쪽보다 낫다.

**6. 기사·개념 한 쌍으로 접는다.** `부츠` 와 `boots` 가 같이 나와도 `boots` 는 그 기사에서 한 번. 어느 표현들이
붙였는지는 `expression_ids` 로 남긴다 — 오류 추적과 "이 표현을 고치면 어느 기사가 바뀌나" 의 근거다.

**연예인은 세되 옷과 섞지 않는다.** `제니` · `장원영` 은 `person` 분류의 개념이다. 세지 않는
쪽으로 치우면 "왜 이 신발이 떴나" 의 답을 버리게 된다 — 2026-09-18 실 DB 미등록에서 `제니`
11건 · `장원영` 10건으로 손꼽히게 큰 덩어리였다. 다만 옷·신발과는 **다른 축**이라 모호성을
가를 때의 근거로는 쓰지 않는다 (`mapping.FASHION_CATEGORIES` 에 없다). 한 사람이 무엇을
신었나는 개념 하나가 아니라 **같은 기사에 함께 붙은 개념 쌍**으로 보이고, 그것은 이미 지금
표로 셀 수 있다.

**일반 단어는 붙이되 세지 않는다.** `느낌` · `요즘` 은 `countable = false` 개념에 붙는다. 사전에 두는 이유는 매일
미등록으로 다시 올라오지 않게 하려는 것이고, 세지 않는 것은 랭킹이 `countable` 로 거른다.

### 실측에서 확인된 오탐 모드 (2026-09-17, 실 DB 478행)

| 모드 | 예 | 행 | 원인 | 고칠 자리 |
| --- | --- | --- | --- | --- |
| 다른 언어 어휘 라벨이 라틴 표기에 붙음 | `rose`(fr) → pink, 실은 로제·로즈골드 | 2 | 라틴 언어 무관 조회가 **어휘**까지 건너뜀 | 아래 예정 규칙 |
| 사람·회사 같은 이름 | `Dior`·`Balenciaga` → 창업자 개인, `루이 비통`(띄어쓴 표기)→개인 | 9 | 위키데이터에 회사 항목 없음 / 둘 다 있음 | 브랜드 질의 확장 · brand 우선 |
| 위키데이터 쓰레기 항목 | `케이트` → "Label" (실은 한국 브랜드 KATE·케이트 모스) | 3 | 라벨이 엉터리인 항목 | 항목 필터(사이트링크 수) |
| 더 긴 후보의 조각 | `레드 카펫` 의 `레드` → 색 | 1 | 추출이 둘 다 내고 우리가 짧은 쪽을 붙임 | 포함 관계 규칙(검토) |

라틴 경로(한국 기사 안의 알파벳 표기) 38행 중 8행 오탐(21%), 한글 경로 440행 중 7행(1.6%). 오탐이 한 경로에 몰려 있다.

### 예정 규칙 — 라틴 조회의 라벨 언어 제한

라틴 표기를 찾을 때 **브랜드·디자이너 라벨은 언어 무관**, **어휘 라벨은 기사 언어에 맞는 것만**(fr 기사→fr, it→it,
그 밖→en). 타입으로 막으면 맞게 붙은 `skirt`·`shirt`·`black`·`red` 27행을 잃고, 언어로 제한하면 틀린 `rose` 만
빠진다. 프랑스 기사에서는 `rose` 가 그대로 핑크로 붙는다.

## 미등록 → 사전 (검수, `scripts/concept-review.py`)

임베딩 기반 Top K 후보와 LLM 재판정 경로는 [concept-vector-retrieval.md](concept-vector-retrieval.md)를 본다.

```sh
python scripts/concept-review.py export --profile dev > review.tsv     # 영향 큰 것부터
python scripts/concept-review.py apply  --profile dev review.tsv --by human:jk
```

결정은 넷 — `LINK 개념id` · `NEW 이름/분류` · `EXCLUDE` · `DEFER`. 하나라도 반영되면 사전 버전이
오르고, 다음 `concept` Job 이 창 안의 기사에 저절로 붙인다. **관리 화면은 MVP 에 없다.**

## 실행

```sh
spark/scripts/submit.sh concept --profile dev --domain fashion            # 매 회차 (Airflow: spark_concept)
spark/scripts/submit.sh concept --profile dev --domain fashion --dry-run  # 사전만 반영하고 개념은 안 쓴다
```

초기 사전은 `spark/conf/concepts/*.json` — 위키데이터 브랜드·디자이너(`scripts/seed-concepts-wikidata.py`),
손으로 만든 어휘(`vocabulary-*.json`), 일반 단어(`generic-*.json`).

**매 실행이 이 파일들을 먼저 반영한다.** 사람이 한 번 넣어 주는 선행 조건으로 두지 않는다 — 순서를
틀리면 승격 키워드 전부가 미등록으로 쌓인다. 나중에 사전을 넣으면 창 안에서 실제로 붙은
표현은 검수 대기에서 내려가고 기사 이력은 남는다. 다시 넣는 것은 싸고 안전하다: 개념은 비어 있는 칸만 채우고 표현은 있으면
건드리지 않아 검수가 `REJECTED` 로 내린 쌍이 되살아나지 않는다. 파일에서 아무것도 못 읽으면 붙이지
않고 설정 오류로 세운다 — 그대로 두면 미등록 더미만 쌓기 때문이다.

## 표현과 개념은 다대다다

**여러 표현 → 개념 하나.** `sneakers` · `sneaker`(단복수) · `trainers`(지역 표현) · `스니커즈` · `スニーカー` 는
전부 개념 하나의 표현 행이다. 같은 언어에 표현이 여럿 있어도 된다 — `pl_concept_expression` 은
`(lang, normalized, concept_id)` 로 유일하고, `kind` 가 canonical · synonym · plural · variant · abbreviation 을
가른다.

**표현 하나 → 개념 여럿.** `trainers` 는 신발이기도 하고 사람(훈련시키는 이)이기도 하다. 두 개념에 다 걸어 두면
`ambiguous = true` 가 되고, 기사 안의 다른 개념 분류로 가른다 (`mapping.disambiguate`). 사람 쪽은 세지
않는 `generic` 개념으로 두면 된다 — 그래야 헬스 기사의 trainers 가 신발로 세어지지 않는다.

**비슷하다고 합치지 않는다.** `운동화` 는 `스니커즈` 보다 넓다. 같은 개념의 표현으로 넣지 말고 별도 개념
(`athletic shoes`)으로 두고 `sneakers` 를 그 하위로 건다. 넓은 말과 좁은 말은 상하위이고, 동의어가 아니다.

## 메모 — 아직 안 한 것

- **편집 거리 층.** 정확 일치가 없을 때 같은 언어 표현 중 글자 하나 차이(라틴 5글자 · 한글 3음절 이상, 후보
  개념이 하나일 때만)를 `VARIANT` 로 붙이는 층. 오타·표기 흔들림이 미등록 배치까지 하루를 기다리지 않게 하려는
  것이다. 임베딩은 오타에 약하고 편집 거리가 맞는 도구다. **보류** — 미등록 더미에서 실제로 얼마나 나오는지 본 뒤
  넣는다 (2026-09-17).

## MVP 밖 (순서대로)

1. 추출이 계약 A 에 `lang` · `context` 를 싣는다 → 질의를 파일 읽기로.
2. 미등록의 후보 생성(라틴 일치 · 음차 · 괄호 병기) + LLM 쌍 판정. **표를 통째로 넣지 않는다** —
   2026-09-16 실험에서 누설을 막고 재니 20%대였고, 후보 둘을 놓고 같은지 묻는 판정은 30/30 이었다.
3. 임베딩 후보 생성 — 아랍어처럼 번역 관계인 표현이 미등록에 쌓이는 것이 관측되면.
4. 여러 부모 · 개념 병합 도구 · 관리 화면 — 필요가 숫자로 보이면.

통합 후보 검색과 재정렬 정책은 [concept-candidate-ranking.md](concept-candidate-ranking.md)를 본다.
