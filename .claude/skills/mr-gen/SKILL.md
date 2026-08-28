---
name: mr-gen
description: Analyze the current Git branch and its diff against origin/dev, then create or update the matching GitLab merge request according to this project's Jira, title, and description conventions. Use when asked to write, create, or refresh an MR for the current branch.
---

# GitLab MR 작성

현재 브랜치의 실제 변경사항을 분석해 이 프로젝트 규칙에 맞는 GitLab MR 제목과 본문을 작성하고, 기존 MR을 수정하거나 새 MR을 생성한다.

## 프로젝트 규칙 확인

`backend/docs/convention/git-convention.md`가 존재하면 먼저 읽고 이 Skill의 규칙과 함께 따른다. 규칙이 충돌하면 이 Skill에 명시된 MR 워크플로와 형식을 적용한다.

MR 작업을 시작하기 전에 다음을 확인한다.

```bash
git branch --show-current
git status --short
glab --version
glab auth status
```

현재 브랜치가 `dev` 또는 `master`이면 MR을 직접 생성하거나 수정하지 말고 사용자에게 알린다.

## 브랜치와 Jira 정보 확인

기능 개발 브랜치는 `{담당자 이니셜}/{Jira 이슈 키}` 형식을 사용한다. 예를 들어 `hg/S15P21A102-66`에서는 다음 정보를 추출한다.

- 담당자 이니셜: `hg`
- Jira Key: `S15P21A102-66`

담당자 이니셜이나 Jira Key를 브랜치명에서 확인할 수 없으면 추측하지 말고 사용자에게 요청한다.

Jira Key를 확인하면 사용 가능한 Jira MCP 또는 Jira 연결 도구로 해당 이슈의 Summary를 조회한다. 조회할 수 없으면 Jira Summary를 만들거나 추측하지 말고 사용자에게 MR 제목에 사용할 Summary를 요청한다.

Related Issue URL은 `https://ssafy.atlassian.net/browse/{Jira Key}` 형식을 사용한다.

## 변경사항 분석

기준 브랜치는 반드시 `origin/dev`를 사용한다. `origin/develop`은 사용하지 않는다. 최신 기준 브랜치가 필요하면 먼저 다음을 실행한다.

```bash
git fetch origin dev
```

다음 세 diff를 확인한다.

```bash
git diff origin/dev...HEAD
git diff origin/dev...HEAD --name-only
git diff origin/dev...HEAD --stat
```

실제 diff를 기반으로 구현 세부사항의 나열보다 사용자 또는 시스템 관점에서 변경된 동작을 정리한다. diff에 없는 변경사항은 작성하지 않는다.

## MR 제목과 본문

MR 제목은 반드시 다음 형식을 사용한다.

```text
[담당자 이니셜] Jira summary
```

`[FEAT] Jira 이슈 제목` 형식은 사용하지 않는다.

본문은 다음 구조를 사용한다.

```markdown
## 📌 Summary

- {주요 변경 사항}
- {주요 변경 사항}

## 📝 Note

- {리뷰어에게 추가로 전달할 내용}

## 📌 Related Issue

[Jira: https://ssafy.atlassian.net/browse/{Jira Key}](https://ssafy.atlassian.net/browse/{Jira Key})
```

- `Summary`에는 실제 diff에 기반한 주요 변경사항을 작성한다.
- `Note`는 리뷰어에게 별도로 전달할 내용이 있을 때만 포함하며, 없으면 섹션 전체를 생략한다.
- `📚 Changes` 섹션은 사용하지 않는다.
- `Related Issue`에는 확인된 Jira Key의 링크를 사용한다.

## 기존 MR 우선 처리

새 MR을 만들기 전에 현재 source branch의 열린 MR을 조회한다.

```bash
glab mr list --source-branch <현재-브랜치> --state opened
```

기존 MR이 있으면 새 MR을 중복 생성하지 않고 제목과 본문을 모두 현재 규칙에 맞게 업데이트한다. 사용할 옵션은 설치된 버전에서 확인한다.

```bash
glab mr update --help
```

기존 MR이 없으면 target branch를 반드시 `dev`로 지정해 생성한다.

```bash
glab mr create \
  --title <생성한-제목> \
  --description <생성한-본문> \
  --target-branch dev
```

`develop`을 target branch로 사용하지 않는다.

## 완료 확인

생성 또는 수정 후 결과를 확인한다.

```bash
glab mr view
```

사용자에게 다음을 간단히 알린다.

- MR을 새로 생성했는지 또는 기존 MR을 수정했는지
- 최종 MR 제목
- MR URL

## 제약

- MR 작성을 위해 소스 코드를 수정하지 않는다.
- 사용자 요청 없이 commit을 생성하거나 push하지 않는다.
- Jira Summary나 담당자 이니셜을 확인할 수 없으면 추측하지 않는다.
- MR 내용은 반드시 `origin/dev...HEAD`의 실제 변경사항을 기준으로 한다.
- 기존 source branch MR이 존재하면 새 MR을 중복 생성하지 않는다.
