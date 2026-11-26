#!/usr/bin/env python3
"""Validate BCLA recipes and rebuild derived indexes without altering recipes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse


def version_directory(version):
    if not isinstance(version, str) or not version:
        raise ValueError("Missing version")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", version)
    if name in {".", ".."}:
        raise ValueError("Invalid version directory")
    return name


def repository_directory(repository):
    url = urlparse(repository)
    parts = url.path.strip("/").removesuffix(".git").split("/")
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.port
            or len(parts) < 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", p)
                                   or p in {".", ".."} for p in parts)):
        raise ValueError("Invalid canonical HTTPS repository")
    return Path(*([] if url.hostname == "github.com" else [url.hostname]), *parts)


def recipe_directory(root, path, recipe):
    """Schema 3 image paths are rooted in repository identity, not file depth."""
    if recipe.get("schema_version") != 3 or recipe.get("producer") != "bcla":
        return path.parent.parent
    if recipe["kind"] == "dependency":
        parent = path.parents[2] / "experience.json"
        if path.parent.parent.name != "dependencies" or not parent.is_file():
            raise ValueError("Dependency recipes must be flat under an image variant's dependencies directory")
        return None
    project = root / repository_directory(recipe["repository"])
    expected = project / version_directory(recipe["requested_version"]) / recipe["variant"] / "experience.json"
    if path != expected:
        raise ValueError("Recipe directory does not match repository/version/variant")
    return project


def atomic_json(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate(path, recipe):
    if not isinstance(recipe, dict):
        raise ValueError("Recipe must be an object")
    url = urlparse(recipe.get("repository", ""))
    if not url.hostname or len(url.path.strip("/").split("/")) < 2:
        raise ValueError("Missing canonical repository identity")
    if not recipe.get("requested_version") or recipe.get("status") != "verified":
        raise ValueError("Missing version or verified status")
    if recipe.get("producer") != "bcla":
        return "historical_metadata_only"
    if recipe.get("schema_version") not in {2, 3} or not recipe.get("resolved_commit"):
        raise ValueError("Missing revision/schema")
    version_directory(recipe["requested_version"])
    for key in ("targets", "build", "tests", "files"):
        if not isinstance(recipe.get(key), list) or not recipe[key]:
            raise ValueError(f"Missing {key}")
    for build in recipe["build"]:
        if not all(build.get(key) for key in ("cwd", "command", "execution_id")):
            raise ValueError("Incomplete build command")
    for test in recipe["tests"]:
        if test.get("result") != "passed" or not test.get("command") or not test.get("execution_id"):
            raise ValueError("Missing passing test evidence")
    files = {}
    for entry in recipe["files"]:
        relative = Path(entry["path"])
        file = (path.parent / relative).resolve()
        if relative.is_absolute() or not file.is_relative_to(path.parent.resolve()) or not file.is_file():
            raise ValueError("Missing or escaping recipe file")
        if hashlib.sha256(file.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Hash mismatch: {relative}")
        files[entry["path"]] = file
    if recipe.get("kind") == "image":
        if recipe["schema_version"] == 3:
            variant = recipe.get("variant")
            if not isinstance(variant, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", variant):
                raise ValueError("Missing or invalid image variant")
        images = recipe.get("images", [])
        covered = set()
        for image in images:
            if (not image.get("id") or image.get("architecture") not in {"loong64", "loongarch64"}
                    or image.get("dockerfile") not in files or not image.get("source")):
                raise ValueError("Incomplete image evidence")
            covered.add(image["target"])
            if recipe["schema_version"] == 3:
                base = image.get("runtime_base")
                if (not isinstance(base, dict) or base.get("family") != variant
                        or not isinstance(base.get("reference"), str) or not base["reference"].strip()
                        or not isinstance(base.get("libc"), str) or not base["libc"].strip()):
                    raise ValueError("Runtime base must identify variant family, exact reference and libc")
        if not set(recipe["targets"]).issubset(covered):
            raise ValueError("Image targets not covered")
        if recipe["schema_version"] == 3 and (set(recipe["targets"]) != covered
                                             or len(covered) != len(images)
                                             or len(set(recipe["targets"])) != len(recipe["targets"])):
            raise ValueError("Variant targets must exactly match unique image targets")
    elif recipe.get("kind") == "dependency":
        if not recipe.get("artifacts"):
            raise ValueError("Missing dependency artifacts")
    else:
        raise ValueError("Invalid recipe kind")
    return "structure_and_hashes_valid"


def rebuild(root, check=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Knowledge checkout does not exist")
    projects, warnings, identities = {}, [], set()
    errors = []
    for path in sorted(root.rglob("experience.json")):
        if not path.resolve().is_relative_to(root):
            errors.append(f"{path}: symlink escapes checkout")
            continue
        if ".git" in path.relative_to(root).parts:
            continue
        recipe = None
        try:
            recipe = json.loads(path.read_text())
            validation = validate(path, recipe)
            project_directory = recipe_directory(root, path, recipe)
            if recipe.get("kind") == "dependency":
                continue
            identity = (recipe["repository"].rstrip("/").removesuffix(".git"),
                        recipe["requested_version"], recipe.get("variant"))
            if identity in identities:
                raise ValueError("Duplicate repository/version/variant identity")
            identities.add(identity)
            entry = dict(version=recipe["requested_version"], path=path.parent.relative_to(project_directory).as_posix(),
                         status=recipe["status"], targets=recipe.get("targets", []), validation=validation)
            if recipe.get("variant") is not None:
                entry["variant"] = recipe["variant"]
            project = projects.setdefault(project_directory, dict(schema_version=3, repository=recipe["repository"], experiences=[]))
            if project["repository"].rstrip("/").removesuffix(".git") != recipe["repository"].rstrip("/").removesuffix(".git"):
                raise ValueError("Conflicting repositories in one project directory")
            project["experiences"].append(entry)
        except (ValueError, TypeError, KeyError, OSError) as error:
            message = f"{path.relative_to(root)}: {error}"
            if isinstance(recipe, dict) and recipe.get("producer") == "bcla":
                errors.append(message)
            else:
                warnings.append(message)
    if errors:
        raise ValueError("\n".join(errors))
    if not check:
        for directory, project in projects.items():
            atomic_json(directory / "index.json", project)
        atomic_json(root / "index.json", dict(schema_version=3, projects=[
            dict(repository=project["repository"], path=str(directory.relative_to(root)))
            for directory, project in projects.items()]))
    return dict(projects=len(projects), warnings=warnings, checked_only=check)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(rebuild(args.checkout, args.check), ensure_ascii=False, indent=2))
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
