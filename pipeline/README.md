# pipeline — TrendIn Airflow 파이프라인

패션 트렌드와 개발 트렌드 두 도메인의 수집·분석 DAG 가 **한 Airflow 배포** 위에서 돈다.
이 디렉터리는 팀 공용 스켈레톤이다: 컴포즈, 이미지, 패키지 배치, 앱 DB 접속 주입, 테스트 틀, 도메인별 예제 DAG.
도메인 로직·테이블·DDL 은 각 부품 브랜치가 가져온다.

- Airflow 3.3.1 · Python 3.12 · LocalExecutor · `apache/airflow:3.3.1-python3.12` 위 자체 Dockerfile
- 결정과 근거: Jira `S15P21A102-146`

## 구조

```
pipeline/
├─ compose.yaml          postgres · airflow-init · airflow-apiserver · airflow-scheduler · airflow-dag-processor (+ airflow-cli)
├─ Dockerfile            정식 이미지 + src/ editable 설치
├─ pyproject.toml        의존성 이름만. 버전은 Airflow constraints 가 고정
├─ pools.json            pool 시드. init 이 import 한다
├─ .env.example          → .env 로 복사해 채운다
├─ docker/postgres-init/ 앱 DB(trendin) 와 계정 생성 (빈 볼륨 초기화 때 한 번)
├─ dags/
│  ├─ fashion/           dag_id 접두어 fashion_, tag fashion
│  └─ dev/               dag_id 접두어 dev_, tag dev
├─ src/trendin/
│  ├─ common/            두 도메인이 진짜로 같이 쓰는 것만
│  ├─ fashion/
│  └─ dev/
├─ tests/                DagBag import 테스트 + 태스크 함수 단위 테스트
├─ spark/                Spark Job — 진입점 · 설정 · jar · 컴포즈 오버레이 (spark/README.md)
└─ scripts/dev-setup.sh  로컬 가상환경 (+ Spark 의존성과 jar)
```

## 처음 실행

요구: Docker Engine + Compose v2, 메모리 4 GB 이상.

```sh
cd pipeline
cp .env.example .env
# AIRFLOW_UID=$(id -u), 비밀번호 둘, AIRFLOW_JWT_SECRET=$(openssl rand -hex 32) 을 채운다
# TRENDIN_MINIO_ACCESS_KEY·SECRET_KEY 는 datastore/.env 의 MINIO_CRAWLER_* 와 같은 값
docker compose config --quiet        # 해석 검증
docker compose up -d --build         # 이미지 빌드 + 다섯 서비스 (datastore 가 먼저 떠 있어야 한다)
docker compose ps                    # 전부 healthy 인지
```

UI: http://127.0.0.1:8080 (로컬은 로그인 없이 admin). 서버에서는 SSH 터널로만 접근한다.

## 검증 명령

