import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from kb_index import rebuild


class VariantKnowledgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_recipe(self, relative="owner/project/1.0/debian", family="debian",
                     repository="https://github.com/owner/project.git", version="1.0"):
        directory = self.root / relative
        directory.mkdir(parents=True, exist_ok=True)
        content = f"FROM {family}:verified\n"
        (directory / "Dockerfile").write_text(content)
        recipe = dict(
            producer="bcla", schema_version=3, kind="image", status="verified",
            repository=repository, requested_version=version, resolved_commit="abc",
            variant=family, targets=["server"],
            build=[dict(cwd="$CONTEXT", command="docker build .", execution_id="exec-build")],
            tests=[dict(command="smoke", result="passed", execution_id="exec-test")],
            files=[dict(path="Dockerfile", sha256=hashlib.sha256(content.encode()).hexdigest())],
            images=[dict(target="server", id="sha256:output", architecture="loong64",
                         dockerfile="Dockerfile", source="official",
                         runtime_base=dict(family=family, reference=f"registry/library/{family}:verified",
                                           libc="musl" if family == "alpine" else "glibc"))])
        path = directory / "experience.json"
        self.save(path, recipe)
        return path, recipe

    @staticmethod
    def save(path, recipe):
        path.write_text(json.dumps(recipe))

    def test_same_version_families_share_project_index(self):
        self.write_recipe()
        self.write_recipe("owner/project/1.0/alpine", "alpine")
        self.assertEqual(rebuild(self.root)["projects"], 1)
        project = self.root / "owner/project"
        index = json.loads((project / "index.json").read_text())
        self.assertEqual(index["schema_version"], 3)
        self.assertEqual({(r["version"], r["variant"], r["path"]) for r in index["experiences"]},
                         {("1.0", "debian", "1.0/debian"), ("1.0", "alpine", "1.0/alpine")})
        self.assertFalse((project / "1.0/index.json").exists())
        global_index = json.loads((self.root / "index.json").read_text())
        self.assertEqual(global_index["projects"][0]["path"], "owner/project")
        self.assertFalse((self.root / "github.com").exists())

    def test_other_host_and_version_normalization(self):
        self.write_recipe("gitlab.example/group/subgroup/project/release_1/alpine", "alpine",
                          "https://gitlab.example/group/subgroup/project.git", "release/1")
        rebuild(self.root)
        project = self.root / "gitlab.example/group/subgroup/project"
        entry = json.loads((project / "index.json").read_text())["experiences"][0]
        self.assertEqual(entry["version"], "release/1")
        self.assertEqual(entry["path"], "release_1/alpine")

    def test_missing_or_mixed_runtime_family_does_not_publish_indexes(self):
        path, recipe = self.write_recipe()
        for base in (None, {}, dict(family="alpine", reference="alpine:3", libc="musl"),
                     dict(family="debian", reference="", libc="glibc"),
                     dict(family="debian", reference="debian:forky")):
            with self.subTest(base=base):
                recipe["images"][0]["runtime_base"] = base
                self.save(path, recipe)
                with self.assertRaisesRegex(ValueError, "Runtime base"):
                    rebuild(self.root)
                self.assertFalse((self.root / "index.json").exists())

    def test_path_must_match_repository_version_and_family(self):
        for field, value in (("variant", "alpine"), ("requested_version", "2.0"),
                             ("repository", "https://github.com/other/project")):
            with self.subTest(field=field):
                path, recipe = self.write_recipe()
                recipe[field] = value
                if field == "variant":
                    recipe["images"][0]["runtime_base"]["family"] = value
                self.save(path, recipe)
                with self.assertRaisesRegex(ValueError, "directory does not match"):
                    rebuild(self.root)

    def test_invalid_family_names(self):
        path, recipe = self.write_recipe()
        for family in (None, "../debian", "debian:forky", "Debian", "lcr/debian"):
            with self.subTest(family=family):
                recipe["variant"] = family
                self.save(path, recipe)
                with self.assertRaisesRegex(ValueError, "invalid image variant"):
                    rebuild(self.root)

    def test_each_variant_covers_only_its_own_unique_targets(self):
        path, recipe = self.write_recipe()
        extra = dict(recipe["images"][0], target="agent")
        recipe["images"].append(extra)
        self.save(path, recipe)
        with self.assertRaisesRegex(ValueError, "exactly match"):
            rebuild(self.root)
        recipe["targets"].append("agent")
        self.save(path, recipe)
        rebuild(self.root, check=True)
        recipe["images"].append(extra)
        self.save(path, recipe)
        with self.assertRaisesRegex(ValueError, "unique image targets"):
            rebuild(self.root)

    def test_dependency_is_local_and_not_an_image_candidate(self):
        path, recipe = self.write_recipe()
        dependency_dir = path.parent / "dependencies/library-2.0"
        dependency_dir.mkdir(parents=True)
        (dependency_dir / "README.md").write_text("validated library build\n")
        dependency = dict(recipe, kind="dependency", repository="https://github.com/other/library",
                          requested_version="2.0", artifacts=[dict(name="library", version="2.0")],
                          files=[dict(path="README.md", sha256=hashlib.sha256(
                              (dependency_dir / "README.md").read_bytes()).hexdigest())])
        dependency.pop("variant")
        dependency.pop("images")
        self.save(dependency_dir / "experience.json", dependency)
        self.assertEqual(rebuild(self.root)["projects"], 1)
        index = json.loads((self.root / "owner/project/index.json").read_text())
        self.assertEqual(len(index["experiences"]), 1)
        self.assertFalse((path.parent / "dependencies/index.json").exists())

    def test_check_only_and_file_integrity(self):
        path, _ = self.write_recipe()
        rebuild(self.root, check=True)
        self.assertFalse((self.root / "index.json").exists())
        (path.parent / "Dockerfile").write_text("FROM something-else\n")
        with self.assertRaisesRegex(ValueError, "Hash mismatch"):
            rebuild(self.root)

    def test_legacy_recipes_remain_readable_without_inventing_family(self):
        path, recipe = self.write_recipe("owner/project/1.0")
        recipe["schema_version"] = 2
        recipe.pop("variant")
        recipe["images"][0].pop("runtime_base")
        self.save(path, recipe)
        self.write_recipe("owner/project/1.0/alpine", "alpine")
        rebuild(self.root)
        entries = json.loads((self.root / "owner/project/index.json").read_text())["experiences"]
        legacy = next(entry for entry in entries if entry["path"] == "1.0")
        self.assertNotIn("variant", legacy)
        self.assertEqual(json.loads(path.read_text())["schema_version"], 2)

    def test_duplicate_legacy_identity_is_rejected(self):
        for directory in ("owner/project/1.0", "owner/project/alias"):
            path, recipe = self.write_recipe(directory)
            recipe["schema_version"] = 2
            recipe.pop("variant")
            self.save(path, recipe)
        with self.assertRaisesRegex(ValueError, "Duplicate repository/version/variant"):
            rebuild(self.root)


if __name__ == "__main__":
    unittest.main()
