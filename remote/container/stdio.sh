#!/bin/sh
set -eu
# docker exec must run in the persistent service container: detached workers live here.
# Never emit banners on stdout; it carries JSON-lines MCP exclusively.
exec python3 -u /opt/bcla/runtime/server.py