| 무엇 | 명령 |
|---|---|
| import 오류 | `docker compose run --rm airflow-cli airflow dags list-import-errors` (비어 있어야 함) |
| DAG 목록 | `docker compose run --rm airflow-cli airflow dags list` |
| 단일 프로세스 실행 | `docker compose run --rm airflow-cli airflow dags test fashion_example` |
| 수집을 실제로 돌린다 | [수집 운영](#수집-운영) 참조. 외부 사이트를 치므로 확인 명령과 다르게 다룬다 |
| 실제 경로 실행 | `docker compose run --rm airflow-cli airflow dags unpause fashion_example` 후 `... airflow dags trigger fashion_example`. 로그는 `./logs/` |
| 로컬 단위 테스트 | `./scripts/dev-setup.sh` 한 번, 이후 `.venv/bin/pytest` |
| 린트 | `.venv/bin/ruff check .` (AIR 규칙이 Airflow 2 식 import 를 잡는다) |

### GMS AI 연결 확인

`pipeline/.env`의 `GMS_KEY`를 Airflow 서비스에 주입하며, 코드는 키 값을 저장하지 않는다.
일반 테스트는 실제 GMS를 호출하지 않는다. 연결과 `gpt-5.4-nano`의 JSON 응답을 확인할 때만
환경변수를 설정해 통합 테스트를 별도로 실행한다.

```sh
GMS_KEY=<발급받은 키> .venv/bin/pytest tests/ai/test_gms_integration.py
```

확정된 분석 결과는 `description`, `summary`, `reason` 세 문자열만 가진 JSON 객체다.

`dags test` 는 메타 DB 만 있으면 된다. scheduler·api-server 없이 `docker compose run` 한 번으로 돈다.

## 수집 운영

기사를 실제로 받아 MinIO 와 장부에 넣는 일이다. 위 검증 명령과 달리 **외부 사이트를 친다** — 돌리기 전에 `datastore` 가 떠 있어야 한다.

기사가 MinIO 에 어떤 모양으로 놓이는지, 그 규칙을 고칠 때 어느 파일을 여는지는 [`docs/collect-storage.md`](docs/collect-storage.md).

아래에서 `CLI` 는 `docker compose run --rm --no-deps airflow-cli` 를 줄인 말이다.

### 주기 실행

| 무엇 | 명령 |
| --- | --- |
| 켠다 | `CLI airflow dags unpause fashion_collect` |
| 끈다 | `CLI airflow dags pause fashion_collect` |
| 지금 한 번 | `CLI airflow dags trigger fashion_collect` |
| 켜졌나 | `CLI airflow dags list` 의 `is_paused` 열 |

`fashion_collect` 은 매시 정각(KST), `dev_collect` 은 30분마다다. `dev_collect` 은 Hacker News 하나를 돌고, 매 실행이 최근 6시간에 올라온 story 를 Algolia API 로 묻는다. 6시간보다 오래 멈췄다면 그 구간은 아래 hn 백필로 메운다.

**켜는 순간 예약 회차가 한 번 바로 돈다.** `catchup=False` 라 밀린 회차가 몰려 돌지는 않지만, 직후에 `trigger` 까지 하면 실행 둘이 겹친다.

한 주기는 7소스 병렬로 20초에서 7분이다. 편차는 새 기사 수에서 온다 — 목록 소스(바자·코스모)가 기사마다 페이지를 받고 건당 3초쯤 걸린다.

### 과거분 백필

주기 실행이 보는 범위보다 오래된 것은 도메인별 백필 명령이 받는다. 둘 다 주기 실행과 같은 저장 루프를 쓴다 — 장부에 적히는 순간 소비 측이 읽는 뷰에 나타나므로, 백필이 따로 할 일은 없다.

#### 매거진 피드

주기 실행은 피드에 보이는 만큼(10건)만 받는다. 백필은 2페이지부터 넘기며 **발행일로 멈춘다** — 기사가 전부 `--since` 보다 오래된 페이지에서 끝난다. 첫 채움은 6개월이다.

```sh
CLI python -m trendin.fashion.collect.backfill vogue --since 2026-03-17T00:00+09:00 --store
```

| 인자 | 뜻 |
| --- | --- |
| `--since` | 이 시각 이후에 발행된 기사만 받는다. ISO-8601, 오프셋 필수. 기본값이 없다 |
| `--store` | MinIO·장부에 실제로 쓴다. 없으면 훑기만 한다 |
| `--json` | 정규화된 article.json 을 한 줄씩 낸다. 훑기 모드에서만 듣는다 — `--store` 와 같이 주면 아무것도 안 나온다 |

**프로필에 `page_param` 이 있는 피드 소스만 된다** — 지금은 `allure` · `gqkorea` · `marieclaire` · `vogue` · `wkorea`. 목록 소스(바자·코스모)와 페이지 넘김이 안 되는 피드는 거부한다. 새 소스의 `page_param` 은 등록할 때 프로브로 잰다.

소스 하나씩 받는다. 소스마다 호스트가 달라 3초 간격이 서로 막지 않으니, 여러 곳은 셸을 나눠 나란히 띄운다.

```sh
for s in allure gqkorea marieclaire vogue wkorea; do
  CLI python -m trendin.fashion.collect.backfill "$s" --since 2026-03-17T00:00+09:00 --store > "backfill-$s.log" 2>&1 &
done; wait
```

이미 받은 기사는 장부가 걸러 기사 페이지를 받지 않지만, 페이지는 끝까지 넘긴다. 그래서 끊긴 실행은 같은 명령으로 이어진다.

**실패가 찍혔으면 24시간 안에 같은 명령을 다시 돌린다.** 기사 페이지를 못 받은 기사는 장부에 대기 행으로 남고(S15P21A102-312) 다시 돌리면 후보로 통과한다. 다만 상한이 3회 또는 첫 실패로부터 24시간이고, 과거분 기사는 주기 실행의 후보에 다시 들어오지 않는다. 상한에 닿으면 주기 실행이 제목·URL·발행일·분류만으로 저장해 그대로 굳는다.

**백필 전에 주기 실행이 새 코드로 한 번 돌아 있어야 한다.** 장부 표와 칸은 DAG 첫 태스크(`ensure_schema`)만 만든다. 칸이 늘어난 코드로 백필을 먼저 돌리면 `column "..." does not exist` 로 끝난다(2026-09-18 실측). 급하면 같은 함수를 한 번 부른다 — `CLI python -c "from trendin.common.collect.db import Database; from trendin.common.collect.ledger import PostgresLedger; from trendin.fashion.collect import sources; PostgresLedger(Database.from_env()).ensure_schema({k: s.country for k, s in sources.BY_KEY.items()})"`.

**백필 중에는 `fashion_collect` 를 멈춘다** (`CLI airflow dags pause fashion_collect`, 끝나면 `unpause`). 백필은 2페이지부터 보고 주기 실행은 1페이지를 본다. 그 사이에 새 글이 올라오면 경계에 걸친 기사가 두 쪽에 동시에 잡히고, 둘 다 장부 거름을 통과해 MinIO 에 두 번 쓴다 — `collected_at` 이 달라 바이트가 갈리고 장부와 어긋난다(불변식 7).

기사 한 건마다 기사 페이지를 받으므로 같은 호스트 3초 간격이 그대로 붙는다. vogue 6개월이면 기사 1300건 남짓이라 한 시간 안팎이 걸린다.

| 끝 | 결과 |
| --- | --- |
| 기사가 전부 `--since` 보다 오래된 페이지 | 정상 종료 |
| 404·410·빈 피드 (역사가 짧은 피드) | 정상 종료 |
| 앞 페이지와 같은 기사 (`page_param` 이 안 먹는 피드) | 오류 — 프로필의 `page_param` 을 고친다 |
| 1000 페이지를 넘겨도 `--since` 에 못 닿음 | 오류 — 발행일 규칙을 의심한다 |
| 403·429 | 오류 — 그 호스트를 멈춘다 |

발행일을 못 읽은 기사는 `--since` 이후인지 몰라 경고를 남기고 건너뛴다.

#### Hacker News

주기 실행은 최근 6시간만 본다. hn 백필은 페이지가 아니라 시각 구간을 받는다. Algolia 가 한 질의에 1000건까지만 주고 페이지를 넘기지 못하게 해서다.

```sh
CLI python -m trendin.dev.collect.backfill hn --since 2026-08-03T00:00+09:00 --store
```

| 인자 | 뜻 |
| --- | --- |
| `--since` | 구간 시작(포함). 오프셋 필수 — KST 면 `+09:00`. 기본값이 없고, `--until` 까지 6주를 넘으면 거부한다 — 실수로 전량이 돌지 않게. 더 긴 공백은 나눠 돌린다 |
| `--until` | 구간 끝(제외). 없으면 지금 |
| `--store` | MinIO·장부에 실제로 쓴다. 없으면 훑기만 한다 |
| `--json` | 정규화된 article.json 을 한 줄씩 낸다. 훑기 모드에서만 듣는다 — `--store` 와 같이 주면 아무것도 안 나온다 |

첫 채움은 6주다(약 3만 3천 건, 6시간 조각이라 요청 170번 남짓·3초 간격). 멈춘 구간을 메울 때는 앞뒤로 넉넉히 줘도 된다 — 장부에 있는 글은 거른다. 이미 받은 조각에서 멈추지 않는다. 빈 구간이 어느 조각에 있을지 모르기 때문이다(매거진 피드 백필도 같다).

**소비 측이 한꺼번에 읽는다.** 6주 백필이 끝나면 그만큼의 행이 뷰에 들어와 있고, 다음 `ingest` 회차가 창(`lookback_hours`, 기본 168시간) 안에 든 몫을 한 번에 가져간다. 창보다 오래된 구간은 `--source objects` 재처리로 넣는다. 돌리기 전에 Spark 쪽에 시점을 알린다.

**백필 중에는 `dev_collect` 를 멈춘다** (`CLI airflow dags pause dev_collect`, 끝나면 `unpause`). `--until` 을 생략하면 마지막 조각이 주기 실행의 6시간 창과 겹치고, 둘이 같은 글을 거의 동시에 장부 거름에 통과시키면 둘 다 MinIO 에 쓴다. 두 쪽의 `collected_at`·점수가 달라 바이트가 다르고, 장부는 먼저 적은 해시를, MinIO 는 나중에 쓴 객체를 남겨 서로 어긋난다(불변식 7).

### 결과 확인

두 곳의 숫자가 맞물려야 한다 — 장부 행 수 = MinIO `article.json` 수.

```sh
CLI python -c "
from trendin.common.collect.db import Database
with Database.from_env().transaction() as c:
    cur = c.cursor()
    cur.execute('SELECT count(*), count(*) FILTER (WHERE fetch_state = %s), max(collected_at)'
                ' FROM collected_article', ('retrying',))
    total, waiting, last = cur.fetchone()
    print('장부', total, '행 / 본문 대기', waiting, '/ 마지막 수집', last)
"
```

```sh
CLI python -c "
import os, boto3, collections
s3 = boto3.client('s3', endpoint_url=os.environ['TRENDIN_MINIO_ENDPOINT'],
    aws_access_key_id=os.environ['TRENDIN_MINIO_ACCESS_KEY'],
    aws_secret_access_key=os.environ['TRENDIN_MINIO_SECRET_KEY'])
kinds, tok = collections.Counter(), {}
while True:
    r = s3.list_objects_v2(Bucket=os.environ['TRENDIN_MINIO_BUCKET'], **tok)
    for o in r.get('Contents', []):
        kinds[o['Key'].rsplit('/', 1)[-1]] += 1
    if not r.get('IsTruncated'):
        break
    tok = {'ContinuationToken': r['NextContinuationToken']}
print(dict(kinds))
"
```

`raw.*` 가 `article.json` 보다 적은 것은 정상이다. 회원 전용 기사는 원문을 저장하지 않는다.

소비 측이 무엇을 보는지는 창구를 직접 센다.

```sh
CLI python -c "
from trendin.common.collect.db import Database
with Database.from_env().transaction() as c:
    cur = c.cursor()
    cur.execute('SELECT count(*) FROM collected_article_event')
    print('창구에 보이는 행', cur.fetchone()[0])
"
```

창구(`collected_article_event` 뷰)의 행 수는 장부 행 수에서 **본문 대기 행을 뺀 값**이다. 대기 행은
MinIO 에 아직 아무것도 없어 뷰가 걸러 낸다 (`S15P21A102-312`). 소비 측이 실제로 몇 건을 가져갔는지는
Spark 의 처리 이력에서 본다 — 뷰는 창을 자를 뿐 무엇이 읽혔는지 기억하지 않는다.

### 조용히 멈췄나

자동 탐지는 아직 없다(`S15P21A102-199`). 그때까지는 이 값을 사람이 본다.

```sh
CLI python -c "
from trendin.common.collect.db import Database
with Database.from_env().transaction() as c:
    cur = c.cursor()
    cur.execute('SELECT source, max(collected_at) FROM collected_article GROUP BY source ORDER BY 2')
    for source, last in cur.fetchall():
        print('%-16s %s' % (source, last))
"
```

**소스 하나만 오래됐으면** 그 사이트가 구조를 바꿨거나 우리를 막은 것이다. 태스크는 성공으로 뜬다 — 후보를 0건 발견해도 실패가 아니라서다.

**전부 오래됐으면** DAG 이 꺼졌거나 앱 DB·MinIO 중 하나가 죽은 것이다. `CLI airflow dags list` 로 `is_paused` 부터 본다.

`discovered`·`skipped`·`not_modified`·단계별 실패 수는 수집 태스크의 XCom 에 남는다. 자동 이상 판정은 `S15P21A102-199`의 몫이다.

### 다시 읽히기

소비 측이 처음부터 다시 받아야 할 때, 장부가 원본이라 되돌릴 것이 없다. 창구는 장부를 그대로 비추므로
**수집 쪽에서 할 일이 없고**, 무엇을 다시 읽을지는 소비 측이 정한다 — Spark 의 처리 이력을 지우거나
`--source objects` 로 MinIO 프리픽스를 훑는다 (`spark/docs/02-input-contract.md` §6).

브로커가 있던 시절에는 여기에 `event_emitted_at` 을 `NULL` 로 되돌려 재발행시키는 절차가 있었다.
발급이 없어지면서 그 절차도 없어졌다 (Kafka 제거 3/3). 그 칸은 장부에 남아 있지만 새 행에는 채워지지
않고, 지금 그것을 지워도 아무 일도 일어나지 않는다.

## DAG 추가 규약

예제 `dags/fashion/fashion_example.py` · `dags/dev/dev_example.py` 를 베낀다.

1. **DAG 파일엔 실행 순서만.** 함수는 `src/trendin/<도메인>/` 에 두고 import 한다. DAG 파일 최상단에서 API·DB 를 부르지 않는다.
2. **import 는 `airflow.sdk` 에서.** `from airflow.sdk import dag, task, ...`. `airflow.decorators`·`airflow.models` 는 Airflow 2 식이라 쓰지 않는다.
3. **dag_id 는 `fashion_` / `dev_` 접두어, tags 에 도메인.**
4. **XCom 엔 ID·건수와 제한된 실패 표본만.** 수집 실패 표본은 최대 10건, 사유는 건당 200자로 제한한다. 문서 본문·행렬은 DB 를 거친다.
5. **모든 태스크는 멱등.** 재시도와 backfill 이 그 위에 선다. `default_args` 에 `retries` 를 둔다.
6. **외부 사이트를 치는 태스크는 `pool="crawler_pool"`.** 새 pool 이 필요하면 `pools.json` 에 줄을 추가한다(init 이 `--overwrite` 없이 import 하므로 기존 값은 유지된다).
7. **오래 기다리는 일(배치 API 등)은 `@task.sensor(mode="reschedule")`.** 대기 중 슬롯을 반납한다. poke 는 10~15분.
8. **동적 매핑 뒤에 결과를 모으는 태스크는 `trigger_rule=TriggerRule.ALL_DONE`.** 부분 실패에도 돈다.
9. **앱 DB 는 Connection ID `app_db`.** `PostgresHook(postgres_conn_id="app_db")` 또는 그 URI. 값은 환경변수 `AIRFLOW_CONN_APP_DB` 가 준다.
10. **UI 에서 Connection·Variable 을 만들지 않는다.** 전부 `.env` 환경변수(`AIRFLOW_CONN_*`, `AIRFLOW_VAR_*`)로 넣는다.
11. **스케줄 의미론은 고정.** `create_cron_data_intervals=True`(cron 스케줄이 구간을 가진다), `default_timezone=Asia/Seoul`(cron 문자열이 KST). 바꾸면 한 회차를 건너뛴다.
12. 새 DAG 는 `tests/test_dag_import.py` 의 `EXPECTED_DAG_IDS` 에 넣고, 태스크 함수는 `tests/<도메인>/` 에서 Airflow 없이 테스트한다.

## 의존성 추가

`pyproject.toml` 의 `dependencies` 에 이름을 넣고 `docker compose build`. 버전은 constraints 가 고정하며, constraints 에 없는 패키지(kiwipiepy 등)는 최신이 잡힌다.
같은 constraints 로 로컬도 맞추려면 `./scripts/dev-setup.sh` 를 다시 돈다.

## 코드 반영

`./src` 와 `./dags` 는 컨테이너에 바인드 마운트되어 있다. 파일을 고치면 재빌드 없이 다음 파싱·실행에 반영된다. 이미지를 다시 만드는 때는 의존성이 바뀔 때뿐이다.

## 수집 계층 저장소 (MinIO)

이 프로젝트에는 없다. `datastore/compose.yaml` 이 띄우고, 여기는 붙기만 한다.
접속 정보 · 기동 절차 · 검증 명령은 `datastore/README.md`.

- 네트워크 `s15p21a102-data` 를 external 로 참조한다. **저장소를 먼저 띄워야 이 프로젝트가 뜬다.**
- Airflow 태스크는 주소를 환경변수로 받는다: `TRENDIN_MINIO_ENDPOINT`, `TRENDIN_MINIO_BUCKET`, `TRENDIN_MINIO_ACCESS_KEY`, `TRENDIN_MINIO_SECRET_KEY`. 코드에 주소를 적지 않는다.
- `TRENDIN_MINIO_*` 키는 `datastore/.env` 의 `MINIO_CRAWLER_*` 와 같은 값이어야 한다. 쓰기만 되고 삭제는 안 되는 키다.

```sh
# 데이터 EC2 기동 순서 — 저장소가 먼저다
docker compose -f datastore/compose.yaml up -d
docker compose -f pipeline/compose.yaml up -d
```

## 배포 시 바뀌는 것

코드는 같고 `.env` 만 다르다.

- `AIRFLOW_CONN_APP_DB` 를 팀 postgres(`forever102`) 로. 같은 EC2 에 있으면 `infra/compose.yaml` 의 `s15p21a102-shared` 네트워크를 외부 참조해 호스트 `postgres`, 다른 EC2 면 접근 경로부터 열어야 한다.
- 비밀번호·JWT 비밀은 서버에서만 생성한다. `.env` 는 Git 에 올리지 않는다.
- UI 포트는 `127.0.0.1` 바인드 그대로 두고 SSH 터널로 본다.

## Spark

`spark/` 에 있다. Airflow 가 `spark-submit` 으로 깨우는 Job 세 개(`ingest` · `extract` · `aggregate`)와 그 실행 환경이다.

**컨테이너는 늘지 않는다.** Spark 는 상시 서비스가 아니라 Airflow 가 `spark-submit` 으로 깨우면 돌고 끝나는 프로그램이다. 그래서 Spark 컨테이너를 따로 띄우는 대신, Airflow 이미지에 JRE 와 `pyspark` 를 얹은 파생 이미지를 쓴다.

```sh
docker compose -f ../datastore/compose.yaml up -d          # MinIO. 먼저다
spark/scripts/fetch-jars.sh                                # jar 를 호스트에 받아둔다
spark/scripts/build-image.sh                               # 런타임 → 배포, 두 단계
docker compose -f compose.yaml -f spark/compose.spark.yaml up -d
```

`compose.yaml` 은 건드리지 않는다 — `spark/compose.spark.yaml` 오버레이가 Airflow 서비스의 `image` 만 바꾼다. 되돌릴 때는 `-f` 를 뺀다.

`Dockerfile` 은 `BASE_IMAGE` 인자 하나를 받는다. 기본값이 정식 Airflow 이미지라 여기까지는 종전과 같고, Spark 배포만 `spark/Dockerfile` 이 만든 런타임 이미지를 넣어 그 위에 우리 패키지를 얹는다. 무거운 것을 아래에 두는 이유는 `src` 가 바뀔 때마다 그 위의 모든 층이 캐시를 잃기 때문이다 — 순서를 반대로 두었을 때 배포 잡이 6분에서 13분이 됐다.

로컬에서 호스트 `.venv` 로 돌릴 때는 `spark/compose.dev.yaml` 쪽을 쓴다.

절차와 결정은 [`spark/README.md`](spark/README.md), 설계는 [`spark/docs/`](spark/docs/).

## 지금 없는 것

triggerer(deferrable), Celery·Redis, CI, slim 이미지, `uv.lock`. MinIO 는 `datastore/` 로 나갔다. 각각 넣을 조건은 Jira `S15P21A102-146` 에 걸린 설계 문서에 있다.
