# Spring Boot 컨벤션

## 기술 스택 / 버전

| 항목 | 기준 |
| --- | --- |
| Java | 25 |
| Spring Boot | 4.1.1 |
| Gradle | Wrapper 9.7.1 |
| 데이터 접근 | Spring Data JPA / Hibernate, Spring Boot 의존성 관리 버전 |
| 로컬 개발 DB | H2, `local` 프로필 |
| 배포 / 공용 DB | PostgreSQL 17, `dev` 프로필 |
| 테스트 / 문서 | JUnit Jupiter, AssertJ, MockMvc, Spring REST Docs |

Spring 설정은 `application.yml`, `application-local.yml`, `application-dev.yml`로 구분한다.
로컬은 메모리 H2와 `ddl-auto: create-drop`, 배포는 PostgreSQL과 `ddl-auto: create`를 사용한다. 배포 DDL 정책은 당분간 유지한다.

저장소 루트에서 로컬 실행: `./backend/gradlew -p backend bootRun --args='--spring.profiles.active=local'`.
Windows PowerShell에서는 `./backend/gradlew.bat -p backend bootRun --args='--spring.profiles.active=local'`을 사용한다.
배포 실행 환경에는 `SPRING_PROFILES_ACTIVE=dev`와 `DEV_POSTGRES_URL`, `DEV_POSTGRES_USER_NAME`, `DEV_POSTGRES_PASSWORD`를 주입한다.

## 프로젝트 구조

```text
backend/
├── src/
│   ├── main/java/com/forever102/backend/
│   │   ├── auth/
│   │   ├── member/
│   │   ├── trend/
│   │   └── global/
│   ├── main/resources/          # application*.yml
│   ├── test/java/
│   └── docs/asciidoc/           # REST Docs 원본
├── docs/                       # 컨벤션 및 설계 문서
├── gradle/wrapper/
├── build.gradle
├── settings.gradle
├── gradlew
└── gradlew.bat
```

도메인 아래 필요한 `controller`, `service`, `repository`, `domain`, `dto` 패키지를 둔다.
공통 코드는 `global`에 둔다. Java 패키지 경로는 `com.forever102`를 유지한다.
