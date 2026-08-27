# 테스트 컨벤션

Java Spring Boot 테스트 작성 시 적용한다.

## 핵심 원칙

- **JUnit 5, AssertJ**를 사용한다.
- `@DisplayName`은 한국어로 작성한다.
- **given / when / then** 구조를 따른다.
- 하나의 테스트에서는 하나의 동작을 검증한다.
- 테스트 이름은 구현 방식보다 **동작과 결과**가 드러나도록 작성한다.
- private 메서드를 직접 테스트하지 않고 public 메서드를 통해 검증한다.
- 불필요한 Spring Context 로딩을 피한다.

## Controller 테스트

요청 검증, 요청·응답 매핑, HTTP 상태 코드, 에러 응답 및 **REST Docs 문서화**를 검증한다.

- Controller 테스트는 `MockMvc`를 사용한다.
- Service는 Mock으로 처리한다.
- Controller의 비즈니스 로직은 검증하지 않는다.
- Repository에 직접 접근하지 않는다.
- API의 경로, HTTP Method, 요청·응답 형식을 검증한다.

## Service 테스트

비즈니스 로직과 예외 케이스를 검증한다.

- 기본적으로 **단위 테스트**로 작성한다.
- Repository와 외부 의존성은 Mock으로 처리한다.
- Service의 public 메서드를 통해 동작을 검증한다.
- 필요한 경우에만 Spring Context를 로딩한다.

## Repository 테스트

Repository 쿼리, JPA 매핑 및 제약조건을 검증한다.

- 실제 영속성 컨텍스트를 사용하는 **통합 테스트**로 작성한다.
- Repository를 Mock으로 처리하지 않는다.
- 저장 및 조회 결과를 명시적으로 검증한다.
- 커스텀 쿼리, fetch join, `@EntityGraph` 등 직접 작성한 Repository 동작을 검증한다.

## REST Docs

- Controller 테스트를 기반으로 **Spring REST Docs**를 생성한다.
- API 문서는 **통과한 테스트를 기준으로 생성**한다.
- Path Parameter, Query Parameter, 요청·응답 필드, 헤더가 존재하는 경우 문서화한다.
- 예시 값은 실제 API에서 사용하는 값과 유사하게 작성한다.
- 주요 에러 응답도 테스트하고 문서화한다.
- 실제 API와 문서가 일치하지 않는 경우 테스트가 실패하도록 작성한다.

## 픽스처

- 반복적으로 사용하는 테스트 데이터는 Fixture 또는 Factory로 분리한다.
- 테스트 데이터는 실행 순서에 의존하지 않도록 작성한다.
- Fixture 이름은 테스트 데이터의 의도가 드러나도록 작성한다.
- 중요한 테스트 조건을 Fixture 내부에 숨기지 않는다.
- Fixture를 위해 프로덕션 코드의 접근 제어자를 변경하지 않는다.

## Mock

- 테스트 대상의 **외부 의존성**만 Mock으로 처리한다.
- Entity와 Value Object 등 직접 생성할 수 있는 객체는 Mock으로 처리하지 않는다.
- Mockito 대신 **BDDMockito** 사용을 기본으로 한다.
```scss
given(articleRepository.findById(articleId)).willReturn(Optional.of(article));then(articleRepository).should().findById(articleId);
```

- 상태와 결과 검증을 우선하고, 호출 여부 자체가 중요한 경우에만 interaction verification을 사용한다.

## Assertion

- **AssertJ**를 사용한다.
- 구현 세부사항보다 실제 결과와 상태를 검증한다.
- 비즈니스 규칙 위반에 대한 예외 케이스도 테스트한다.

예를 들면:
```scss
assertThat(article.getTitle()).isEqualTo("패션 트렌드");assertThatThrownBy(() ->articleService.getArticle(1L)).isInstanceOf(ArticleNotFoundException.class);
```
