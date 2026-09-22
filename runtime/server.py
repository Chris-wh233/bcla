#!/usr/bin/env python3
"""Dependency-free JSON-lines MCP server, using the existing plugin's transport convention."""

import json
import sys
import traceback

from runtime import Runtime
from store import Store


def schema(properties, required=()):
    return dict(type="object", properties=properties, required=list(required), additionalProperties=False)


STRING = {"type": "string"}
OBJECT = {"type": "object"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
TASK = {"task_id": STRING}


TOOLS = [
    ("task_open", "Create, read, or list BCLA tasks. Never selects a task automatically.",
     schema(dict(action={"enum": ["create", "get", "list"]}, task_id=STRING, goal=OBJECT, session_id=STRING), ["action"])),
    ("task_checkpoint", "Save decisions with revision checking. execution_reviews maps finished execution IDs to interpretations. Other fields replace. No route or child-resource gate.",
     schema(dict(**TASK, expected_revision=INTEGER, changes=OBJECT, note=STRING), ["task_id", "expected_revision", "changes"])),
    ("task_context", "Read goal, checkpoint, decisions, resources and unreviewed execution reminders. No mutation or scheduling; use on resume and after context loss.",
     schema(TASK, ["task_id"])),
    ("task_read", "Read events, environment records, or execution summaries; no task mutation.",
     schema(dict(**TASK, kind={"enum": ["events", "environments", "executions"]}, after=INTEGER, limit=INTEGER), ["task_id", "kind"])),
    ("task_file", "Save exact final text as immutable content-addressed evidence, or read an existing accepted file.",
     schema(dict(**TASK, action={"enum": ["save", "read"]}, name=STRING, content=STRING, sha256=STRING), ["task_id", "action", "name"])),
    ("image_pull", "Start a recoverable asynchronous Docker pull for linux/loong64. Poll execution_read; image existence and source selection remain model responsibilities.",
     schema(dict(**TASK, image=STRING, request_key=STRING, checkpoint=OBJECT), ["task_id", "image", "request_key"])),
    ("environment_ensure", "Create/reuse a helper from a locally available LoongArch image. Mounts workspace and Docker socket, sets high nofile. Then call environment_bootstrap for new helpers. variables are transient exec overlays; never supply secrets.",
     schema(dict(**TASK, name=STRING, image=STRING, variables=OBJECT, container=STRING), ["task_id", "name", "image"])),
    ("environment_bootstrap", "Asynchronously install git, ca-certificates, curl, docker-cli only. Poll exit status before use. No daemon/buildx/compose packages.",
     schema(dict(**TASK, environment_id=STRING, request_key=STRING, direct=BOOLEAN), ["task_id", "environment_id", "request_key"])),
    ("environment_exec", "Run asynchronously with the task revision recorded. Optional checkpoint {expected_revision,changes,note} commits before launch. Reuse request_key to recover, new key to retry. No phase gates.",
     schema(dict(**TASK, environment_id=STRING, command=STRING, request_key=STRING, cwd=STRING,
                 variables=OBJECT, direct=BOOLEAN, timeout_seconds=INTEGER, checkpoint=OBJECT), ["task_id", "environment_id", "command", "request_key"])),
    ("execution_read", "Read execution status and bounded log bytes. A client timeout does not prove a container command stopped. offset and next_offset are byte offsets.",
     schema(dict(**TASK, execution_id=STRING, offset=INTEGER, limit=INTEGER), ["task_id", "execution_id"])),
]


class Server:
    def __init__(self, store=None):
        self.store = store or Store()
        self.runtime = Runtime(self.store)
        self.modern = False

    def call(self, name, args, session_id=None):
        result = self.dispatch(name, args, session_id)
        task_id = args.get("task_id") if isinstance(args, dict) else None
        if name == "task_open" and args.get("action") == "create":
            task_id = result["id"]
        if task_id and name != "task_context":
            result = dict(result, context=self.store.context(task_id))
        return result

    def dispatch(self, name, args, session_id=None):
        definitions = {item[0]: item[2] for item in TOOLS}
        if name not in definitions:
            raise ValueError("Unknown tool")
        definition = definitions[name]
        if not isinstance(args, dict) or set(args) - set(definition["properties"]):
            raise ValueError("Unknown arguments")
        if set(definition["required"]) - set(args):
            raise ValueError("Required arguments missing")
        args = dict(args)
        if name == "task_context":
            return self.store.context(**args)
        if name == "task_open":
            action = args.pop("action")
            if action == "create":
                return self.store.create(args["goal"], args.get("session_id") or session_id)
            if action == "get":
                return self.store.get(args["task_id"])
            if action == "list":
                return {"tasks": self.store.list(args.get("session_id") or session_id)}
            raise ValueError("Unknown action")
        if name == "task_checkpoint":
            return self.store.checkpoint(**args)
        if name == "task_read":
            kind = args.pop("kind")
            if kind == "events":
                return {"events": self.store.events(**args)}
            records = self.store.records(kind, args["task_id"])
            offset = max(0, args.get("after", 0))
            page = records[offset:offset + max(1, min(args.get("limit", 50), 200))]
            return {kind: [{k: v for k, v in r.items() if k not in {"argv", "variables"}} for r in page],
                    "next_offset": offset + len(page), "has_more": offset + len(page) < len(records)}
        if name == "task_file":
            if args["action"] == "save":
                return self.store.save_file(args["task_id"], args["name"], args["content"])
            if args["action"] != "read":
                raise ValueError("Unknown file action")
            import hashlib
            import re
            if not re.fullmatch(r"[0-9a-f]{64}", args.get("sha256", "")):
                raise ValueError("Invalid content hash")
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", args["name"]) or args["name"] in {".", ".."}:
                raise ValueError("Invalid filename")
            self.store.get(args["task_id"])
            path = self.store.directory(args["task_id"]) / "accepted" / args["sha256"] / args["name"]
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != args["sha256"]:
                raise ValueError("Accepted file hash mismatch")
            return {"content": content.decode(), "sha256": args["sha256"]}
        methods = {"image_pull": self.runtime.pull, "environment_ensure": self.runtime.ensure,
                   "environment_bootstrap": self.runtime.bootstrap, "environment_exec": self.runtime.execute,
                   "execution_read": self.runtime.poll}
        result = methods[name](**args)
        return {key: value for key, value in result.items() if key != "argv"}

    def handle(self, message):
        method, request_id = message.get("method"), message.get("id")
        params = message.get("params") or {}
        if request_id is None:
            return None
        if method == "initialize":
            version = params.get("protocolVersion")
            if version not in {"2024-11-05", "2025-03-26", "2025-06-18", "2026-07-28"}:
                version = "2025-06-18"
            result = dict(protocolVersion=version, capabilities={"tools": {}},
                          serverInfo={"name": "bcla", "version": "2.0.0"})
        elif method == "server/discover":
            self.modern = True
            result = dict(resultType="complete", supportedVersions=["2026-07-28"],
                          capabilities={"tools": {}}, ttlMs=0, cacheScope="private",
                          _meta={"io.modelcontextprotocol/serverInfo": {"name": "bcla", "version": "2.0.0"}})
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [dict(name=n, description=d, inputSchema=s) for n, d, s in TOOLS]}
            if self.modern:
                result.update(resultType="complete", ttlMs=0, cacheScope="private")
        elif method == "tools/call":
            try:
                payload = self.call(params["name"], params.get("arguments", params.get("input", {})),
                                    (params.get("_meta") or {}).get("threadId"))
                error = False
            except Exception as exc:
                payload, error = {"error": type(exc).__name__, "message": str(exc)}, True
                if not isinstance(exc, (ValueError, KeyError, FileNotFoundError)):
                    traceback.print_exc(file=sys.stderr)
            result = dict(content=[{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                          structuredContent=payload, isError=error)
            if self.modern:
                result["resultType"] = "complete"
        else:
            return dict(jsonrpc="2.0", id=request_id, error={"code": -32601, "message": "Method not found"})
        return dict(jsonrpc="2.0", id=request_id, result=result)

    def serve(self):
        for line in sys.stdin:
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Expected an object")
                result = self.handle(message)
            except (ValueError, TypeError, AttributeError) as exc:
                result = dict(jsonrpc="2.0", id=None, error={"code": -32700, "message": str(exc)})
            if result is not None:
                print(json.dumps(result), flush=True)


if __name__ == "__main__":
    Server().serve()
