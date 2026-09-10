#!/usr/bin/env bash
# 데이터 EC2(J15A102A) 배포. datastore → jar → 이미지 → Airflow·Spark 순으로 올린다.
#
#   scripts/deploy-data-ec2.sh
#
# 이 순서는 취향이 아니라 강제다. datastore/compose.yaml 이 네트워크 s15p21a102-data 의
# 주인이고 pipeline 쪽은 그것을 external 로 참조하므로, 저장소가 먼저 뜨지 않으면
# Airflow 는 뜨다 실패한다 (datastore/README.md "어디에 뜨나").
#
# --- CI 와 손 실행이 같은 경로를 쓴다 ----------------------------------------
# GitLab 배포 잡도 이 스크립트를 부르고, 서버에서 사람이 칠 때도 이것을 친다. 배포 절차가
# .gitlab-ci.yml 안에 흩어져 있으면 CI 가 멈춘 날 손으로 올릴 방법이 사라지고, 두 경로가
# 갈리면 "CI 로는 되는데 손으로는 안 된다" 를 디버깅하게 된다.
#
# --- 왜 체크아웃에서 바로 띄우지 않고 옮기나 ---------------------------------
# 러너의 빌드 디렉터리는 잡마다 지워질 수 있고, 거기에는 비밀값(.env)도 jar 도 없다.
# 그래서 서버에 배포 전용 디렉터리를 하나 두고 소스만 덮어쓴다. 그 디렉터리에 남아야 하는
# 것 셋 — .env 두 벌, 530 MB 짜리 jar, Airflow 로그 — 은 아래 rsync 가 건너뛴다.
set -euo pipefail

DEPLOY_ROOT=${DEPLOY_ROOT:-/srv/trendin}
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-300}
SKIP_VERIFY=${SKIP_VERIFY:-0}

HERE=$(cd "$(dirname "$0")" && pwd)
SOURCE=$(cd "$HERE/.." && pwd)

die() { echo "배포 중단: $*" >&2; exit 1; }
step() { echo; echo "── $*"; }

# --- 0. 전제 확인 ------------------------------------------------------------
# 여기서 걸러야 할 것은 "절반쯤 올라간 상태" 다. 저장소만 뜨고 Airflow 가 못 뜨면
# 되돌릴 것이 생기므로, 손댈 수 있는 조건은 손대기 전에 전부 본다.
command -v docker >/dev/null 2>&1 || die "docker 가 없다"
docker compose version >/dev/null 2>&1 || die "docker compose v2 가 없다 (docker-compose v1 은 쓰지 않는다)"
docker info >/dev/null 2>&1 || die "도커 데몬에 붙지 못했다 — 이 계정이 docker 그룹에 있는지 본다"

if [ "$SOURCE" != "$DEPLOY_ROOT" ]; then
  command -v rsync >/dev/null 2>&1 || die "rsync 가 없다 — sudo apt-get install -y rsync"

  step "소스 반영  $SOURCE → $DEPLOY_ROOT"
  mkdir -p "$DEPLOY_ROOT"
  # --delete 는 켠다. 지운 파일이 서버에만 남아 있으면 어느 날 그 옛 파일이 읽힌다.
  # 아래 --exclude 로 뺀 것은 --delete 대상에서도 자동으로 보호된다 (rsync 기본 동작).
  #
  # '.env' 는 와일드카드가 없어 이름이 정확히 .env 인 것만 잡는다. .env.example 은
  # 그대로 따라간다 — 그쪽은 Git 에 있고 서버에서도 참조본으로 필요하다.
  rsync -a --delete \
    --exclude '.git/' \
    --exclude '.env' \
    --exclude 'pipeline/spark/jars/' \
    --exclude 'pipeline/logs/' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '.ruff_cache/' \
    "$SOURCE/" "$DEPLOY_ROOT/"
else
  step "배포 디렉터리에서 직접 실행 — 소스 반영을 건너뛴다"
fi

cd "$DEPLOY_ROOT"

# .env 는 Git 에 없다. 서버에만 있고, 없으면 compose 의 `${VAR:?}` 가 이해하기 어려운
# 메시지로 죽는다. 여기서 먼저 사람이 읽을 수 있는 말로 세운다.
for env_path in datastore/.env pipeline/.env; do
  [ -s "$DEPLOY_ROOT/$env_path" ] || die "$DEPLOY_ROOT/$env_path 가 없거나 비었다 — docs/deploy-data-ec2.md '서버 최초 세팅' 을 따른다"
done

