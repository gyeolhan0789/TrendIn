FROM eclipse-temurin:25-jdk-noble AS builder

WORKDIR /workspace

COPY . .

RUN chmod +x gradlew \
    && ./gradlew clean bootJar --no-daemon \
    && find build/libs -maxdepth 1 -type f -name '*.jar' ! -name '*-plain.jar' \
        -exec cp '{}' /workspace/app.jar \;

FROM eclipse-temurin:25-jre-noble

RUN groupadd --system spring \
    && useradd --system --gid spring --no-create-home spring

WORKDIR /app

COPY --from=builder --chown=spring:spring /workspace/app.jar /app/app.jar

USER spring

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
