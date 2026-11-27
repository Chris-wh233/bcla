# Dockerfile adaptation and export

Use the exact official or user-supplied Dockerfile for the requested version and variant as the baseline. Preserve its stage structure/names, stage transfers, instruction order, variable names, comments, indentation and line wrapping wherever compatible with the accepted resource route. Do not reformat, regroup RUN commands or redesign stages for personal preference. Update comments made inaccurate by an adaptation.

Resource-first acquisition still applies, including to artifacts compiled by upstream stages. If `fix-pkg-miss` finds a compatible prebuilt output and the real consumer validates it, retain the producing stage and replace its compilation with acquisition of that output. Preserve the paths expected by later stages. Remove only now-unused source inputs, compiler packages and commands in that stage; do not retain them as decoration. Keep compilation in the stage when it remains the justified route.

For upstream downloads, package installs or context copies with no compatible LoongArch output, obtain the needed resource through `fix-pkg-miss`. A separately built or user-generated output may be copied locally into the corresponding stage. Preserve system-package installation when compatible packages exist. Do not turn package installation into arbitrary archive extraction without preserving required runtime files and setup.

Make broader changes only when concrete compatibility, functionality or export constraints require them. Record the reason and verification in existing task decisions/build definitions; no new gate is needed. A major change need not trigger user approval unless it changes the requested version, features or deliverables. Preserve the authentic baseline even when the successful adaptation differs substantially.

Apply [no-extra-checksums](../skills/no-extra-checksums/SKILL.md) to local and downloaded inputs. Retain applicable upstream Dockerfile/user-required checks, not extra task-added verification.

Before task success, compare the final Dockerfile against that baseline, remove trial-only commands and complete any intended formatting cleanup. Build and test using this exact final file and its actual arguments/inputs, then save it as accepted evidence. Later edits are not covered by an earlier build's success.

## Export with gen-maker

Compare the baseline, accepted Dockerfile and exported Dockerfile. Preserve justified adaptations, including stages that now download instead of compiling. Missing style similarity alone is not permission to reconstruct the build. Report unexplained substantial differences; do not silently redesign a completed task. If no reference template is available, skip style comparison and explain the limitation; this does not relax the build task's official/user Dockerfile requirement.

Choose exported artifact handling from its actual provenance, not its current cache location, extension, size or whether some release exists today:

- Artifacts actually obtained from authoritative upstream or configured `fix-pkg-miss` sources are downloaded inside the Dockerfile from their exact recorded sources, even if the accepted task used a local COPY. Preserve the corresponding stage, extraction, layout, permissions and consumer interface. Compatible system packages may keep their verified package-install route.
- Artifacts built separately during the task, including local CI outputs and architecture-independent outputs produced by the user on x86, are bundled and copied locally. Do not replace them with a newly discovered release or recreate their generation chain during export.
- Outputs already produced inside a retained Dockerfile stage remain stage-local builds/transfers. Upstream source-tree inputs can become pinned source downloads with the actual required patches applied inside that stage.
- Small adapted upstream support files may retain a pristine local baseline plus an actually consumed patch/preparation rule. Locally authored scripts/configuration remain local. Preserve required licenses. This is not permission to bundle unused originals, alternate files or cached remote distributions.

Java exception: bundle a verified post-replacement distribution for local COPY/ADD, keeping normal extraction/runtime setup. Omit the original distribution and replacement inputs/scripts/steps; replacement history remains in task records and `gen-experience`.

Use pinned versions/commits and verified download URLs. If the actual remote source cannot be reproduced without missing credentials, expired links or an unidentified asset, report the exact gap; do not silently relabel a download as a task-built artifact. Internal evidence hashes do not become build steps.

Only make export changes required for these provenance rules, flat context paths and actual build parameters. Static validation does not prove that a transformed Dockerfile has built successfully. Keep that distinction in the delivery response.
