# Spring-boot 컨벤션

Java 25, Spring Boot 4.1.x, JPA/Hibernate, MySQL 기반 코드에 적용한다.

## 레이어드 아키텍처

도메인별로 `Controller → Service → Repository → DB`의 계층 구조를 따른다.
```
Controller → Service → Repository → DB
                ↓
             Domain
```

- **`Controller`**: HTTP 요청 처리, 요청 검증 및 응답 반환
- **`Service`**: 비즈니스 로직 및 트랜잭션 관리
- **`Repository`**: 데이터베이스 접근
- **`Domain`**: Entity의 상태와 비즈니스 규칙 관리
- `Controller`는 `Repository`를 직접 호출하지 않는다.
- 상위 레이어가 하위 레이어를 호출하며 역방향·순환 의존을 만들지 않는다.

## 검증 책임 분리

- **`DTO`**: 요청·응답 데이터 전달에 사용하며, Request DTO `@Valid`와 Bean Validation을 사용해 null, 길이, 범위, 형식 등 요청 값 자체를 검증한다.
- **`Service`**: 권한, 중복, 현재 상태, Entity 간 관계 등 비즈니스 규칙을 검증한다.
- **`Domain Entity`**: Entity 자체의 상태 변경과 항상 지켜야 하는 불변식을 관리한다.
- 동일한 검증 로직을 여러 계층에 불필요하게 중복하지 않는다.

## Service CQRS

조회와 상태 변경 책임이 모두 존재하는 경우, `XxxCommandService / XxxReadService`로 Service 책임을 분리한다
```
service
├── ArticleCommandService.java
└── ArticleReadService.java
```

- **`Command Service`**: 생성·수정·삭제 등 상태 변경을 담당한다.
- **`Read Service`**: 조회만 담당하며 Entity의 상태를 변경하지 않는다.
- 단순한 도메인은 불필요하게 Command/Read Service로 분리하지 않는다.

## 트랜잭션

- 트랜잭션은 **Service 계층에서 관리**한다.
- `XxxCommandService`에는 `@Transactional`, `XxxReadService`에는 `@Transactional(readOnly = true)`를 클래스 레벨에 선언한다.
- 필요한 경우 메서드 레벨에서 별도의 트랜잭션 설정을 사용할 수 있다.
- DB 트랜잭션을 유지한 상태에서 외부 HTTP API를 호출하지 않는 것을 원칙으로 한다.

## JPA/Entity

- Entity에 `@Table(name = "...")`을 명시한다.
- `createdAt`, `updatedAt` 등 공통 필드는 `@MappedSuperclass`를 활용해 관리한다.
- 단일 컬럼의 유니크 제약조건은 `@Column(unique = true)`로 선언한다.
- 복합 유니크 제약조건은 `@Table`의 `@UniqueConstraint`로 선언한다.
- 연관관계는 필요한 경우에만 정의하며 기본적으로 `FetchType.LAZY`를 사용한다.
- 연관관계 사용 시 N+1 문제를 검토하고, 필요한 경우 fetch join 또는 `@EntityGraph`를 사용한다.
- Enum은 `@Enumerated(EnumType.STRING)`을 사용하며 `EnumType.ORDINAL`은 사용하지 않는다.
- `CascadeType.ALL`은 기본적으로 사용하지 않으며, Entity의 생명주기가 명확하게 함께 관리되는 경우에만 cascade를 적용한다.

## 외부 API

- 외부 HTTP API 통신은 **WebClient** 사용을 기본으로 하며 `RestTemplate` 사용을 지양한다.
- HTML 크롤링은 목적에 맞는 별도의 크롤링·파싱 라이브러리를 사용할 수 있다.
- 외부 API 연동 코드는 일반 비즈니스 로직과 분리한다.
- 외부 API 호출과 DB 작업을 함께 조율해야 하는 경우 별도의 Facade/Application Service 등의 분리를 고려한다.
