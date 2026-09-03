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
└─ scripts/dev-setup.sh  로컬 가상환경
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
| 실제 경로 실행 | `docker compose run --rm airflow-cli airflow dags unpause fashion_example` 후 `... airflow dags trigger fashion_example`. 로그는 `./logs/` |
| 로컬 단위 테스트 | `./scripts/dev-setup.sh` 한 번, 이후 `.venv/bin/pytest` |
| 린트 | `.venv/bin/ruff check .` (AIR 규칙이 Airflow 2 식 import 를 잡는다) |

`dags test` 는 메타 DB 만 있으면 된다. scheduler·api-server 없이 `docker compose run` 한 번으로 돈다.

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

## 지금 없는 것

triggerer(deferrable), Celery·Redis, CI, slim 이미지, `uv.lock`. Kafka·MinIO 는 `datastore/` 로 나갔다. 각각 넣을 조건은 Jira `S15P21A102-146` 에 걸린 설계 문서에 있다.
