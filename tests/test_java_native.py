import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile


SCRIPT = (Path(__file__).resolve().parents[1] / "skills" / "fix-pkg-miss"
          / "scripts" / "scan_java_native.py")
sys.path.insert(0, str(SCRIPT.parent))
from scan_java_native import Scanner


def elf(machine, bits=2, byteorder="little"):
    data = bytearray(64)
    data[:4] = b"\x7fELF"
    data[4:6] = bytes((bits, 1 if byteorder == "little" else 2))
    data[18:20] = machine.to_bytes(2, byteorder)
    return bytes(data)


def jar(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class JavaNativeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_nested_war_jar_without_architecture_filename(self):
        path = self.write("app.war", jar({"WEB-INF/lib/library.jar": jar({
            "native/linux/libexample.so": elf(62),
            "native/loongarch64/libexample.so.1.2": elf(258),
            "Example.class": b"bytecode"})}))
        report = Scanner().scan([path])
        self.assertTrue(report["complete"])
        self.assertEqual(report["archives_scanned"], 2)
        self.assertEqual({r["architecture"] for r in report["native_libraries"]},
                         {"x86_64", "loongarch"})
        self.assertTrue(all("!/WEB-INF/lib/library.jar!/" in r["path"]
                            for r in report["native_libraries"]))
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_distribution_tar_and_loose_library(self):
        path = self.root / "distribution.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, data in {"lib/example.jar": jar({"lib.so": elf(258)}),
                               "lib/libextra.so.2": elf(183)}.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        report = Scanner().scan([path])
        self.assertTrue(report["complete"])
        self.assertEqual(report["archives_scanned"], 2)
        self.assertEqual(len(report["native_libraries"]), 2)

    def test_unpacked_directory_and_pure_java(self):
        self.write("lib/pure.jar", jar({"Example.class": b"class"}))
        self.write("native/lib.so", elf(258))
        self.write("README", b"not a library")
        report = Scanner().scan([self.root])
        self.assertTrue(report["complete"])
        self.assertEqual(len(report["native_libraries"]), 1)
        self.assertEqual(report["native_libraries"][0]["elf_class"], 64)

    def test_unknown_and_big_endian_elf(self):
        path = self.write("lib.jar", jar({"unknown.so": b"not ELF", "mystery.so": elf(65535),
                                         "ppc.so": elf(21, byteorder="big")}))
        findings = Scanner().scan([path])["native_libraries"]
        self.assertEqual([r["architecture"] for r in findings], ["unknown", "unknown", "ppc64"])
        self.assertEqual(findings[1]["elf_machine"], 65535)

    def test_depth_limit_marks_incomplete(self):
        path = self.write("app.jar", jar({"nested.jar": jar({"library.so": elf(62)})}))
        report = Scanner(max_depth=0).scan([path])
        self.assertFalse(report["complete"])
        self.assertIn("nesting limit", report["issues"][0]["reason"])
        self.assertFalse(report["native_libraries"])

    def test_size_budget_rejects_nested_member_before_read(self):
        path = self.write("app.jar", jar({"nested.jar": jar({"library.so": elf(62)})}))
        report = Scanner(max_member_bytes=1).scan([path])
        self.assertFalse(report["complete"])
        self.assertEqual(report["bytes_read"], 0)
        self.assertIn("member size limit", report["issues"][0]["reason"])

    def test_total_budget_and_entry_budget(self):
        path = self.write("app.jar", jar({"one.so": elf(62), "two.so": elf(258)}))
        for scanner, message in ((Scanner(max_total_bytes=64), "total read"),
                                 (Scanner(max_entries=2), "entry limit")):
            with self.subTest(message=message):
                report = scanner.scan([path])
                self.assertFalse(report["complete"])
                self.assertIn(message, report["issues"][0]["reason"])
                self.assertEqual(len(report["native_libraries"]), 1)

    def test_corrupt_nested_archive_is_not_clean(self):
        path = self.write("app.jar", jar({"broken.jar": b"broken", "ok.so": elf(258)}))
        report = Scanner().scan([path])
        self.assertFalse(report["complete"])
        self.assertIn("!/broken.jar", report["issues"][0]["path"])
        self.assertEqual(len(report["native_libraries"]), 1)

    def test_unsupported_nested_archive_is_not_clean(self):
        path = self.write("app.jar", jar({"resources.tar.zst": b"compressed data"}))
        report = Scanner().scan([path])
        self.assertFalse(report["complete"])
        self.assertIn("unsupported archive", report["issues"][0]["reason"])

    def test_unsupported_zip_compression_reports_incomplete(self):
        data = bytearray(jar({"native.so": elf(62)}))
        data[8:10] = (99).to_bytes(2, "little")
        central = data.index(b"PK\x01\x02")
        data[central + 10:central + 12] = (99).to_bytes(2, "little")
        path = self.write("app.jar", data)
        report = Scanner().scan([path])
        self.assertFalse(report["complete"])
        self.assertFalse(report["native_libraries"])

    def test_pure_java_archive_has_no_native_findings(self):
        path = self.write("pure.jar", jar({"Example.class": b"class", "META-INF/MANIFEST.MF": b""}))
        report = Scanner().scan([path])
        self.assertTrue(report["complete"])
        self.assertEqual(report["archives_scanned"], 1)
        self.assertFalse(report["native_libraries"])

    def test_tar_and_zip_links_not_followed(self):
        path = self.root / "links.tar"
        with tarfile.open(path, "w") as archive:
            info = tarfile.TarInfo("native.so")
            info.type = tarfile.SYMTYPE
            info.linkname = "/outside/library.so"
            archive.addfile(info)
        self.assertFalse(Scanner().scan([path])["complete"])
        path = self.root / "links.jar"
        with zipfile.ZipFile(path, "w") as archive:
            info = zipfile.ZipInfo("native.so")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            archive.writestr(info, "/outside/library.so")
        report = Scanner().scan([path])
        self.assertFalse(report["complete"])
        self.assertFalse(report["native_libraries"])

    def test_filesystem_links_and_missing_paths_are_incomplete(self):
        real = self.write("library.so", elf(258))
        link = self.root / "linked.so"
        link.symlink_to(real)
        for path in (link, self.root / "missing.jar"):
            with self.subTest(path=path):
                report = Scanner().scan([path])
                self.assertFalse(report["complete"])
                self.assertFalse(report["native_libraries"])

    def test_archive_paths_are_reported_not_extracted(self):
        path = self.write("app.jar", jar({"../outside.so": elf(62), "/absolute.so": elf(258)}))
        report = Scanner().scan([path])
        self.assertTrue(report["complete"])
        self.assertEqual(len(report["native_libraries"]), 2)
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_cli_findings_do_not_mean_failure_and_incomplete_does(self):
        path = self.write("app.jar", jar({"library.so": elf(62)}))
        result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True,
                                text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["native_libraries"]), 1)
        result = subprocess.run([sys.executable, str(SCRIPT), str(path), "--max-total-mib", "0"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        path.write_bytes(b"broken")
        result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True,
                                text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["complete"])


if __name__ == "__main__":
    unittest.main()
