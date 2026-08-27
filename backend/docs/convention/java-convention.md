# Java 컨벤션

## 공통 원칙

- 지정되지 않은 기술이나 라이브러리는 도입 전에 팀원과 공유한다.
- 불필요한 import, 사용하지 않는 코드, 매직 넘버·매직 스트링을 남기지 않는다.
- 하나의 클래스와 메서드는 가능한 하나의 책임을 갖도록 작성한다.
- 기능 변경 후 관련 빌드와 테스트를 실행한다.

## 코드 스타일

- 모든 파일의 마지막은 개행으로 마무리한다.
- import문에서 wildcard 사용을 지양한다.

## 📁 디렉터리 구조
```css
src/main/java/com/forever102/backend
├── global
│   ├── config
│   ├── exception
│   ├── response
│   └── util
│
├── member
│   ├── controller
│   ├── service
│   ├── repository
│   ├── domain
│   └── dto
│
└── article
    ├── controller
    ├── service
    ├── repository
    ├── domain
    └── dto
```

도메인을 기준으로 패키지를 분리하며, 새로운 기능이 추가되면 동일한 구조를 따른다.

## 네이밍 컨벤션

#### API - REST 원칙

- 리소스명은 **복수형**을 사용한다.&#x20;
  - `/members`
  - `/articles`
- 여러 단어가 들어가는 경우 **kebab-case**를 사용한다.&#x20;
  - `/trend-keywords`
- Path Variable과 Query Parameter는 **camelCase**를 사용한다.&#x20;
  - `/members/{memberId}`
  - `/articles?keywordId=1`

#### 클래스

- 클래스와 인터페이스는 **PascalCase**를 사용한다.
- 계층별 클래스는 다음 형식을 사용한다.&#x20;
  - Controller: `XXXController`
  - Service: `XXXService`
  - Repository: `XXXRepository`
- Entity는 별도의 접미사를 붙이지 않는다.&#x20;
  - `MemberEntity` ❌
  - `Member` ✅
- 요청 DTO: `XXXRequest`
- 응답 DTO: `XXXResponse`

#### 메서드와 변수

- 메서드와 변수는 **camelCase**를 사용한다.
- 메서드명은 가능한 **동사 + 명사** 형태로 작성한다.&#x20;
  - `getMember()`
  - `createArticle()`
  - `findTrendKeywords()`
- `cnt`, `idx`, `msg` 등의 축약어보다 `count`, `index`, `message`처럼 의미가 드러나는 이름을 사용한다.
- 상수는 **UPPER\_SNAKE\_CASE**를 사용한다.

## 의존성 주입과 Lombok

- 의존성 주입은 **생성자 주입**을 사용한다.
- `@Autowired`를 통한 필드 주입은 사용하지 않는다.
- Spring Bean의 의존성은 `private final`로 선언하고 `@RequiredArgsConstructor`를 사용한다.
- DTO는 가능하면 **Java&#x20;****`record`** 사용을 우선한다.
- Lombok은 다음을 허용한다.&#x20;
  - `@Getter`
  - `@Builder`
  - `@RequiredArgsConstructor`
- `@Data`는 사용하지 않는다.
- Entity에는 `@Setter` 사용을 지양한다.&#x20;
  - 지양 : `member.setNickname(nickname);`
  - 권장 : `member.updateNickname(nickname);`

## 예외 처리

- 비즈니스 예외는 `RuntimeException`을 상속한 커스텀 예외로 정의한다.
- 예외를 빈 `try-catch`로 숨기지 않는다.
- 중첩된 `if`문이 많아지는 경우 **early return**을 우선 고려한다.
- 공통 예외 응답은 `global.exception`에서 처리한다.
  ```java
  if (member == null) {
      throw new MemberNotFoundException();
  }

  ```
