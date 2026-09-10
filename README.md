# S15P21A102

## CI

MR 을 열면 `.gitlab-ci.yml` 이 바뀐 디렉터리의 job 만 돌린다. dev 브랜치에서는 전부 돈다.

| job | 언제 | 무엇 |
|---|---|---|
| `datastore:compose` | `datastore/**` 변경 | `docker compose config --quiet` — compose 해석 검증 |
| `datastore:guard` | `datastore/compose.yaml` 변경 | 되돌릴 수 없는 설정이 위험한 방향으로 바뀌었는지 |
| `pipeline:verify` | `pipeline/**` 변경 | `ruff check` · `pytest` (DAG import 검사 포함) |
| `pipeline:verify-spark` | `pipeline/**` 변경 | `pytest spark/tests` — pyspark 세션까지 |

컨테이너를 띄워야 하는 `datastore/scripts/verify.sh` 는 CI 가 아니라 CD 에서 부른다.

## CD

`deploy:data-ec2` 가 데이터 EC2 `J15A102A` 에 Kafka · MinIO · Airflow · Spark 를 올린다.
**dev 에 `datastore/` · `pipeline/` 변경이 머지되면 자동으로 돈다.** 문서나 백엔드만 고친 머지로는
서버를 건드리지 않는다.

`compose.yaml` 이 `./dags` · `./src` · `./spark` 를 바인드 마운트하므로, 파이썬 코드만 고친 배포는
이미지가 그대로라 컨테이너를 재생성하지 않는다. 몇 분씩 걸리는 것은 `Dockerfile` 이나
`pyproject.toml` 을 고쳐 이미지를 다시 구워야 할 때뿐이다.

잡이 부르는 것은 [`scripts/deploy-data-ec2.sh`](scripts/deploy-data-ec2.sh) 하나다. CI 가 멈춘 날
서버에서 사람이 치는 명령도 같은 것이다. 절차·러너 설치·서버 최초 세팅은
[`docs/deploy-data-ec2.md`](docs/deploy-data-ec2.md).

## Runner

**러너 두 벌이 데이터 EC2 한 대에 붙어 있어야 한다.** 검증 잡은 잡마다 다른 `image:` 를 쓰므로
docker executor 여야 하고, 배포 잡은 compose 의 상대 경로 바인드 마운트가 호스트 기준으로
풀려야 하므로 shell executor 여야 한다. 배포 잡은 `data-ec2` 태그로 후자에 간다.

러너가 없으면 job 이 대기열에 올라간 채 pending 에 멈춘다. GitLab 화면의 러너 상태가
`Never contacted` 면 등록만 돼 있고 서버에는 설치되지 않은 것이다. 설치 절차는
[`docs/deploy-data-ec2.md`](docs/deploy-data-ec2.md) 1절.
