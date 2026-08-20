#!/usr/bin/env bash
set -euo pipefail

if redis-cli ping >/dev/null 2>&1; then
  exit 0
fi

redis-server --daemonize yes
sleep 1
redis-cli ping >/dev/null 2>&1 || {
  echo "Redis failed to start" >&2
  exit 1
}
