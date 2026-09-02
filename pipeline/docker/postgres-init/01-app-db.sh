#!/usr/bin/env bash
# 앱 DB 와 전용 계정을 만든다. postgres 공식 이미지가 빈 볼륨을 처음 초기화할 때 한 번만 실행한다.
# 메타 DB(airflow) 와 앱 DB(trendin) 는 같은 인스턴스, 다른 DB · 다른 계정.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_db="$APP_DB_NAME" -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" <<'EOSQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';
CREATE DATABASE :"app_db" OWNER :"app_user";
EOSQL
