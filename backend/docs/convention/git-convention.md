# Git 컨벤션

# Git-branch

## 브랜치

[이니셜]/이슈번호\~

## 브랜치 전략

- 평상시에 `master`, `dev` 두 브랜치만 운용한다.
- 기능 개발 시 `dev` 에서 분기하며, 브랜치명은 `{이니셜}/{이슈번호}` 으로 생성한다. (e.g. `hg/34`)
- `feat` → `dev` 은 squash merge, `dev` → `master`은 merge commit 방식으로 병합한다.
- MR 최소 승인 리뷰어 수는 없으나, Merge 후 mm혹은 리뷰 달아주기 !
- `dev` 브랜치를 default 브랜치로 설정한다.
- `dev`, `master` 브랜치에는 force-push, 삭제를 금지한다.

# Git-commit

## 머리글

| 타입 이름 내용   |                                   |
| ---------- | --------------------------------- |
| `feat`     | 새로운 기능에 대한 커밋                     |
| `fix`      | 버그 수정에 대한 커밋                      |
| `chore`    | 그 외 자잘한 수정에 대한 커밋                 |
| `build`    | 빌드 관련 파일 수정 / 모듈 설치 또는 삭제에 대한 커밋  |
| `hotf`     | 긴급 배포용 수정에 대한 커밋                  |
| `docs`     | 문서 수정에 대한 커밋                      |
| `refactor` | 기능 변경이나 버그 수정 없이 기존 코드 구조를 개선한 커밋 |

## 바디

- 머리글에서 표현할 수 없는 상세한 내용을 기재.&#x20;
  - 머리글에서 충분히 표현 가능하다면 생략 가능.

## 바닥글

- 어떤 이슈에서 왔는지 같은 참조 정보들을 추가하는 용도
- 특정 이슈를 참조하려면 Issues #1234 와 같이 작성하면 됨
- 생략 가능
```jsx
git commit -m "feat: 로그인 구현"
git commit -m "fix: 회원 정보 수정 오류 해결"
```

# Git-MR

- `origin/dev...HEAD` diff를 기준으로 MR 본문을 작성한다.
- 변경된 코드의 구현 방식보다 사용자·시스템 관점에서 변경된 동작을 중심으로 작성한다.
- `Summary`에는 주요 변경 사항을 작성하고, 추가로 전달할 내용이 있는 경우에만 `Note`를 작성한다.
- Jira 키가 확인되면 `Related Issue`에 `https://ssafy.atlassian.net/browse/{key}`를 추가한다.
- MR 제목은 `[담당자 이니셜] Jira summary` 형식을 사용한다.
- 담당자 이니셜 또는 Jira 정보를 확인할 수 없는 경우 사용자에게 요청한다.
- 기존 source branch MR이 있으면 본문을 갱신하고, 없으면 target branch `dev`으로 생성한다.
```markdown
## 📌 Summary
[설명]

## 📝 Note
[필요한 경우에만 작성]

## 📌 Related Issue
[Jira: <https://ssafy.atlassian.net/browse/S15P21A102-(이슈번호)>]
```
