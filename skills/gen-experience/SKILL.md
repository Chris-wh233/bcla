---
name: gen-experience
description: "On explicit user request, generate a verified reusable build recipe from a SUCCEEDED BCLA task's final accepted files and actual execution evidence. Save locally on knowledge-base main; never automatically publish."
---

# Generate experience

Run only on explicit user invocation after the selected task is `SUCCEEDED`. Select the task unambiguously. Read `task.result`, its accepted file references via `task_file(action=read)`, successful execution logs and immutable image evidence. The task store is a record, not a success certifier: verify evidence consistency.

If evidence is missing, recover only from actual task files matching recorded hashes, source commits or execution results. Never invent commands or reconstruct Dockerfiles from conversation. Report incomplete evidence without changing the completed task's status.

Use `result`, `resources`, `decisions` and accepted execution/file references; inspect actual successful consumer/test results. Historical node notes in older tasks can supply evidence references, but no graph is required. Exclude abandoned routes and rejected artifacts. Include temporary adaptations that actually produced accepted outputs even if later restored; use their captured patches/configuration, not only the final workspace diff. Pending execution reviews are a prompt to inspect evidence, not an automatic prohibition on recipe generation.

Read [the recipe format](references/recipe.md) before generating files.

Read [knowledge identity and variants](../../docs/knowledge-layout.md). Determine each accepted final image's actual runtime family from successful arguments, stage ancestry and environment evidence; never use the helper/builder image as the variant. If required base facts cannot be recovered, report incomplete evidence rather than guessing. Group targets by runtime family before writing recipes.

## Write locally

Use a dedicated `<BCLA_HOME>/knowledge/generation` checkout of `https://github.com/Chris-wh233/bcla-kb.git` on `main`. Clone if absent. If clean, fetch and fast-forward; never reset or force-update it. If the checkout contains another unfinished generation, use a task-local staging bundle until it is resolved. Host-side KB file/Git operations are allowed; recipe builds remain in helpers.

Generate schema 3 image recipes under `<owner>/<repo>/<version-directory>/<variant>` for GitHub; use a host prefix for other hosts. Follow the shared version normalization and family naming rules. Do not also create `github.com/<owner>/<repo>`, a version-level recipe/index, or one branch per task. Keep exact requested versions and runtime base references in metadata. Do not migrate existing recipes as part of generation.

Save only final successful facts: requested/resolved version, targets, nonsecret build environment and commands, consumed dependency provenance, exact final Dockerfiles, retained adaptations, immutable images and passing tests. Exclude trial steps, superseded patches, unused artifacts, regional proxies and ephemeral host/container identifiers.

For Java dependency replacements, record original/replacement Maven coordinates, sources, destination paths, actual preparation/repacking steps and successful consumer tests, not just the original distribution URL.

Within each family recipe include only its assigned targets and relevant successful evidence, while preserving necessary cross-image build relationships. For each target save the exact accepted Dockerfile and runtime_base metadata. For source adaptation save adaptation.md and patches/loongarch.patch, excluding separately stored Dockerfiles and incidental generated files. For each actually source-built dependency, create one flat `dependencies/<name>-<version>` recipe inside that variant, with dependency references rather than nested directories. Do not claim one variant covers every target of a multi-family task.

README must include critical prepared artifacts with consumers/acquisition methods, clean project artifact and final-image build flows (working directory, variables, actual commands), verified results and optional omissions. If the official Dockerfile builds the binary internally, describe that actual flow; do not fabricate a separate build step.

Run `python3 scripts/kb_index.py <checkout> --check` from the plugin root to validate BCLA recipes. Then run it without `--check` to rebuild derived indexes. It validates structural evidence and file hashes, not semantic reproducibility; inspect command/test evidence yourself. Historical foreign-schema recipes are preserved and indexed only if their basic identity is valid, without claiming validation.

Stage only the intended recipe and index files and commit locally on main. If identity is missing, leave files intact and report the path. Push only if explicitly authorized in the invocation or `goal.options.kb_publication=push-main`; never force-push. Default is local-commit. Network failure may leave a validated task-local bundle for later integration.

## Existing recipe

Compare before editing within the same repository/version/family identity. Different family directories coexist without merging. Identical data is a no-op. Merge complementary compatible targets only when existing verified facts remain intact and the complete recipe validates. Conflicting commands, changed commits behind a tag, normalized version collisions or competing outputs require a conflict report and separate task-local bundle; do not silently replace the old recipe or add a tag suffix to the family directory. Different Debian tags remain one debian identity and can still conflict.

Return task ID, every generated variant/recipe path, validation, local commit or pending state, and publication status. No automatic KB write happens during a build's success response.
