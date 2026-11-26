#!/bin/sh
set -eu
: "${BCLA_HOME:?Set BCLA_HOME to the host data directory and mount it at the same absolute path}"
case "$BCLA_HOME" in
    /*) ;;
    *) echo 'BCLA_HOME must be absolute' >&2; exit 1 ;;
esac
test -d "$BCLA_HOME"
test -w "$BCLA_HOME"
test -S /var/run/docker.sock
exec "$@"
