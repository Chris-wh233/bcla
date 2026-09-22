# BCLA recipe format

Use `schema_version: 2`, `producer: "bcla"`, `kind: "image"` (or `"dependency"`), and `status: "verified"`.

Required facts:

- `repository`: canonical HTTPS repository URL; `requested_version`; `resolved_commit`.
- `targets`: nonempty target names.
- `build`: nonempty array of `{cwd, command, environment, execution_id}` for successful effective commands. Paths should use explained reproducible variables rather than ephemeral absolute task paths.
- `tests`: nonempty array of `{command, execution_id, result: "passed"}`.
- `files`: array of `{path, sha256}`, relative to this recipe; include final Dockerfiles, patches and explanatory files except experience.json itself.
- `images`: for image recipes, nonempty records with `target`, `id`, `architecture: "loong64"` or `"loongarch64"`, `dockerfile`, and `source` describing official/user provenance. Cover every requested target.
- `artifacts`: for dependency recipes, nonempty records with name, version, source, content identity and consumers. Native artifacts require verified architecture/ABI; architecture-independent artifacts require evidence of that classification.
- `dependencies`: existing resource provenance or relative references to flat dependency recipes.
- `applicability`: required files, build entrypoints, compatible targets and environment assumptions.
- `provenance`: task ID and checkpoint revision used for generation.

Do not present task-local execution IDs as universally resolvable URLs. They identify the local evidence; README and commands must carry sufficient information for another build.

Indexes are derived from metadata. They do not upgrade an old or damaged recipe to verified status. Publisher hashes are optional; `files.sha256` are locally calculated hashes for exact recipe file bytes.
