# BCLA task protocol

`environment_cleanup(task_id)` is an explicit-user-request operation. The existing environments table is the cleanup inventory: newly ensured containers store their full container_id. The tool excludes adopted containers, checks the task label and image identity, stops/removes helpers by ID, and records cleaned_at/cleanup_status. Legacy records without IDs are resolved by exact name and verified before removal. Missing containers are treated as already absent; failures are reported per environment. No workspace, image or volume deletion is performed. The response includes workspace and workspace_preserved. Repeated cleanup is supported. Cleaned environments require a new name and bootstrap on resume.

All tools are supplied by `bcla`. They store facts or run commands and never select the next Skill. The model owns technical judgments and success verification.

## Task selection and checkpoints

Use `task_open(action=create, goal={...}, session_id=...)` to create. Include repository, requested version, target names and user constraints; resolve commit when fetched. Options may include `release_ci_mode` (manual/local-build, default manual) and `kb_publication` (local-commit/push-main, default local-commit). Omit unknown session identity rather than guessing.

Use `task_open(action=get, task_id=...)` for the current record. `task_open(action=list)` uses MCP thread metadata when supplied; otherwise it returns all tasks. Never assume a listed task belongs to the current conversation without matching evidence.

`task_checkpoint(task_id, expected_revision, changes, note)` is an atomic compare-and-save. Top-level fields replace previous values, except `execution_reviews` merges named reviews. Arrays replace previous values, not append. Reread and merge after REVISION_CONFLICT; do not blindly replay stale arrays.

Writable fields:

| Field | Meaning |
| --- | --- |
| goal | Repository, revision, targets, constraints, options |
| status | ACTIVE, WAITING_FOR_USER, PAUSED, SUCCEEDED, CANCELLED |
| checkpoint | Accomplishments, current problem, important executions, suggested next action |
| waiting | Need, reason, validation, resume_at; optional producer/location/version |
| decisions | Current choices with evidence and reconsideration conditions |
| resources | Concise searches, rejections, accepted artifacts and consumer evidence |
| build_definitions | Official/user source URL/commit/path and original/final file references |
| result | Final artifacts/images, tests, successful executions, accepted files, omissions |
| execution_reviews | Map of finished execution ID to nonempty interpretation text |

Goal changes require an explanatory note; reserve them for factual clarification or explicit user revisions. The store cannot verify user intent. Current progress and next action belong in checkpoint, choices in decisions, and resource acquisition/verification in resources.

No status transition requires dependency completion. A wait only requires its four descriptive fields. On valid resumption set status ACTIVE and waiting null together. Task status does not stop running processes; inspect and intentionally stop obsolete work before pausing if necessary. SUCCEEDED is the model's recorded conclusion, not a tool-certified state.

If storage fails, report the failure and preserve the intended checkpoint in the response. Do not change technical routes because recording them failed.

## Task working memory

`task_context(task_id)` returns goal, revision, status, checkpoint, decisions, resources, waiting, running executions and up to ten unreviewed results. Task-bound MCP responses include this context. Summaries are bounded and explicitly marked when truncated; use task_open(get) and task_read for full records and history.

Each execution captures the task revision at reservation. Interpret finished results with `execution_reviews={"exec-...":"Missing generator binary; reassess output generation"}` and update the relevant task fields in the same checkpoint. Reviews cannot reference another task or a running execution. A changed status/exit/end time makes a result unreviewed again. Reading logs alone does not acknowledge results. Exit zero does not certify artifact validity.

Older tasks retain historical nodes, paths and execution metadata as read-only reference data. No graph is generated, validated or maintained. Context reports `legacy_notes_available` when historical nodes exist; inspect task_open(get) to recover their facts before resuming. Save current conclusions in checkpoint/resources/decisions. Historical metadata and events are preserved on save; no bulk database migration is needed.

## Environments and execution

Use image_pull then execution_read until pull completion. environment_ensure expects a local image and creates/reuses a helper with same-path workspace mount, Docker socket and high nofile. Call environment_bootstrap for a new helper and verify completion before project commands. Supplied containers are adopted without package changes; they must be running and mount the task workspace read-write at its exact host path.

environment_exec accepts task_id, environment_id, command, request_key, optional cwd, variables, direct and timeout_seconds. The shell is `/bin/sh`. It returns immediately with an execution record. Poll execution_read with bounded byte offsets; keep meaningful updates to the user while waiting. Commands can continue across an MCP restart or model turn.

environment_exec and image_pull also accept optional `checkpoint={"expected_revision":N,"changes":{...},"note":"..."}`. The checkpoint and new execution reservation commit in one transaction before launching the process. Invalid updates/conflicts launch nothing. Reusing a request_key returns the original execution and does not reapply the bundled checkpoint. Use task_checkpoint separately for a new decision about an existing execution. If reservation succeeds but process launch is interrupted, recover the existing record and inspect actual processes rather than assuming no side effects.

Choose a stable request_key before submission. Reusing it returns the same execution, even if that execution failed. Use a new key only for an intentional new attempt; the same key with a different command is rejected. A STARTING execution without an eventual worker or an UNKNOWN/TIMED_OUT result needs process inspection, not blind resubmission. Killing the Docker client on timeout cannot guarantee the container process stopped.

Helpers receive nonsecret overlays on every tool-mediated exec. direct=true masks standard HTTP/HTTPS/ALL proxy variables for one command; it does not modify Git config or daemon routes. Tools do not automatically retry or interpret errors. No passwords/tokens in tool variables or command literals: execution records are local diagnostic data, not a secret store.

Project analysis, installs, edits, builds and tests use helper execution. Host operations may manage Docker, task/KB records and artifact transfer. The shared workspace is mounted at its host absolute path so nested Docker bind mounts address the same files. Do not use helper-only paths as host-daemon bind sources. Helper Docker client config is isolated from host proxy forwarding.

## Evidence and reads

task_read returns events (after is an event sequence number), environments or execution summaries (after is an offset; use next_offset). limit defaults to 50 records. execution_read returns log slices. These read tools are available during ordinary non-BCLA conversation too.

Use task_file(action=save, name, content) for exact UTF-8 final Dockerfiles, patches or small reports (up to 2 MB). It returns an immutable hash/path reference. Keep binaries and large assets in the workspace or explicit artifact storage and record their hash/path separately. Read saved content using task_file(action=read, name, sha256).

Before success, capture files actually used by the successful build, not a reconstructed approximation. Verify hashes against container workspace content when copying text. Record successful commands, test evidence and image IDs. gen-experience uses these facts and refuses to invent absent evidence.

Temporary generator changes must be saved before restoration if their outputs are accepted. Reference exact patch/config, producing execution, input commit and artifact in resources; include accepted file and execution references in the final result. A later clean checkout is not reproduction evidence. Before clearing waiting, validate the actual supplied artifact and save that evidence in resources, then return to its consumer. Persistence only checks record structure; these technical judgments belong to the model and Skills.

Data live at BCLA_HOME (default ~/.local/share/bcla). records.sqlite3 transactionally stores tasks/events/environments/executions; tasks/<id>/ contains workspace, accepted files, logs and a runtime lock. SQLite is an implementation detail for atomic persistence; it contains no work-item scheduler or dependency state machine. Retain the database and task directories together for backup.
