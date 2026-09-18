# Spark 런타임 이미지. **우리 패키지는 들어 있지 않다** — 정식 Airflow 이미지 위에 무겁고
# 잘 안 바뀌는 것 넷만 깔고 끝낸다.
#
#   1) JRE      — Spark 는 JVM 위에서 돈다. airflow 이미지에는 자바가 없다
#   2) pyspark  — spark-submit 과 파이썬 API
#   3) torch(CPU) · gliner — 실체 인식 ([04 §2], `extract/entities.py`)
#   4) GLiNER 모델 가중치
#
# 이 이미지만으로는 DAG 도 Job 도 돌지 않는다. pipeline/Dockerfile 이 이 위에 우리 패키지를
# 얹어 s15p21a102/pipeline-spark:local 을 만든다 (spark/compose.spark.yaml 의 BASE_IMAGE).
# 두 단계를 순서대로 부르는 것은 spark/scripts/build-image.sh 다.
#
# --- 상속 방향이 예전과 반대다 (2026-09-18) ----------------------------------
# 예전에는 이 파일이 s15p21a102/pipeline:local 을 FROM 했다. 그 이미지의 맨 위층이
# `COPY src` 라 소스가 한 줄만 바뀌어도 이미지 ID 가 달라졌고, 그러면 도커는 이 아래
# 3.5 GB(모델 2.36 GB · torch 1.04 GB · pyspark 491 MB)를 캐시 없는 것으로 보고 전부 다시
# 받았다. 데이터 EC2 배포 잡이 6분에서 13분으로 늘어난 원인이 이것이다 (러너 로그 09-17).
#
# 여기 깔린 것이 실제로 의존하는 값은 versions.sh 하나다. 그 파일은 지난 한 달에 두 번
# 바뀌었고 src 는 최근 일주일에 열네 번 바뀌었다. 안 바뀌는 것을 아래에, 자주 바뀌는 것을
# 위에 두면 도커가 옳게 판단한다 — versions.sh 를 고치는 날에는 여기가 제대로 다시 빌드된다.
#
# --- pipeline/Dockerfile 을 왜 건드렸나 --------------------------------------
# 그 파일은 팀 공용이라 손대지 않는 것이 원칙이었다 (09 §2). 그런데 "우리 패키지를 맨 위에
# 둔다" 는 그 파일이 만드는 층의 위치에 관한 것이라 여기서는 표현할 수 없다. 대신 BASE_IMAGE
# 기본값을 정식 이미지로 두어, Spark 를 쓰지 않는 팀의 빌드 명령과 결과는 그대로 두었다.
#
# 왜 아예 컨테이너에 넣나 — Airflow 가 컨테이너 안에 있으면 호스트의 spark-submit 을 부를
# 방법이 없다. 태스크가 도는 곳에 Spark 가 있어야 DAG 로 엮인다 (09 §2).

ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.12
# 정식 이미지를 직접 상속한다. 이 두 값은 pipeline/Dockerfile 과 같아야 한다 —
# build-image.sh 가 그 파일에서 읽어 넘기므로 손으로 맞추지 않는다.
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# apt 는 root 로. 끝나면 airflow 로 돌려놓는다 — 그대로 두면 이후 태스크가 root 로 돈다.
USER root
# default-jre-headless 는 베이스 배포판이 정하는 JRE 다 (bookworm→17, trixie→21).
# Spark 4.0 은 둘 다 지원한다. 버전을 못박지 않는 이유는 베이스 이미지가 옮겨갈 때
# 없는 패키지를 가리키며 빌드가 깨지기 때문이다.
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
USER airflow

# 버전의 단일 출처. ARG 로 받지 않는 이유는 컴포즈 쪽에 숫자를 한 벌 더 두게 되기 때문이다.
# --chown 이 없으면 root 소유로 들어와 airflow 사용자가 지우지 못한다 (pip 은 성공하고
# rm 에서 빌드가 깨진다). pipeline/Dockerfile 도 같은 이유로 --chown 을 쓴다.
COPY --chown=airflow:0 versions.sh /tmp/versions.sh
# pyspark 의 런타임 의존성은 py4j 하나다 (pandas·pyarrow 는 extra). 그래서 Airflow
# constraints 가 고정한 패키지를 건드리지 않는다.
# PyPI 에 sdist(434 MB)만 있어서 휠을 직접 빌드한다 — 이 단계만 2~3분 걸린다.
RUN . /tmp/versions.sh \
 && pip install --no-cache-dir "pyspark==${SPARK_VERSION}"

# 실체 인식 ([04 §2], `extract/entities.py`). torch 를 CPU 휠로 **먼저** 깔아야 gliner 가
# 그것을 그대로 쓴다 — 순서를 바꾸면 CUDA 런타임이 딸려와 이미지가 3 GB 넘게 커진다.
RUN . /tmp/versions.sh \
 && pip install --no-cache-dir --index-url "${TORCH_CPU_INDEX}" "torch==${TORCH_VERSION}" \
 && pip install --no-cache-dir "gliner==${GLINER_VERSION}"

# 모델 가중치를 이미지에 굽는다. 런타임에 받으면 executor 마다 HuggingFace 로 나가고,
# 망이 막힌 환경에서는 그 실패가 "후보가 0개" 로만 나타난다 ([09 §7]).
RUN . /tmp/versions.sh \
 && python -c "from gliner import GLiNER; GLiNER.from_pretrained('${GLINER_MODEL}')" \
 && rm /tmp/versions.sh

# checkpoint 디렉터리를 이미지 안에 미리 만든다. 도커는 빈 named volume 을 마운트할 때
# 이 경로의 소유권을 그대로 물려주므로, 이렇게 해두면 uid 50000 이 쓸 수 있다.
# 안 만들면 볼륨이 root 소유로 생겨 Job 이 checkpoint 를 못 쓴다 ([01 §4]).
RUN mkdir -p /opt/airflow/checkpoints

# 이 이미지가 책임지는 것만 본다. 설정을 읽는 yaml 은 Airflow 가 이미 갖고 있어서 따로
# 설치하지 않는데, 없어지면 런타임이 아니라 여기서 깨져야 한다.
#
# **kiwipiepy 는 여기서 보지 않는다.** 그것은 우리 패키지의 의존성이라 위층에서 깔린다.
# 다 쌓은 뒤의 검사는 build-image.sh 가 `docker run` 으로 한다.
RUN python -c "import yaml, pyspark, gliner; print('pyspark', pyspark.__version__)"
