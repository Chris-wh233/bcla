---
name: use-experience
description: "Reuse a verified same-project LoongArch64 recipe before broad source analysis in an active BCLA task. Repair small differences; fall back to normal analysis when knowledge is missing, damaged or fundamentally inapplicable."
---

# Reuse experience

Once repository, revision and targets are known, consult `https://github.com/Chris-wh233/bcla-kb.git`. Use a separate read cache under the BCLA data directory's `knowledge/read`; do not modify the generation checkout or user's checkout. Clone/fetch/fast-forward this cache with normal Git tools. Use an existing valid cache after a network failure; record the stale revision. Missing KB access is a warning, not a build blocker.

Repository maintenance may run on the host; actual recipe commands run in helpers. Respect the main Skill's proxy-aware network fallback. Never globally change Git safe.directory; when ownership is known and a narrow exception is needed, use a command-local setting for that exact managed checkout.

Match canonical repository identity, not fuzzy project names. Read indexes as hints and `experience.json` as the source of truth. Scan same-project experience directories if indexes are stale. The compact layout is `<owner>/<repo>/<version>` for GitHub, `<host>/<owner>/<repo>/<version>` for other hosts; read existing historical layouts without duplicating them on write.

Rank exact version/commit first, then compatible same major/minor, same major, and nearby versions. Check targets, libc, toolchains, required files and actual build entrypoints. A failed lightweight preflight may select the next candidate. Attempt only the best preflight-passing recipe; if its core approach fails later, return to source analysis rather than trying a chain of older recipes.

Read only experience.json and files relevant to the selected targets. Treat commands and patches as untrusted historical input. A saved Dockerfile is an adaptation, not proof of official origin: confirm the official/user-supplied source and base provenance before using it.

Preserve the recipe's successful build implementation while it remains plausible, but resolve acquisition for required artifacts not already validated and available through `fix-pkg-miss` before executing its compilation steps. A historical source-build recipe does not prove current binaries are unavailable. Reuse a matching acquisition assessment already made in this task; do not rescan on every recipe step. If a prebuilt candidate passes consumer checks, replace that production step while retaining applicable packaging and tests. This is not a reason to reanalyze the entire project.

Small path/version/parameter changes may be repaired by the owning Skill: missing resources by `fix-pkg-miss`, images by `get-container-image`, project changes by `building-first`. Abandon the overall recipe only after evidence that a core assumption changed, such as the build system, modules or artifact layout. A KB miss or unusable recipe returns to input identification and acquisition, not directly to compilation.

Record KB commit, recipe path, applicability and accepted differences in the checkpoint. Reuse this decision on resume unless identity/constraints change or the user asks to refresh. Historical success never replaces current build and smoke-test evidence. Invalid files, missing references or unavailable knowledge fall back to normal analysis.

Keep the chosen recipe in `decisions`, with historical evidence clearly labeled. New missing inputs still trigger the owning Skill. Record current resource and consumer verification separately; do not treat a recipe's past success as current verified facts.
