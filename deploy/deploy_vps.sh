#!/usr/bin/env bash
# Phase 2 (lift-and-shift): copy the committed code to a VM and start the
# same Docker Compose stack we run locally. Nothing in the app changes.
#
# Usage: deploy/deploy_vps.sh <ssh-host> <deployment-name> [port]
#   e.g. deploy/deploy_vps.sh admin-vps vps-mumbai-16gb 8090
set -euo pipefail

HOST="${1:?ssh host required}"
NAME="${2:?deployment name required}"
PORT="${3:-8090}"
DIR=/opt/mini-predix

cd "$(git rev-parse --show-toplevel)"
start=$(date +%s)

echo "==> uploading $(git rev-parse --short HEAD) to $HOST:$DIR"
git archive --format=tar HEAD | ssh "$HOST" "mkdir -p $DIR && tar -x -C $DIR --no-same-owner"

echo "==> configuring and starting containers"
ssh "$HOST" bash -s -- "$DIR" "$NAME" "$PORT" <<'REMOTE'
set -euo pipefail
DIR="$1"; NAME="$2"; PORT="$3"
cd "$DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
fi
sed -i "/^DEPLOYMENT_NAME=/d; /^API_PORT=/d" .env
printf 'DEPLOYMENT_NAME=%s\nAPI_PORT=%s\n' "$NAME" "$PORT" >> .env
docker compose up -d --build --quiet-pull
for i in $(seq 1 30); do
  if curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
    echo "healthy after ${i} checks"; exit 0
  fi
  sleep 2
done
echo "API did not become healthy" >&2
docker compose logs --tail 50 api >&2
exit 1
REMOTE

echo "==> deployed in $(( $(date +%s) - start ))s"
