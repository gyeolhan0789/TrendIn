# 테스트 컨벤션

## 테스트 방식

- JUnit Jupiter와 AssertJ를 사용하고, `@DisplayName`은 한국어로 작성한다.
- `given / when / then`으로 구분하여 동작과 결과를 검증한다.
- Controller: MockMvc로 요청·응답과 상태 코드를 검증하고 REST Docs를 생성한다.
- Service / Domain: 단위 테스트를 작성하고 외부 의존성은 BDDMockito로 대체한다.
- Repository: H2와 실제 영속성 컨텍스트를 사용하는 통합 테스트를 작성한다.
- 기능 변경 후 전체 테스트와 빌드를 실행한다.

저장소 루트 기준:

```sh
./backend/gradlew -p backend clean test asciidoctor build
```

Windows PowerShell에서는 `./backend/gradlew.bat -p backend clean test asciidoctor build`를 사용한다.

결과 경로는 테스트 보고서 `backend/build/reports/tests/test/index.html`, REST Docs 스니펫 `backend/build/generated-snippets`, API 문서 `backend/build/docs/asciidoc/index.html`, JAR `backend/build/libs`이다.
실행 JAR에는 API 문서가 `BOOT-INF/classes/static/docs/index.html`로 포함된다.
