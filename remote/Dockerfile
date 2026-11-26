ARG BASE_IMAGE=lcr.loongnix.cn/library/debian:forky@sha256:f5ef929388a56fb070c8c86cd572e70b0241f13a227c624c36260ef067f43d2b
FROM ${BASE_IMAGE}

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 ca-certificates curl git docker-cli ripgrep tar \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -c 'import sys; assert sys.version_info >= (3, 10), sys.version' \
    && docker --version

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOCKER_HOST=unix:///var/run/docker.sock \
    BCLA_DOCKER_BIN=/usr/bin/docker

WORKDIR /opt/bcla
COPY .codex-plugin/ ./.codex-plugin/
COPY .mcp.json README.md install.sh uninstall.sh ./
COPY runtime/ ./runtime/
COPY scripts/ ./scripts/
COPY skills/ ./skills/
COPY docs/ ./docs/
COPY tests/ ./tests/
COPY remote/container/entrypoint.sh /usr/local/bin/bcla-remote-entrypoint
COPY remote/container/stdio.sh /usr/local/bin/bcla-remote-stdio
COPY remote/container/healthcheck.py /usr/local/bin/bcla-remote-healthcheck
COPY remote/container/call.py /usr/local/bin/bcla-remote-call
COPY remote/docs/session.md /opt/bcla/docs/remote-session.md
RUN chmod 0755 /usr/local/bin/bcla-remote-*

ARG BCLA_REVISION=unknown
ARG BCLA_VERSION=2.0.0
LABEL org.opencontainers.image.title="BCLA Remote" \
      org.opencontainers.image.description="Shared BCLA stdio MCP runtime for a native LoongArch64 Docker host" \
      org.opencontainers.image.version="${BCLA_VERSION}" \
      org.opencontainers.image.revision="${BCLA_REVISION}"

HEALTHCHECK --interval=30s --timeout=15s --start-period=10s --retries=3 \
    CMD ["python3", "/usr/local/bin/bcla-remote-healthcheck"]
ENTRYPOINT ["/usr/local/bin/bcla-remote-entrypoint"]
CMD ["sleep", "infinity"]
