---
name: gen-maker
description: On user request, export a SUCCEEDED BCLA task into a flat, portable Dockerfile/Makefile project using accepted files and execution evidence. Supports multiple images, patches and separately supplied artifacts; defaults to the current conversation's most recently created task.
---

# Generate a flat build project

Produce a standalone build context from the selected BCLA task's actual successful path. Preserve its versions, LoongArch adaptations, features, image relationships, and runtime behavior. This exports a project; it does not generate a knowledge-base recipe or resume the original build.

## Select task and destination

Run on a user request to export a build project, including natural language routed here by BCLA. Do not automatically export at build completion. Use `@BCLA $bcla:gen-maker`, optionally with a task ID and output directory.

- An explicit task ID takes precedence. Otherwise select the current conversation's task; if several belong to this conversation, select the most recently created one, not the most recently updated or most recently successful one. Announce the selected task ID before exporting.
- Use the actual session identity with `task_open(action=list)` when available. Without MCP thread metadata, the list can include all tasks: verify session ownership using recorded session IDs or task creation evidence in this conversation. Never substitute the globally newest task or invent a session ID. If ownership or creation order cannot be established, ask for the task ID.
- Read the selected task and require `SUCCEEDED` with consistent final-image and successful build/test evidence. If it is unfinished or later findings invalidate its success, explain what must be completed first; do not silently choose an older task, resume a build, or change task status.
- Use the requested output directory, otherwise `<BCLA_HOME>/exports/<task-id>/` (`BCLA_HOME` defaults to `~/.local/share/bcla`). Keep it outside the task workspace and accepted-file storage. Inspect existing output before writing; identical contents may be reused, but preserve user edits and conflicting exports by using a new sibling directory and reporting its path.

## Recover the accepted build

- When available, discover BCLA's read tools: `task_open`, `task_context`, `task_read`, `execution_read`, and `task_file(action=read)`. Read the result, accepted Dockerfiles/file references, successful commands, logs, and test evidence. Follow recorded workspace/log paths rather than assuming a fixed task-store layout.
- If BCLA tools are unavailable, use persisted task metadata, accepted files and saved logs read-only; workspace contents alone do not establish task ownership or success. Distinguish accepted files from experiments: use recorded hashes, commits, build commands, image IDs, and successful consumer results. Do not reconstruct missing files from conversational recollection. A changed workspace file is not automatically the accepted one.
- Recover every delivered final-image target and the exact artifacts each consumes. Record provenance while working: source/commit or release URL, checksum, whether independently native-built, necessary patches, consumer, and destination path. Also identify upstream-documented intermediate images that this task actually built.
- Recover the successful invocation as well as the Dockerfile: context root, selected Dockerfile and target stage, platform, build arguments, named contexts and actual base-image references. Preserve required LCR overrides even when Dockerfile ARG defaults still name upstream images. Translate task-local paths into exported inputs; report unrecoverable external contexts or prerequisites. Exclude credentials and regional proxy settings.
- Use the task evidence directly; do not substitute an older knowledge-base recipe. Do not mutate task status, accepted evidence, source workspace, or knowledge base. Do not clean up task directories as part of this export.
- Resolve only missing essentials. If an accepted artifact, patch, or image relationship cannot be recovered, identify the precise gap; do not silently omit a target or claim the export is complete.

Export file assembly, evidence reads, artifact transfer, safe local preparation and static checks may run on the host. Keep the original workspace and accepted evidence read-only. Any separately requested compilation or real image build/test follows BCLA's helper-container rules. Recovering files from an existing image may use a temporary stopped container; remove only that export-created container afterward. Do not bootstrap or alter original helpers merely to export files.

## Decide what belongs in the project

Apply this table **in order**; origin takes precedence over size.

| Input actually needed by a Dockerfile | Placement |
| --- | --- |
| Independently native-built artifact, not built inside that Dockerfile, with no usable upstream LoongArch release | Include the actual accepted artifact in the project, regardless of size. |
| Small upstream inputs, such as entrypoint scripts, configuration, signing keys, and licenses | Include files in the project. Acquire the exact upstream revision, or copy a workspace file whose upstream identity is verified. |
| Large accepted inputs with a stable version/commit-specific download URL usable without local credentials, including third-party LoongArch releases and published architecture-independent outputs | Download with `curl` or `wget` **inside the Dockerfile**, even if the accepted BCLA Dockerfile used local `COPY`. Do not bundle the cached download. |
| Other externally supplied outputs without such a URL, including user-provided x86-generated frontend assets and local/private CI outputs | Include the exact accepted payload, regardless of size, with provenance and a local checksum. Do not introduce a new native generation step or depend on an expiring CI URL. |
| Artifact already built inside a retained Dockerfile stage | Keep that build and its stage-to-stage transfer; do not invent an external native-build prerequisite. |

