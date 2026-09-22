---
name: proxy-197
description: "Optionally configure the regional 10.2.10.197 HTTP proxy for BCLA helper container commands. Trigger when a helper is created; exclude target image stages, final images and smoke-test containers."
---

# Regional helper proxy

This optional Skill configures an execution overlay, not an image requirement. If removed, the rest of BCLA remains functional.

Before `environment_ensure`, provide these `variables` for task-owned helper containers:

```json
{
  "http_proxy": "http://10.2.10.197:7890",
  "https_proxy": "http://10.2.10.197:7890",
  "no_proxy": "localhost,127.0.0.1,cloud.loongnix.cn",
  "HTTP_PROXY": "http://10.2.10.197:7890",
  "HTTPS_PROXY": "http://10.2.10.197:7890",
  "NO_PROXY": "localhost,127.0.0.1,cloud.loongnix.cn"
}
```

Preserve these current source-Skill defaults; explicit user settings take precedence. Do not add ALL_PROXY or edit host/daemon, profiles, Git, package-manager or project configuration. Tools persist this overlay in the environment record and apply it to every `environment_exec`, including bootstrap. Direct external `docker exec` does not inherit it; use the helper tool.

Do not inject the overlay into Dockerfile ARG/ENV, build arguments/secrets, base images, target build stages or smoke-test containers. Use the isolated Docker client configuration provided by the execution tool; do not copy the host Docker proxy config into it. A Docker daemon's pull networking is separate.

On transport failures, the calling Skill checks the effective route and may retry once with `direct=true`; tool-specific proxy settings need scoped overrides. The generic fallback does not require this Skill.

Before success inspect final image environment, labels, relevant filesystem/startup files and final Dockerfiles for injected variables/endpoint. Test without helper overlays. Remove any introduced leak at its source and rebuild, rather than only unsetting it on startup. Exclude regional variables from accepted build commands, patches and knowledge recipes. Task-local diagnostic records may retain this nonsecret endpoint.
