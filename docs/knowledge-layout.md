# Knowledge identity and variants

New recipes use schema_version 3. An image recipe's identity is canonical repository + exact requested version + runtime base family (`variant`). GitHub layout is `<owner>/<repo>/<version-directory>/<variant>/experience.json`; other hosts add `<host>/` before the complete repository path. Replace each character outside `[A-Za-z0-9._-]` in a version with `_`, retain the exact version in metadata, and reject `.`/`..`. A normalized path collision is a conflict, not permission to merge different versions.

```text
mysql/mysql-server/
  index.json
  8.4.0/
    debian/
      experience.json
      README.md
      Dockerfile
      dependencies/<name>-<version>/experience.json
    alpine/
      experience.json
      README.md
      Dockerfile
```

The version directory only groups variants. Do not create a version-level experience or index. KB README/adaptation documents remain part of the recipe format; gen-maker's minimal export rules do not apply to KB recipes.

## Determine the runtime family

Derive family from the actual accepted final image for each target, resolving FROM arguments using successful build arguments, stage inheritance, base-image inspect/distribution evidence and accepted source. Ignore helper containers and intermediate builder environments. Do not guess from a language/toolchain image's repository name: `golang:...-alpine` is alpine; a verified Debian-based Java runtime is debian. Use lowercase family identifiers matching `[a-z][a-z0-9-]*`, such as debian, alpine, openeuler, ubuntu, scratch or distroless. No registry, repository prefix, tag, digest, architecture or project version belongs in the identifier.

Use `scratch` for an actual final FROM scratch; do not label it after its builder. Classify distroless as distroless and record its actual underlying distribution/libc separately. For an opaque custom image, use verified distribution identity, not a guessed name. Missing evidence is an incomplete-generation gap, never an automatic debian/unknown variant.

Each image records `runtime_base={family, reference, libc}`. Reference is the exact effective external runtime base (or `scratch`); include its digest when known and distribution/version when verified. For final FROM of an internal stage, trace the stage chain to its runtime base. Libc is the verified libc or `none` for a genuinely libc-free image; FROM scratch alone does not establish absence of copied libc. An image ID/digest identifies output bytes, not automatically its base. The model verifies these facts; the indexer only validates metadata structure and consistency.

## Generation and conflicts

Group a successful task's final targets by family. Emit one independently complete recipe per family, containing only that family's targets, relevant successful commands/tests, Dockerfiles, files and dependencies. Preserve necessary cross-image build relationships and actual producing evidence even when they cross families; do not claim another variant's image belongs to this recipe. Evidence can reference the same successful task without copying irrelevant task history.

Dependencies remain flat inside each variant's `dependencies/`; dependency recipes use schema 3 and kind dependency, with their own upstream repository/version and artifact evidence. They do not need an image variant/runtime_base field and are not indexed as image candidates. Do not introduce cross-variant shared dependency storage.

Different families coexist. Within one family, identical recipes are a no-op; complementary compatible targets may merge while preserving all existing verified facts. Conflicting versions behind one normalized path, commits, commands or outputs require a conflict report and task-local staging bundle. Debian tag differences are metadata, not new variant directories: incompatible same-family recipes still conflict. Do not silently replace an existing recipe or manufacture a suffix to avoid the conflict.

## Indexes and selection

The global index points to project directories. One project index lists all versions/variants using paths relative to that project:

```json
{
  "schema_version": 3,
  "repository": "https://github.com/mysql/mysql-server",
  "experiences": [
    {"version": "8.4.0", "variant": "debian", "path": "8.4.0/debian", "status": "verified", "targets": ["server"]},
    {"version": "8.4.0", "variant": "alpine", "path": "8.4.0/alpine", "status": "verified", "targets": ["server"]}
  ]
}
```

Repository identity and hard target/runtime constraints filter candidates before version ranking. Explicit Alpine requirements exclude Debian as an executable recipe even if its version is closer. A supplied Debian helper alone is not a final-image constraint. Compare libc, exact base tag, distribution and toolchain assumptions from each experience.json; directory family alone never proves compatibility.

With no explicit runtime family, prefer the requested official Dockerfile variant and current environment compatibility. Do not perform broad source analysis merely to determine that preference; use known task/official metadata and bounded inspection. Then rank exact commit/version, compatible same major/minor, same major and nearby versions; break otherwise equal ties by project-relative recipe path. Record the chosen path, variant, KB commit and compatibility reasoning. Multi-family requests may select one recipe per requested family, each covering its assigned targets.

Lightweight preflight failure permits another candidate. After actually trying the best passing recipe for a family, failure of its core assumptions returns that family's work to normal analysis, not a sequence of older recipes or another family. Other-family knowledge can be labeled as reference, but cannot bypass explicit constraints. A missing/damaged index permits bounded scanning of `<version>/<variant>/experience.json` for that project; ignore dependency recipes. KB errors remain warnings with normal-analysis fallback.

Existing schema 2 recipes may still be validated/read at their original paths without inventing a variant or migrating them. Inspect their real environment before reuse; they cannot outrank a compatible explicit-family match merely because their family metadata is absent. New generation always uses schema 3. Migration of existing knowledge is a separate operation.