- A native-built `.jar`, archive, library, or executable follows the first row when its provenance meets that row; filename extension alone cannot determine placement. Do not replace it with an incompatible upstream architecture or a new unverified source build.
- Include accepted task-authored small scripts/configuration with their actual origin when no upstream original exists; do not invent an upstream baseline or patch for an originally local file.
- Small versus large concerns practical context size: scripts/configuration are normally local; distributions and sizeable binary/source archives are normally remote. Use observed sizes and explicit user preferences for borderline cases instead of imposing an arbitrary universal byte cutoff.
- Copy the accepted native outputs from workspace/artifact locations or recover the exact consumed bytes from the recorded build environment/image if needed. Preserve executable modes, symlinks, and any required companion files. For a directory-shaped payload, a local archive is acceptable if extraction preserves paths/modes/links and the Dockerfile installs it at the original locations. Record its provenance and checksum; do not fabricate an upstream download URL.
- Use versioned releases or commit-pinned raw/source URLs. Verify new URLs refer to the correct artifact and target architecture. Do not upload native outputs to create a download route.
- Preserve existing checksum/signature verification and add a recorded expected checksum for downloads where available. A local hash is not publisher verification; absence of a published SHA-256 alone does not invalidate an accepted resource. Ensure required download/verification tools exist in their Dockerfile stages; remove temporary build-only tools or retain a download stage as appropriate. Never bake local proxy addresses or credentials into files.
- When the Dockerfile compiles the project from a local source tree, a pinned upstream source download in its build stage can replace that tree if it preserves the accepted build, including source patches. Do not remove native compilation merely to make the directory look flat.

## Lay out the project

Put `Makefile`, Dockerfile(s), small inputs, patch files, and external native-built artifacts at the project root. Use descriptive filename prefixes to avoid collisions; adjust `COPY`/`ADD` and install paths without changing runtime paths. Avoid copying an entire upstream checkout, BCLA workspace, logs, caches, or absolute host paths. Preserve licenses needed by included files.

For one final image, use `Dockerfile`. For multiple final images, include **all** of them as `Dockerfile.<target>` and give each a distinct output image reference based on the accepted target identity. A multi-stage builder stage is not itself another delivered final image.

Create a child project only for an intermediate image that meets **both** conditions:

1. Upstream explicitly describes it as a separate image dependency, for example a base image used by the final image.
2. This BCLA task actually built it.

Each such child directory has the same flat structure, its own Dockerfile(s), Makefile, dependencies, and patch handling. Its own Makefile handles its build/push, including any final-image variants it delivers. Do not add recursive child builds/pushes to the outer Makefile. Preserve the parent `FROM` reference to the intermediate image's generated tag and document the manual build order. Ordinary internal stages, helper containers, and merely pulled base images do not justify child projects. If needed, exclude independent child projects from the parent's build context with a targeted `.dockerignore`; never blanket-ignore bundled native artifacts.

## Generate the Makefile and patches

Start with [assets/Makefile](assets/Makefile), which preserves the user's original template. Fill `ORGANIZATION`, `REPOSITORY`, and `TAG` from the accepted image identity and user choices. Retain `REGISTRY ?= lcr.loongnix.cn`, `LATEST ?= false`, both proxy build arguments, `default: image`, and explicit `image`/`push` behavior. If identity is missing, resolve it before claiming the project is ready.

- `make` builds all final images owned by this Makefile; `make push` pushes every corresponding versioned tag. With `LATEST=true`, tag and push each corresponding `:latest`. Keep distinct repositories for targets that need distinct latest tags; never have two targets overwrite the same image reference. Pushing is a separate operation, not a build side effect.
- Keep the supplied template asset intact. In generated Makefiles, ensure shell blocks containing several tag/push commands propagate every failure, for example with `set -e` inside the latest block.
- Extend the template only for actual build needs: distinct `-f` options, verified build args, native-artifact extraction, preparation rules, or recorded network requirements. Do not carry task-specific proxy endpoints. Keep `.PHONY` declarations accurate and preserve the default goal when adding preparation rules.
- For an upstream small file that needs adaptation, include its exact **unmodified** baseline, the patch, and a Makefile rule that produces the adapted file consumed by the Dockerfile. Never distribute only a silently edited script. Recover a known upstream baseline and diff against the accepted adapted file; exclude unrelated workspace changes.
- Make patch rules repeatable: rebuild from the pristine baseline, track baseline/patch prerequisites, avoid repeated in-place patching, fail on mismatch, and publish the output only after success. Make every consuming image target depend on preparation, including under `make -j`. Include all required patches in the root. Internal source patches for source downloaded in a Dockerfile stage remain applied there; the host Makefile prepares bundled small files, not large remote source trees.
- Read [references/makefile-patterns.md](references/makefile-patterns.md) when adding patch rules or multiple final targets. It supplies dependency-safe preparation and multi-image extensions to the base template.

Add a concise generated-project README with task ID and evidence revision, required host architecture/tools, commands, complete image/tag mapping, child-project build order when applicable, bundled-artifact provenance/checksums, and which inputs are downloaded during image build. State what was actually verified. Bundling a native output reproduces image assembly, not that dependency's source build. With independent child projects, root `make` builds only the root project's images after the documented prerequisites; do not claim one command builds the entire hierarchy. This is project documentation, not a copy of BCLA trial logs.

## Validate and deliver

- Inspect every local `COPY`/`ADD` and other context input after renaming. Check file modes and required paths; no dependency may resolve outside the exported project. For necessary local `ADD` archives, preserve their extraction semantics.
- Verify remote-download substitutions preserve version, architecture, destination, extraction, permissions, and checksum/signature checks. Check all final targets and qualifying intermediate projects are present, with collision-free versioned/latest tags.
- Run safe local preparation when present; compare patched outputs with the accepted versions. Check that rebuilding from the baseline and repeating preparation work. Inspect `make -n image`, `make -n push`, and `make -n push LATEST=true` for each independent project without invoking Docker or recursive Make side effects. A dry run is not a build or a push test.
- Project generation alone does not authorize a real build or push test. If the user requests an actual build, test the exported context under that authorization. Never infer registry publication from the existence of a `push` target.
- Return the output directory, main files, included native artifacts and independent child projects if any, validation performed, and unresolved limitations. Separate evidence that the original BCLA build succeeded from checks performed on the exported project.
