---
name: bcla
description: "Start or resume BCLA LoongArch64 container builds in the current conversation when explicitly invoked with @BCLA, @bcla, or this plugin's qualified skill name. Skills and the model choose the build route; the task store saves facts without scheduling work."
---

# BCLA

Use the current Codex conversation and model. Codex owns the agent loop. There is no BCLA work-item scheduler, stop hook, child-resource gate, or automatic continuation daemon.

Read [the task protocol](../../docs/task-protocol.md) before creating or resuming a task. Tools come from this plugin's `bcla` MCP server. Use this plugin's sibling Skills.

## Enter or resume

Activate task execution only when explicitly requested. Ordinary conversation may read and discuss logs without continuing builds.

For a request to export a completed build as a standalone Makefile/Dockerfile project, read [gen-maker](../gen-maker/SKILL.md) and follow its export-only workflow before entering the build/resume steps below. Its default is the current conversation's most recently created task; that selection rule applies only to this export. Exporting does not resume the build, change task status or generate knowledge-base experience.

1. Read the selected task or list tasks for the actual session identity when available. Do not fabricate a thread ID. If multiple tasks could match, ask for the task ID; never silently select the newest global task.
2. For a new task, establish canonical repository, requested revision, target images/variants, user constraints and supplied Dockerfile/environment. Resolve ambiguity before costly work; persist with `task_open(action=create)`.
3. For a waiting task, read its wait contract first. Check that the user's supplied path exists and meets version, format, completeness and architecture requirements. A statement that an artifact exists is insufficient. Missing paths or invalid inputs leave the task waiting. Copy validated inputs into the task workspace; never clear the wait just because the user said "continue".
4. If the user reports that a recorded manual CI cannot produce the requested version, record that evidence and resume the source fallback under `fix-pkg-miss`. Do not repeat the same CI recommendation.
5. Resume interrupted commands by reading their execution records and container state. Do not rerun a still-running command or an UNKNOWN/TIMED_OUT execution without determining whether the container workload remains active.

## Decide acquisition before construction

A request to build an image specifies a deliverable, not permission to assume its binaries must be compiled. Once identity and required image inputs are known, read [fix-pkg-miss](../fix-pkg-miss/SKILL.md) and its [source references](../fix-pkg-miss/references/sources.md) for every required non-image artifact not already validated and available. This includes the project's own binary/distribution, even if its official Dockerfile contains a compile stage or downloads an amd64 archive. Do this before choosing a source-build route, adding compilation stages, or installing a compiler stack for that artifact. Lightweight inspection to identify inputs remains allowed; no deliberate failing build is needed.

The acquisition decision must have actual evidence: requested artifact/version and consumer constraints; applicable sources queried with URLs and results; accepted candidate or concrete rejection reasons; applicable CI result; chosen route and reason. Save this concise conclusion in the existing checkpoint. A plan to search or reading the Skill is not a completed search. Reuse current matching evidence on resume rather than searching again after every failure.

No KB recipe means no reusable recipe, not no available binary. An upstream amd64-only download means that candidate is unsuitable, not that LoongArch sources have none. A native ELF may already have a LoongArch build. Conversely, a loong64 filename does not prove Alpine/musl compatibility: inspect and test the candidate before accepting it, or record a specific incompatibility.

`fix-pkg-miss` owns the choice between existing resources, available CI, source fallback and external generation. `building-first` implements justified adaptations; it does not make that acquisition choice. When a new required library/tool/output appears, apply the same decision to that input before expanding the source build. Do not restart unrelated searches or discard already validated outputs.

Explicit user requirements to compile a particular artifact from modified/source code can rule out stock binaries for that artifact: record the requirement instead of performing a pointless release search. "Build the image", "use Alpine", a repository URL, or absence of a KB recipe are not such requirements. Third-party dependencies still follow resource-first acquisition. Completed tasks are not rebuilt merely to correct old search omissions.

## Decision checkpoints

