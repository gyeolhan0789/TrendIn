# S15P21A102

## CI

MR 을 열면 `.gitlab-ci.yml` 이 바뀐 디렉터리의 job 만 돌린다. dev 브랜치에서는 둘 다 돈다.

| job | 언제 | 무엇 |
|---|---|---|
| `datastore:compose` | `datastore/**` 변경 | `docker compose config --quiet` — compose 해석 검증 |
| `pipeline:verify` | `pipeline/**` 변경 | `ruff check` · `pytest` (DAG import 검사 포함) |

컨테이너를 띄워야 하는 `datastore/scripts/verify.sh` 는 CI 가 아니라 CD 에서 부른다.

Runner: 도커 executor 러너가 프로젝트에 하나 붙어 있어야 한다. 없으면 job 이 이미지를 못 받아 pending 에 멈춘다.
