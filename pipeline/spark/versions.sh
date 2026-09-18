# Spark 실행에 쓰는 모든 버전의 단일 출처. 셸에서 source 하고, Dockerfile 은 COPY 해서 읽는다.
#
# 여기 한 곳만 고치면 jar · 가상환경 · 컨테이너 이미지가 같이 따라온다. 예전에는 이 값이
# fetch-jars.sh 와 Dockerfile 두 곳에 있었는데, 그러면 한쪽만 올리고 다른 쪽을 잊는다.
# 어긋나면 세션은 멀쩡히 뜨고 처음 Kafka 를 읽을 때 NoSuchMethodError 로 죽는다 ([01 §7]).
#
# 아래 숫자는 추측이 아니라 pyspark 4.0.4 를 깔고 확인한 값이다:
#   번들된 것 → hadoop-client-api/runtime 3.4.1, scala-library 2.13.16, jsr305, snappy, lz4
#   번들에 없는 것 → kafka-clients, commons-pool2 (번들된 commons-pool 1.5.4 는 다른 물건)
#
# 올릴 때는 SPARK_VERSION 만 바꾸지 말고 KAFKA_CLIENTS · HADOOP_VERSION · AWS_SDK_VERSION 을
# 다시 확인한다.
#   https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.13/<버전>/*.pom
#   https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-project/<hadoop>/*.pom 의 aws-java-sdk-v2.version

SPARK_VERSION=4.0.4      # pyspark 핀. Python 3.12 지원 (4.0.x 는 3.9+)
SCALA_BINARY=2.13        # Spark 4.x 는 2.13 만 낸다
KAFKA_CLIENTS=3.9.1      # spark-sql-kafka-0-10_2.13:4.0.4 의 compile 의존성
COMMONS_POOL2=2.12.0     # 같음
HADOOP_VERSION=3.4.1     # pyspark 가 번들한 hadoop-client-api 와 같아야 한다
AWS_SDK_VERSION=2.24.6   # hadoop-project 3.4.1 의 aws-java-sdk-v2.version. 530 MB
POSTGRES_JDBC=42.7.13    # 비교적 자유롭다

# 실체 인식 (spark/docs/04 §2, src/trendin/spark/extract/entities.py). 2026-09-16 추가.
#
# torch 를 CPU 휠로 따로 먼저 깐다 — 기본 인덱스는 CUDA 런타임까지 끌고 와 이미지가 3 GB
# 넘게 커진다. **배포에는 GPU 가 없다** (데이터 EC2). 문서당 약 1초이고 하루 3,000건이면
# executor 4개로 13분이라, 운영 이미지는 CPU 로 충분하다.
#
# 모델 가중치도 이미지에 미리 받는다. 런타임에 받으면 executor 마다 HuggingFace 로 나가고,
# 망이 막힌 환경에서는 그 실패가 "후보가 0개" 로만 나타난다.
GLINER_VERSION=0.2.29
GLINER_MODEL=urchade/gliner_multi-v2.1
TORCH_CPU_INDEX=https://download.pytorch.org/whl/cpu

# GPU 로 돌리는 개발 PC 용 (spark/Dockerfile.gpu). **운영 이미지는 이것을 읽지 않는다.**
# 재추출은 코퍼스 전체를 다시 추론하는 일이라 CPU 로는 시간 단위가 되는데, 그 반복이 개발
# PC 에서 일어난다.
#
# **cu130 이 아니라 cu126 이다.** 드라이버(591.44 · CUDA 13.1)는 둘 다 받지만, cu126 은 더
# 오래된 드라이버에서도 돌아 팀의 다른 GPU 로 옮기기 쉽다. 아키텍처 지원은 같다.
TORCH_CUDA_INDEX=https://download.pytorch.org/whl/cu126
# **두 이미지의 torch 를 같은 버전으로 묶는다.** 인덱스마다 최신이 달라서(cu128 은 2.11 에
# 멈춰 있다) 핀이 없으면 CPU 와 GPU 가 다른 torch 를 쓰게 되고, 그러면 "GPU 에서만 결과가
# 다르다" 를 gliner 가 아니라 torch 에서 찾아야 한다.
TORCH_VERSION=2.14.0
