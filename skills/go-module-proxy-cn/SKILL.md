---
name: go-module-proxy-cn
description: "Optionally set GOPROXY=https://goproxy.cn,direct for BCLA helpers about to run Go module commands, or after a concrete proxy.golang.org transport failure. Keep routing out of target images and knowledge recipes."
---

# Go module route

Apply when a helper will execute Go module operations, supported by go.mod/go.work or the actual build command. Merely copying a prebuilt Go executable does not trigger this Skill.

Add `GOPROXY=https://goproxy.cn,direct` to `environment_ensure.variables`. If the need appears later, pass it through `environment_exec.variables` for each relevant command and record the intended route in the checkpoint; no container replacement is required for a command-scoped overlay. Verify `go env GOPROXY` before using it. Do not run `go env -w`.

For a real transport error:

1. If a generic HTTP/HTTPS/ALL proxy affected the request, retry the same command once with `direct=true`, retaining the Go module route.
2. If reaching goproxy.cn still fails, or no generic proxy applied, retry once with command-scoped `GOPROXY=direct`, clearing the failed generic proxy as necessary.
3. If both routes fail, preserve the evidence and let the main Skill pause or choose a justified alternate resource. Do not cycle routes indefinitely.

The comma-separated fallback does not automatically handle every network error. Do not confuse transport failures with missing modules, invalid versions or checksum failures, and do not disable module integrity checks.

The overlay applies only to commands executing directly in helpers. Do not forward it into Docker build stages, project files, final image configuration or reusable recipes. If a target stage needs a fix, use `building-first` to evaluate a project-supported cache/vendor/configurable mechanism, preserving reproducibility without hard-coding the regional endpoint.

Validate final images without the overlay and exclude transient variables from accepted commands and experience. Removal of this optional Skill must not break the BCLA workflow.
