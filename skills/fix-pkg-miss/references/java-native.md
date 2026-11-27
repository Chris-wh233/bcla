# Java native-library check

## Scan before use

Check downloaded Java distributions, JARs and WARs before use, whether Maven, Gradle or prebuilt-only. Include official Dockerfile downloads and files without architecture classifiers. Reuse a recorded scan only for the same bytes and relevant runtime constraints.

Run the bundled Python standard-library tool inside a BCLA helper, transferring it there if needed. The script is [scan_java_native.py](../scripts/scan_java_native.py):

```sh
python3 /path/to/scan_java_native.py /workspace/distribution.tar.gz
python3 /path/to/scan_java_native.py /workspace/unpacked-distribution
```

It scans ZIP/JAR/WAR/EAR and TAR/gzip/xz/bzip2, including nested archives and loose `.so` / `.so.<numeric-version>` files, without extracting files. JSON findings report archive paths and readable ELF machine/class. Exit 0 means complete, even with native findings; exit 2 means incomplete. An empty result is not proof of application compatibility.

Defaults are depth 8, nested member 128 MiB, inspected payload 512 MiB and 100000 entries; see `--help` for overrides. Links are not followed. Review reported errors or limits before retrying; unpack unsupported formats in an isolated helper and scan the result. Use a bounded execution timeout: payload limits do not bound CPU or memory. Include additional Java artifacts fetched by the build/runtime.

## Interpret and replace

1. Identify each relevant library's containing JAR and actual consumer. Foreign-architecture libraries alone do not make a package unusable: it may also contain a compatible LoongArch64 library, or the library may be optional and never selected. Use ELF information when names are ambiguous; check 64-bit class, libc/ABI and loader selection, not just an architecture label.
2. For required native functionality without a compatible library, determine Maven group/artifact/version/classifier from embedded `META-INF/maven` metadata, POMs, manifests or the dependency tree. Search `https://maven.loongnix.cn/loongarch/maven/` for an exact-version replacement first.
3. Otherwise assess nearby repository versions or a newer upstream dependency supporting LoongArch64. Preserve the requested project version, explicit pins, Java/API/ABI requirements and companion dependency compatibility. Changes outside these constraints need user agreement.
4. Prefer replacing the complete dependency/classifier artifact rather than injecting a `.so`. Preserve signing/integrity requirements and executable/nested packaging; remove conflicting old copies and check the actual classpath. Scope repository configuration to the affected module/project; tracked-file changes use `building-first`.
5. If replacement fails, distinguish candidate incompatibility from loader configuration or unrelated failures. Return to `fix-pkg-miss` acquisition/CI/source/external-generation rules when no compatible candidate works, accounting for applicable configured sources before source fallback.

## Verify and record

Rescan changed archives and verify the consumer loads the intended dependency. Test application startup and the affected native feature, then run the normal final-image smoke tests. State any untested native paths; file replacement or `java -version` alone is not verification.

Save distribution identity/source, scan coverage/execution, original and replacement Maven coordinates/URLs, destination paths, actual replacement steps and consumer tests in existing `resources`/`decisions`. Keep the verified post-replacement distribution available for export.

`gen-experience` records the effective replacement process. `gen-maker` instead bundles the verified final distribution for local COPY/ADD, without the original distribution or replacement inputs/scripts/steps; see its export rules. Normal extraction/runtime setup remains necessary.
