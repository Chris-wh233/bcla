# LoongArch resource sources

These are discovery endpoints, not assertions of current artifact availability. Query exact required versions and check platform/libc/ABI at use time.

## General binaries, native modules, libraries and distribution packages

1. `https://cloud.loongnix.cn/releases/loongarch64`
2. `https://github.com/loongarch64-releases`

Search the missing component, not only the top-level project. For example, search lightningcss itself and its locked version. Inspect both Releases and the CI repository. Directory names may differ from upstream naming; inspect archive content rather than rejecting on filename alone.

For `loongarch64-releases`, use the manual/auto behavior in the main Skill. The container wrapper is `scripts/build_in_docker.sh`; inspect its real interface and expect outputs under `dists/`. An absent exact-version Release is not proof that the repository's CI cannot produce it.

## LuaJIT 2.1

For a LoongArch64 LuaJIT 2.1 requirement, use `https://github.com/loongson/luajit2.git` branch `v2.1-agentzh-loongarch64`. This is the configured LoongArch adaptation source; do not replace it with the generic upstream LuaJIT 2.1 branch. Resolve and record the exact commit used, preserve the repository and branch as provenance, and validate the resulting library or executable in its real consumer. A compatible prebuilt artifact may still be reused after verifying that it provides the required LuaJIT 2.1 ABI and behavior.

## Node.js runtime

Check `https://unofficial-builds.nodejs.org/download/release/` for the exact version's Linux `loong64` archive. Do not assume every version or libc is supported. This source addresses Node itself; npm native modules still require their own general-source search above. Keep versions within project constraints and identify unofficial provenance accurately.

## Maven / Gradle

Check `https://maven.loongnix.cn/loongarch/maven/` for exact group/artifact/version/classifier. Inspect native payloads; ordinary JARs may be architecture independent. Also check the general release/CI sources before upstream Release fallback. Scope repository changes to the affected build or module, never global Maven/Gradle configuration. Tracked build-file edits use `building-first`.

## Python

For non-system wheels, check in order:

1. `https://lpypi.loongnix.cn/loongson/pypi/+simple`
2. `https://mirrors.loong64.com/pypi/simple`

Match Python implementation, version, ABI, LoongArch platform and libc tags. Download an exact compatible wheel; avoid broad permanent extra indexes. Verify imports and the real consumer. For `python-build-standalone`, also check `https://github.com/loong64/python-build-standalone`. Search applicable general CI sources before upstream fallback or source construction.

For all sources, verify published integrity metadata when available, but do not invent a mandatory publisher SHA-256 requirement. Record a local hash separately from publisher verification. Reject incompatible architecture artifacts; never silently substitute emulation or another project/version.
