# 09 — 개발과 테스트

폴더 구조, 로컬 실행, 테스트 전략, Airflow 연동.

## 1. 폴더 구조

`pipeline/README.md` 의 배치 규약을 따른다 — **DAG 파일에는 실행 순서만, 함수는 `src/trendin/` 아래.**

```
pipeline/
├─ spark/
│  ├─ docs/                    이 문서들
│  ├─ jobs/                    spark-submit 진입점
│  │  ├─ ingest.py
│  │  ├─ extract.py
│  │  └─ aggregate.py
│  ├─ conf/
│  │  ├─ base.yaml             임계값 기본값
│  │  ├─ local.yaml            로컬 오버라이드 (호스트 포트)
│  │  ├─ dev.yaml              데이터 EC2 오버라이드 (서비스 이름)
│  │  └─ log4j2.properties     JVM 로그
│  ├─ versions.sh              Spark · jar 버전의 단일 출처
│  ├─ Dockerfile               팀 공용 이미지 + JRE + pyspark
│  ├─ compose.dev.yaml         로컬 오버레이 (호스트 .venv 용)
│  ├─ compose.spark.yaml       배포 오버레이 (컨테이너 안 실행)
│  ├─ scripts/                 dev-setup · fetch-jars · build-image · submit · check-jars
│  ├─ sql/                     서버사이드 MERGE 문 ([08 §4])
│  ├─ jars/                    런타임 jar (git 제외)
│  └─ tests/
│     ├─ unit/                 Spark 없이
│     ├─ spark/                local[2] SparkSession
│     ├─ integration/          compose 필요
│     └─ fixtures/
│        ├─ corpus/            고정 샘플 문서
│        └─ snapshots/         추출 결과 스냅샷
│
├─ src/trendin/spark/          로직 (jobs 가 import 한다)
│  ├─ io/                      kafka · minio · jdbc
│  ├─ normalize/               [03]
│  │  ├─ base.py
│  │  └─ adapters/
│  ├─ extract/                 [04]
│  ├─ registry/                [05]
│  ├─ metrics/                 [06] [07]
│  └─ common/                  설정 · 로깅 · 시각
│
└─ dags/dev/ · dags/fashion/   Spark 태스크를 붙이는 DAG
```

**`jobs/` 와 `src/trendin/spark/` 를 나누는 이유** — `jobs/*.py` 는 `spark-submit` 이 실행하는 얇은 진입점이다. 인자 파싱, SparkSession 생성, 단계 호출만 한다. 로직이 여기 있으면 테스트할 때 `spark-submit` 을 거쳐야 한다.

`src/trendin/` 아래에 두는 것은 `pipeline/Dockerfile` 이 이미 editable 설치를 하고 `compose.yaml` 이 바인드 마운트하기 때문이다. 새 경로를 만들면 그 배선을 다시 해야 한다.

## 2. 로컬 실행

### 필요한 것

| | 기존 | 추가 |
| --- | --- | --- |
| PostgreSQL | `pipeline/compose.yaml` 에 있음 | — |
| Airflow | 있음 | — |
| Kafka | `datastore/compose.yaml` 에 있음 (S15P21A102-156) | — |
| MinIO | `datastore/compose.yaml` 에 있음 (S15P21A102-156) | — |
| Spark | 없음 | 로컬 `pyspark` |

이 절을 처음 쓸 때는 Kafka·MinIO 가 없었다. 지금은 `datastore/` 가 띄우므로 **오버레이가 다시 띄우지 않는다.** 같은 브로커를 두 컴포즈 프로젝트가 각자 띄우면 컨테이너가 둘이 되고 포트와 볼륨이 부딪힌다.

```sh
docker compose -f datastore/compose.yaml up -d              # Kafka · MinIO. 먼저다
cd pipeline

# 로컬 (호스트 .venv 에서 spark-submit)
docker compose -f compose.yaml -f spark/compose.dev.yaml up -d

# 데이터 EC2 (Job 이 컨테이너 안)
spark/scripts/build-image.sh                                # 이미지 두 단계
docker compose -f compose.yaml -f spark/compose.spark.yaml up -d
```

순서는 강제돼 있다 — `pipeline/compose.yaml` 이 네트워크 `s15p21a102-data` 를 external 로 참조하므로, 저장소가 없으면 두 번째 명령이 뜨지 않는다.

