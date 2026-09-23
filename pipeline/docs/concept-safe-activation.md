# 개념 연결 안전 활성화 (S15P21A102-363)

자동 연결을 **도는 것**과 **사전에 반영하는 것**으로 갈랐다. 2026-09-23 팀 결정으로 반영을 켠다 —
LLM 이 넣되, 넣은 것은 전부 회차 번호와 함께 원장에 남기고 회차 단위로 되돌릴 수 있게 한다.

평가 계약과 승인 기준은 [concept-quality-evaluation.md](concept-quality-evaluation.md) 에 있다.
이 문서는 **켜고 끄는 방법, 무엇이 남는가, 어떻게 되돌리는가**다.

## 왜 갈랐나

붙이는 것과 떼는 것이 비대칭이라서다. `apply_links` 가 하는 일은 `pl_concept_expression` 에
행을 넣는 것이고, 그 행이 생기면 그다음부터는 LLM 이 끼지 않는다 — 평범한 사전 조회가 그 표기를
계속 그 개념에 붙인다. 동시에 미등록 행이 `RESOLVED` 가 되어 검수 대기에서도 내려간다. 틀린
판정 하나가 "그때 한 번 틀렸다" 가 아니라 **아무도 다시 보지 않는 사전 항목**이 된다.

그 비대칭을 원장과 되돌리기 명령으로 메웠다. 붙이는 것도 떼는 것도 회차 하나 단위다.

## 스위치

| 설정 | 하는 일 | 지금 |
| --- | --- | --- |
| `concept.automation.enabled` | 판정을 **돌린다.** LLM 을 부르고 후보를 찾고 관문을 태운다 | `false` |
| `concept.automation.apply_links` | 판정을 **사전에 넣는다.** 끄면 제안으로만 남는다(관찰 모드) | `true` |
| `concept.automation.create_concepts` | "새 개념" 판정을 새 개념으로 넣는다 (세는 개념) | `true` |
| `concept.automation.mint_uncounted` | 새 개념을 세지 않는 개념으로 만들 분류. 예: `["person"]` | `[]` |

`enabled` 는 아직 꺼 둔다. 첫 회차는 `--auto-link` 로 손수 돌려 걸리는 시간과 갈래를 로그로 본
뒤에 올린다. `create_concepts` 는 `apply_links` 없이 켜지지 않는다 (`concept/workflow.AutomationPolicy`).

## 반영 모드가 남기는 것

자동 판정이 사전과 순위에 닿는 자리는 셋이고, 셋 다 원장 `pl_concept_change` 에 회차 번호
(`run_id`, 예: `auto-20260923T003612Z`)로 남는다.

| action | 무엇이 바뀌었나 |
| --- | --- |
| `DECISION` | 판정 표에 결론을 적었다. `EXCLUDE` 는 적히는 순간 순위에서 그 표기를 뺀다 |
| `LINK` | 기존 개념에 표현을 붙였다. 미등록은 `RESOLVED` 가 된다 |
| `MINT` | 새 개념과 그 표현을 만들었다. `mint_uncounted` 에 든 분류만 세지 않는다 |

사전 버전은 회차당 새 개념 한 번, 연결 한 번씩만 오른다. 원장 줄마다 모델·프롬프트 버전·근거·바꾸기
전 미등록 상태가 같이 남는다. 로그 끝에는 회차 번호와 되돌리는 명령이 찍힌다.

```
자동 반영 회차 auto-20260923T003612Z 시작
자동 반영 회차 auto-20260923T003612Z: 질문 N · 호출 시도 N · LINK N · DEFER N — 되돌리려면
scripts/concept-review.py rollback --run auto-20260923T003612Z --by human:<이름>
```

## 되돌리기

```sh
.venv/Scripts/python scripts/concept-review.py runs --profile dev
.venv/Scripts/python scripts/concept-review.py rollback --profile dev \
    --run auto-20260923T003612Z --by human:jk --dry-run
.venv/Scripts/python scripts/concept-review.py rollback --profile dev \
    --expr ko 무신사 --by human:jk
```

지우지 않고 상태를 내린다.

- 연결 표현은 `REJECTED`, 새 개념은 `RETIRED` 와 그 표현 `REJECTED` 가 된다
- 기사에 붙은 행을 치운다. 되돌린 표현만으로 붙은 행은 지우고, 다른 표현과 함께 붙은 행은 그 표현만 뺀다
- 되돌린 표기마다 **사람 보류(`DEFER`)** 가 최신 결정으로 남는다. `EXCLUDE` 로 빠졌던 표기가 순위에
  돌아오고, 다음 회차 판정이 그 표기를 다시 묻지 않으며, 연결 반영도 사람 결정이 있는 표기를 덮지 않는다
