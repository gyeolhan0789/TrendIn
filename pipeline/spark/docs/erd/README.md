# ERD 사본

다른 곳에서 관리되는 문서의 **사본**이다. 여기서 고치지 말고 원본을 고친 뒤 다시 복사한다.

| 파일 | 상태 | 내용 |
| --- | --- | --- |
| [`erd-00-current.md`](erd-00-current.md) | **정본** | 현행 스키마. 다이어그램 이미지의 전사본 |
| [`erd-01-enum-member-taxonomy.md`](erd-01-enum-member-taxonomy.md) | 미채택 제안 | 열거 타입 · 회원 · 인증 · 분류 체계 |
| [`erd-02-keyword-trend-relation.md`](erd-02-keyword-trend-relation.md) | 미채택 제안 | 키워드 사전 · 분석 기반 · 트렌드 · 연관 관계 |

## 01·02 를 지우지 않고 두는 이유

01·02 는 현행 스키마를 다듬으려던 개정 제안이다. 채택되지 않았지만 **거기 적힌 문제 지적은 여전히 유효하다.** 나중에 같은 문제에 부딪혔을 때 이미 검토된 근거를 다시 만들지 않으려고 남긴다.

특히 아래 지적들은 현행 스키마에 그대로 남아 있는 위험이다.

| 01·02 의 지적 | 현행 스키마 |
| --- | --- |
| `url` 에 직접 UNIQUE 를 걸면 멀티바이트 URL 이 B-tree 인덱스 항목 상한(약 2704바이트)을 넘겨 삽입이 실패할 수 있다. 해시 컬럼에 걸어야 한다 (02 §8) | `contents.url` 이 varchar UK 다 |
| 언급량 0인 날과 수집 실패한 날을 구분하려면 일자별 수집 상태 테이블이 필요하다 (02 §2) | 해당 테이블이 없다 |
| 기간 종속 데이터는 PK 에 `period` 를 포함해야 한다 (02 §9) | `keyword_relations` 에 `period` 가 없다 |
| 분석 미완료와 분석 실패를 구분하려면 상태 컬럼이 필요하다 (02 §7) | `trends.summary`·`reason` 이 인라인이라 상태가 없다 |
| 분야 계층을 테이블로 두면 무결성을 DB 가 보장한다 (01 §6·§7) | `domain` 이 varchar 다 |

**현행 스키마를 따르되, 이 목록은 알고 있어야 한다.** 각 항목이 Spark 쪽에 어떤 한계로 나타나는지는 [`../00-overview.md` §7](../00-overview.md) 에 정리했다.

01·02 의 회원·인증 부분(`MEMBER_OAUTH_ACCOUNTS`, `REFRESH_TOKENS`, `MEMBER_NOTIFICATION_SETTINGS`)은 Spark 범위 밖이라 검토하지 않았다.