These essentials apply even before a specialist Skill is loaded: reuse existing resources before source construction; search configured LoongArch sources before upstream artifacts; establish an official/user Dockerfile; preserve requested behavior; reassess expanding native generator chains instead of automatically porting them. The specialist Skills contain the source lists and procedures, not permission gates.

| Observed need | Read this plugin's sibling Skill before choosing the route |
| --- | --- |
| Known project/targets, before broad analysis | `use-experience` |
| Initial helper, different toolchain/libc, any external image | `get-container-image` |
| Required non-image artifact not yet validated/available, including the project's own binary | `fix-pkg-miss` and its source references, before source-route selection |
| Project-owned tracked source/build change | `building-first` |
| User requests recipe after verified completion | `gen-experience` |
| User requests a standalone Makefile/Dockerfile project after verified completion | `gen-maker` |

Skills are instructions to read and apply, not automatically invoked functions. Do not assume mentioning a Skill ran its search procedure. Reapply the same routing to dependencies discovered inside other dependencies. Optional proxy Skills remain optional.

These are situational routing rules, not Controller phases. The acquisition-before-construction rule above is not optional when its trigger applies:

- Before broad source analysis: use `use-experience` once identity and targets are known. Pass final-image family/libc constraints separately from helper-container choices; compatible knowledge is organized by project/version/runtime family. Record actual final runtime bases from successful build arguments and image evidence for later experience generation.
- Before project commands: use `get-container-image` to obtain a compatible helper. All project analysis, fetching, modifications, generation, compilation and tests run inside helpers. Host operations may handle task files, KB metadata, Docker lifecycle and input transfer.
- Find the official Dockerfile, including official cross-repository references, or use the user-supplied source. Record URL/repository, commit, path and exact original bytes. If no authoritative source can be established, ask the user and wait. Never invent a replacement Dockerfile.
- When adapting or finalizing a Dockerfile, apply [Dockerfile guidelines](../../docs/dockerfile-guidelines.md): preserve upstream stages and layout while allowing verified prebuilt resources to replace compilation inside the same stage.
- Inspect all final-image inputs, including project distribution archives and generated frontend files. Absence triggers `fix-pkg-miss` before automatically choosing source construction.
- Before using downloaded Java distributions, JARs or WARs, apply the [native-library check](../fix-pkg-miss/references/java-native.md), including nested JARs. Official download instructions and filenames without architecture classifiers do not exempt them.
- When a project involves LuaJIT 2.1, whether missing, bundled, or downloaded/compiled by existing build scripts, first read the [LuaJIT source rule](../fix-pkg-miss/references/sources.md#luajit-21) before choosing its acquisition or adaptation route. This applies even without a missing-package error.
- When failure belongs to tracked project source/build logic, use `building-first`. A verified FROM mapping may be applied before a failing build; do not deliberately run a known wrong-architecture base.
- Missing/incompatible images belong to `get-container-image`; confirmed missing non-image resources belong to `fix-pkg-miss`. Network errors are not package absence or source defects.
- State briefly which Skill is being used and why, then follow its actual instructions. Persist decisions after meaningful progress or before changing routes, not after every shell command.

Load a sibling Skill when its trigger becomes true, including when a new dependency appears inside a dependency build. The main model maintains context; there are no parent/child resource status requirements.

## Working memory

Use task-level records as working memory. Keep the goal stable except explicit user revisions or factual clarification, with a note explaining any change.

- On entry, resume or context loss, read `task_context` and needed full records before acting. Tool responses show the checkpoint, decisions, resources and pending execution interpretations.
- Save current progress, issue and next action in `checkpoint`; save route choices and reasons in `decisions`; save resource identity, consumer, searches, acceptance criteria and verification evidence in `resources`. Update at meaningful milestones and before route changes or handoff, not after every inspection.
- Interpret finished results with `execution_reviews` referencing execution IDs. Reading a log does not save its interpretation. Group routine inspections at the next checkpoint.
- Bundle a checkpoint into the next `environment_exec` when convenient. It commits with the execution reservation before launch. Avoid concurrent workspace modifications; reread and merge after a revision conflict.
- After obtaining an input, rerun its real consumer. A producer's own test does not establish consumer compatibility; record both results separately.
- On route changes, replace current decisions and mark obsolete resources clearly. Events retain the previous record. Do not report abandoned work as verified.
- Before pausing, record the expected input, reason, validation and resume point in `waiting`, and inspect outstanding commands. Task status does not terminate processes.

For older tasks, `task_open(get)` may contain historical node notes and `task_context` reports `legacy_notes_available`. Read those notes if present to recover useful evidence, then maintain current facts in the task-level fields. No node or path maintenance is required.

## Route changes and pauses

Record a current decision with its evidence and conditions for reconsidering it. If an architecture-independent artifact is assigned to external generation, immediately save `WAITING_FOR_USER` and stop the build. Do not first resolve its native generator dependencies, attempt native generation, mark the artifact unnecessary, or continue an image build requiring that artifact.

Reassess the affected artifact's route whenever a new native prerequisite, growing adaptation scope, or replacement compiler/plugin changes its cost or semantics. Compare existing resources, native generation, and a concrete external producer against the same acceptance criteria. Read `fix-pkg-miss` for the newly missing component; do not silently skip its configured sources or available CI. If evidence already establishes the external-generation conditions, pause immediately instead of resolving children just to finish a checklist. Native generation is allowed when supported by evidence; the label "frontend" alone determines neither route.

If saving a pause fails, report the persistence error and stop the current build activity. Preserve the intended wait contract in the user response. Storage failure is never evidence to change the technical route.

On repeated equivalent failures, compare new evidence and scope. Stop repeating commands without a changed hypothesis; reassess or pause with a concrete reason. No hard attempt count or wall-time budget is imposed by BCLA. User-provided limits still apply.

For transport errors, inspect effective HTTP/HTTPS/ALL proxy settings. If a proxy affected the failed destination, retry the same operation once with `direct=true` and any necessary command-local tool override. Keep TLS verification. Never change host/daemon/global configuration; a direct CLI retry cannot change a Docker daemon's own network route. Treat authorization, missing versions and checksums separately.

## Completion

When the user explicitly requests environment cleanup, resolve the task ID and call `environment_cleanup`. Never clean automatically after success, interruption or recipe generation. This stops any workloads in the registered task-owned helpers; adopted/user containers and direct docker-run containers are outside its scope. Report per-container failures or skips accurately and always show the returned workspace path, which is preserved. Cleanup does not change task completion status. To resume after cleanup, create and bootstrap a helper under a new environment name; use a new request_key for new commands.

Continue while useful work remains within the user's request. End on a real pause, cancellation, interruption or verified completion; BCLA does not force Codex to continue after a turn ends.

Before recording `SUCCEEDED`, compare the final Dockerfile with its recorded baseline using [Dockerfile guidelines](../../docs/dockerfile-guidelines.md). Complete cleanup before the final build/test; a later reformatted file is not covered by an earlier build. Verify every requested image exists, has immutable image ID/digest and Linux LoongArch64 architecture, and passes required startup/smoke tests without helper proxy overlays. Record any allowed optional omissions. A compilation exit code alone does not prove image success.

Save final Dockerfiles and retained patches with `task_file(action=save)` before writing the result. Reference successful execution IDs, input provenance, image identities and test evidence. Do not freeze the task against later factual corrections. The store records the model's status; it does not certify success.

Capture every modification actually used to produce an accepted artifact, including temporary generator/config changes, before restoring the source. Keep exact applied patch/config and its successful execution reference. A clean final Git diff cannot establish that the unmodified source produced the output. Final result should reference accepted resource, file and execution evidence, not copy the complete failed-attempt history.

After success, remind the user: `可使用 @BCLA $bcla:gen-experience 为本任务生成构建经验。` Never generate or publish experience automatically.

## Delegation

Use subagents only for bounded investigations that benefit from parallel work: locating official Dockerfiles, checking specified artifact sources, or analyzing one failure. Give them exact inputs and scope. They return evidence; the main agent merges task records and owns the build route. Avoid concurrent modifications of the same workspace.
