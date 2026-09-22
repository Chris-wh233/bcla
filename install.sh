#!/usr/bin/env bash
set -euo pipefail

plugin_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Error: Python 3.10+ is required. Install python3 first.' >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    printf '%s\n' 'Error: Python 3.10+ is required.' >&2
    exit 1
fi

needs_codex=true
for argument in "$@"; do
    case "$argument" in
        --prepare-only|--help|-h) needs_codex=false ;;
    esac
done
if "$needs_codex" && ! command -v codex >/dev/null 2>&1; then
    printf '%s\n' 'Error: codex is not in PATH. Install the Codex CLI with plugin support first.' >&2
    exit 1
fi

exec python3 "$plugin_root/scripts/install.py" "$@"
