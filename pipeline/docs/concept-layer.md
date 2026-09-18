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

**지금(MVP)은 이 파일이 없고 DB 에서 만든다.** `pl_document_candidate ⋈ pl_keyword_id_map ⋈
pl_content_id_map` 으로 기사별 선별 표기를 읽는다 (`io/concepts.py` `OCCURRENCES_SQL`). 그 표에는
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

랭킹이 기대는 규칙 셋:

- **기사·개념 한 쌍에 한 행.** 기본키다. 같은 기사에서 표현이 몇 개든, 몇 번 다시 처리하든 한 행.
- **`countable = false` 는 세지 않는다.** `pl_concept` 을 조인해 거른다.
- **상위 묶음은 자손을 합쳐 `count(distinct article_id)`.** `boots` 와 `ankle boots` 가 한 기사에
  같이 있어도 `boots` 묶음은 1 이다. 세부 순위는 개념 id 그대로(정확 집계), 분류 수준 순위는 묶음.

## 표

**전부 파이프라인 표다. Flyway 마이그레이션이 없다.** 스프링이 개념 표를 읽지 않으므로 서비스 표로 만들
이유가 없고, 만들면 백엔드 배포와 엮이기만 한다 (2026-09-17 결정). 개념 표 넷도 `pl_` 접두사로
`concept` Job 이 처음 돌 때 만든다 (`io/concepts.py` 의 DDL). 화면이 개념을 읽게 되는 날 서비스
표로 승격한다 — `contents` 가 걸어온 길이다(표가 먼저 있고 Flyway 가 뒤에 baseline 으로 받아들였다).
표는 팀 서비스 DB 한 곳(`SPARK_APP_DB_URL` 이 가리키는 곳, 지금 `pl_document_candidate` 가 있는 DB)에만 생긴다.

| 표 | 키 | 쓰는 쪽 |
| --- | --- | --- |
| `pl_concept_category` | `code` | 분류 목록. Job 이 만들 때 아홉 개를 넣는다 |
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

## 붙이는 규칙 (`concept/mapping.py`)

1. 표기를 비교키로 만든다. 기존 규칙 + 아랍어(발음 부호·알리프 변형·타 마르부타) + 일본어(가운뎃점).
2. 사전을 본다. 한글·가나·아랍 문자는 `(lang, key)`, **라틴은 언어 무관** — `Gucci` 는 영어·프랑스어·
   이탈리아어 기사와 한국 기사 안에서 같은 글자다. 라틴은 악센트를 접은 2차 키로 한 번 더 본다.
3. 하나면 붙인다(`DICT`). 없으면 미등록.
4. 둘 이상이면 기사 안에 이미 붙은 개념들의 분류로 가른다(`CONTEXT`). 같은 분류 후보가 하나면 그것,
   후보 분류가 서로 부딪히면 유보, 근거가 없고 패션 후보가 하나면 그것, 아니면 유보.
   **유보는 세지 않고 기록만 남긴다** — 세지 않는 쪽이 잘못 세는 쪽보다 낫다.

## 미등록 → 사전 (검수, `scripts/concept-review.py`)

```sh
python scripts/concept-review.py export --profile dev > review.tsv     # 영향 큰 것부터
python scripts/concept-review.py apply  --profile dev review.tsv --by human:jk
```

결정은 넷 — `LINK 개념id` · `NEW 이름/분류` · `EXCLUDE` · `DEFER`. 하나라도 반영되면 사전 버전이
오르고, 다음 `concept` Job 이 창 안의 기사에 저절로 붙인다. **관리 화면은 MVP 에 없다.**

## 실행

```sh
spark/scripts/submit.sh concept --profile dev --domain fashion --seed   # 처음 한 번: 초기 사전 넣고 붙인다
spark/scripts/submit.sh concept --profile dev --domain fashion          # 매 회차 (Airflow: spark_concept)
```

초기 사전은 `spark/conf/concepts/*.json` — 위키데이터 브랜드·디자이너(`scripts/seed-concepts-wikidata.py`),
손으로 만든 어휘(`vocabulary-*.json`), 일반 단어(`generic-*.json`). 다시 넣어도 있는 것을 덮지 않는다.

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
