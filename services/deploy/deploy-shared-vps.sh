#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

edge_network="mobius_edge"
data_volume="${MOBIUS_LAUNCH_VOLUME:-deploy_mobius_launch_data}"
git_sha="${MOBIUS_LAUNCH_GIT_SHA:-$(git -C ../.. rev-parse --short=12 HEAD 2>/dev/null || echo unknown)}"

if ! docker network inspect "$edge_network" >/dev/null 2>&1; then
  docker network create "$edge_network" >/dev/null
fi

if ! docker volume inspect "$data_volume" >/dev/null 2>&1; then
  docker volume create "$data_volume" >/dev/null
fi

MOBIUS_LAUNCH_GIT_SHA="$git_sha" \
MOBIUS_LAUNCH_DEPLOY_MODE="${MOBIUS_LAUNCH_DEPLOY_MODE:-shared-vps}" \
docker compose -f docker-compose.shared-vps.yml up -d --build

docker compose -f docker-compose.shared-vps.yml ps
