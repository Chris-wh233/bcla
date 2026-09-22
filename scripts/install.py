#!/usr/bin/env python3
"""Prepare an immutable local marketplace package, then install via the Codex CLI."""

import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def prepare(source, home):
    source, home = Path(source).resolve(), Path(home).expanduser().resolve()
    if home.is_relative_to(source):
        raise ValueError("Package storage must be outside the source directory")
    packages = home / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    package = Path(tempfile.mkdtemp(prefix="bcla-", dir=packages))
    shutil.copytree(source, package, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv", "*.swp"))
    manifest_path = package / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = manifest["version"].split("+")[0] + "+codex." + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S%f")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    marketplace = home / "marketplace"
    plugins = marketplace / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    target = plugins / "bcla"
    if target.exists() and not target.is_symlink():
        raise ValueError("Existing marketplace plugin path is not a managed symlink")
    temporary = plugins / (".bcla-" + package.name)
    temporary.symlink_to(package, target_is_directory=True)
    os.replace(temporary, target)
    metadata_dir = marketplace / ".agents" / "plugins"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata = dict(name="bcla-local", interface={"displayName": "BCLA Local"}, plugins=[
        dict(name="bcla", source={"source": "local", "path": "./plugins/bcla"},
             policy={"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, category="Productivity")])
    path = metadata_dir / "marketplace.json"
    if path.exists() and json.loads(path.read_text()) != metadata:
        raise ValueError("Existing marketplace metadata differs; refusing to replace unrelated entries")
    path.write_text(json.dumps(metadata, indent=2) + "\n")
    return marketplace, package


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", default=os.environ.get("BCLA_HOME", "~/.local/share/bcla"))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    marketplace, package = prepare(Path(__file__).resolve().parents[1], args.home)
    print(f"Package: {package}\nMarketplace: {marketplace}", flush=True)
    if not args.prepare_only:
        subprocess.run(["codex", "plugin", "marketplace", "add", str(marketplace)], check=True)
        subprocess.run(["codex", "plugin", "add", "bcla@bcla-local"], check=True)
        print("Installed. Start a new Codex thread and invoke $bcla:bcla.")


if __name__ == "__main__":
    main()
