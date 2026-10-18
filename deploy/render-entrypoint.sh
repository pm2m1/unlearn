#!/usr/bin/env bash
# Start FalkorDB on a unix socket (no TCP port) with the baked dump.rdb, wait until the graphs are loaded, then run
# the API on $PORT. With no TCP port, the host's port probe can't reach FalkorDB (it logged "Possible SECURITY ATTACK"
# each time it sent HTTP to 127.0.0.1:6379).
# If either process exits, the container exits, and the host restarts it.
set -euo pipefail

FALKOR_PASSWORD="${FALKOR_PASSWORD:-$(python -c 'import secrets; print(secrets.token_hex(16))')}"
export FALKOR_PASSWORD REDISCLI_AUTH="$FALKOR_PASSWORD"

# The password goes in on stdin, so it never shows in the process list.
# shellcheck disable=SC2086
printf 'requirepass %s\n' "$FALKOR_PASSWORD" | redis-server - \
  --port 0 --unixsocket "$FALKOR_SOCKET" --unixsocketperm 700 \
  --dir /app/falkordb-data --dbfilename dump.rdb --save "" --appendonly no \
  --loadmodule /opt/falkordb/falkordb.so ${FALKORDB_ARGS} &
REDIS_PID=$!  # the pipeline's last process: redis-server itself

for _ in $(seq 1 120); do  # PING answers LOADING until dump.rdb is in memory
  redis-cli -s "$FALKOR_SOCKET" ping 2>/dev/null | grep -q PONG && break
  sleep 0.5
done
redis-cli -s "$FALKOR_SOCKET" ping | grep -q PONG

uvicorn main:app --app-dir api --host 0.0.0.0 --port "${PORT:-10000}" &
API_PID=$!
stop() {  # the host's SIGTERM: stop the API first, then FalkorDB
  set +e
  kill -TERM "$API_PID" 2>/dev/null; wait "$API_PID"
  kill -TERM "$REDIS_PID" 2>/dev/null; wait "$REDIS_PID"
  exit 0
}
trap stop TERM INT
wait -n
exit 1
