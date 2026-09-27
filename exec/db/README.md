# 3. DB 덤프

> **로컬에서 띄워 보실 거라면 이 파일은 필요 없습니다.** `local` 프로파일이 인메모리 H2 를 쓰고
> 기동하면서 데모 데이터를 자동으로 넣습니다 — [1번 문서의 로컬 실행](../1-build-deploy.md#로컬-실행)
> 을 보세요. 이 덤프는 **PostgreSQL 로 운영과 같은 구성을 띄울 때** 씁니다.


| 파일 | 크기 | 뽑은 날 | 출처 |
| --- | --- | --- | --- |
| `trendin-dump-20260927.sql` | 387 MB | 2026-09-27 | 운영 DB `forever102` |

## 들어 있는 것

표 구조는 **71개 전부**(`CREATE TABLE`), 데이터는 아래와 같습니다.

| 표 | 행 수 | 무엇 |
| --- | ---: | --- |
| `keyword_contents` | 226,754 | 키워드–기사 연결 |
| `keyword_metric_history` | 71,626 | 구간별 언급량 추이 |
| `keyword_country_daily_metrics` | 55,873 | 나라별 일간 지표 |
| `keyword_relations` | 42,026 | 키워드 연관 관계 |
| `contents` | 36,782 | 수집·정제된 기사 |
| `keyword_metrics` | 25,626 | 구간별 지표와 트렌드 유형 |
| `keywords` | 16,835 | 승격된 키워드 |
| `trends` | 166 | 트렌드 |
| `trend_analyses` | **130** | **AI 해설** (정의·주요 흐름·주목받는 이유) |

집계는 **2026-09-26 구간까지** 들어 있습니다. `pl_*`(파이프라인 내부 표)도 함께 들어 있으나 서비스 화면은 읽지 않습니다.

## 뺀 것

| 뺀 것 | 이유 |
| --- | --- |
| `members` · `member_domains` · `member_interest_keywords` · `member_oauth_accounts` | 실제 이메일과 비밀번호 해시가 들어가므로 제외 |
| `saved_trends` · `notifications` · `notification_settings` | 위 회원에 딸린 개인 활동 기록 |
| `pl_concept_embedding` | 개념 연결용 벡터. 재생성 가능하며 서비스 화면과 무관 |

**표 구조는 모두 들어 있고 데이터만 비어 있습니다.** 복원 후 회원가입을 하면 그대로 씁니다.

---

## 복원

```sh
# 1. DB 기동
docker compose -f infra/compose.yaml up -d postgres

# 2. 복원 (387MB 라 몇 분 걸립니다)
cat exec/db/trendin-dump-20260927.sql | \
  docker exec -i $(docker compose -f infra/compose.yaml ps -q postgres) \
  psql -U ssafy -d forever102

# 3. 백엔드 기동
docker compose -f infra/compose.yaml up -d backend
```

**복원 후 화면에서 회원가입을 해야** 개인화 기능(관심 키워드·저장·알림)을 볼 수 있습니다. 회원 데이터는 덤프에 없습니다.

---

## ⚠️ 복원했는데 화면이 비어 보일 때

트렌드 목록은 **오늘 기준** 집계 구간을 등호로 조회합니다. 이 덤프는 `2026-09-26` 구간까지라, 그보다 뒤에 복원하면 24시간 목록이 빕니다.

```sql
-- 어느 날짜까지 집계돼 있나
SELECT period, MAX(period_end) FROM keyword_metrics GROUP BY period;
```

해결은 두 가지입니다.

1. **파이프라인을 돌려 오늘 집계를 만듭니다** (정상 경로)

   ```sh
   docker compose run --rm airflow-cli airflow dags trigger spark_aggregate
   ```

2. 기간 필터를 `7일` · `30일` 로 바꿔 봅니다. 그 구간에는 자료가 남아 있을 수 있습니다.

---

## 스키마만 필요할 때

**Flyway 가 스키마를 소유합니다.** 덤프 없이 백엔드만 기동해도 표 16개가 만들어집니다.

| 항목 | 위치 |
| --- | --- |
| 마이그레이션 | `backend/src/main/resources/db/migration/V1`~`V12` |
| ERD | [`docs/erd/erd.md`](../../docs/erd/erd.md) |

덤프의 역할은 **스키마가 아니라 데이터 복원**입니다. 빈 DB 로 띄우면 표는 생기지만 트렌드·기사가 없어 화면이 빕니다.

---

## 덤프를 다시 뽑을 때

서비스 EC2 의 저장소 루트에서 실행합니다. 이 파일을 만든 명령입니다.

```sh
docker exec $(docker compose -f infra/compose.yaml ps -q postgres) \
  pg_dump -U ssafy -d forever102 \
  --exclude-table-data='members' \
  --exclude-table-data='member_domains' \
  --exclude-table-data='member_interest_keywords' \
  --exclude-table-data='member_oauth_accounts' \
  --exclude-table-data='saved_trends' \
  --exclude-table-data='notifications' \
  --exclude-table-data='notification_settings' \
  --exclude-table-data='pl_concept_embedding' \
  > exec/db/trendin-dump-$(date +%Y%m%d).sql
```

> ⚠️ `docker exec` 에 **`-t` 를 붙이면 안 됩니다.** TTY 가 붙으면 줄바꿈이 `\r\n` 으로 바뀌어 SQL 파일이 오염됩니다.