**오버레이는 두 개고, 같이 얹지 않는다.**

| | 언제 | 하는 일 |
| --- | --- | --- |
| `spark/compose.dev.yaml` | 로컬. 호스트 `.venv` 에서 직접 `spark-submit` | 앱 DB 를 호스트에 연다 (`127.0.0.1:55432`) |
| `spark/compose.spark.yaml` | 데이터 EC2. Job 이 컨테이너 안 | Airflow 이미지를 Spark 가 든 것으로 바꾸고 `./spark` · checkpoint 볼륨을 붙인다 |

`compose.dev.yaml` 이 포트를 여는 이유는, Spark 가 컨테이너 밖에서 돌 때 붙어야 할 세 곳 중 하나가 닫혀 있기 때문이다.

| | 호스트에 열려 있나 | |
| --- | --- | --- |
| Kafka | ✓ `127.0.0.1:29092` | datastore 의 EXTERNAL 리스너 |
| MinIO | ✓ `127.0.0.1:9000` | datastore 의 API 포트 |
| PostgreSQL | ✗ | `pipeline/compose.yaml`: "호스트 포트는 열지 않는다" |

기본 포트 5432 를 피하는 이유는 개발 PC 에 PostgreSQL 이 깔려 있는 경우가 많기 때문이다.

`compose.spark.yaml` 을 쓰면 Job 이 컨테이너 안에서 돌아 주소가 서비스 이름(`kafka:9092` · `minio:9000` · `postgres:5432`)이 되고, 호스트 포트를 열 이유가 사라진다.

`compose.yaml` 을 직접 고치지 않는 이유는 그 파일이 팀 공용 스켈레톤이고 다른 담당의 작업과 충돌하기 때문이다. 오버레이로 얹으면 각자 필요한 것만 켠다.

### 로컬은 호스트, 배포는 컨테이너

이 절의 원래 결정은 "Spark 는 컨테이너에 넣지 않는다" 였다. **배포에 대해서는 뒤집었다.**

