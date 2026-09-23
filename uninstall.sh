#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 1 && ( "$1" == --help || "$1" == -h ) ]]; then
    printf '%s\n' \
        'Usage: uninstall.sh' \
        'Uninstall bcla@bcla-local and remove its Codex installation cache.' \
        'Keep the local marketplace, packages, task records, logs and knowledge base.' \
        'Run as the same user and with the same CODEX_HOME used for installation.'
    exit 0
fi
if [[ $# -ne 0 ]]; then
    printf '%s\n' 'Error: unexpected arguments. Use --help for usage.' >&2
    exit 2
fi
if ! command -v codex >/dev/null 2>&1; then
    printf '%s\n' 'Error: codex is not in PATH. Use the Codex CLI with plugin support.' >&2
    exit 1
fi

codex plugin remove bcla@bcla-local
printf '%s\n' \
    'BCLA uninstalled. Local marketplace, packages and build data were retained.' \
    'Start a new Codex session to stop loading the plugin.'