- 미등록은 검수 대기(`PENDING`)로 돌아가 다음 `export` 에 나온다

**사람이 손댄 것은 되돌리지 않는다.** 원장에는 자동 판정이 한 일만 적힌다. 새 개념이라도 검수가 표현을
더 붙였으면 그 개념은 두고, 두었다고 알린다.

## 세지 않는 개념은 순위에서 키워드를 뺀다

`countable=false` 개념에 붙은 키워드는 순위에서 빠진다 (`metrics/concepts.build_grouping`).
여름·Vogue 처럼 늘 나오지만 트렌드가 아닌 말을 사전에서 알아보되 순위에서 빼는 칸이다.

새 개념에 이 칸을 쓰면 안 된다. 사전에 없던 표기는 그때까지 키워드 그대로 순위에 셌으므로, 세지 않는
새 개념을 만드는 순간 원래 순위에 오르던 것이 숨는다. 2026-09-23 첫 회차는 837개를 전부 세지 않게
만들어 키워드 833개(사람 443 · 브랜드 133 · 스타일 63 · 의류 55 …)가 빠질 뻔했고, 순위 집계 전에
세는 개념으로 바꿨다.

2026-09-23 임시 Postgres 에서 한 회차(판정 3 · 새 개념 2 · 연결 1)를 넣고 되돌려, 위 항목과
"같은 연결·같은 새 개념이 자동으로 다시 들어가지 않는다" 를 확인했다.

## 관찰 모드로 돌아가기

`apply_links` 를 `false` 로 내리면 판정은 돌되 결과는 `pl_unmapped_expression.proposal` 에 제안으로만
남는다. 판정 표에도 적지 않는다 — 적으면 `concept/workflow.reusable` 이 그 표현을 다시 묻지 않는다.
이미 들어간 것은 그대로이니 필요하면 위 명령으로 회차를 내린다.

## 검수

```sh
.venv/Scripts/python scripts/concept-review.py export --profile dev > review.tsv
#   ... decision·concept 열이 제안으로 미리 채워져 있다. 틀린 줄만 고친다 ...
.venv/Scripts/python scripts/concept-review.py apply --profile dev review.tsv --by human:jk
```

`why` 열에 판정이 왜 그렇게 봤는지가 적힌다. `apply` 는 그 열을 읽지 않는다. **손대지 않은 줄은
제안대로 반영된다.**

## 한 번 해야 하는 것 — 제목 시절 문맥을 비운다

문맥 표본은 표현당 20개가 상한이고, 같은 기사의 표본은 다시 쓰지 않는다
(`io/concepts.UNMAPPED_MERGE_SQL`). 2026-09-21 에 쌓인 표본은 전부 **기사 제목**이라 그 표현은
앞으로도 등장 문장을 받지 못한다. 2026-09-23 기준 판정 대상 1,257개 표현의 표본 9,729행 중 본문
문장은 380행뿐이었다.

판정에 오르는 표현만 한 번 비운다. 다음 회차가 등장 문장으로 다시 채운다.

```sql
DELETE FROM pl_unmapped_context c
 USING pl_unmapped_expression u
 WHERE c.unmapped_id = u.id AND u.article_count >= 5;
```

지워도 잃는 것이 없다 — 기사에서 다시 만드는 파생 데이터다. 판정이 보는 문맥은 이것과 무관하게
그 회차에 본문에서 뽑은 등장 문장이다 (Job 이 메모리에서 바로 넘긴다). 이 표본은 **사람이 읽는
쪽**이다.

## 2026-09-23 실측과 남은 것

문맥이 붙은 운영 미등록 773건(gpt-4o-mini, 묶음 10)이 새 개념 615 · 제외 93 · 연결 49 · 유보 16 으로
갈렸다. 연결 49건 중 확실한 오류는 2건(`무신사 → musinsa standard`, `materials → fabric`)이라 승인
기준(precision 99%)에는 못 미친다. 그래서 첫 몇 회차는 `runs` 로 회차마다 훑는다.

반영을 켠 채로 고쳐 나갈 것:

- 분류 감점이 이름이 정확히 맞는 후보를 "없음" 으로 지운다 (`Kim Kardashian` person ↔ designer 등 5건)
- 모델이 복수형으로 답하면 단수 개념을 못 찾는다 (`slip dresses`, `uggs` 등 3건)
- 패션 낱말이 제외로 샌다 (`윈터`, `bra`, `반팔`, `calzini bianchi`)
- 사전에 브랜드 항목이 없어 창업자 개념에 붙는다 (`balenciaga`, `르메르`, `Wales Bonner`)
- `retrieval.meaningful_candidate_threshold` 를 벡터가 켜진 상태로 다시 잰다
