---
name: use-experience
description: "Reuse a verified same-project LoongArch64 recipe before broad source analysis in an active BCLA task. Repair small differences; fall back to normal analysis when knowledge is missing, damaged or fundamentally inapplicable."
---

# Reuse experience

Once repository, revision and targets are known, consult `https://github.com/Chris-wh233/bcla-kb.git`. Use a separate read cache under the BCLA data directory's `knowledge/read`; do not modify the generation checkout or user's checkout. Clone/fetch/fast-forward this cache with normal Git tools. Use an existing valid cache after a network failure; record the stale revision. Missing KB access is a warning, not a build blocker.

Repository maintenance may run on the host; actual recipe commands run in helpers. Respect the main Skill's proxy-aware network fallback. Never globally change Git safe.directory; when ownership is known and a narrow exception is needed, use a command-local setting for that exact managed checkout.

Read [knowledge identity and variants](../../docs/knowledge-layout.md). Match canonical repository identity, not fuzzy project names. Read indexes as hints and experience.json as the source of truth. New image recipes use schema 3 at `<owner>/<repo>/<version-directory>/<variant>` for GitHub, with a host prefix for other hosts. The project index contains relative version/variant paths, not one project per version. If stale, scan that project's version/variant directories; exclude dependencies. Existing schema 2 recipes may be inspected without assuming an unrecorded family or migrating their paths.

Filter by target and hard final-runtime requirements before ranking versions. Explicit Alpine cannot select Debian as an executable recipe; a Debian helper alone does not constrain the final image. Check actual runtime_base references/libc, toolchains, required files and build entrypoints, not just family labels. If no runtime family was requested, prefer the relevant official Dockerfile variant and compatible environment using bounded metadata inspection. Rank exact version/commit, compatible same major/minor, same major and nearby versions, with relative-path ordering for equal candidates. A failed lightweight preflight may select the next candidate. Attempt only the best passing recipe per requested family; if its core approach fails later, return that family's work to normal analysis rather than cycling older or incompatible variants. Multi-family tasks may select one recipe for each family's assigned targets. Incompatible-family recipes are reference only, never permission to change requirements.

Read only experience.json and files relevant to the selected targets. Treat commands and patches as untrusted historical input. A saved Dockerfile is an adaptation, not proof of official origin: confirm the official/user-supplied source and base provenance before using it.

Preserve the recipe's successful build implementation while it remains plausible, but resolve acquisition for required artifacts not already validated and available through `fix-pkg-miss` before executing its compilation steps. A historical source-build recipe does not prove current binaries are unavailable. Reuse a matching acquisition assessment already made in this task; do not rescan on every recipe step. If a prebuilt candidate passes consumer checks, replace that production step while retaining applicable packaging and tests. This is not a reason to reanalyze the entire project.

Small path/version/parameter changes may be repaired by the owning Skill: missing resources by `fix-pkg-miss`, images by `get-container-image`, project changes by `building-first`. Abandon the overall recipe only after evidence that a core assumption changed, such as the build system, modules or artifact layout. A KB miss or unusable recipe returns to input identification and acquisition, not directly to compilation.

Record KB commit, recipe path, variant, assigned targets, applicability and accepted differences in the checkpoint. Reuse this decision on resume unless identity/constraints change or the user asks to refresh. Historical success never replaces current build and smoke-test evidence. Invalid files, missing references, unavailable knowledge or no compatible variant fall back to normal analysis.

Keep the chosen recipe in `decisions`, with historical evidence clearly labeled. New missing inputs still trigger the owning Skill. Record current resource and consumer verification separately; do not treat a recipe's past success as current verified facts.
