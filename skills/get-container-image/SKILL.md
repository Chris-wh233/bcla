---
name: get-container-image
description: "Choose and provision LoongArch64 helper, base, stage and runtime images for BCLA, including task startup without a supplied container and later incompatible toolchain/libc needs. Prefer verified lcr.loongnix.cn images; do not guess tags."
---

# Container images and helpers

Trigger when a helper is needed, a user-supplied environment needs validation, or a Dockerfile contains an external image reference. Read [the task protocol](../../docs/task-protocol.md) for tools and workspace paths.

## Choose from evidence

- Honor explicit user environment and variant constraints after checking architecture, libc, tool versions and workspace access. Do not silently replace them with defaults. An incompatible supplied environment requires explanation and clarification.
- For unknown projects, start with `lcr.loongnix.cn/library/debian:forky`, verifying its existence and architecture at use time.
- Prefer a matching dedicated language/toolchain image when the version requirement is known.
- Prefer `lcr.loongnix.cn/library/alpine:latest` for upstream Alpine or verified musl/static requirements. Do not force Debian when the requested variant is Alpine.
- RPM package installation alone may admit a small Debian conversion. For substantive RPM ecosystem dependence, consider `lcr.loongnix.cn/openeuler/openeuler:24.03-LTS-SP4` and verify it.

For LCR tag discovery, run `python3 scripts/image_tags.py library/golang` from the plugin root, substituting the required repository. This metadata query may run on the host even when a helper exists. The script follows all HTTP Link next-page URLs, deduplicates tags and returns complete/pages/count. A large requested page size does not guarantee a complete response: LCR may cap it at 50. An equivalent registry client must also exhaust pagination. A failed or partial query is unknown availability, not evidence that an image is absent. On proxy transport failure use the main Skill's scoped retry, with `--direct` for this script.

Evaluate the complete tag set before filtering or truncating output. Distinguish exact version pins from minimum/range requirements; compare numeric version components, not lexical order or a hardcoded list of minor releases. For example, a Go `go 1.26.6` directive is a minimum requirement; newer compatible toolchains are candidates unless other project/user constraints pin the version. Preserve libc and variant requirements and assess compatibility before choosing. Moving aliases such as latest are candidates too, but require checking the actual tool version and recording the resolved digest. Tag names alone do not prove compatibility.

Inspect candidate manifests and verify platform/tool versions before accepting them. Do not infer registry-wide absence from one missing exact tag or an incomplete listing, and do not switch to acquiring/building a toolchain until compatible listed images have been considered. Metadata inspection and Docker lifecycle commands may run on the host. Do not repeatedly guess tags from Docker Hub conventions. An exact default pull may establish its availability; after a not-found response, discover alternatives instead of guessing.

For every Dockerfile, inspect all stages with a proper parser/build frontend when available and read the source to resolve ARG defaults and actual arguments. Exclude scratch and earlier stage aliases, resolve external FROM and COPY --from sources, check platform overrides and base ONBUILD behavior where applicable. Missing ARG values must be resolved, not guessed. Record the mapping, digest and compatibility evidence.

## Provision

1. Pull the verified reference with `image_pull`; poll the execution to completion. User-supplied local images may skip pulling.
2. Select optional helper overlays from installed sibling Skills before `environment_ensure`. No overlay is a valid configuration. Do not depend on an optional Skill being installed.
3. Call `environment_ensure` with a stable name, local image reference and nonsecret runtime variables. The tool validates Linux LoongArch64, mounts the shared workspace at the identical absolute host path, attaches `/var/run/docker.sock` and sets `nofile=1048576:1048576`.
4. For newly created helpers call `environment_bootstrap`, then poll and inspect its actual result. It installs git, ca-certificates, curl and docker-cli; apt/apk helpers also receive ripgrep. Do not install a Docker daemon, compose or buildx by default. Missing baseline support is an environment problem, not a missing project artifact.
5. Verify required tool versions, workspace access and `docker version` server access when needed. A created container is not proof that bootstrap succeeded. Reuse compatible helpers; choose a distinct name/image for incompatible requirements.

All actual project commands run in helpers. Tools impose no phase restrictions, so inspection is always possible after a Dockerfile edit. A user-supplied running container can be adopted if it mounts the task workspace identically; do not bootstrap or modify its system configuration without user intent. Otherwise explain the required mount or create a helper from the user-specified image with agreement.

Docker socket builds use the host daemon. Bind mount source paths in sibling containers must be host-visible absolute workspace paths, not helper-only directories. Keep target build contexts under the task workspace. Final-image smoke containers use clean environments and do not receive the helper socket or overlays.

## Missing images and project changes

Use LCR, verified user-supplied images or locally built LoongArch images. Never silently pull another registry or emulate another architecture. Apply tracked Dockerfile/package-command changes through `building-first`, using the registered-by-record official/user source.

If an image is absent, reconstruct it from an actual public recipe/source and available LoongArch resources when reasonable. Resolve package requirements with `fix-pkg-miss`. If reconstruction is disproportionate or source is unavailable, save a wait with required image capabilities and validation. Validate a supplied image/archive before resuming.

Network failures follow the main Skill's scoped direct retry. Docker daemon fetch routes cannot be changed by clearing client variables; record that limitation without altering daemon settings. Record accepted tag/digest, platform, source, usage and tests. Verify output images contain no helper proxy configuration.

Record accepted helper/image identity, compatibility and consumer in `resources`, referencing the environment and execution IDs. After validation resume the consuming operation. Environment availability does not replace missing-resource searches or the required input of a task waiting for the user.
