# Session-scoped BCLA Remote

Use these instructions when the user explicitly chooses this remote BCLA service for the current conversation. No local plugin installation, client generation or MCP registration is required. Other conversations can keep using local BCLA or another host. This routing is followed by the model; it is not a native per-conversation MCP configuration switch.

## Establish the selected service

Use the SSH connection selected by the user and the persistent service container (default `bcla-remote`). Establish SSH authentication through the available connection method; an SSH alias is convenient but not required. Do not save passwords in task records, source files or connection examples. Record the selected SSH host, container, remote BCLA_HOME and task ID in conversation working context so reconnects target the same service. A task ID alone is not a host locator.

Read the remote `/opt/bcla/skills/bcla/SKILL.md` and its required references/owning Skills through SSH/container reads. Read instructions from the remote service's version, not an unrelated local plugin cache. Project and resource decisions follow those shared Skills unchanged.

Every BCLA operation for this task must target this service. Do not call the locally registered bcla MCP tools, edit local .mcp.json, install a remote client, or open a local task store to simulate remote tools. Mentioning @BCLA does not rewire local tools. This instruction applies to subsequent use-experience, fix-pkg-miss, building-first, gen-experience and gen-maker operations for the remote task too.

## Call shared BCLA tools through SSH

The service provides `/usr/local/bin/bcla-remote-call`. It invokes the same Server dispatch as native MCP, in the same persistent service container. Discover the available tool names and JSON schemas first:

```sh
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote /usr/local/bin/bcla-remote-call --list'
```

For a tool call, supply one JSON argument object on stdin. For example, list tasks:

```sh
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote /usr/local/bin/bcla-remote-call task_open' <<'JSON'
{"action":"list"}
JSON
```

The result is the MCP tool result object; use structuredContent and inspect isError. Nonzero exit indicates an invocation/tool error, not necessarily failure of an earlier asynchronous workload. No raw MCP initialization/handshake is needed for this one-shot entry point. If a real conversation identity is available, pass --session-id to preserve create/list scoping. Otherwise a list can include all remote tasks: use conversation evidence or ask for an explicit remote task ID, never fabricate an identity or choose the newest global task.

Use task_open/task_context/checkpoint/read/file and environment/execution tools through this entry point. Long commands still use environment_exec and execution_read; do not replace them with long SSH shell builds. Keep request_key stable when recovering a lost response. Each call opens a new tool process, but records and detached workers live in the persistent service container and survive normal SSH disconnection. Before retrying UNKNOWN/TIMED_OUT or lost submissions inspect actual remote task/container state.

## Remote filesystem operations

All task paths are remote. For operations allowed outside helpers, execute commands through the same SSH/docker exec route. Examples:

```sh
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote printenv BCLA_HOME'
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote python3 /opt/bcla/scripts/image_tags.py library/debian'
```

KB read/sync/generation, indexes, Git commits, accepted evidence and default gen-maker exports belong to the remote BCLA_HOME. Follow project/version/runtime-family matching rules. Use remote scripts at /opt/bcla/scripts and remote Git identity. Do not interpret a remote path using local filesystem tools or copy host global configuration/credentials automatically. Export assembly and static checks may run in the service; project analysis, installs, modifications, compilation and tests still use task helpers through BCLA tools.

Distinguish a user-supplied local input from a remote existing artifact. Transfer local files into the actual remote workspace before validating them inside the task helper. Use SSH/docker exec tar streams for binary inputs or export downloads, not MCP JSON. If gen-maker output is requested on the local machine, assemble in a distinct remote export directory and transfer the result; do not mistake the local output path for a remote path. Report artifacts with host identity and full remote path.

Image archive export, registry push and helper cleanup remain explicit requests. Service container lifecycle is not task cleanup. Switching or reconnecting hosts never migrates tasks automatically. A switch to another host requires an explicit user choice and reestablishing the host/container/data-home/task tuple. Do not write a globally shared current-host configuration.
