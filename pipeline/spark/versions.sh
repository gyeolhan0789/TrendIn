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