**뒤집은 이유** — Airflow 가 컨테이너 안에 있으면 호스트의 `spark-submit` 을 부를 방법이 없다. 컨테이너 안 프로세스는 호스트 바이너리를 실행하지 못한다. 그 상태로는 손으로 `spark-submit` 을 치는 것만 되고, `collect_* >> ingest >> extract >> aggregate` 를 DAG 로 엮는 것([§5](#5-airflow-연동))이 성립하지 않는다. 실행 환경 얘기가 아니라 **연결이 되느냐**의 문제였다.

| | Spark 가 도는 곳 | 어떻게 |
| --- | --- | --- |
| 로컬 개발 | 호스트 `.venv` | 원래 결정 그대로. 디버거를 붙이기 쉽고 재빌드가 없다 |
| 데이터 EC2 | `airflow` 컨테이너 안 | Airflow 태스크가 같은 컨테이너에서 `spark-submit` 을 부른다 |

원래 결정의 근거 셋 중 둘은 로컬에서만 유효했다 — (b) 코드 수정 시 재빌드는 `./spark` 를 바인드 마운트하면 없어지고(`./src`·`./dags` 와 같은 방식), (c) 디버거는 로컬에서 붙이면 된다. 남는 것은 (a) 이미지 무게뿐이고, 그건 연결이 되는 값을 못 이긴다.

**Spark 컨테이너를 따로 띄우지는 않는다.** 실행 모델이 `Trigger.AvailableNow` 라 Spark 는 상시 서비스가 아니다 ([01 §1](01-architecture.md)). 상시 컨테이너를 붙일 자리가 없고, 단일 노드에서 standalone master·worker 를 띄워도 자기 자신에게 작업을 배분하는 것 말고 하는 일이 없다. 그래서 **컨테이너 수는 늘지 않는다.**

```
데이터 EC2 ── Docker 엔진 1개
├─ [datastore]  kafka · minio                                    상시 2
└─ [pipeline]   postgres · apiserver · scheduler · dag-processor  상시 4
                  ↳ 태스크가 뜰 때 이 안에서 spark-submit 이 돌고 끝난다
```

#### `pipeline/Dockerfile` 을 고치지 않는 방법으로 한다

`spark/Dockerfile` 이 팀 공용 이미지를 `FROM` 으로 상속해 JRE 와 `pyspark` 만 얹고, `spark/compose.spark.yaml` 오버레이가 Airflow 서비스의 `image` 를 그것으로 바꾼다. `pipeline/Dockerfile` 과 `pipeline/compose.yaml` 은 한 줄도 바뀌지 않는다.

이미지가 바뀌면 팀 전원의 빌드가 바뀌기 때문이다 — `compose.yaml` 을 직접 고치지 않는 것과 같은 이유고, 되돌릴 때도 `-f` 하나를 빼면 끝난다. 대가는 이미지를 두 단계로 빌드해야 하는 것이고, `spark/scripts/build-image.sh` 가 순서를 강제한다.

Airflow 서비스 **전부**에 같은 파생 이미지를 준다. 태스크가 실제로 도는 곳은 LocalExecutor 라 `scheduler` 하나지만, Airflow 는 모든 구성요소가 같은 이미지를 쓰는 것을 전제로 만들어져 있다. 파생 이미지는 기본 이미지의 상위집합이고 추가 빌드도 없으므로 나눠서 얻을 것이 없다.

#### 로컬 준비

```sh
./scripts/dev-setup.sh              # 팀 공용 — Airflow · pytest · ruff
spark/scripts/dev-setup.sh          # Spark — pyspark + jar
```

둘로 나눈 이유는 Spark 를 만지지 않는 사람이 `pyspark` 450 MB 와 jar 530 MB 를 받을 이유가 없기 때문이다. 버전은 두 경로가 같은 `spark/versions.sh` 를 읽으므로 어긋나지 않는다.

```sh
spark/scripts/submit.sh ingest --profile local
```

`submit.sh` 가 붙여주는 것 — jar 목록, log4j 설정, 드라이버 파이썬. 직접 부르면 이렇다.

```sh
spark-submit \
  --jars "$(ls spark/jars/*.jar | paste -sd,)" \
  --driver-java-options "-Dlog4j.configurationFile=file://$PWD/spark/conf/log4j2.properties" \
  spark/jobs/ingest.py --source kafka --profile local
```

`shuffle.partitions` 는 `conf/base.yaml` 이 8 로 낮춘다. 기본값 200 이 [00 §3](00-overview.md) 규모에서 순수 오버헤드이기 때문이다. 파티션당 수십 건짜리 태스크 200개를 만드는 데 계산보다 스케줄링에 시간이 더 든다.

log4j 설정을 파일로 주는 이유는 코드의 `setLogLevel` 이 SparkContext 가 뜬 뒤에야 걸려서 기동 구간 50여 줄을 못 막기 때문이다.

**jar 는 쉼표로 이어 붙인다.** `--jars "spark/jars/*"` 는 Windows/Git Bash 에서 `No main class set in JAR` 로 죽는 것을 확인했다. 쉼표 목록은 Spark 문서가 정의한 형식이라 어디서나 확실하다. 손으로 적지 않으려고 `submit.sh` 가 있다.

**드라이버 파이썬은 PATH 운에 맡기지 않는다.** `spark-submit` 은 `PYSPARK_DRIVER_PYTHON` 이 없으면 PATH 의 `python3` 을 쓴다. 그게 `.venv` 의 것이 아니면 워커와 버전이 갈려 첫 UDF 에서 `PYTHON_VERSION_MISMATCH` 로 죽는다. 워커 쪽은 `trendin.spark.common.session.ensure_worker_python` 이 `sys.executable` 로 맞춘다.

### jar

`--packages` 로 런타임에 받지 않는다. 매 실행마다 네트워크를 타고, 오프라인이면 죽고, 버전이 조용히 바뀔 수 있다. `spark/jars/` 에 받아두고 `.gitignore` 에 넣는다. 받는 스크립트는 버전을 고정해 커밋한다 — `spark/scripts/fetch-jars.sh`.

받은 jar 가 실제로 물리는지는 `spark-submit --jars "spark/jars/*" spark/scripts/check-jars.py` 로 확인한다. 어긋난 조합은 보통 처음 Kafka 를 읽을 때 `NoSuchMethodError` 로 죽는데, 그때는 원인이 jar 인지 코드인지 구분하기 어렵다.

### 확정된 버전

[01 §7](01-architecture.md) 이 "실제로 확인한 뒤 09 에 고정한다" 고 미뤄둔 값이다. **숫자의 단일 출처는 `spark/versions.sh` 이고, 아래는 그 요약이다** — 올릴 때는 그 파일을 고친다. 아래는 실행으로 확인했다 — `spark-submit spark/jobs/ingest.py --profile local` 이 Python 3.12.12 · Spark 4.0.4 에서 종료 코드 0 으로 끝난다.

| | 값 | 왜 이 값인가 |
| --- | --- | --- |
| `pyspark` | **4.0.4** | 4.0.x 는 Python 3.9+ 를 지원한다. 4.1 부터는 3.10+ 로 조건이 더 좁고, 4.0 계열이 더 오래 돌았다 |
| Python | **3.12** | `pyproject.toml` 의 `>=3.12,<3.13` 그대로 |
| Hadoop | **3.4.1** | pyspark 4.0.4 가 번들한 `hadoop-client-api` 버전. `hadoop-aws` 를 여기 맞춘다 |
| Scala | **2.13** | Spark 4.x 는 2.13 만 낸다 |

받는 jar 는 일곱 개다. 번들에 이미 있는 것(`jsr305` · `snappy-java` · `lz4-java`)은 받지 않는다.

| jar | 버전 | 근거 |
| --- | --- | --- |
| `spark-sql-kafka-0-10_2.13` | 4.0.4 | Spark 버전과 **정확히** 같아야 한다 |
| `spark-token-provider-kafka-0-10_2.13` | 4.0.4 | 위와 한 쌍 |
| `kafka-clients` | 3.9.1 | 위 두 개의 compile 의존성 |
| `commons-pool2` | 2.12.0 | 같음. 번들된 `commons-pool` 1.5.4 와 **다른 물건**이다 |
| `hadoop-aws` | 3.4.1 | 번들 Hadoop 과 같아야 한다 |
| `software.amazon.awssdk:bundle` | 2.24.6 | `hadoop-project` 3.4.1 의 `aws-java-sdk-v2.version`. 530 MB |
| `postgresql` | 42.7.13 | 비교적 자유롭다 |

Hadoop 3.4 부터 S3A 가 AWS SDK **v2** 를 쓴다. 그래서 아티팩트가 `software.amazon.awssdk:bundle` 이다 — `aws-java-sdk-bundle` 은 3.3.x 시절 이름이고 이 조합에서는 안 맞는다 ([01 §7](01-architecture.md) 을 함께 고쳤다). v2 는 리전을 못 찾으면 요청을 만들기 전에 죽으므로, 리전 개념이 없는 MinIO 에도 `fs.s3a.endpoint.region` 을 줘야 한다 (`conf/base.yaml` 의 `minio.region`).

Spark 버전을 올릴 때는 `SPARK_VERSION` 만 바꾸지 말고 `kafka-clients` · `hadoop` · `awssdk` 세 줄을 다시 확인한다. 확인법은 스크립트 주석에 있다.

## 3. 설정

```
conf/base.yaml  ←  conf/{profile}.yaml  ←  환경변수
     (기본)          (프로파일 오버라이드)      (비밀)
```

| 무엇 | 어디 |
| --- | --- |
| 알고리즘 임계값 | `conf/*.yaml`. 튜닝 대상이라 코드 밖 |
| 접속 정보·비밀 | 환경변수만. `pipeline/README.md` 규약 10번 |
| 프로파일 선택 | `--profile` 인자 또는 `SPARK_JOB_PROFILE` |

**임계값을 코드 상수로 두지 않는다.** [04](04-keyword-extraction-spec.md)·[05](05-keyword-registry-spec.md)·[07](07-metrics-and-ranking-spec.md) 의 값은 튜닝 반복이 전제라, 한 번 바꿀 때마다 이미지를 다시 빌드할 수는 없다.

**설정 변경은 `pl_config_history` 에 기록한다** ([04 §10](04-keyword-extraction-spec.md)). 기록 없이 바꾸면 통계의 계단을 나중에 설명할 수 없다.

## 4. 테스트

세 층으로 나눈다. 위로 갈수록 빠르고 많다.

### 층 1 — 순수 함수 (Spark 없음)

**여기에 대부분을 넣는다.** 이 묶음의 로직은 대부분 문자열과 숫자를 다루는 순수 함수라, Spark 없이 테스트할 수 있다.

| 대상 | 문서 |
| --- | --- |
| URL 정규화, HTML 제거, 코드 블록 분리, 언어 판별 | [03](03-normalization-spec.md) |
| 토큰화, 후보 생성, 비교키, C-value | [04](04-keyword-extraction-spec.md) |
| 결정적 병합 규칙, 약어 대응 판정, 승격 조건 | [05](05-keyword-registry-spec.md) |
| NPMI, 점수 사상, 상위 N 절단 | [06](06-related-keyword-spec.md) |
| 윈도우 경계, 성장률(0 분모 포함), 동점 정렬, `trend_type` 판정 | [07](07-metrics-and-ranking-spec.md) |
| 도메인 값 검증 | [01 §6](01-architecture.md) |

**이렇게 짜려면 로직이 DataFrame 에 묶여 있으면 안 된다.** 스칼라 입출력 함수로 쓰고 UDF 로 감싼다. 이게 `src/trendin/spark/` 를 `jobs/` 와 분리한 실질적인 이유다.

`pipeline/tests/` 가 이미 같은 패턴이다 — 태스크 함수를 Airflow 없이 테스트한다.

경계값은 반드시 넣는다: 빈 문자열, 한 글자, 분모 0, `NULL` 시각, 미래 시각, 동점, 후보 1개.

### 층 2 — Spark local

DataFrame 을 실제로 다루는 부분. `local[2]` SparkSession 을 세션 스코프 픽스처로 만든다.

| 대상 | |
| --- | --- |
| 집계·조인·윈도우 SQL | 결과 행이 맞는지 |
| 중복 제거 | 대표 선택이 결정적인지 |
| 파티션 쓰기 | 경로가 규약대로 나오는지 |
| 스키마 | 필드 누락 시 실패하는지 |

**세션 생성이 느리므로 세션 스코프로 한 번만 만든다.** 테스트마다 만들면 전체 실행이 몇 분 단위가 되고 아무도 안 돌리게 된다.

Kafka·MinIO·PostgreSQL 은 안 쓴다. 입력은 인메모리 DataFrame, 출력은 임시 디렉터리.

### 층 3 — 통합

compose 를 띄우고 실제 경로를 한 번 훑는다. 수는 적게, 시나리오는 넓게.

| 시나리오 | 확인 |
| --- | --- |
| 정상 기사 이벤트 하나 | Kafka → MinIO `article.json` → curated → `contents` |
| **실행 요약 이벤트 하나** | `object_key: null` 로 분기해 **원문 조회를 건너뛰고** 원장에 남는지 ([02 §2](02-input-contract.md)) |
| 같은 `event_id` 두 번 | 원장이 막는지 ([01 §4](01-architecture.md)) |
| checksum 불일치 | DLQ 로 가는지. **대조 대상이 `article.json` 바이트인지** ([02 §3](02-input-contract.md)) |
| 미지의 `schema_version` | DLQ 로 가는지 |
| `object_key` 는 있는데 객체가 없음 | `OBJECT_NOT_FOUND` 로 DLQ 에 가는지 |
| 허용 목록 밖 `domain` | `UNKNOWN_DOMAIN` 으로 DLQ 에 가는지. **`dev` 는 통과하고 `development` 는 걸리는지** ([01 §6](01-architecture.md)) |
| `status: failed` 요약 이벤트 | 원장 + `pl_batch_stat` 에 기록되고 원문 조회를 건너뛰는지 ([02 §4](02-input-contract.md)) |
| **`members_only: true` 기사** | 본문 없이 제목만으로 통과하는지 ([03 §2](03-normalization-spec.md)) |
| **`route: api` 기사 (`hn`)** | 같음. 본문 필터에 걸려 사라지지 않는지 |
| checkpoint 유지 재실행 | **아무것도 다시 처리하지 않는지** |
| objects 모드 재처리 | Kafka 없이 프리픽스 스캔으로 도는지 ([02 §6](02-input-contract.md)) |
| aggregate 두 번 | `trend_metrics` 에 중복 행이 생기지 않는지 ([07 §6](07-metrics-and-ranking-spec.md)) |
| 수집 실패한 날 | 그 날짜의 `24H` 행이 **만들어지지 않는지** ([07 §2](07-metrics-and-ranking-spec.md)) |

**요약 이벤트 줄이 새로 가장 중요하다.** 한 토픽에 모양이 둘 흐르는데, 분기를 빠뜨리면 요약 이벤트가 전부 DLQ 로 간다. 그러면 문서는 정상으로 들어오면서 수집 상태만 조용히 사라져서 층 1·2 에서 전혀 드러나지 않는다.

**`members_only`·`route: api` 두 줄도 같은 종류다.** 본문 없는 문서가 정상 입력인데 필터가 물면, dev 도메인이 통째로 비면서 "수집이 안 됐나" 로 보인다.

**마지막 두 줄은 층 1·2 에서 잡히지 않는다.** 실제 운영에서 자주 일어나고, 재실행 안정성은 compose 를 실제로 두 번 돌려야만 확인된다.

### Spark 자격증명이 read 전용인지 확인하는 법

[02 §3](02-input-contract.md) 이 요구하는 것이다. 통합 테스트에 한 줄 넣는다.

```python
# raw-data 에 쓰기를 시도해서 실패해야 통과다.
with pytest.raises(Exception):
    spark.createDataFrame([("x",)], "c string") \
         .write.mode("append").parquet("s3a://raw-data/_write_probe/")
```

**실패를 기대하는 테스트를 쓰는 이유** — 권한은 조용히 넓어진다. 키를 다시 발급하거나 정책을 손볼 때 쓰기가 붙어도 아무 증상이 없고, 증상이 생기는 날은 원문이 이미 덮인 날이다. `raw-data` 는 담당 1 소유이고 복구 수단이 없다.

### 회귀 스냅샷 — [04 §9](04-keyword-extraction-spec.md)

```
tests/fixtures/
├─ corpus/      article.json 30건 (실제 수집분에서 발췌)
└─ snapshots/   각 문서의 추출 결과
```

코드를 고쳤을 때 스냅샷이 바뀌면 실패한다. **의도한 변경이면 갱신하고 diff 를 커밋에 남긴다.** 목적은 변경을 막는 것이 아니라 **의도하지 않은 변경을 드러내는 것**이다. 정규식 하나를 손봤는데 추출 결과가 바뀌는 일은 흔하고, 스냅샷이 없으면 배포 후에야 안다.

코퍼스는 **입력의 모양이 갈리는 축을 모두 덮게** 고른다. 30건은 눈으로 diff 를 볼 수 있는 상한이다.

| 축 | 반드시 포함 |
| --- | --- |
| `route` | `rss`(피드 전문) · `listing`(기사 페이지 파싱) · `api`(본문 없음) |
| 본문 유무 | 있음 · `members_only` 로 없음 · `hn` 으로 없음 |
| 도메인 | `fashion` · `dev` |
| 언어 | `ko` 주류. `en` 은 `hn` 제목 |

**`en`·`mixed` 표본이 얇을 것이다.** 소스 셋이 국내 매체 7곳과 `hn` 이라 한국어 본문과 영어 제목으로 갈린다. 배치 계약 시절 상정한 "영어 본문 다수" 는 오지 않는다. [03 §5](03-normalization-spec.md) 의 언어 판별 임계값을 이 분포로 정해야 한다.

**⚠️ 본문을 저장소에 커밋할 때 주의한다.** 코퍼스는 매체 본문이고, 불변식 3 이 *"본문과 리드는 내부 저장소에만 둔다"* 고 못박았다. 이 저장소는 팀 내부지만 공개 저장소로 옮겨질 수 있다. 회원 전용 기사의 본문은 애초에 오지 않으므로 문제가 아니고(그게 불변식 2), **일반 기사 본문은 발췌 길이를 짧게 자르고 출처(URL·매체·발행일)를 함께 둔다** — 저작권법 제37조.

### 안 하는 것

**추출 품질의 절대 수치를 테스트로 검증하지 않는다.** precision 은 사람이 매기는 값이라 CI 에 넣을 수 없다. 절차는 [04 §9](04-keyword-extraction-spec.md) 에 있고, 테스트가 지키는 것은 재현성이지 품질이 아니다.

## 5. Airflow 연동

**수집 DAG 과 같은 DAG 에 두지 않는다.** 수집은 시간 주기(fashion 1시간, `hn` 30분)이고 처리는 그보다 드물게 돌린다. 근거는 [01 §2](01-architecture.md).

```python
# 수집 — 도메인당 DAG. 담당 1 소유
fashion_collect   (1시간 주기)
dev_collect       (30분 주기)

# 처리 — 별도 DAG. 자기 스케줄로 돈다
ingest >> extract >> aggregate
```

| 태스크 | 설정 |
| --- | --- |
| `ingest` | 수집 태스크의 downstream 이 **아니다.** `Trigger.AvailableNow` 가 쌓인 오프셋을 한 번에 먹는다 |
| 전부 | `retries` 를 `default_args` 에 (`pipeline/README.md` 규약 5번) |
| 전부 | 멱등. 같은 logical date 로 재실행해도 결과가 같다 |

**`trigger_rule=ALL_DONE` 이 필요 없어졌다.** 수집 태스크와 의존 관계가 없기 때문이다. 배치 계약 시절에는 `ingest` 가 수집의 downstream 이라 "소스 하나가 실패해도 돌아야 한다" 를 `trigger_rule` 로 표현했는데, 지금은 실패가 요약 이벤트로 토픽에 들어오고 `ingest` 는 그걸 데이터로 읽는다.

**대가는 관측성이다.** Airflow 그래프만 봐서는 "수집이 끝났는데 처리가 안 됐다" 를 알 수 없다. 두 DAG 이 남남이라 화면에 선이 없다. 그래서 `pl_batch_stat` 의 `(일자, 소스)` 상태([02 §4](02-input-contract.md))가 유일한 연결 지점이다 — 그 표를 보지 않으면 결손을 못 찾는다.

**XCom 에는 ID 와 건수만 넣는다** (규약 4번). 처리 결과는 `pl_processing_ledger` 를 거친다.

`SparkSubmitOperator` 와 `BashOperator` + `spark-submit` 중에서는 후자로 시작한다. `SparkSubmitOperator` 는 `apache-airflow-providers-apache-spark` 의존성이 하나 늘고 Airflow constraints 와의 정합을 확인해야 하는데, 로컬 `spark-submit` 을 부르는 것과 실질적 차이가 크지 않다. 클러스터로 가면 그때 바꾼다.

Spark 태스크는 `crawler_pool` 을 쓰지 않는다. 외부 사이트를 치지 않기 때문이다. 동시 실행을 제한할 필요가 생기면 `spark_pool` 을 `pools.json` 에 추가한다 (규약 6번).

## 6. 린트

`pipeline/pyproject.toml` 의 ruff 설정을 그대로 쓴다 (`E`, `F`, `I`, `AIR`). Spark 코드에 별도 규칙을 두지 않는다.

`AIR` 규칙은 DAG 파일에만 의미가 있고 Spark 로직에는 걸릴 것이 없다. 규칙 세트를 갈라놓으면 나중에 두 벌을 관리하게 된다.

## 7. 구현 착수 전에 필요한 것

문서가 다 있어도 아래가 없으면 시작할 수 없다.

### 막는 것

| # | 필요한 것 | 없으면 | 막히는 Job |
| --- | --- | --- | --- |
| 1 | **`ddl-auto: create` → `update`** | 백엔드 재배포마다 수집 데이터가 전부 사라진다. `keywords.first_seen_at` 은 재수집으로 복구되지 않는다 ([08 §6](08-storage-schema.md)) | 전부 |
| 2 | **`keywords (domain, normalized_name)` UNIQUE 적용** | 같은 키워드가 계속 새 행으로 쌓인다. **나중에 붙일 수 없다** ([05 §5](05-keyword-registry-spec.md)) | `extract` |
| 3 | `period` · `trend_type` 값 규약 | varchar 라 코드가 정하는 대로 굳는다 ([07 §5](07-metrics-and-ranking-spec.md)) | `aggregate` |
| 4 | `trend_metrics (trend_id, period, period_start)` UNIQUE | 재실행마다 중복이 쌓인다 | `aggregate` |
| 4b | **MinIO `curated` 버킷 + Spark 쓰기 권한** | 지금 Spark 키는 `raw-data` 읽기만 한다 (`datastore/minio-init/init.sh`). 정제 결과를 쓸 곳이 없다 ([01 §3](01-architecture.md)) | `ingest` · `extract` |
| 4c | **DLQ 토픽명 + 메시지 스키마** | 검증 실패의 재투입 경로가 없다 ([02 §5](02-input-contract.md)). 담당 2 소관 | `ingest` — **부분** |

`domain` 값은 합의됐다 — 이벤트 슬러그 `dev` → `DEVELOP`, `fashion` → `FASHION` ([01 §6](01-architecture.md)). **`development` 가 아니다.**

**1·2 만 적용되면 `ingest` 와 `extract` 를 만들 수 있다.** 3·4 는 `aggregate` 착수 전에 필요하다.

**1번을 먼저 해야 하는 이유** — 2번을 적용해도 `create` 상태면 다음 재배포에 그 제약까지 함께 날아간다. 순서가 뒤바뀌면 같은 일을 두 번 한다.

**4c 가 `ingest` 를 완전히 막지는 않는다.** DLQ 싱크를 인터페이스로 두고 `pl_processing_error` 테이블만 쓰면 검증 로직 전체를 만들고 검증까지 할 수 있다 ([02 §5](02-input-contract.md)). 토픽이 생기면 구현 하나를 더한다. 그 사이 재투입 경로가 없는 것만 감수한다.

### 품질을 정하려면

| # | 필요한 것 | 없으면 |
| --- | --- | --- |
| 5 | **실제 수집 데이터 샘플** | 04~07 의 임계값을 정할 근거가 없다. **추측으로 정하면 전부 다시 하게 된다.** 수집기는 구현돼 있으므로(`src/trendin/*/collect/`) 한 번 돌린 결과를 받으면 된다 |
| 5b | **dev 도메인 본문 부재 결론** | `hn` 은 제목만 온다 ([00 §7](00-overview.md) 한계 19). 제목 한 줄로 동시출현·NPMI 를 계산할지, `hn` 댓글을 받을지, dev 는 빈도만 쓸지가 안 정해지면 [04](04-keyword-extraction-spec.md)·[06](06-related-keyword-spec.md) 의 설계가 바뀐다 |
| ~~6~~ | ~~Kafka · MinIO 로컬 환경~~ | 해소됐다 — `datastore/compose.yaml` (S15P21A102-156·157) |
| ~~7~~ | ~~Spark 버전 정합 검증~~ | 해소됐다 — [§2 확정된 버전](#확정된-버전) |

**5번이 가장 중요하다.** [04](04-keyword-extraction-spec.md)~[07](07-metrics-and-ranking-spec.md) 의 임계값을 이 문서들이 숫자로 못박지 않은 것이 그래서다. 실제 데이터의 문서 빈도 분포·문서 길이·발행일 지연을 재기 전에 정한 숫자는 전부 다시 정하게 된다.

**5b 는 5번보다 먼저 답이 나와야 한다.** 데이터를 재도 "dev 에 본문이 없다" 는 사실은 안 바뀌고, 그 상태로 임계값을 재면 도메인 하나의 분포만 재는 것이 된다.

### 기획이 답해야 하는 것

구현은 진행할 수 있지만, 답에 따라 화면이 달라진다.

| # | 질문 | 근거 |
| --- | --- | --- |
| 8 | 수집이 실패한 날을 **그래프의 구멍**으로 그릴 것인가 | [07 §2](07-metrics-and-ranking-spec.md). 프론트가 구현해야 의미가 있다 |
| 9 | 트렌드가 아닌 관심 키워드의 지표를 보여줄 것인가 | [07 §2](07-metrics-and-ranking-spec.md). 보여준다면 `trends` 생성 조건이 바뀐다 |
| 10 | 연관 키워드의 기준 기간 | [06 §3](06-related-keyword-spec.md). `30D` 를 제안했다 |
| 11 | `growth_rate` 가 `NULL` 인 카드를 어떻게 보일 것인가 | [07 §5](07-metrics-and-ranking-spec.md). 0 으로 그리면 안 된다 |

### 착수 순서 제안

```
1·2 를 받는다
  → ingest 구현            (실제 데이터가 생긴다)
  → 그 데이터로 임계값 측정   (5번 해소)
  → extract 구현
  → 3·4 를 받아 aggregate 구현
```

`ingest` 가 돌기 시작하면 5번이 저절로 풀린다. 그래서 임계값이 필요 없는 `ingest` 를 먼저 만드는 것이 순서상 맞다.
