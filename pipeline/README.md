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

`dags test` 는 메타 DB 만 있으면 된다. scheduler·api-server 없이 `docker compose run` 한 번으로 돈다.

## 수집 운영

기사를 실제로 받아 MinIO·Kafka·장부에 넣는 일이다. 위 검증 명령과 달리 **외부 사이트를 친다** — 돌리기 전에 `datastore` 가 떠 있어야 한다.

아래에서 `CLI` 는 `docker compose run --rm --no-deps airflow-cli` 를 줄인 말이다.

### 주기 실행

| 무엇 | 명령 |
| --- | --- |
| 켠다 | `CLI airflow dags unpause fashion_collect` |
| 끈다 | `CLI airflow dags pause fashion_collect` |
| 지금 한 번 | `CLI airflow dags trigger fashion_collect` |
| 켜졌나 | `CLI airflow dags list` 의 `is_paused` 열 |

`fashion_collect` 은 매시 정각(KST), `dev_collect` 은 30분마다다. `dev_collect` 은 소스가 비어 있어 켜도 수집 태스크가 돌지 않는다 — 어댑터는 `S15P21A102-165` 가 채운다.

**켜는 순간 예약 회차가 한 번 바로 돈다.** `catchup=False` 라 밀린 회차가 몰려 돌지는 않지만, 직후에 `trigger` 까지 하면 실행 둘이 겹친다.

한 주기는 7소스 병렬로 20초에서 7분이다. 편차는 새 기사 수에서 온다 — 목록 소스(바자·코스모)가 기사마다 페이지를 받고 건당 3초쯤 걸린다.

### 과거분 백필

주기 실행은 피드에 보이는 만큼(10건)만 받는다. 그보다 오래된 것은 이 명령이 받는다.

```sh
CLI python -m trendin.fashion.collect.backfill vogue --pages 30 --store
```

| 인자 | 뜻 |
| --- | --- |
| `--pages` | 2페이지부터 몇 장. 기본값이 없다 — 실수로 30장이 돌지 않게 |
| `--store` | MinIO·장부에 실제로 쓴다. 없으면 훑기만 한다 |
| `--json` | 정규화된 article.json 을 한 줄씩 낸다. 훑기 모드에서만 듣는다 — `--store` 와 같이 주면 아무것도 안 나온다 |

**RSS 5소스만 된다** — `allure` · `gqkorea` · `marieclaire` · `vogue` · `wkorea`. 목록 소스(바자·코스모)는 거부한다. 목록에 보이는 것이 전부라 과거분이라는 개념이 없다.

`--store` 를 주면 한 페이지가 통째로 이미 받은 기사일 때 멈춘다. 훑기 모드는 장부가 없어 그 판정을 못 하므로 `--pages` 만큼 다 돈다.

발급은 백필이 하지 않는다. 다음 주기 실행의 발급 태스크가 장부의 미발급 행을 이어 낸다.

### 결과 확인

세 곳의 숫자가 맞물려야 한다 — 장부 행 수 = MinIO `article.json` 수 = 토픽의 기사 이벤트 수.

```sh
CLI python -c "
from trendin.common.collect.db import Database
with Database.from_env().transaction() as c:
    cur = c.cursor()
    cur.execute('SELECT count(*), count(event_emitted_at), max(collected_at) FROM collected_article')
    total, emitted, last = cur.fetchone()
    print('장부', total, '행 / 미발급', total - emitted, '/ 마지막 수집', last)
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

```sh
docker exec s15p21a102-datastore-kafka-1 \
  /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic raw-file-ready
