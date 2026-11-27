#!/usr/bin/env python3
"""Report Linux native libraries in Java distributions without extracting files."""

import argparse
import io
import json
import os
from pathlib import Path
import re
import tarfile
import zipfile
import zlib


NATIVE = re.compile(r"\.so(?:\.[0-9]+)*$", re.IGNORECASE)
ZIP_SUFFIXES = (".jar", ".war", ".ear", ".zip")
TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")
UNSUPPORTED_SUFFIXES = (".7z", ".rar", ".zst", ".tzst")
MACHINES = {3: "x86", 8: "mips", 20: "ppc", 21: "ppc64", 40: "arm",
            62: "x86_64", 183: "aarch64", 243: "riscv", 258: "loongarch"}


class LimitReached(Exception):
    pass


def archive_kind(name):
    name = name.lower()
    if name.endswith(ZIP_SUFFIXES):
        return "zip"
    if name.endswith(TAR_SUFFIXES):
        return "tar"
    return None


def relevant(name):
    return NATIVE.search(name) or archive_kind(name) or name.lower().endswith(UNSUPPORTED_SUFFIXES)


class Scanner:
    def __init__(self, max_depth=8, max_member_bytes=128 * 1024 * 1024,
                 max_total_bytes=512 * 1024 * 1024, max_entries=100000):
        self.max_depth = max_depth
        self.max_member_bytes = max_member_bytes
        self.max_total_bytes = max_total_bytes
        self.max_entries = max_entries
        self.bytes_read = 0
        self.entries = 0
        self.archives = 0
        self.findings = []
        self.issues = []

    def issue(self, path, reason):
        self.issues.append({"path": path, "reason": str(reason)})

    def entry(self):
        self.entries += 1
        if self.entries > self.max_entries:
            raise LimitReached("entry limit exceeded")

    def read(self, stream, amount):
        if self.bytes_read + amount > self.max_total_bytes:
            raise LimitReached("total read limit exceeded")
        data = stream.read(amount)
        self.bytes_read += len(data)
        return data

    def library(self, stream, path):
        header = self.read(stream, 64)
        finding = {"path": path, "elf_machine": None, "architecture": "unknown"}
        if (len(header) >= 20 and header[:4] == b"\x7fELF"
                and header[4] in (1, 2) and header[5] in (1, 2)):
            machine = int.from_bytes(header[18:20], "little" if header[5] == 1 else "big")
            finding.update(elf_machine=machine, architecture=MACHINES.get(machine, "unknown"),
                           elf_class=32 if header[4] == 1 else 64)
        self.findings.append(finding)

    def member(self, stream, size, name, path, depth):
        if NATIVE.search(name):
            self.library(stream, path)
        elif archive_kind(name):
            if depth > self.max_depth:
                self.issue(path, "archive nesting limit exceeded")
            elif size > self.max_member_bytes:
                self.issue(path, "nested archive member size limit exceeded")
            else:
                data = self.read(stream, size + 1)
                if len(data) != size:
                    self.issue(path, "archive member size mismatch")
                else:
                    self.archive(io.BytesIO(data), name, path, depth)
        else:
            self.issue(path, "unsupported archive format; unpack separately and scan the result")

    def archive(self, source, name, path, depth):
        self.archives += 1
        try:
            if archive_kind(name) == "zip":
                with zipfile.ZipFile(source) as archive:
                    for info in archive.infolist():
                        self.entry()
                        if info.is_dir():
                            continue
                        child = path + "!/" + info.filename
                        if not relevant(info.filename):
                            continue
                        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                            self.issue(child, "archive link not followed")
                            continue
                        with archive.open(info) as stream:
                            self.member(stream, info.file_size, info.filename, child, depth + 1)
            else:
                kwargs = {"name": str(source)} if isinstance(source, Path) else {"fileobj": source}
                with tarfile.open(mode="r|*", **kwargs) as archive:
                    for info in archive:
                        self.entry()
                        if not relevant(info.name):
                            continue
                        child = path + "!/" + info.name
                        if not info.isfile():
                            self.issue(child, "archive link or special member not followed")
                            continue
                        with archive.extractfile(info) as stream:
                            self.member(stream, info.size, info.name, child, depth + 1)
        except (OSError, EOFError, ValueError, RuntimeError, NotImplementedError,
                zipfile.BadZipFile, tarfile.TarError, zlib.error) as error:
            self.issue(path, error)

    def file(self, path):
        self.entry()
        if path.is_symlink():
            self.issue(str(path), "filesystem link not followed")
        elif not path.is_file():
            self.issue(str(path), "input is missing or not a regular file")
        elif NATIVE.search(path.name):
            with path.open("rb") as stream:
                self.library(stream, str(path))
        elif archive_kind(path.name):
            self.archive(path, path.name, str(path), 0)
        else:
            self.issue(str(path), "unsupported input; supply a Java/ZIP/TAR archive or directory")

    def scan(self, paths):
        for value in paths:
            path = Path(value)
            try:
                if path.is_dir() and not path.is_symlink():
                    def walk_error(error):
                        self.issue(str(error.filename), error)

                    for directory, dirs, files in os.walk(path, onerror=walk_error, followlinks=False):
                        for name in dirs[:]:
                            self.entry()
                            child = Path(directory) / name
                            if child.is_symlink():
                                self.issue(str(child), "filesystem directory link not followed")
                                dirs.remove(name)
                        for name in files:
                            child = Path(directory) / name
                            if relevant(name):
                                self.file(child)
                            else:
                                self.entry()
                else:
                    self.file(path)
            except LimitReached as error:
                self.issue(str(path), error)
                break
            except (OSError, ValueError) as error:
                self.issue(str(path), error)
        return {"schema_version": 1, "complete": not self.issues,
                "archives_scanned": self.archives, "entries_checked": self.entries,
                "bytes_read": self.bytes_read, "native_libraries": self.findings,
                "issues": self.issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="archives or unpacked distribution directories")
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--max-member-mib", type=int, default=128)
    parser.add_argument("--max-total-mib", type=int, default=512)
    parser.add_argument("--max-entries", type=int, default=100000)
    args = parser.parse_args()
    if args.max_depth < 0 or min(args.max_member_mib, args.max_total_mib, args.max_entries) < 1:
        parser.error("limits must be positive; max-depth may be zero")
    report = Scanner(args.max_depth, args.max_member_mib * 1024 * 1024,
                     args.max_total_mib * 1024 * 1024, args.max_entries).scan(args.paths)
    print(json.dumps(report, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
