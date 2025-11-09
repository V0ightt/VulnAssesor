#!/bin/sh
# wait-for-db.sh: wait for a PostgreSQL server to become available
# Usage: ./wait-for-db.sh host:port [timeout_seconds]

set -e

TARGET=${1:-db:5432}
TIMEOUT=${2:-60}

HOST=${TARGET%%:*}
PORT=${TARGET##*:}

echo "Waiting for PostgreSQL at $HOST:$PORT (timeout: ${TIMEOUT}s)"

while ! pg_isready -h "$HOST" -p "$PORT" >/dev/null 2>&1; do
  if [ "$TIMEOUT" -le 0 ]; then
    echo "Timed out waiting for PostgreSQL at $HOST:$PORT" >&2
    exit 1
  fi
  TIMEOUT=$((TIMEOUT - 1))
  sleep 1
done

echo "PostgreSQL is available at $HOST:$PORT"

