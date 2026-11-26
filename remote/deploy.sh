#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$project_dir/.." && pwd -P)

usage() {
    cat <<'EOF'
Usage: ./deploy.sh {build|up|deploy|status|stdio|down}
  build   Build the image on this native LoongArch64 host.
  up      Start/reuse a persistent service using an already built local image.
  deploy  Build, then start the service (one-step deployment).
  status  Show service state and health.
  stdio   Attach a new MCP stdio session; workers outlive this connection.
  down    Remove only the service container; retain data, images and helpers.
Configuration: copy deploy.env.example to deploy.env, or set BCLA_* variables.
EOF
}

action=${1:-help}
case "$action" in
    help|-h|--help) usage; exit 0 ;;
    build|up|deploy|status|stdio|down) ;;
    *) usage >&2; exit 2 ;;
esac
[[ $# -eq 1 ]] || { usage >&2; exit 2; }
if [[ -f "$project_dir/deploy.env" ]]; then
    # shellcheck source=/dev/null
    source "$project_dir/deploy.env"
fi
BCLA_IMAGE=${BCLA_IMAGE:-bcla-remote:local}
BCLA_CONTAINER=${BCLA_CONTAINER:-bcla-remote}
[[ "$BCLA_CONTAINER" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || {
    echo 'Invalid BCLA_CONTAINER name' >&2; exit 2;
}
# Always address the daemon on THIS host. Inherited contexts must not redirect bind mounts.
docker_local() { docker --host unix:///var/run/docker.sock "$@"; }

check_host() {
    local platform
    platform=$(docker_local info --format '{{.OSType}}/{{.Architecture}}')
    case "$platform" in
        linux/loong64|linux/loongarch64) ;;
        *) echo "Expected native Linux/LoongArch64 Docker; got $platform" >&2; exit 1 ;;
    esac
}

build_image() {
    check_host
    local version revision=unknown options=()
    version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"].split("+")[0])' "$repo_root/.codex-plugin/plugin.json")
    if git -C "$repo_root" rev-parse --verify HEAD >/dev/null 2>&1; then
        revision=$(git -C "$repo_root" describe --always --dirty)
    fi
    options+=(--build-arg "BCLA_VERSION=$version" --build-arg "BCLA_REVISION=$revision")
    if [[ -n ${BCLA_BASE_IMAGE:-} ]]; then
        options+=(--build-arg "BASE_IMAGE=$BCLA_BASE_IMAGE")
    fi
    docker_local build "${options[@]}" --file "$project_dir/Dockerfile" --tag "$BCLA_IMAGE" "$repo_root"
}

check_owned() {
    local owner
    owner=$(docker_local inspect --format '{{index .Config.Labels "bcla-remote.managed"}}' "$BCLA_CONTAINER")
    [[ "$owner" == true ]] || { echo 'Refusing to operate on an unmanaged container' >&2; exit 1; }
}

start_service() {
    check_host
    local data_dir image_id image_platform signature existing_signature
    data_dir=$(realpath -m -- "${BCLA_DATA_DIR:-$HOME/.local/share/bcla}")
    case "$data_dir" in
        /|*,*|*$'\n'*) echo 'Choose a data directory other than /, without commas or newlines' >&2; exit 2 ;;
    esac
    mkdir -p -- "$data_dir"
    data_dir=$(cd -- "$data_dir" && pwd -P)
    image_platform=$(docker_local image inspect --format '{{.Os}}/{{.Architecture}}' "$BCLA_IMAGE")
    case "$image_platform" in
        linux/loong64|linux/loongarch64) ;;
        *) echo "Expected Linux/LoongArch64 service image; got $image_platform" >&2; exit 1 ;;
    esac
    image_id=$(docker_local image inspect --format '{{.Id}}' "$BCLA_IMAGE")
    signature=$(printf '%s\0' "$image_id" "$data_dir" | sha256sum)
    signature=${signature%% *}
    if docker_local inspect "$BCLA_CONTAINER" >/dev/null 2>&1; then
        check_owned
        existing_signature=$(docker_local inspect --format '{{index .Config.Labels "bcla-remote.config"}}' "$BCLA_CONTAINER")
        [[ "$signature" == "$existing_signature" ]] || {
            echo 'Service configuration/image changed. Finish active executions, then run down and up.' >&2
            exit 1
        }
        docker_local start "$BCLA_CONTAINER" >/dev/null
    else
        docker_local run --detach --init --pull=never \
            --name "$BCLA_CONTAINER" --restart unless-stopped \
            --label bcla-remote.managed=true --label "bcla-remote.config=$signature" \
            --ulimit nofile=1048576:1048576 \
            --mount "type=bind,source=$data_dir,target=$data_dir" \
            --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
            --env "BCLA_HOME=$data_dir" \
            "$BCLA_IMAGE" >/dev/null
    fi
    docker_local exec "$BCLA_CONTAINER" python3 /usr/local/bin/bcla-remote-healthcheck
    printf 'BCLA Remote ready: container=%s data=%s\n' "$BCLA_CONTAINER" "$data_dir"
}

case "$action" in
    build) build_image ;;
    up) start_service ;;
    deploy) build_image; start_service ;;
    status) docker_local inspect --format '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$BCLA_CONTAINER" ;;
    stdio) check_owned; exec docker --host unix:///var/run/docker.sock exec -i "$BCLA_CONTAINER" /usr/local/bin/bcla-remote-stdio ;;
    down) check_owned; docker_local rm --force "$BCLA_CONTAINER" ;;
esac
