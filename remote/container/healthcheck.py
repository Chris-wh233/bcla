#!/usr/bin/env python3
"""Check persistent storage, same-path bind mount, and the host Docker daemon."""

import json
import os
from pathlib import Path
import subprocess
import sys


def check():
    directory = Path(os.environ["BCLA_HOME"])
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ValueError("BCLA_HOME must be a canonical absolute path")
    if not directory.is_dir() or not os.access(directory, os.W_OK):
        raise ValueError("BCLA_HOME is not a writable directory")
    info = json.loads(subprocess.check_output(["docker", "info", "--format", "{{json .}}"], timeout=5))
    if info.get("OSType") != "linux" or info.get("Architecture") not in {"loong64", "loongarch64"}:
        raise ValueError("Expected a native Linux LoongArch64 Docker daemon")
    container = json.loads(subprocess.check_output(["docker", "inspect", os.environ["HOSTNAME"]], timeout=5))[0]
    if not any(m.get("Type") == "bind" and m.get("Source") == str(directory)
               and m.get("Destination") == str(directory) and m.get("RW")
               for m in container.get("Mounts", [])):
        raise ValueError("BCLA_HOME must be a writable host bind mount at the same absolute path")


if __name__ == "__main__":
    try:
        check()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