# Airflow 로그 디렉터리를 여기서 만든다. 위 rsync 가 제외하는 유일한 바인드 마운트 소스라
# 소스 반영으로는 생기지 않는다. 없는 채로 compose 를 올리면 도커가 root 소유로 만들고,
# AIRFLOW_UID 로 도는 Airflow 가 그 안에 하위 디렉터리를 못 만들어 dag-processor 가
# FileNotFoundError 로 재시작을 반복한다. 컨테이너는 뜬 것처럼 보이므로 원인 찾기가 어렵다.
LOGS=$DEPLOY_ROOT/pipeline/logs
mkdir -p "$LOGS" 2>/dev/null || :
# 이미 root 소유로 만들어진 뒤라면 이 스크립트 권한으로는 못 고친다. 사람에게 넘긴다.
[ -w "$LOGS" ] || die "$LOGS 에 쓸 수 없다 ($(stat -c '%U:%G %a' "$LOGS" 2>/dev/null)) — sudo chown -R $(id -un):$(id -gn) $LOGS"

# 서비스가 healthy 가 될 때까지 기다린다. up -d 는 컨테이너를 만들면 바로 돌아오는데,
# Kafka 는 그 시점에 아직 리스너를 안 열었다. 곧바로 검증하면 항상 처음 한 번은 빨갛다.
#
# `docker compose up --wait` 를 쓰지 않는 이유는 datastore 에 한 번 돌고 끝나는
# init 컨테이너가 셋 있어서다. --wait 는 그것들의 정상 종료를 실패로 셀 수 있다.
wait_healthy() {
  local compose_args=$1; shift
  local deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
  local svc cid state
  for svc in "$@"; do
    while :; do
      # shellcheck disable=SC2086
      cid=$(docker compose $compose_args ps -q "$svc" 2>/dev/null || true)
      if [ -n "$cid" ]; then
        state=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)
        case $state in
          healthy|running) echo "  ok      $svc ($state)"; break ;;
          exited|dead)     die "$svc 가 $state 로 끝났다 — docker compose $compose_args logs $svc" ;;
        esac
      fi
      [ "$(date +%s)" -lt "$deadline" ] || die "$svc 가 ${HEALTH_TIMEOUT}s 안에 준비되지 않았다 — docker compose $compose_args logs $svc"
      sleep 5
    done
  done
}

# --- 1. 저장소 계층 ----------------------------------------------------------
# 네트워크 주인이라 항상 먼저다. init 컨테이너 셋은 매 up 마다 멱등하게 다시 돈다.
step "1/5  Kafka · MinIO"
docker compose -f datastore/compose.yaml up -d
wait_healthy "-f $DEPLOY_ROOT/datastore/compose.yaml" kafka minio

# --- 2. jar -----------------------------------------------------------------
# 이미지에 굽지 않고 마운트한다. 이미 받아둔 것은 건너뛰므로 두 번째 배포부터는 즉시 끝난다.
# 목록에 없는 옛 jar 가 남아 있으면 이 스크립트가 exit 1 로 배포를 세운다 — 클래스패스가
# 갈린 채로 뜨면 첫 Kafka 읽기에서 NoSuchMethodError 로 죽는다.
step "2/5  Spark 런타임 jar"
pipeline/spark/scripts/fetch-jars.sh

# --- 3. 이미지 ---------------------------------------------------------------
# 두 단계다. 파생 이미지가 기본 이미지를 FROM 하는데 컴포즈는 그 관계를 모른다.
step "3/5  이미지 (기본 → Spark 파생)"
pipeline/spark/scripts/build-image.sh

# --- 4. Airflow · Spark ------------------------------------------------------
# 컨테이너 수는 늘지 않는다. 오버레이는 Airflow 이미지를 JRE·pyspark 가 든 것으로 바꿀 뿐이다.
step "4/5  Airflow · Spark"
PIPELINE_COMPOSE="-f $DEPLOY_ROOT/pipeline/compose.yaml -f $DEPLOY_ROOT/pipeline/spark/compose.spark.yaml"
(
  cd "$DEPLOY_ROOT/pipeline"
  docker compose -f compose.yaml -f spark/compose.spark.yaml up -d
)
wait_healthy "$PIPELINE_COMPOSE" airflow-apiserver airflow-scheduler airflow-dag-processor

# --- 5. 검증 -----------------------------------------------------------------
# 컨테이너를 띄워야 하는 검증이라 CI 의 verify 스테이지가 못 한다. 여기가 그 자리다
# (.gitlab-ci.yml 머리말). 검증용 객체는 _verify/ 아래에만 만들고 끝나면 지운다.
if [ "$SKIP_VERIFY" = "1" ]; then
  step "5/5  검증 건너뜀 (SKIP_VERIFY=1)"
else
  step "5/5  datastore 검증"
  ./datastore/scripts/verify.sh
fi

step "배포 끝"
docker compose -f "$DEPLOY_ROOT/datastore/compose.yaml" ps
# shellcheck disable=SC2086
docker compose $PIPELINE_COMPOSE ps
echo
echo "Airflow UI 는 127.0.0.1 에만 열려 있다. 볼 때는 SSH 터널을 쓴다:"
echo "  ssh -i <pem> -N -L 127.0.0.1:8080:127.0.0.1:8080 ubuntu@<데이터 EC2>"
