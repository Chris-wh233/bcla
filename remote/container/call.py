#!/usr/bin/env python3
"""Call one existing BCLA tool inside the persistent remote service container."""

import argparse
import json
from pathlib import Path
import sys

# Support source-tree tests and the installed container entry point.
core = Path(__file__).resolve().parents[2]
if not (core / "runtime/server.py").is_file():
    core = Path("/opt/bcla")
sys.path.insert(0, str(core / "runtime"))
from server import Server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", nargs="?", help="BCLA tool name; read its JSON arguments from stdin")
    parser.add_argument("--list", action="store_true", help="List the service's actual tool schemas")
    parser.add_argument("--session-id", help="Actual conversation identity when available; never invent one")
    args = parser.parse_args()
    if bool(args.tool) == args.list:
        parser.error("Provide a tool name or --list")
    try:
        if args.list:
            message = dict(id=1, method="tools/list", params={})
        else:
            arguments = json.load(sys.stdin)
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object")
            params = dict(name=args.tool, arguments=arguments)
            if args.session_id:
                params["_meta"] = {"threadId": args.session_id}
            message = dict(id=1, method="tools/call", params=params)
        result = Server().handle(message)["result"]
    except (ValueError, OSError) as error:
        result = dict(isError=True, structuredContent={"error": type(error).__name__, "message": str(error)})
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 1 if result.get("isError") else 0


if __name__ == "__main__":
    sys.exit(main())
