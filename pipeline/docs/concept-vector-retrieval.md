# 개념 후보 Top K: pgvector + 다국어 E5

2026-09-20 서비스 DB 실측 결과: [개념 벡터 다국어 평가](concept-vector-live-eval-2026-09-20.md).

## 데이터 흐름

1. 기존 `concept` Job은 정확 일치 사전을 먼저 적용하고 미등록 표현을 남긴다. 기사 제목도 미등록 문맥 표본에 저장한다.
2. `concept-vectors.py`는 활성 `pl_concept_expression`을 다국어 E5-small(384차원)로 임베딩해 `pl_concept_embedding`에 적재한다. 모델 리비전과 입력 해시가 같으면 재계산하지 않는다.
3. `concept-judge.py --vector-top-k 5`는 미등록 표현과 LLM이 제안한 영어 이름으로 각각 검색한 뒤, 개념 ID별로 합쳐 Top K를 만든다. PostgreSQL의 정확 코사인 거리 검색을 쓴다. 약 1.7만 표현에서는 ANN 인덱스보다 정확 검색의 후보 재현율을 먼저 잰다.
4. LLM은 원표기, 영어 이름·분류 제안, 가능하면 기사 제목, 후보의 이름·분류를 받고 **같은 대상·같은 범위**인 개념 하나 또는 `null`을 고른다. 기사 제목이 없거나, 분류가 다르거나, 명시한 유사도 관문을 못 넘으면 자동 연결 대상에서 빠진다.

벡터 거리는 **후보 검색용**이다. 가까운 것 자체가 동의어라는 결론은 아니다. `Dior` 브랜드·디자이너처럼 이름이 같아도 대상이 다른 사례는 기사 제목만으로 모호하면 LLM이 `null`을 답해야 한다. 정확 일치 자동 연결은 기존 경로를 유지한다.

## 배포 순서

운영 서비스 DB는 기본 EC2의 PostgreSQL 17이다. 현재 이미지는 `postgres:17-bookworm`이며 `vector` 확장이 설치돼 있지 않다(2026-09-20 읽기 전용 확인). 코드의 `infra/compose.yaml`은 같은 주 버전의 `pgvector/pgvector:0.8.6-pg17-bookworm`로 바꾼다. 기존 볼륨을 지우거나 DB 주 버전을 바꾸지 않는다. 이미지 교체는 DB 컨테이너 재기동이므로 정상 배포 창에 진행한다.

1. DB 백업과 복구 가능 여부를 기존 운영 절차대로 확인한 뒤, 기본 EC2의 `infra` PostgreSQL 이미지를 배포한다. 로컬 개발용 `pipeline/compose.yaml`도 같은 pgvector 이미지를 쓴다.
2. 서비스 DB에서 `SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';`로 확장을 확인한다.
3. 데이터 EC2의 Spark 파생 이미지를 다시 빌드한다. 이미지가 E5 모델 리비전을 미리 받아 런타임 외부 다운로드를 피한다.
4. `concept` Job으로 개념 표가 생성된 상태에서 Airflow 컨테이너 안에서 다음을 실행한다. 명령은 `CREATE EXTENSION IF NOT EXISTS vector`와 `pl_concept_embedding` 생성, 활성 표현의 신규·변경 임베딩 적재를 한다.

```sh
docker exec s15p21a102-pipeline-airflow-scheduler-1 \
  python /opt/airflow/scripts/concept-vectors.py --profile dev
```

5. 먼저 LLM 호출 횟수와 입력 비용을 확인한다. `--estimate`는 첫 번째 영어 이름 판정의 견적이며, 벡터 후보 재판정은 미등록 표현당 최대 1회가 추가될 수 있다. `--max-calls`가 두 단계를 합쳐 제한한다.

```sh
# LLM 호출 없이 미등록 표기의 벡터 후보를 먼저 확인한다.
docker exec s15p21a102-pipeline-airflow-scheduler-1 \
  python /opt/airflow/scripts/concept-candidates-eval.py --profile dev \
  --dictionary db --vector-top-k 5 --detail
```

```sh
docker exec s15p21a102-pipeline-airflow-scheduler-1 \
  python /opt/airflow/scripts/concept-judge.py --profile dev --limit 10 \
  --vector-top-k 5 --max-calls 15 --estimate

# 후보와 LLM 재판정만 출력. DB에 연결 결과를 쓰지 않는다.
docker exec s15p21a102-pipeline-airflow-scheduler-1 \
  python /opt/airflow/scripts/concept-judge.py --profile dev --limit 10 \
  --vector-top-k 5 --max-calls 15
```

`--apply-verified`는 검증된 벡터 후보를 실제 사전에 연결한다. 실행에는 `--min-vector-similarity`를 명시해야 한다. 이 값은 E5의 절대 유사도가 아니라 **실제 표본에서 오연결률을 재고 정할 운영 관문**이다. 라벨 평가 전에는 적용값을 정하지 않는다. `--apply-links`는 기존 정확 이름 일치 자동 연결만 반영하며, 두 옵션은 함께 사용할 수 있다. 사전 반영 뒤 다음 `concept` Job이 최근 창의 기사 개념을 다시 계산한다.

## 평가 기준

- JP·KR·IT·FR의 미등록 표현에서 정답 개념이 Top 5에 드는 비율(`recall@5`)을 먼저 측정한다. 발음·철자 후보만 쓴 기존 경로와 벡터 후보 합집합을 같은 라벨 표본에서 비교한다.
- 자동 연결 후보는 사람이 `같음 / 다름 / 문맥 부족`으로 평가해 **오연결률**을 따로 잰다. 한 언어의 매핑률 상승만으로 적용하지 않는다.
- 특히 브랜드↔창업자, 일반 품목↔특정 제품, 일반 단어↔패션 용어 쌍을 실패 사례로 넣는다.
- `concept` Job의 정기 실행 시간은 모델 적재·벡터 검색과 분리돼 있다. 벡터 적재는 별도 명령이며, 새 표현이 추가되면 다시 동기화해야 한다.

모델: [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small). 이 모델은 `query:`/`passage:` 접두어를 요구한다. pgvector 설치·거리 연산: [pgvector 공식 문서](https://github.com/pgvector/pgvector).
