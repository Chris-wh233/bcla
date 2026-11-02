# Makefile extensions

Use only the sections relevant to the exported project. Keep the basic variable names, proxy arguments, and opt-in latest behavior from `../assets/Makefile`. Examples use placeholder image identities; replace them from actual evidence.

## Adapted upstream small files

For a single-file adaptation, put these inputs at the project root:

- `entrypoint.sh.upstream`: exact original upstream file.
- `entrypoint.patch`: diff from that original to the accepted adapted file.
- `entrypoint.sh`: generated output consumed by `COPY` in the Dockerfile.

Extend the base Makefile with the following. Place default-goal selection before other targets; do not mark the generated file phony.

```makefile
.DEFAULT_GOAL := default
.PHONY: default image push prepare

prepare: entrypoint.sh

entrypoint.sh: entrypoint.sh.upstream entrypoint.patch
	@set -eu; \
	trap 'rm -f "$@.tmp"' EXIT HUP INT TERM; \
	patch --force --fuzz=0 --no-backup-if-mismatch --reject-file=- -o "$@.tmp" "$<" < entrypoint.patch; \
	chmod 0755 "$@.tmp"; \
	mv "$@.tmp" "$@"

image: prepare
```

This `image: prepare` declaration adds a prerequisite to the original `image` recipe; it does not replace the recipe. Set mode to the accepted file's mode, for example `0644` for configuration. One rule per generated file works for several inputs; split multi-file patches when doing so keeps the rules simple and faithful. If a required patch utility is absent, report/install it within existing authorization rather than silently copying an edited output.

The patched output starts from the baseline on every regeneration. Failed patching removes the temporary output and fails Make. `--force` keeps the patch direction fixed; `--batch` alone can automatically reverse an already-applied patch and is unsuitable here. Do not use `patch ... || true`, `--forward` to conceal a mismatch, a stamp detached from the real inputs, or two recipes racing to rewrite the same output. Include baseline and patch even if a validated generated output is also left in the project.

A source patch needed after a large source download inside a Dockerfile is a different case: bundle that patch and apply it in the relevant Dockerfile stage, retaining the accepted compile commands. Do not download the large source onto the host just to apply it in Make.

## Several final images

Use the following complete example when there are two actual final targets, `server` and `agent`. Fill defaults from evidence; the repository suffixes illustrate distinct latest tags, not a mandatory upstream naming convention. Prefer accepted per-target repositories when available. Include preparation prerequisites on **each** consuming target if small inputs are patched.

```makefile
REGISTRY	?=lcr.loongnix.cn
ORGANIZATION	?=example
REPOSITORY	?=product
TAG		?=1.2.3
LATEST		?=false

REPOSITORY_SERVER ?=$(REPOSITORY)-server
REPOSITORY_AGENT ?=$(REPOSITORY)-agent

IMAGE_SERVER=$(REGISTRY)/$(ORGANIZATION)/$(REPOSITORY_SERVER):$(TAG)
IMAGE_AGENT=$(REGISTRY)/$(ORGANIZATION)/$(REPOSITORY_AGENT):$(TAG)
LATEST_IMAGE_SERVER=$(REGISTRY)/$(ORGANIZATION)/$(REPOSITORY_SERVER):latest
LATEST_IMAGE_AGENT=$(REGISTRY)/$(ORGANIZATION)/$(REPOSITORY_AGENT):latest

.DEFAULT_GOAL := default
.PHONY: default image image-server image-agent push

default: image

image: image-server image-agent

image-server:
	docker build \
		--build-arg http_proxy=$(http_proxy) \
		--build-arg https_proxy=$(https_proxy) \
		-f Dockerfile.server \
		-t $(IMAGE_SERVER) \
		.

image-agent:
	docker build \
		--build-arg http_proxy=$(http_proxy) \
		--build-arg https_proxy=$(https_proxy) \
		-f Dockerfile.agent \
		-t $(IMAGE_AGENT) \
		.

push:
	docker push $(IMAGE_SERVER)
	docker push $(IMAGE_AGENT)
	#latest image
	@if [ "$(LATEST)" = "true" ]; then \
		set -e; \
		docker tag $(IMAGE_SERVER) $(LATEST_IMAGE_SERVER); \
		docker push $(LATEST_IMAGE_SERVER); \
		docker tag $(IMAGE_AGENT) $(LATEST_IMAGE_AGENT); \
		docker push $(LATEST_IMAGE_AGENT); \
	fi
```

Targets may instead have different versions, tags, build arguments, or recorded build ordering. Extend the mappings rather than forcing one shared version. If one final target consumes another final target's image, preserve the corresponding Make dependency and exact reference. Distinguish this from an upstream-documented intermediate image exported into an independent child project.

Ensure failures in a multi-command latest recipe propagate (as `set -e` does above); do not report success if an earlier tag/push failed. The original single-image template is preserved as supplied in the asset; this failure-propagation improvement may also be applied when generating from it.

## Independent intermediate-image projects

Only for an upstream-documented separate image that the task actually built:

```text
output/
  Dockerfile
  Makefile
  entrypoint.sh
  README.md
  base-image/
    Dockerfile
    Makefile
    native-runtime.tar.gz
    README.md
```

`base-image/Makefile` uses the same template and rules as the root, with its own image identity. The outer Makefile does not call `make -C base-image`, build its Dockerfile, or push its tags. Root `Dockerfile` uses the actual base-image tag. Document that users run `make -C base-image image` before `make image` when the base image is not already available. Each project publishes only through its own explicit `push` target.

Exclude `base-image/` from the root Docker build context when it is independent. Do not treat helper images, pulled images, or internal `FROM ... AS builder` stages as standalone projects just because they appear in the logs.
