# Git 컨벤션

## 네이밍

- 작업 브랜치: `{이니셜}/{Jira 키}`. 예: `hg/S15P21A102-184`.
- 커밋: `{type}: {변경 요약}`. 타입은 `feat`, `fix`, `chore`, `build`, `hotf`, `docs`, `refactor`를 사용한다.
- MR 제목: `[{이니셜}] {Jira Summary}`.
- MR 대상: `dev`. 본문은 `origin/dev...HEAD`의 실제 변경에 기반해 `📌 Summary`, 필요한 경우 `📝 Note`, `📌 Related Issue`로 작성한다.
- Jira 링크: `https://ssafy.atlassian.net/browse/{Jira 키}`.

작업은 commit·push 및 요청된 MR 작성/갱신까지 진행한다. 명시적인 merge 요청 전에는 병합하지 않는다. `dev`, `master`의 force-push와 삭제는 금지한다.
