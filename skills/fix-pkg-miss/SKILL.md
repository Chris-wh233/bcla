---
name: fix-pkg-miss
description: "Choose acquisition for a required non-image artifact not yet validated and available in BCLA, including the target project's own binary/distribution before any source build, and newly needed libraries/tools/generated output. Search configured LoongArch resources and CI before upstream/source fallback; no build failure is required."
---

# Missing resources

Use as soon as an identified required non-image artifact is not already validated and available, not only after a package-not-found error. The project's own binary/distribution is also a resource. An official Dockerfile compiling it or downloading another architecture does not bypass acquisition. Missing images belong to `get-container-image`; tracked project changes belong to `building-first` after acquisition is decided.

Read [the task protocol](../../docs/task-protocol.md) for recording and resumption. No work item, resource registration or Controller permission is required.

Before proposing source construction, read [source references](references/sources.md) and perform the applicable searches below. A KB miss, native-code classification, an upstream-only search or confidence that compilation is easy is not evidence that these sources lack a usable artifact. An existing source-build recipe supplies implementation guidance, not current availability evidence.

LuaJIT 2.1 on LoongArch64 is a configured special case. Apply the dedicated LuaJIT source rule in [source references](references/sources.md); do not substitute the generic upstream LuaJIT 2.1 source.

## Identify and search

Record the exact component/version, consumer, missing evidence, artifact format, architecture and libc/ABI. Distinguish native executables/libraries from architecture-independent data, static frontend files and pure Java archives. Inspect payloads before claiming independence.

Record the artifact, its consumer, acceptance criteria, source searches and return point in `resources`. The consumer may itself be a dependency. Preserve this evidence on resume so searches are not restarted unnecessarily.

Search in this order, recording URLs, results and why an inapplicable source was skipped:

1. Sources explicitly supplied by the user/task.
2. Compatible distribution packages.
3. The applicable LoongArch sources in [source references](references/sources.md), including `loongarch64-releases` under the missing component's own name.
4. Project ecosystem repositories, existing cross-architecture reusable outputs, and project-permitted compatible versions.
5. Authoritative upstream Release/download artifacts, last.

Stop searching when a candidate is validated for the real consumer; do not exhaust lower-priority sources needlessly. Before source fallback, account for each applicable preceding source and CI, distinguishing checked-and-absent, verified-incompatible, not-applicable and unreachable. Do not label an unqueried source absent. Persist the acquisition conclusion and cite execution or lookup evidence before compilation; the existing checkpoint is sufficient, without graph construction or a new registration tool.

Record whether each accepted output was downloaded, installed as a package, built inside a Dockerfile stage, built separately during the task, or supplied after external generation. Keep exact remote URLs/package identity or producing execution and consumer paths in existing resources. For Dockerfile changes, apply [Dockerfile guidelines](../../docs/dockerfile-guidelines.md): verified prebuilt outputs may replace compilation inside an existing stage without discarding that stage. This provenance also determines gen-maker download versus COPY behavior; a local cache path does not change a downloaded artifact's origin.

A fetch timeout is not "no matching release". Apply the main Skill's one-shot direct retry before recording a network blocker. Do not silently skip a required source and build from source. A source archive is not a prebuilt distribution package.

Validate candidate identity, version, format, architecture/libc, contents, provenance and real-consumer behavior. Verify published checksums/signatures when supplied; their absence alone is not a reason to reject. A locally computed hash identifies bytes, not publisher authentication.

If a real integration fails because of the candidate, record its URL/version/hash and rejection evidence, then try another independent source. Do not keep repackaging or patching that candidate. An unrelated project failure does not reject a good resource.

Establish attribution from the failing command and inspected artifact: for example, wrong ELF architecture, missing required exports, or incompatible ABI. An unspecific link failure alone does not establish that the candidate is defective; first distinguish consumer configuration from resource incompatibility.

## Existing CI without a matching asset

Inspect both Releases and CI in the matching `loongarch64-releases` repository. Lack of a release does not mean no solution exists.

Read `goal.options.release_ci_mode`, default `manual`:

- `manual`: save `WAITING_FOR_USER` with CI repository, exact version, expected output and validation. Tell the user how to produce it. On return, validate the supplied artifact or record that this CI cannot produce the requested version and move to source fallback.
- `auto`: inspect and fetch the CI into an isolated workspace, then invoke its `scripts/build_in_docker.sh` with the expected version. The host-side wrapper is permitted solely to orchestrate container builds; inspect its paths and arguments first. It must not compile/install dependencies on the host. Validate `dists/` contents. A failed CI candidate is rejected, not repeatedly repaired.

Do not trigger remote workflows or publish releases. CI mode is a task preference, not a code-enforced gate.

Manual CI waiting applies to the needed artifact even when it is native; it does not require proving architecture independence. However, if its parent has already been assigned to external generation, the native child is no longer needed for that route: wait for the parent output, not for its abandoned generator's CI.

## Native versus external generation

After existing resources are exhausted, inspect actual manifests, lockfiles and generator scripts. For frontend output, check transitive native modules, compiler/runtime requirements and known platform-specific downloads before running an install that may invoke native compilation.

Choose external generation when all are supported by evidence:

- The required output is architecture independent and no reusable copy is available.
- Native LoongArch generation would introduce substantial porting or a complex new dependency chain.
- A concrete mature-architecture producer, such as an upstream x86_64 GitHub Workflow, provides a materially simpler route.

Immediately save a wait with the exact output/version, producer, reason, accepted path/archive shape, completeness checks and resume point. Record that native generation is no longer the chosen route. Stop without first attempting that native chain. Resolving its generator dependencies is not a prerequisite to waiting.

This immediate pause takes precedence over completing searches for newly obsolete child dependencies. While the parent's external-generation conditions are still unproven, gather the applicable resource/CI and generator evidence; do not use an untested external alternative to skip needed searches.

Frontend files are not automatically external: simple, demonstrably compatible generation may run natively. Record why it is feasible. If a new native blocker appears, search that component in the required sources and reassess the parent; do not automatically expand into porting the toolchain. Do not pause merely because compilation takes time.

Native feasibility is provisional. Record what would invalidate it (for example, an unavailable generator plugin requiring a compiler port). At that point compare routes for the parent output again; do not confuse the generator's architecture with the output's. A native toolchain replacement needs output-equivalence evidence, not just a passing install command.

For a justified source fallback, use the authoritative revision in a separate dependency workspace and compatible helper. Build, inspect the output and test it in the original consumer. Preserve only required patches. Additional missing resources follow these same rules; record concise facts rather than creating a dependency state machine.

## Record and return

Update `resources` with searches, accepted/rejected candidates, source revision, produced output and execution references. Keep current choices in `decisions` and the next action in `checkpoint`. Reconcile finished commands using `execution_reviews`. For external generation, save expected input, reason, validation and resume point in `waiting`; preserve it until the supplied path is actually validated. Hand tracked-file changes to `building-first`, resume the original consumer and record its actual consuming test; producing the dependency alone does not prove integration.
