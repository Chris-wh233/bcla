import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from store import Store
from runtime import Runtime, BOOTSTRAP
from server import Server
from kb_index import rebuild
from install import prepare


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(self.temporary.name)
        self.task = self.store.create({"repository": "https://github.com/example/site", "targets": ["hub"]}, "session-a")
        self.task_id = self.task["id"]

    def test_pause_with_unresolved_native_dependencies_and_resume(self):
        wait = dict(need="internal/site/dist", reason="native generator requires unsupported module",
                    validation=["index.html", "matching source commit"], resume_at="hub image build")
        saved = self.store.checkpoint(self.task_id, 1, dict(
            resources=[{"name": "lightningcss", "resolved": False}],
            decisions=[{"route": "external x86 generation"}], status="WAITING_FOR_USER", waiting=wait))
        recovered = Store(self.temporary.name).get(self.task_id)
        self.assertEqual(saved, recovered)
        resumed = self.store.checkpoint(self.task_id, 2, {"status": "ACTIVE", "waiting": None}, "validated user archive")
        self.assertIsNone(resumed["waiting"])
        self.assertEqual(len(self.store.events(self.task_id)), 3)

    def test_concurrent_checkpoint_has_one_winner_and_atomic_event(self):
        def update(note):
            try:
                self.store.checkpoint(self.task_id, 1, {"checkpoint": {"note": note}})
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(update, ["one", "two"]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.store.get(self.task_id)["revision"], 2)
        self.assertEqual(len(self.store.events(self.task_id)), 2)

    def test_invalid_wait_is_atomic(self):
        with self.assertRaises(ValueError):
            self.store.checkpoint(self.task_id, 1, {"status": "WAITING_FOR_USER", "waiting": {"need": "file"}})
        self.assertEqual(self.store.get(self.task_id)["revision"], 1)
        self.assertEqual(len(self.store.events(self.task_id)), 1)

    def test_files_are_versioned_and_readable_without_active_task(self):
        server = Server(self.store)
        first = self.store.save_file(self.task_id, "Dockerfile", "FROM scratch\n")
        second = self.store.save_file(self.task_id, "Dockerfile", "FROM local\n")
        self.assertNotEqual(first["sha256"], second["sha256"])
        result = server.call("task_file", dict(task_id=self.task_id, action="read", name="Dockerfile", sha256=first["sha256"]))
        self.assertEqual(result["content"], "FROM scratch\n")
        with self.assertRaises(ValueError):
            self.store.save_file(self.task_id, "../escape", "bad")

    def test_session_list_and_no_implicit_task_selection(self):
        self.store.create({"target": "other"}, "session-b")
        result = Server(self.store).call("task_open", {"action": "list"}, "session-a")
        self.assertEqual([t["id"] for t in result["tasks"]], [self.task_id])

    def test_execution_survives_server_recreation_and_is_idempotent(self):
        runtime = Runtime(self.store)
        argv = [sys.executable, "-c", "import time; time.sleep(.1); print('done')"]
        first = runtime.launch(self.task_id, argv, "once", 10)
        second = Runtime(Store(self.temporary.name)).launch(self.task_id, argv, "once", 10)
        self.assertEqual(first["id"], second["id"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = runtime.poll(self.task_id, first["id"], limit=2)
            if result["execution"]["status"] not in {"STARTING", "RUNNING"}:
                break
            time.sleep(.03)
        self.assertEqual(result["execution"]["status"], "SUCCEEDED")
        self.assertEqual(result["output"], "do")
        self.assertTrue(result["has_more"])
        self.assertEqual(runtime.poll(self.task_id, first["id"], offset=2)["output"], "ne\n")
        with self.assertRaises(ValueError):
            runtime.launch(self.task_id, ["different"], "once", 10)

    def test_timeout_reports_unknown_container_liveness(self):
        runtime = Runtime(self.store)
        job = runtime.launch(self.task_id, [sys.executable, "-c", "import time; time.sleep(10)"], "timeout", 1)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = runtime.poll(self.task_id, job["id"])
            if result["execution"]["status"] not in {"STARTING", "RUNNING"}:
                break
            time.sleep(.03)
        self.assertEqual(result["execution"]["status"], "TIMED_OUT")
        self.assertIn("may still be running", result["execution"]["warning"])

    def test_direct_overlay_is_scoped_and_all_inspections_are_allowed(self):
        environment = dict(id="env-" + "a" * 32, container="helper", workspace=self.task["workspace"],
                           variables={"HTTP_PROXY": "http://proxy", "GOPROXY": "https://goproxy.cn,direct"})
        self.store.put_record("environments", self.task_id, environment)
        runtime = Runtime(self.store)
        with patch.object(runtime, "launch", return_value={}) as launch:
            runtime.execute(self.task_id, environment["id"], "cat Dockerfile", "inspect", direct=True)
            argv = launch.call_args.args[1]
        self.assertIn("HTTP_PROXY=", argv)
        self.assertIn("GOPROXY=https://goproxy.cn,direct", argv)
        self.assertIn("DOCKER_CONFIG=/tmp/bcla-docker-client", argv)
        self.assertEqual(self.store.record("environments", self.task_id, environment["id"])["variables"]["HTTP_PROXY"], "http://proxy")

    def test_helper_uses_same_path_socket_high_nofile_and_client_only(self):
        runtime = Runtime(self.store)
        info = json.dumps([dict(Architecture="loong64", Os="linux", Id="sha256:test")])
        calls = []
        def docker(*args):
            calls.append(args)
            return info if args[:2] == ("image", "inspect") or args[0] == "inspect" else ""
        with patch.object(runtime, "docker_call", side_effect=docker), patch("runtime.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "")):
            result = runtime.ensure(self.task_id, "main", "local:verified")
        create = next(call for call in calls if call[0] == "create")
        self.assertTrue(result["container"].startswith("bcla-"))
        self.assertIn("bcla.task=" + self.task_id, create)
        self.assertIn("nofile=1048576:1048576", create)
        self.assertIn("type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock", create)
        self.assertIn(f"type=bind,source={self.task['workspace']},target={self.task['workspace']}", create)
        self.assertIsNone(result["adopted_container"])
        self.assertIn("docker-cli", BOOTSTRAP)
        self.assertEqual(BOOTSTRAP.count("docker-cli ripgrep"), 2)
        self.assertNotIn("dnf install -y git ca-certificates curl docker-cli ripgrep", BOOTSTRAP)
        self.assertNotIn("yum install -y git ca-certificates curl docker-cli ripgrep", BOOTSTRAP)
        self.assertNotIn("docker.io", BOOTSTRAP)
        self.assertNotIn("buildx", BOOTSTRAP)

    def test_wrong_architecture_rejected(self):
        runtime = Runtime(self.store)
        with patch.object(runtime, "docker_call", return_value=json.dumps([dict(Architecture="amd64", Os="linux")])):
            with self.assertRaisesRegex(ValueError, "LoongArch"):
                runtime.ensure(self.task_id, "main", "wrong")

    def test_cleanup_removes_owned_helper_once_and_preserves_workspace(self):
        runtime = Runtime(self.store)
        cid = "a" * 64
        environment = dict(id="env-" + "c" * 32, container="helper", container_id=cid,
                           image_id="sha256:image", adopted_container=None)
        self.store.put_record("environments", self.task_id, environment)
        marker = Path(self.task["workspace"]) / "keep.txt"
        marker.write_text("retained")
        def docker(*args):
            if args[0] == "ps":
                return cid
            if args[0] == "inspect":
                return json.dumps([dict(Id=cid, Image="sha256:image",
                                        Config={"Labels": {"bcla.task": self.task_id}})])
            return ""
        with patch.object(runtime, "docker_call", side_effect=docker) as call:
            result = runtime.cleanup(self.task_id)
            self.assertEqual(result["environments"][0]["status"], "removed")
            call.assert_any_call("stop", "--time", "10", cid)
            call.assert_any_call("rm", cid)
            call.reset_mock()
            self.assertEqual(runtime.cleanup(self.task_id)["environments"][0]["status"], "already_cleaned")
            call.assert_not_called()
        self.assertEqual(marker.read_text(), "retained")
        self.assertEqual(result["workspace"], self.task["workspace"])
        self.assertEqual(self.store.get(self.task_id)["status"], "ACTIVE")

    def test_cleanup_refuses_mismatched_ownership_and_skips_adopted(self):
        runtime = Runtime(self.store)
        cid = "b" * 64
        for suffix, adopted in [("d", None), ("e", "user-helper")]:
            self.store.put_record("environments", self.task_id,
                                  dict(id="env-" + suffix * 32, container="helper", container_id=cid,
                                       image_id="sha256:image", adopted_container=adopted))
        def docker(*args):
            if args[0] == "ps":
                return cid
            if args[0] == "inspect":
                return json.dumps([dict(Id=cid, Image="sha256:image", Config={"Labels": {"bcla.task": "another-task"}})])
            self.fail("Unexpected destructive Docker call")
        with patch.object(runtime, "docker_call", side_effect=docker):
            result = runtime.cleanup(self.task_id)
        self.assertEqual({e["status"] for e in result["environments"]}, {"failed", "skipped_external"})

    def test_mcp_initialization_and_errors(self):
        server = Server(self.store)
        init = server.handle(dict(id=1, method="initialize", params={"protocolVersion": "2025-06-18"}))
        self.assertEqual(init["result"]["serverInfo"]["name"], "bcla")
        server.handle(dict(id=2, method="server/discover"))
        result = server.handle(dict(id=3, method="tools/call", params=dict(name="task_open", input=dict(action="get", task_id="missing"))))
        self.assertTrue(result["result"]["isError"])
        self.assertEqual(result["result"]["resultType"], "complete")

    def test_mcp_stdio_roundtrip(self):
        root = Path(__file__).resolve().parents[1]
        requests = [dict(jsonrpc="2.0", id=1, method="initialize", params={"protocolVersion": "2025-06-18"}),
                    dict(jsonrpc="2.0", id=2, method="tools/list"),
                    dict(jsonrpc="2.0", id=3, method="tools/call", params=dict(name="task_open", arguments={"action": "list"}))]
        result = subprocess.run([sys.executable, str(root / "runtime" / "server.py")],
                                input="".join(json.dumps(r) + "\n" for r in requests), capture_output=True,
                                text=True, timeout=10, env={**os.environ, "BCLA_HOME": self.temporary.name})
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), 3)
        self.assertIn("task_context", {tool["name"] for tool in responses[1]["result"]["tools"]})
        self.assertFalse(responses[2]["result"]["isError"])

    def test_dead_worker_is_unknown_not_success(self):
        runtime = Runtime(self.store)
        record = dict(id="exec-" + "b" * 32, status="STARTING", worker_pid=999999999,
                      log_path=str(Path(self.temporary.name) / "missing.log"))
        self.store.put_record("executions", self.task_id, record)
        result = runtime.poll(self.task_id, record["id"])
        self.assertEqual(result["execution"]["status"], "UNKNOWN")
        self.assertEqual(self.store.context(self.task_id)["unreviewed"][0]["id"], record["id"])


class PackagingTests(unittest.TestCase):
    def test_install_preparation_preserves_previous_package(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(__file__).resolve().parents[1]
            marketplace, first = prepare(source, directory)
            _, second = prepare(source, directory)
            self.assertNotEqual(first, second)
            self.assertTrue((first / "runtime" / "server.py").is_file())
            self.assertEqual((marketplace / "plugins" / "bcla").resolve(), second)
            self.assertFalse((second / "hooks").exists())
            self.assertFalse((second / "remote").exists())
            self.assertFalse((second / "dist").exists())
            for relative in ("skills/fix-pkg-miss/scripts/scan_java_native.py",
                             "skills/fix-pkg-miss/references/java-native.md",
                             "skills/no-extra-checksums/SKILL.md"):
                self.assertEqual((second / relative).read_bytes(), (source / relative).read_bytes())
            manifest = json.loads((second / ".codex-plugin" / "plugin.json").read_text())
            self.assertEqual(manifest["name"], "bcla")
            metadata = json.loads((marketplace / ".agents" / "plugins" / "marketplace.json").read_text())
            self.assertEqual(metadata["name"], "bcla-local")
            self.assertEqual(metadata["plugins"][0]["name"], "bcla")


class KnowledgeTests(unittest.TestCase):
    def test_indexes_do_not_duplicate_host_path_and_verify_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe_path = root / "owner" / "project" / "1.0"
            recipe_path.mkdir(parents=True)
            dockerfile = recipe_path / "Dockerfile"
            dockerfile.write_text("FROM scratch\n")
            recipe = dict(producer="bcla", schema_version=2, kind="image", status="verified",
                          repository="https://github.com/owner/project.git", requested_version="1.0", resolved_commit="abc",
                          targets=["server"], build=[dict(cwd="$SOURCE", command="docker build .", execution_id="exec-1")],
                          tests=[dict(command="smoke", result="passed", execution_id="exec-2")],
                          files=[dict(path="Dockerfile", sha256=hashlib.sha256(dockerfile.read_bytes()).hexdigest())],
                          images=[dict(target="server", id="sha256:output", architecture="loong64", dockerfile="Dockerfile", source="official")])
            (recipe_path / "experience.json").write_text(json.dumps(recipe))
            self.assertEqual(rebuild(root)["projects"], 1)
            self.assertFalse((root / "github.com").exists())
            self.assertTrue((root / "owner" / "project" / "index.json").exists())
            dockerfile.write_text("changed")
            with self.assertRaisesRegex(ValueError, "Hash mismatch"):
                rebuild(root)


if __name__ == "__main__":
    unittest.main()
