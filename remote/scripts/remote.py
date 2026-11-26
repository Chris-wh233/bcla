#!/usr/bin/env python3
"""Forward explicit host-side maintenance/transfer commands to the service container."""

import json
import os
from pathlib import Path
import shlex
import sys


def ssh_command(host, container, command):
    return ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
            "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3", host,
            shlex.join(["docker", "--host", "unix:///var/run/docker.sock", "exec", "-i", container, *command])]


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 scripts/remote.py COMMAND [ARG ...]")
    config = json.loads((Path(__file__).resolve().parents[1] / "bcla-remote.json").read_text())
    argv = ssh_command(config["host"], config["container"], sys.argv[1:])
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
