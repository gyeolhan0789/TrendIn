# spark — TrendIn 데이터 처리

Kafka 이벤트를 받아 MinIO 객체을 처리하고, 서비스가 조회하는 PostgreSQL 테이블을 채운다.

`ingest` 는 **Kafka 소비 → 계약 판별 → MinIO 객체 조회·checksum 대조 → 정제 → 중복 제거 →
`curated` Parquet → `contents` upsert → 처리 이력·DLQ·배치 통계** 까지 돈다. 백필
(`--source objects`)도 있다. `extract`·`aggregate` 는 뼈대뿐이다.

**두 가지가 아직 막혀 있다** — MinIO `curated` 버킷 쓰기 권한이 없고([아래](#minio--curated-버킷과-쓰기-권한이-없다)),
백엔드에 `contents` 테이블이 없다. 둘 다 코드는 완성이고 권한·스키마가 붙으면 그대로 돈다.
착수 조건은 [`docs/09-dev-and-test.md` §7](docs/09-dev-and-test.md), 스토리 분해와 진행 상태는 [`docs/10-delivery-plan.md`](docs/10-delivery-plan.md).

## 무엇을 하나

```
Kafka raw-file-ready  →  ingest     객체 검증 · 정제 · contents 적재 · curated 기록
MinIO curated         →  extract    키워드 추출 · 통합 · 승격 · keywords 적재
내부 통계             →  aggregate  언급량 · 순위 · 성장률 · 연관 키워드
```

입력은 **기사 하나에 이벤트 하나**다. 토픽 `raw-file-ready` 에 기사 이벤트와 실행 요약 이벤트가
함께 흐르고, 객체는 MinIO 의 기사별 `article.json` 이다. 계약과 근거는
[02](docs/02-input-contract.md), 생산자 쪽 기준은 [`../docs/web-collect.md`](../docs/web-collect.md).

Airflow 가 `spark-submit` 으로 각 Job 을 깨우고, Job 은 처리 후 스스로 종료한다.

쓰는 서비스 테이블은 여섯 개다 — `contents`, `keywords`, `keyword_contents`,
`keyword_metrics`, `keyword_metric_history`, `keyword_relations`. 나머지 일곱은 건드리지 않는다.
**`trends` 도 그 일곱에 든다** — 트렌드 배지가 `keyword_metrics.trend_types` 로 옮겨오면서
([07 §6](docs/07-metrics-and-ranking-spec.md)) 그 표에 쓸 것이 없어졌다.
스키마 기준은 [`docs/erd/erd-00-current.md`](docs/erd/erd-00-current.md) (v2).

## 어떻게 도나

Spark 는 **상시 서비스가 아니다.** Airflow 가 `spark-submit` 으로 깨우고 Job 이 처리 후 스스로
종료한다 ([01 §1](docs/01-architecture.md)). 그래서 Spark 컨테이너를 따로 띄우지 않고,
**컨테이너 수도 늘지 않는다.**

```
데이터 EC2 ── Docker 엔진 1개
├─ [datastore]  kafka · minio                                    상시 2
└─ [pipeline]   postgres · apiserver · scheduler · dag-processor  상시 4
                  ↳ 태스크가 뜰 때 이 안에서 spark-submit 이 돌고 끝난다
```

| | Spark 가 도는 곳 | 오버레이 |
| --- | --- | --- |
| 로컬 개발 | 호스트 `pipeline/.venv` | `spark/compose.dev.yaml` |
| 데이터 EC2 | `airflow` 컨테이너 안 | `spark/compose.spark.yaml` |

두 오버레이를 같이 얹지 않는다 — 같은 일을 두 경로로 하게 된다.

## 데이터 EC2 에 올리기

```sh
# 1. 저장소부터. Kafka · MinIO 는 datastore 가 띄운다
docker compose -f datastore/compose.yaml up -d

# 2. jar 를 호스트에 받아둔다 (이미지에 굽지 않고 마운트한다). curl 만 있으면 된다
cd pipeline
spark/scripts/fetch-jars.sh

# 3. 이미지 두 단계 — 팀 공용 이미지 → JRE·pyspark 를 얹은 파생 이미지
#    pyproject.toml 의 의존성이 바뀌면 반드시 다시 돌린다 (한국어 형태소 분석기 등)
spark/scripts/build-image.sh

# 4. 띄운다
docker compose -f compose.yaml -f spark/compose.spark.yaml up -d
```

`pipeline/.env` 에 Spark 용 값 몇 개가 더 필요하다 — `.env.example` 의 `--- Spark ---` 절.
`TRENDIN_MINIO_SPARK_*` 는 `datastore/.env` 의 `MINIO_SPARK_*` 와 같은 값이어야 한다.

**`pipeline/Dockerfile` 과 `pipeline/compose.yaml` 은 건드리지 않는다.** [spark/Dockerfile](Dockerfile) 이
팀 공용 이미지를 `FROM` 으로 상속하고, 오버레이가 `image` 만 바꾼다. 되돌릴 때는 `-f` 를 뺀다.

## 로컬에서 돌리기

호스트 `.venv` 에서 `local[*]` 로 돈다.

```sh
docker compose -f datastore/compose.yaml up -d
cd pipeline
docker compose -f compose.yaml -f spark/compose.dev.yaml up -d

./scripts/dev-setup.sh              # 팀 공용 — Airflow · pytest · ruff
spark/scripts/dev-setup.sh          # Spark — pyspark + jar (530 MB, 처음만 오래 걸린다)
source .venv/bin/activate

cp spark/.env.example spark/.env    # 값을 채운다
set -a; . spark/.env; set +a

spark/scripts/submit.sh ingest --profile local
```

`submit.sh` 는 `spark-submit` 감싸개다. jar 목록과 log4j 설정, 드라이버 파이썬을 붙여준다.
직접 부르려면 jar 를 **쉼표로 이어 붙인다.** `--jars "spark/jars/*"` 는 Windows/Git Bash 에서
`No main class set in JAR` 로 죽는 것을 확인했다.

```sh
spark-submit \
  --jars "$(ls spark/jars/*.jar | paste -sd,)" \
  --driver-java-options "-Dlog4j.configurationFile=file://$PWD/spark/conf/log4j2.properties" \
  spark/jobs/ingest.py --profile local
```

| 확인 | 명령 |
| --- | --- |
| jar 정합 | `spark/scripts/check-jars.sh` |
| 테스트 | `pytest spark/tests` (층 1·2. 층 3 은 아직 비어 있다) |
| 린트 | `ruff check .` |

### 고정된 버전

전부 [versions.sh](versions.sh) 한 곳에서 온다 — jar 스크립트 · 로컬 가상환경 · 컨테이너
이미지가 같은 파일을 읽는다. 예전에는 두 곳에 있었는데, 그러면 한쪽만 올리고 다른 쪽을 잊는다.

| | 값 | 왜 이 값인가 |
| --- | --- | --- |
| Spark (pyspark) | 4.0.4 | 4.0.x 는 Python 3.9+ 지원. 4.1 부터는 3.10+ 로 조건이 더 좁다 |
| Python | 3.12 | `pyproject.toml` 의 `>=3.12,<3.13` |
| Hadoop | 3.4.1 | pyspark 번들. `hadoop-aws` 를 여기 맞춘다 |
| Scala | 2.13 | Spark 4.x 는 2.13 만 낸다 |
| torch | 2.14.0 | CPU 이미지와 CUDA 이미지를 같은 버전으로 묶는다. 핀이 없으면 인덱스마다 최신이 달라(cu128 은 2.11 에 멈춰 있다) "GPU 에서만 결과가 다르다" 를 gliner 가 아니라 torch 에서 찾게 된다 |
| CUDA 휠 | cu126 | 드라이버는 cu130 도 받지만 cu126 이 더 오래된 드라이버에서도 돈다. 아키텍처 지원은 같다 |
| jar 7개 | — | `--packages` 를 쓰지 않는다 ([09 §2](docs/09-dev-and-test.md)) |

### Windows 에서의 제약

호스트 `.venv` 로 돌릴 때만 해당한다. `--jars` 를 쓰는 순간 Hadoop 이 `winutils.exe` 를 찾고,
없으면 SparkContext 기동이 `HADOOP_HOME and hadoop.home.dir are unset` 으로 **실패한다.**
jar 없이 도는 뼈대 실행은 멀쩡하지만, Kafka·MinIO·JDBC 를 쓰는 순간부터 막힌다.
2026-09-08 에 실제로 확인했다 — `submit.sh` 는 세션이 뜨기 전에 죽는다.

**층 2 테스트도 파일을 쓰는 것만 막힌다.** `pytest spark/tests` 는 통과하지만 `curated`
Parquet 을 실제로 쓰는 다섯 건은 건너뛴다 (`conftest.py` 의 `writable_spark` 픽스처가 세션당
한 번 재 보고 건너뛴다). 리눅스 CI·컨테이너에서는 그대로 돈다 — **건너뛰는 것이지 없는
것이 아니다.**

경로 문제는 스크립트가 이미 처리한다. jar 목록·log4j·앱 스크립트 경로를 `file:///` URI 로
바꿔 넘긴다 — 안 그러면 spark-submit 이 드라이브 문자를 URI 스킴으로 읽어
`No FileSystem for scheme "C"` 로 죽는다. 변환은 `_common.sh` 한 곳에 있고
(`jar_list` · `to_file_uri` · `to_app_uri`) `submit.sh` 와 `check-jars.sh` 가 함께 쓴다.
그건 winutils 와 별개 문제이고 이미 고쳐져 있다.

| | |
| --- | --- |
| 컨테이너에서 실행 | **가장 간단하다.** `compose.spark.yaml` 로 띄우면 리눅스 컨테이너 안이라 이 문제가 없다. 한 번만 돌려볼 때는 `docker compose -f compose.yaml -f spark/compose.spark.yaml run --rm --no-deps airflow-cli bash -c "spark/scripts/submit.sh ingest --profile dev"` |
| WSL2 에서 개발 | 호스트 `.venv` 를 쓰고 싶으면 이쪽. 서버와 같은 환경이다 |
| `winutils.exe` 설치 | 서드파티 저장소에서 받아 `HADOOP_HOME` 에 둔다. 출처는 팀이 정해야 한다 |

로그의 한글이 깨지는 것도 Windows 콘솔 인코딩 탓이다. `PYTHONUTF8=1` 을 넣으면 된다.

### GPU 로 추출하기 (개발 PC 전용)

`extract` 의 병목은 GLiNER 추론이고 **문서당 약 1초다.** 하루치는 CPU 로 견디지만 재추출은
코퍼스를 통째로 다시 추론하는 일이라, 임계값을 한 번 바꿔 볼 때마다 시간 단위가 된다.
**배포(데이터 EC2)에는 GPU 가 없으므로 운영 이미지는 그대로 CPU 다.**

```sh
# 0. Docker 에 nvidia 런타임이 있는지. 없으면 NVIDIA Container Toolkit 을 먼저 깐다
docker info | grep -i runtimes
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# 1. CUDA 이미지 (운영 이미지 위에 torch 만 갈아끼운다. 약 2.5 GB 를 더 받는다)
spark/scripts/build-image.sh --gpu

# 2. 돌린다 — 오버레이 세 장을 겹친다
docker compose -f compose.yaml -f spark/compose.spark.yaml -f spark/compose.gpu.yaml \
  --profile debug run --rm --no-deps airflow-cli \
  bash -c "spark/scripts/submit.sh extract --profile local --domain fashion --force"
```

⚠️ **워커가 하나여야 한다.** 모델은 executor 파이썬 프로세스마다 적재되므로
(`entities.recognizer_for`) `local[*]` 로 두면 코어 수만큼 209M 파라미터가 VRAM 에 올라간다.
터지는 자리가 `_predict_chunk` 의 `except` 안이라 **Job 은 후보 0건으로 정상 종료하고**, 로그를
안 보면 성공으로 오인한다. `compose.gpu.yaml` 이 `SPARK_MASTER=local[1]` 을 주고,
`extract/batch.py` 의 `_partition_count` 가 그래도 어긋나면 시작 전에 거부한다.

병렬을 하나로 줄여도 느려지지 않는다. 추론이 나머지 단계를 묻고, 그 추론 자체는 GPU 안에서
배치로 병렬이 된다.

| 환경변수 | 값 | |
| --- | --- | --- |
| `EXTRACT_DEVICE` | `cuda` | `auto` 도 되지만 쓰지 않는다 — GPU 를 넘기지 못한 실행이 조용히 CPU 로 돌면 신호가 없다 |
| `SPARK_MASTER` | `local[1]` | 위의 이유 |

## 설정

```
conf/base.yaml  ←  conf/{profile}.yaml  ←  환경변수
```

| 무엇 | 어디 | 왜 |
| --- | --- | --- |
| 알고리즘 임계값 | `conf/*.yaml` | 튜닝 대상이라 코드 밖 ([09 §3](docs/09-dev-and-test.md)) |
| 비밀 (비밀번호·시크릿 키) | 환경변수만 | 파일에 적으면 그대로 커밋된다 |
| 주소 | 프로파일 파일의 기본값을 환경변수가 덮는다 | 비밀이 아니고, 기본값이 있어야 빈손으로도 뜬다 |

환경변수는 아무 이름이나 받지 않는다. `src/trendin/spark/common/config.py` 의 `ENV_BINDINGS`
에 적힌 것만이다 — 일반 규칙을 열면 오타 난 이름이 조용히 무시되고, "왜 값이 안 바뀌지"
를 며칠 뒤에 발견한다.

예외가 하나 있다. `io/jdbc.assert_producer_database` 가 `AIRFLOW_CONN_APP_DB` 를
`os.environ` 에서 직접 읽는다 (S15P21A102-247). 그 값은 설정으로 들어오는 것이 아니라
**수집 쪽이 쓰는 접속 문자열**이고, 이 Job 이 Spark 설정과 그것을 대조해 서로 다른 DB 를
보고 있는지 본다. 설정 경로로 받으면 "우리 설정" 과 "저쪽 설정" 이 한 덩어리가 되어 대조라는
뜻이 사라진다.

⚠️ 이름이 틀리면 **대조를 건너뛰고 info 로그만 남긴다.** 검사가 실패한 것과 검사를 못 한
것은 다르고, Airflow 밖에서 손수 돌릴 때는 그 변수가 없는 것이 정상이기 때문이다. 대신
오타는 조용히 넘어간다 — 로그에 `AIRFLOW_CONN_APP_DB 가 없어 ... 건너뛴다` 가 있는데
Airflow 안에서 돌고 있다면 그게 신호다.

## 폴더

```
spark/
├─ jobs/      spark-submit 진입점. 인자 파싱 · 세션 생성 · 단계 호출만
├─ conf/      base · local · dev · log4j2
├─ scripts/   fetch-jars · submit · check-jars (+ check-jars.py)
├─ sql/       서버사이드 MERGE 문 ([08 §4]). 아직 비어 있다
├─ jars/      런타임 jar (git 제외)
└─ tests/     unit(층 1) · spark(층 2) · integration(층 3)

src/trendin/spark/    로직. jobs 가 import 한다
├─ common/    설정 · 로깅 · 세션
├─ io/        contract.py(판별) · schema.py(스키마) · kafka.py(소비)
│             objects.py(MinIO 조회) · ledger.py(처리 이력) · dlq.py(DLQ) · jdbc.py(앱 DB)
│             contents.py(contents 적재) · stats.py(pl_batch_stat) · candidates.py(후보 표 넷)
│             keywords.py(keywords · keyword_contents 적재 · 별칭·검수 큐·이력)
├─ ingest/    routing.py(판별→상태·단계) · objects.py(객체 검증) · batch.py(배치 배선)
│             normalize.py(정제·적재 단계) · backfill.py(--source objects)
├─ normalize/ [03] documents · text · urls · lang · filters · dedup · simhash · curated · adapters/
├─ extract/   [04] entities(실체 인식기) · adapters(언어별 후처리) · morphology(ko 분석기)
│             abbreviations(약어 관측) · keys · filters · scoring
│             document(문서 하나) · batch(Spark 배선) · source(curated 읽기) · thresholds
├─ registry/  [05] normalize(층1 복수형) · merge(층2 판정) · alias(대표 선정)
│             promote(승격 관문) · review(검수 큐) · embedding(층3) · batch(단계 배선)
│             thresholds. **pyspark 를 import 하지 않는다**
├─ metrics/   아직 비어 있다 ([06] [07])
```

`conf/lexicon/userdict-{domain}.txt` 는 **한국어 형태소 분석기 사용자 사전**이다
(`extract/morphology.py`) — 한 줄에 하나, `표기` 또는 `표기 품사`, 원표기 그대로. 모르는
브랜드명을 고유명사로 알려 주면 조사 경계가 제대로 잡힌다.

⚠️ **불용어·노이즈 사전(`stopwords-*.txt` · `noise-*.txt`)은 2026-09-17 에 지웠다.** 후보
생성이 실체 인식으로 옮겨지면서 **무엇이 키워드인지를 라벨이 정의하므로 뺄 것을 따로 셀
필요가 없어졌고** (`extract/entities.py`), 읽는 코드가 사라진 뒤로 파일만 남아 있었다.
되돌려야 하면 `git log -- spark/conf/lexicon/` 에서 꺼낸다. 옛 `protected-*.txt`(조사
규칙이 자르면 안 되는 어절)는 2026-09-09 에 없어졌다.

로직을 `src/trendin/` 아래 두는 이유는 [09 §1](docs/09-dev-and-test.md) 에 있다 —
`pipeline/Dockerfile` 이 이미 editable 설치를 하고 `compose.yaml` 이 바인드 마운트한다.

## 문서

번호 순서가 곧 읽는 순서다.

| | | |
| --- | --- | --- |
| [00](docs/00-overview.md) | 개요 | 담당 경계 · 확정된 결정 · 용어 · **스키마 한계와 미결 항목** |
| [01](docs/01-architecture.md) | 아키텍처 | 실행 모델 · Job 분해 · 중간 저장소 · 멱등성 |
| [02](docs/02-input-contract.md) | 입력 계약 | Kafka 소비 · MinIO 검증 · DLQ · 재처리 |
| [03](docs/03-normalization-spec.md) | 정제 규격 | 객체 → 표준 문서 · 중복 제거 · 품질 필터 |
| [04](docs/04-keyword-extraction-spec.md) | 키워드 추출 | 후보 생성 · 스코어링 · 선별 · 품질 측정 |
| [05](docs/05-keyword-registry-spec.md) | 키워드 레지스트리 | 정규화 · 동의어 통합 · 승격 |
| [06](docs/06-related-keyword-spec.md) | 연관 키워드 | 동시출현 · NPMI · 동의어와의 구분선 |
| [07](docs/07-metrics-and-ranking-spec.md) | 지표와 순위 | 언급량 · 시계열 · 성장률 · 트렌드 유형 |
| [08](docs/08-storage-schema.md) | 저장 스키마 | 적재 전략 · 내부 테이블 · **백엔드에 요청할 것** |
| [09](docs/09-dev-and-test.md) | 개발과 테스트 | 폴더 구조 · 로컬 실행 · 테스트 · 착수 조건 |
| [10](docs/10-delivery-plan.md) | 실행 계획 | 에픽 · 스토리 분해 · 착수 순서 · **차단 항목** |

상위 설계는 [`../docs/data-pipeline-design.md`](../docs/data-pipeline-design.md).
서비스 테이블 정의는 [`docs/erd/`](docs/erd/) — 기준은 `erd-00-current.md` 다.

## 핵심 결정 요약

| 항목 | 결정 |
| --- | --- |
| 실행 모델 | `Trigger.AvailableNow`. Airflow 가 깨우고 Job 이 스스로 종료 |
| Job | `ingest` / `extract` / `aggregate` 세 개 |
| 언어 | PySpark, 단일 노드 `local[*]` |
| 키워드 추출 | 통계·자동 발견. 사전 화이트리스트 없음 |
| 의미 유사도 | 경량 임베딩까지. **LLM 미사용** |
| 서비스 스키마 | Spark 는 값만 넣는다. DDL 권한 없음 |

### 의도적으로 비워두는 것

MVP 에서 아래는 채우지 않는다. 누락이 아니라 결정이다 — 근거는 [00 §4](docs/00-overview.md).

- `trends` 전체 → 손대지 않음. `description` · `summary` · `reason` 은 AI 설명 에픽 몫이고,
  `trend_types` 는 `keyword_metrics` 로 옮겨갔다
- `briefings` · `briefing_trends` · `notifications` → 차후 확장, 손대지 않음

v1 의 `contents.summary` 는 스키마에서 없어졌다 — 결정이 컬럼 부재로 굳었다.

## 지금 막혀 있는 것

DB 가 초기 버전이라 대부분은 **구현하면서 고쳐도 된다.** 다만 변경 비용이 균일하지 않아 아래 순서를 지켜야 한다 — 근거는 [08 §6](docs/08-storage-schema.md).

| | 필요한 것 | 막히는 Job |
| --- | --- | --- |
| 1 | **`ddl-auto: create` → `update`** — 지금은 백엔드 재배포마다 수집 데이터가 전부 사라진다 | 전부 |
| 2 | **`keywords (domain, normalized_name)` UNIQUE** — **나중에 붙일 수 없는 유일한 항목.** 2026-09-09 확인 결과 `Keyword.java` 에 없다 | `extract` — **승격 단계만** |
| 3 | `period` 값 규약 (varchar 라 코드가 정하는 대로 굳는다) | `aggregate` |
| 4 | `keyword_metrics (keyword_id, period)` · `keyword_metric_history (keyword_id, bucket_start)` UNIQUE | `aggregate` |
| 4a | ~~**`trends.trend_types` 의 실제 타입**~~ — 적재가 실행 시점에 컬럼 타입을 보고 캐스트를 붙이므로(`io/metrics._cast`) 어느 쪽이든 같게 돈다 | 해결 |
| 4b | **`keyword_metrics.trend_types` 칸** — 배지를 기간별로 실을 자리. 없으면 `aggregate` 가 시작에서 거부한다 | `aggregate` |
| 4c | **백엔드 목록 조회를 `keyword_metrics.trend_types` 로 옮기는 일** — `KeywordMetricRepository` 의 세 조회가 아직 `join trends ... = any(trend.trend_types)` 다. 파이프라인이 그 표를 더는 갱신하지 않으므로, 옮기기 전까지 화면의 배지는 마지막으로 쓴 값에 멈춰 있다 | 화면 |
| 5 | **실제 수집 데이터 샘플** — 임계값을 추측으로 정하면 전부 다시 하게 된다 | 품질 |

**1·2 만 적용되면 `ingest` 와 `extract` 는 착수할 수 있다.** 1을 2보다 먼저 해야 한다 — `create` 상태에서는 2번 제약도 다음 재배포에 함께 날아간다.

**2026-09-09 — 둘 다 없이 `ingest`·`extract` 를 다 만들었다.** 파이프라인 내부 테이블(`pl_*`)만 쓰는 부분이 대부분이라 그럴 수 있었고, 실제로 막혀 있는 것은 **키워드 승격 한 단계**다 — `keywords` 에 쓰는 유일한 자리이기 때문이다. 그동안 `extract` 는 병합·검수 큐·이력·재집계를 정상으로 돌리고 승격만 건너뛴다 (`extract.registry.required`, [10 §4](docs/10-delivery-plan.md) S5). 그리고 같은 날 `contents`·`keyword_contents`·`keywords.normalized_name` 이 생겨(`2967bce`) 이 표에서 빠졌다.

### MinIO — `curated` 버킷과 쓰기 권한이 없다

`datastore/` 를 세우면서 드러난 것이다. 지금 상태로는 `ingest` 가 결과를 쓸 곳이 없다.

| | 지금 | 필요한 것 |
| --- | --- | --- |
| 버킷 | `raw-data` 하나 | `curated` 추가 ([01 §3](docs/01-architecture.md)) |
| Spark 계정 | `spark-read` — `raw-data` 읽기만 | `curated` 에 대한 쓰기 |

`datastore/minio-init/init.sh` 가 정책을 만든다. 담당이 다르므로 그쪽에 요청한다 (S15P21A102-156·157).
읽기 전용으로 나눈 것 자체는 옳다 — 객체를 Spark 가 지우지 못하게 하는 것이 목적이었다.
`curated` 는 Spark 소유이므로 그 버킷에만 쓰기를 더하면 된다.

### 합의된 것

| 항목 | 결론 |
| --- | --- |
| `domain` 값 | enum 상수명. 이벤트 슬러그 `dev` → `DEVELOP`, `fashion` → `FASHION`. `ingest` 가 매핑. **`development` 가 아니다** ([01 §6](docs/01-architecture.md)) |
| `keywords` 유일성 | `(domain, normalized_name)` 복합 UNIQUE. 단독이면 개발의 `모델` 과 패션의 `모델` 이 충돌한다 |
| 지표의 키 | `keyword_id`. `trends` 를 거치지 않으므로 **트렌드가 아닌 키워드도 지표와 그래프를 갖는다** |
| 트렌드 유형 | `keyword_metrics.trend_types` 배열. `CURRENT`/`NEW`/`RISING` 이고 **복수 가능**하다. 그 행의 기간에 대한 판정이라 `24H` 와 `30D` 가 서로 다른 배지를 갖는다 ([07 §6](docs/07-metrics-and-ranking-spec.md)) |
| 기준일 | 집계의 마지막 날 D 는 **KST 로 완결된 마지막 날**(기본 = 실행일 전날). 진행 중인 오늘을 쓰면 증가율이 시각에 따라 뒤집힌다 |

백엔드에 부탁할 것 둘 — `@Enumerated(EnumType.STRING)` 명시(JPA 기본값이 `ORDINAL` 이라 컬럼이 int 가 된다), PostgreSQL 네이티브 enum 타입 미사용(Spark JDBC 쓰기가 캐스트 없이 죽는다). [01 §6](docs/01-architecture.md).

**두 번째 부탁이 `trend_types` 에서 바로 걸린다.** ERD 표기가 `trend_type_array` 라, 네이티브 enum 배열이면 스테이징 + 캐스트가 필요하고 `@ElementCollection` 이면 적재 대상이 조인 테이블로 바뀐다.

전체 요청 목록은 [08 §5](docs/08-storage-schema.md), 스키마 한계는 [00 §7](docs/00-overview.md).

## 기획이 답해야 하는 것

현행 스키마에는 담을 자리가 없어서 생기는 것들이다. 구현은 진행할 수 있지만 답에 따라 화면이 달라진다.

- 수집이 실패한 날을 **그래프의 구멍**으로 그릴 것인가 ([07 §3](docs/07-metrics-and-ranking-spec.md))
- **`24H` 상세의 추이를 무엇으로 그릴 것인가** — 버킷이 1일이라 24시간 구간에는 점이 하나다. 최근 N일을 보여주는 안을 제안했다 ([07 §3](docs/07-metrics-and-ranking-spec.md))
- **`24H` 라벨이 "어제 하루" 를 뜻하는 것을 어떻게 표기할 것인가** ([07 §4](docs/07-metrics-and-ranking-spec.md))
- 기간별 유형 배지를 정확히 보여줄 것인가 — 지금 `trend_types` 에는 기간 구분이 없다 ([07 §6](docs/07-metrics-and-ranking-spec.md))
- 연관 키워드의 기준 기간 — `30D` 를 제안했다 ([06 §3](docs/06-related-keyword-spec.md))
- `growth_rate` 가 `NULL` 인 카드를 어떻게 보일 것인가 ([07 §5](docs/07-metrics-and-ranking-spec.md))

"트렌드가 아닌 관심 키워드의 지표" 는 v2 스키마에서 **해소됐다** — 지표가 키워드에 직접 붙는다.
