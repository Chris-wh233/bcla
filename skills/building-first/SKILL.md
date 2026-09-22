---
name: building-first
description: "Apply minimal project-owned source, build-script, architecture mapping or Dockerfile adaptations for an active BCLA build, after identifying the project-owned cause or a verified image/dependency mapping. Preserve requested version, features and real artifact behavior."
---

# Build first

The goal is a usable requested LoongArch64 artifact. Preserve user changes and fixed requirements. Work in the task's helper container and read [the task protocol](../../docs/task-protocol.md) for evidence storage.

This Skill chooses how to adapt, not whether to compile an artifact. Before introducing a build stage, replacing a binary download with compilation, or compiling a newly required native library, use `fix-pkg-miss` to establish acquisition with evidence. A wrong-architecture upstream archive alone is not a project defect requiring a source build. If the task already has a valid acquisition conclusion, reuse it; ordinary repairs on that chosen route do not require repeated searches. Verified image mappings and genuine project defects remain in scope.

1. Establish exact source revision, failure command and evidence. Locate the smallest project-owned cause. A known verified FROM replacement can be applied without deliberately reproducing an incompatible base.
2. Read relevant upstream mappings/configuration. Prefer an existing supported option, applicable upstream correction or narrow conditional over a broad refactor.
3. Record one hypothesis and modify only files needed for it. Do not upgrade the project, replace requested output, fake generated files, silently use another architecture, or disable required behavior.
4. Run the narrowest meaningful check, then the original consuming stage. Preserve the result and retained patch. Successful compilation does not establish runtime/image success.

Missing external non-image resources belong to `fix-pkg-miss`. Missing base/helper images belong to `get-container-image`. Apply their accepted resolutions when they require changing tracked files; do not duplicate their searches.

Dockerfile adaptation requires an actual official or user-supplied source, recorded with repository/URL, commit and path. Modify that file or a clearly derived copy. Never synthesize a new replacement to avoid finding the official file. Reinspect FROM and required inputs after changes; no tool permissions or work-item reset are needed.

Disable an optional component only when it is outside the user's requirements, demonstrably optional, and omission preserves basic functionality. Record the omission and its test evidence in the final result and experience.

When equivalent errors repeat, patches are repeatedly reverted, or new dependencies/unrelated adaptations accumulate, reassess. Change route only with a concrete simpler alternative satisfying the same targets. If no viable small adaptation remains, pause with reasons and the artifact/input that would permit continuation. Do not persist because of sunk effort.

Record accepted changes and execution references at milestones. Keep failed hypotheses in events, not in final recipes. Network transport failures follow the main Skill's proxy-aware retry; they are not evidence for source patches.

Record the hypothesis, issue and validation in the checkpoint and decisions, identifying the affected artifact. New missing inputs trigger the corresponding Skill and resource assessment. Reassess the parent route when adaptation introduces another toolchain or replaces a compiler/plugin. A substitution must preserve expected generated content and runtime behavior, with appropriate tests; a successful build alone is insufficient.

Save exact patches/configuration actually used by successful artifact generation before undoing temporary changes. Link them to the producing execution and artifact. Do not discard necessary reproduction steps just because the final workspace is restored. When returning to the consumer, record consumer verification separately from the producer's own checks.
