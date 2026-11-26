# Remote execution rules

These rules apply to the optional installed fixed-host client. Installing it changes the shared Codex profile's bcla endpoint; it is not a per-conversation switch. Session-only SSH usage instead reads /opt/bcla/docs/remote-session.md on the service and needs no client installation.

This client uses the persistent BCLA Remote service selected in `bcla-remote.json`. All task paths returned by tools belong to that SSH host, including workspace, accepted files, logs, knowledge caches and exports. A same-named local path is unrelated. Read packaged skills/docs locally as instructions; do not read or write remote task paths using local filesystem tools or a local SQLite connection.

Use the remote `bcla` MCP tools for task state, helper containers, project commands and accepted evidence. The core rules requiring project analysis, installs, edits, compilation and tests in helpers still apply. Only metadata/KB maintenance, Docker lifecycle, file transfer and export assembly/static checks may run in the service container.

For those operations, run `python3 scripts/remote.py COMMAND [ARG ...]` from this installed client plugin root. It forwards arguments through SSH to docker exec in the configured service, inheriting its BCLA_HOME. Prefer this wrapper to constructing a second connection. Remote core scripts live at `/opt/bcla/scripts/`; for example:

```sh
python3 scripts/remote.py printenv BCLA_HOME
python3 scripts/remote.py python3 /opt/bcla/scripts/image_tags.py library/debian
python3 scripts/remote.py python3 /opt/bcla/scripts/kb_index.py /REMOTE/BCLA_HOME/knowledge/generation --check
```

Knowledge read/sync/generation, Git commits and indexes belong to the remote BCLA_HOME and follow the same project/version/runtime-family rules. Use remote Git identity/configuration; do not copy local credentials or global configuration automatically. The locally installed kb_index.py is not permission to inspect a remote checkout using local paths. Read recorded evidence remotely if MCP tools are unavailable; never silently start the local runtime against another task store.

gen-maker uses remote task evidence and writes its default export under remote BCLA_HOME/exports/<task-id>. Perform file assembly and Make dry runs there. An explicitly requested local delivery directory needs a separately identified remote staging export followed by file transfer; never interpret that local directory as a remote path. Do not include the service/helper images as delivered intermediate-image projects unless the original export conditions actually apply.

Distinguish local supplied inputs from remote existing files. Upload a local artifact into the selected task's existing remote workspace before helper-side validation:

```sh
tar -C /LOCAL/INPUT -cf - artifact.tar.gz \
  | python3 scripts/remote.py tar -xf - -C /REMOTE/WORKSPACE
```

Download an accepted artifact or an assembled export with the reverse stream:

```sh
python3 scripts/remote.py tar -cf - -C /REMOTE/PARENT export-directory \
  | tar -xf - -C /LOCAL/DESTINATION
```

Use the actual reported paths, existing/appropriate destination directories, quoted arguments and exact desired filenames. Binary data belongs in a transfer stream, not MCP JSON. Upload completion does not validate version, architecture, ABI or completeness; follow the waiting contract inside the task helper before resuming.

Report remote artifact locations with the SSH host identity. Images belong to the remote Docker daemon; image archive export, registry push and environment cleanup remain explicit user-request operations. SSH disconnect or client timeout does not establish that a detached execution stopped. Reconnect and recover using task/execution IDs and request keys before retrying.

Client and service should come from the same BCLA source revision. Check the client's source_revision in bcla-remote.json against the service's OCI revision label when diagnosing a mismatch. A dirty/unknown revision is diagnostic information, not proof of identical source bytes. Update the service image and regenerate the client together when core tools/skills change. No runtime compatibility handshake is introduced.
