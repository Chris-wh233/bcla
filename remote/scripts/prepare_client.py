#!/usr/bin/env python3
"""Optionally generate a fixed-host BCLA plugin wired to SSH stdio for this Codex profile."""

import argparse
import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from remote import ssh_command

PROJECT = Path(__file__).resolve().parents[1]
CORE = PROJECT.parent
sys.path.insert(0, str(CORE / "scripts"))
from install import copy_plugin

REMOTE_RULES = """
## Remote deployment

All task paths returned by BCLA tools belong to the remote host configured in
`bcla-remote.json`. Read [remote execution rules](../../docs/remote.md) before
filesystem, Docker, knowledge-base or export operations. Local skills/docs are
instructions; task data and execution stay remote.

"""


def prepare(host, container, output):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]*", host):
        raise ValueError("Use an SSH config alias or user@hostname, without options or whitespace")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container):
        raise ValueError("Invalid container name")
    output = Path(output).expanduser().resolve()
    if (output == CORE or output in CORE.parents
            or (output.is_relative_to(CORE) and not output.is_relative_to(PROJECT / "dist"))):
        raise ValueError("Choose an output outside core sources or under remote/dist")
    if output.exists():
        raise ValueError("Output already exists; choose a new output directory")
    copy_plugin(CORE, output)
    shutil.copy2(PROJECT / "scripts/remote.py", output / "scripts/remote.py")
    shutil.copy2(PROJECT / "docs/client.md", output / "docs/remote.md")
    revision = subprocess.run(["git", "-C", str(CORE), "describe", "--always", "--dirty"],
                              capture_output=True, text=True)
    connection = dict(host=host, container=container,
                      source_revision=revision.stdout.strip() if revision.returncode == 0 else "unknown")
    (output / "bcla-remote.json").write_text(json.dumps(connection, indent=2) + "\n")
    argv = ssh_command(host, container, ["/usr/local/bin/bcla-remote-stdio"])
    config = {"mcpServers": {"bcla": {"cwd": ".", "command": argv[0], "args": argv[1:], "tool_timeout_sec": 120}}}
    (output / ".mcp.json").write_text(json.dumps(config, indent=2) + "\n")
    manifest_path = output / ".codex-plugin/plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = manifest["version"].split("+")[0] + "+remote." + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S%f")
    manifest["description"] = "BCLA skills with a remote SSH stdio MCP service."
    manifest["interface"]["shortDescription"] = "LoongArch64 builds on a remote Docker host"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    for skill_path in sorted((output / "skills").glob("*/SKILL.md")):
        original = skill_path.read_text()
        end = original.index("\n---", 3) + len("\n---")
        skill_path.write_text(original[:end] + "\n" + REMOTE_RULES + original[end:])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="SSH config alias, recommended; configure port and identity in ~/.ssh/config")
    parser.add_argument("--container", default="bcla-remote")
    parser.add_argument("--output", default=str(PROJECT / "dist/bcla-remote"))
    args = parser.parse_args()
    output = prepare(args.host, args.container, args.output)
    print(f"Client plugin prepared: {output}\nNo plugin or MCP configuration has been installed/changed.\n"
          "Installing this client replaces bcla for the shared Codex profile; session-only SSH use needs no installation.")


if __name__ == "__main__":
    main()
