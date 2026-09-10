#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CONTAINER_NAME=${SUPABASE_DB_CONTAINER:-supabase_db_scam-radar-offline}

if [ -n "${DOCKER_BIN:-}" ]; then
    docker_bin=$DOCKER_BIN
elif command -v docker >/dev/null 2>&1; then
    docker_bin=$(command -v docker)
elif [ -x "/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/docker" ]; then
    docker_bin="/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/docker"
else
    echo "A Docker-compatible local container engine is required." >&2
    exit 1
fi

if ! "$docker_bin" inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    echo "Local Supabase is not running. Start it before make database-test." >&2
    exit 1
fi

"$docker_bin" exec -i "$CONTAINER_NAME" \
    psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
    < "$REPO_ROOT/supabase/tests/local_policy_contract.sql"
