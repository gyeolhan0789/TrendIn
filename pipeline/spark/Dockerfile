# Spark 를 쓰는 Airflow 이미지. 팀 공용 pipeline 이미지를 상속해 도구 두 개만 얹는다.
#
#   1) JRE  — Spark 는 JVM 위에서 돈다. airflow 이미지에는 자바가 없다
#   2) pyspark — spark-submit 과 파이썬 API
#
# pipeline/Dockerfile 을 고치지 않는 이유 — 그 파일은 팀 공용이고 이미지가 바뀌면 팀 전원의
# 빌드가 바뀐다 (09 §2 의 "compose.yaml 을 직접 고치지 않는다" 와 같은 이유). 상속으로
# 얹으면 이 디렉터리 안에서만 끝나고, 되돌릴 때도 오버레이만 빼면 된다.
#
# 왜 아예 컨테이너에 넣나 — Airflow 가 컨테이너 안에 있으면 호스트의 spark-submit 을 부를
# 방법이 없다. 태스크가 도는 곳에 Spark 가 있어야 DAG 로 엮인다 (09 §2).

ARG PIPELINE_IMAGE=s15p21a102/pipeline:local
FROM ${PIPELINE_IMAGE}

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

# 설정은 yaml 로 읽는다. Airflow 가 이미 PyYAML 을 갖고 있어서 따로 설치하지 않는다 —
# 없어지면 여기서 빌드가 실패해야 한다. 런타임에 발견하면 원인 찾기가 훨씬 어렵다.
RUN python -c "import yaml, pyspark, gliner, kiwipiepy; print('pyspark', pyspark.__version__)"
