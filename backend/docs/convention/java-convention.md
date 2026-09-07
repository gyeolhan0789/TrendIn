# Java 컨벤션

## 네이밍

| 대상 | 규칙 / 예시 |
| --- | --- |
| 패키지 | 소문자, 도메인 단위: `member`, `trend` |
| 클래스 / 인터페이스 | PascalCase: `TrendService` |
| 계층별 클래스 | `XxxController`, `XxxService`, `XxxRepository` |
| Entity | `Entity` 접미사 없이 `Member`, `Trend` |
| 요청 / 응답 DTO | `XxxRequest`, `XxxResponse` |
| 메서드 / 변수 | camelCase: `getTrendDetail`, `mentionCount` |
| 상수 | UPPER_SNAKE_CASE |
| API 리소스 경로 | 복수형, 여러 단어는 kebab-case: `/trends`, `/trend-keywords` |
| Path / Query 파라미터 | camelCase: `trendId`, `pageSize` |
