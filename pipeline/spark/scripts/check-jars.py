"""받아둔 jar 가 실제로 물리는지 확인한다. 외부 서비스는 필요 없다.

    spark/scripts/check-jars.sh 가 jar 목록을 붙여 이 파일을 돌린다.

버전이 어긋나면 보통 **처음 S3A 나 JDBC 를 쓸 때** NoSuchMethodError 로 죽는다 ([01 §7]).
그때는 원인이 jar 인지 코드인지 구분하기 어렵다. 여기서 먼저 갈라둔다.
"""

from __future__ import annotations

import sys

from pyspark.sql import SparkSession

# 클래스 이름 → 어느 jar 가 주는 것인지
REQUIRED = {
    "org.apache.hadoop.fs.s3a.S3AFileSystem": "hadoop-aws",
    "software.amazon.awssdk.services.s3.S3Client": "aws sdk bundle",
    "org.postgresql.Driver": "postgresql",
}


def main() -> int:
    spark = SparkSession.builder.master("local[1]").appName("trendin-check-jars").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    loader = spark._jvm.java.lang.Thread.currentThread().getContextClassLoader()

    missing = []
    for class_name, jar in REQUIRED.items():
        try:
            spark._jvm.java.lang.Class.forName(class_name, False, loader)
        except Exception:  # py4j 가 감싸서 던지므로 타입을 좁히지 않는다
            missing.append((class_name, jar))
            print(f"없음  {jar:34} {class_name}")
        else:
            print(f"있음  {jar:34} {class_name}")

    print()
    print(f"Spark {spark.version} · Python {sys.version_info.major}.{sys.version_info.minor}")
    spark.stop()

    if missing:
        print("\nspark/scripts/fetch-jars.sh 를 돌리고 --jars 경로를 확인한다.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
