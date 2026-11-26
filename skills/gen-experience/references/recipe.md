# BCLA recipe format

Use `schema_version: 3`, `producer: "bcla"`, `kind: "image"` (or `"dependency"`), and `status: "verified"`. Read [knowledge identity and variants](../../../docs/knowledge-layout.md) for layout, runtime-family evidence, grouping and selection rules.

Required facts:

- `repository`: canonical HTTPS repository URL; `requested_version`; `resolved_commit`.
- `targets`: nonempty unique target names assigned to this recipe, not necessarily all targets of the originating task.
- `build`: nonempty array of `{cwd, command, environment, execution_id}` for successful effective commands. Paths should use explained reproducible variables rather than ephemeral absolute task paths.
- `tests`: nonempty array of `{command, execution_id, result: "passed"}`.
- `files`: array of `{path, sha256}`, relative to this recipe; include final Dockerfiles, patches and explanatory files except experience.json itself.
- `variant`: image recipes only, final runtime family such as debian/alpine/openeuler/scratch, matching the directory. No tag or registry prefix. Dependency recipes do not require this field.
- `images`: for image recipes, nonempty records with `target`, `id`, `architecture: "loong64"` or `"loongarch64"`, `dockerfile`, `source` describing official/user provenance, and `runtime_base: {family, reference, libc}`. Each family equals variant; reference is the exact effective runtime base, not the helper or overridden ARG default. Include digest and distribution/version when verified. Images must cover exactly the unique targets of this recipe; split other families into independent recipes.
- `artifacts`: for dependency recipes, nonempty records with name, version, source, content identity and consumers. Native artifacts require verified architecture/ABI; architecture-independent artifacts require evidence of that classification.
- `dependencies`: existing resource provenance or relative references to flat dependency recipes.
- `applicability`: required files, build entrypoints, compatible targets and environment assumptions.
- `provenance`: task ID and checkpoint revision used for generation.

Do not present task-local execution IDs as universally resolvable URLs. They identify the local evidence; README and commands must carry sufficient information for another build.

Indexes are derived from metadata. They do not upgrade an old or damaged recipe to verified status. Publisher hashes are optional; `files.sha256` are locally calculated hashes for exact recipe file bytes.

`scripts/kb_index.py` checks schema 3 paths and runtime-base metadata, builds one project-level index with version/variant paths, and excludes dependency recipes from image candidates. Schema 2 reading/validation remains available for existing knowledge; do not generate new schema 2 recipes or migrate old ones implicitly.