```

`raw.*` 가 `article.json` 보다 적은 것은 정상이다. 회원 전용 기사는 원문을 저장하지 않는다.

토픽 건수는 장부보다 **소스 수 × 실행 횟수**만큼 많다. 실행마다 소스별 요약 이벤트가 하나씩 더 나가기 때문이다 — `object_key` 가 `null` 인 것이 그것이다.

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

**전부 오래됐으면** DAG 이 꺼졌거나 앱 DB·MinIO·Kafka 중 하나가 죽은 것이다. `CLI airflow dags list` 로 `is_paused` 부터 본다.

새 글이 없어서 안 늘어난 것과는 구분이 안 된다. 그 판정이 `S15P21A102-199` 의 몫이다.

### 다시 내기

토픽을 비웠거나 소비 측이 처음부터 다시 받아야 할 때, 장부가 원본이라 그대로 재구성한다.

```sh
CLI python -c "
from trendin.common.collect.db import Database
with Database.from_env().transaction() as c:
    cur = c.cursor()
    cur.execute('UPDATE collected_article SET event_emitted_at = NULL, event_run_id = NULL')
    print('되돌린 행:', cur.rowcount)
"
CLI airflow dags trigger fashion_collect
```

발급 태스크가 미발급 행을 내므로 다음 실행부터 다시 나간다. MinIO 는 건드리지 않는다.

한 회차가 밀린 것을 **다 비운다.** 500건씩 묶어 내되 남은 게 없을 때까지 돈다 — 1200건에 0.2초다. `trigger` 한 번이면 끝이고 회차를 나눠 돌릴 필요가 없다.

## DAG 추가 규약

예제 `dags/fashion/fashion_example.py` · `dags/dev/dev_example.py` 를 베낀다.

1. **DAG 파일엔 실행 순서만.** 함수는 `src/trendin/<도메인>/` 에 두고 import 한다. DAG 파일 최상단에서 API·DB 를 부르지 않는다.
2. **import 는 `airflow.sdk` 에서.** `from airflow.sdk import dag, task, ...`. `airflow.decorators`·`airflow.models` 는 Airflow 2 식이라 쓰지 않는다.
3. **dag_id 는 `fashion_` / `dev_` 접두어, tags 에 도메인.**
4. **XCom 엔 ID·건수만.** 문서 본문·행렬은 DB 를 거친다.
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

## 수집 계층 저장소 (Kafka · MinIO)

이 프로젝트에는 없다. `datastore/compose.yaml` 이 띄우고, 여기는 붙기만 한다.
접속 정보 · 기동 절차 · 검증 명령은 `datastore/README.md`.

- 네트워크 `s15p21a102-data` 를 external 로 참조한다. **저장소를 먼저 띄워야 이 프로젝트가 뜬다.**
- Airflow 태스크는 주소를 환경변수로 받는다: `TRENDIN_KAFKA_BOOTSTRAP`, `TRENDIN_KAFKA_TOPIC_RAW_FILE_READY`, `TRENDIN_MINIO_ENDPOINT`, `TRENDIN_MINIO_BUCKET`, `TRENDIN_MINIO_ACCESS_KEY`, `TRENDIN_MINIO_SECRET_KEY`. 코드에 주소를 적지 않는다.
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
docker compose -f ../datastore/compose.yaml up -d          # Kafka · MinIO. 먼저다
spark/scripts/fetch-jars.sh                                # jar 를 호스트에 받아둔다
spark/scripts/build-image.sh                               # 이미지 두 단계
docker compose -f compose.yaml -f spark/compose.spark.yaml up -d
```

`Dockerfile` 과 `compose.yaml` 은 건드리지 않는다 — `spark/Dockerfile` 이 `s15p21a102/pipeline:local` 을 `FROM` 으로 상속하고, `spark/compose.spark.yaml` 오버레이가 Airflow 서비스의 `image` 만 바꾼다. 되돌릴 때는 `-f` 를 뺀다.

로컬에서 호스트 `.venv` 로 돌릴 때는 `spark/compose.dev.yaml` 쪽을 쓴다.

절차와 결정은 [`spark/README.md`](spark/README.md), 설계는 [`spark/docs/`](spark/docs/).

## 지금 없는 것

triggerer(deferrable), Celery·Redis, CI, slim 이미지, `uv.lock`. Kafka·MinIO 는 `datastore/` 로 나갔다. 각각 넣을 조건은 Jira `S15P21A102-146` 에 걸린 설계 문서에 있다.
