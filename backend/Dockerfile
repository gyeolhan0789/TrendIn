FROM eclipse-temurin:25-jre-noble

RUN groupadd --system spring \
    && useradd --system --gid spring --no-create-home spring

WORKDIR /app

COPY --chown=spring:spring build/libs/app.jar /app/app.jar

USER spring

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
