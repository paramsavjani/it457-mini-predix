#!/usr/bin/env bash
# Phase 3: switch a deployed VM from its local PostgreSQL container to RDS.
#
# Usage: deploy/use_rds.sh <ssh-host> <deployment-name> <rds-endpoint>
# The RDS master password must already be in /opt/mini-predix/.rds_password
# on the VM (mode 600), so it never appears in shell history or this repo.
set -euo pipefail

HOST="${1:?ssh host required}"
NAME="${2:?deployment name required}"
ENDPOINT="${3:?rds endpoint required}"

ssh "$HOST" bash -s -- "$NAME" "$ENDPOINT" <<'REMOTE'
set -euo pipefail
NAME="$1"; ENDPOINT="$2"
cd /opt/mini-predix
URL=$(python3 -c 'import sys, urllib.parse as u
pw = open(".rds_password").read().strip()
print(f"postgresql://predix:{u.quote(pw, safe=str())}@{sys.argv[1]}:5432/predix?sslmode=require")' "$ENDPOINT")
sed -i "/^RDS_DATABASE_URL=/d; /^DEPLOYMENT_NAME=/d" .env
printf 'RDS_DATABASE_URL=%s\nDEPLOYMENT_NAME=%s\n' "$URL" "$NAME" >> .env
chmod 600 .env

docker compose stop db
docker compose -f docker-compose.yml -f docker-compose.rds.yml up -d --build --remove-orphans
for i in $(seq 1 30); do
  if curl -fsS "http://localhost:8090/health" >/dev/null 2>&1; then
    echo "API healthy on RDS after ${i} checks"; exit 0
  fi
  sleep 2
done
docker compose logs --tail 40 api >&2
exit 1
REMOTE
