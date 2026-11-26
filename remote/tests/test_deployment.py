import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
from prepare_client import prepare
from remote import ssh_command


class SourceTests(unittest.TestCase):
    def test_python_sources_compile_without_creating_bytecode(self):
        for path in PROJECT.rglob("*.py"):
            if "dist" not in path.relative_to(PROJECT).parts:
                compile(path.read_bytes(), str(path), "exec")


class ClientTests(unittest.TestCase):
    def test_generated_plugin_keeps_skills_and_uses_remote_mcp(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = prepare("build-host", "bcla-remote", Path(temporary) / "client")
            config = json.loads((output / ".mcp.json").read_text())["mcpServers"]["bcla"]
            self.assertEqual(config["command"], "ssh")
            self.assertIn("BatchMode=yes", config["args"])
            self.assertEqual(config["args"][-2], "build-host")
            remote = shlex.split(config["args"][-1])
            self.assertEqual(remote, ["docker", "--host", "unix:///var/run/docker.sock", "exec", "-i",
                                      "bcla-remote", "/usr/local/bin/bcla-remote-stdio"])
            skill = (output / "skills/bcla/SKILL.md").read_text()
            self.assertIn("All task paths returned", skill)
            self.assertLess(skill.index("## Remote deployment"), skill.index("## Enter or resume"))
            self.assertTrue((output / "scripts/remote.py").is_file())
            self.assertTrue((output / "docs/task-protocol.md").is_file())
            self.assertEqual(json.loads((output / "bcla-remote.json").read_text())["host"], "build-host")
            self.assertFalse((output / "remote").exists())
            self.assertFalse((output / "dist").exists())
            self.assertFalse((output / "vendor").exists())
            for relative in ("scripts/kb_index.py", "docs/knowledge-layout.md",
                             "docs/dockerfile-guidelines.md", "skills/gen-maker/assets/Makefile"):
                self.assertEqual((output / relative).read_bytes(), (PROJECT.parent / relative).read_bytes())
            self.assertEqual((output / "docs/remote.md").read_bytes(), (PROJECT / "docs/client.md").read_bytes())
            for sibling in (output / "skills").glob("*/SKILL.md"):
                self.assertIn("../../docs/remote.md", sibling.read_text())
            with self.assertRaises(ValueError):
                prepare("build-host", "bcla-remote", output)

    def test_output_cannot_overwrite_core_or_deployment_sources(self):
        for output in (PROJECT.parent, PROJECT / "scripts/new-client", PROJECT.parent / "skills/new-client"):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "outside core sources"):
                prepare("build-host", "bcla-remote", output)

    def test_generated_client_can_be_installed_without_losing_remote_configuration(self):
        from install import prepare as install_prepare
        with tempfile.TemporaryDirectory() as temporary:
            output = prepare("build-host", "bcla-remote", Path(temporary) / "client")
            _, package = install_prepare(output, Path(temporary) / "installed")
            self.assertEqual((package / "bcla-remote.json").read_bytes(), (output / "bcla-remote.json").read_bytes())
            self.assertEqual((package / ".mcp.json").read_bytes(), (output / ".mcp.json").read_bytes())
            self.assertTrue((package / "scripts/remote.py").is_file())
            self.assertTrue((package / "docs/remote.md").is_file())
            self.assertFalse((package / "remote").exists())

    def test_remote_arguments_are_preserved_and_no_tty_is_allocated(self):
        args = ["sh", "-c", "printf '%s' 'a b; $(secret)'", "file with spaces"]
        command = ssh_command("build-host", "bcla-remote", args)
        self.assertIn("-T", command)
        self.assertNotIn("-t", command)
        self.assertEqual(shlex.split(command[-1])[-len(args):], args)

    def test_connection_values_cannot_inject_ssh_options(self):
        for host, container in [("-oProxyCommand=bad", "bcla-remote"), ("host;echo bad", "bcla-remote"),
                                ("host", "bad;name")]:
            with self.subTest(host=host, container=container), self.assertRaises(ValueError):
                prepare(host, container, PROJECT / "dist/test-invalid")


class HealthTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("healthcheck", PROJECT / "container/healthcheck.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_same_path_bind_mount_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = str(Path(temporary).resolve())
            info = json.dumps({"OSType": "linux", "Architecture": "loong64"}).encode()
            mounts = [{"Type": "bind", "Source": directory, "Destination": directory, "RW": True}]
            with patch.dict(os.environ, BCLA_HOME=directory, HOSTNAME="service"), \
                    patch.object(self.module.subprocess, "check_output", side_effect=[info, json.dumps([{"Mounts": mounts}]).encode()]):
                self.module.check()
            mounts[0]["Source"] = "/different-host-directory"
            with patch.dict(os.environ, BCLA_HOME=directory, HOSTNAME="service"), \
                    patch.object(self.module.subprocess, "check_output", side_effect=[info, json.dumps([{"Mounts": mounts}]).encode()]), \
                    self.assertRaisesRegex(ValueError, "same absolute path"):
                self.module.check()


FAKE_DOCKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['FAKE_DOCKER_LOG'], 'a') as out:
    out.write(json.dumps(args) + '\n')
assert args[:2] == ['--host', 'unix:///var/run/docker.sock'], args
args = args[2:]
if args[0] == 'info':
    print(os.environ.get('FAKE_PLATFORM', 'linux/loong64'))
elif args[:2] == ['image', 'inspect']:
    print('sha256:testimage' if args[3] == '{{.Id}}' else 'linux/loong64')
elif args[0] == 'inspect':
    if os.environ.get('FAKE_EXISTING') != '1':
        sys.exit(1)
    if '--format' in args:
        print(os.environ.get('FAKE_OWNER', 'true') if 'managed' in args[2]
              else os.environ.get('FAKE_SIGNATURE', 'different-config'))
    else:
        print('[]')
elif args[0] == 'run':
    print('fake-container-id')
elif args[0] == 'exec':
    pass
elif args[0] == 'start':
    print(args[1])
elif args[0] == 'build':
    print('fake-image-id')
else:
    raise AssertionError(args)
'''


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        fake = root / "docker"
        fake.write_text(FAKE_DOCKER)
        fake.chmod(0o755)
        self.log = root / "calls.jsonl"
        self.data = root / "data with spaces"
        self.env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                        FAKE_DOCKER_LOG=str(self.log), BCLA_DATA_DIR=str(self.data),
                        BCLA_CONTAINER="test-bcla", BCLA_IMAGE="test:local")

    def test_build_uses_repo_root_and_records_core_revision(self):
        result = subprocess.run(["bash", str(PROJECT / "deploy.sh"), "build"], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line)[2:] for line in self.log.read_text().splitlines()]
        build = next(call for call in calls if call[0] == "build")
        self.assertEqual(build[-1], str(PROJECT.parent))
        self.assertEqual(build[build.index("--file") + 1], str(PROJECT / "Dockerfile"))
        self.assertTrue(any(arg.startswith("BCLA_REVISION=") for arg in build))
        version = json.loads((PROJECT.parent / ".codex-plugin/plugin.json").read_text())["version"].split("+")[0]
        self.assertIn("BCLA_VERSION=" + version, build)
        self.assertFalse(any(call[0] in {"run", "pull"} for call in calls))

    def test_up_uses_existing_image_and_same_path_mount_without_build_or_pull(self):
        result = subprocess.run(["bash", str(PROJECT / "deploy.sh"), "up"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line)[2:] for line in self.log.read_text().splitlines()]
        self.assertFalse(any(call[0] in {"build", "pull"} for call in calls))
        run = next(call for call in calls if call[0] == "run")
        self.assertIn(f"type=bind,source={self.data},target={self.data}", run)
        self.assertIn(f"BCLA_HOME={self.data}", run)
        self.assertIn("--init", run)
        self.assertIn("--pull=never", run)
        self.assertNotIn("--rm", run)
        self.assertNotIn("-t", run)

    def test_wrong_host_architecture_launches_nothing(self):
        self.env["FAKE_PLATFORM"] = "linux/amd64"
        result = subprocess.run(["bash", str(PROJECT / "deploy.sh"), "up"], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        calls = [json.loads(line)[2:] for line in self.log.read_text().splitlines()]
        self.assertEqual([call[0] for call in calls], ["info"])
        self.assertFalse(self.data.exists())

    def test_existing_service_is_reused_only_with_matching_configuration(self):
        self.env["FAKE_EXISTING"] = "1"
        signature = hashlib.sha256(b"sha256:testimage\0" + str(self.data).encode() + b"\0").hexdigest()
        self.env["FAKE_SIGNATURE"] = signature
        result = subprocess.run(["bash", str(PROJECT / "deploy.sh"), "up"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line)[2:] for line in self.log.read_text().splitlines()]
        self.assertIn("start", [call[0] for call in calls])
        self.assertFalse(any(call[0] in {"run", "rm", "stop"} for call in calls))

    def test_configuration_change_and_unmanaged_container_are_not_replaced(self):
        for owner in ["true", "false"]:
            with self.subTest(owner=owner):
                self.log.unlink(missing_ok=True)
                self.env.update(FAKE_EXISTING="1", FAKE_OWNER=owner, FAKE_SIGNATURE="different-config")
                result = subprocess.run(["bash", str(PROJECT / "deploy.sh"), "up"], env=self.env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                calls = [json.loads(line)[2:] for line in self.log.read_text().splitlines()]
                self.assertFalse(any(call[0] in {"start", "run", "rm", "stop", "exec"} for call in calls))


class ToolCallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.env = dict(os.environ, BCLA_HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1")

    def invoke(self, arguments, payload=None, raw=None):
        result = subprocess.run([sys.executable, str(PROJECT / "container/call.py"), *arguments],
                                input=raw if raw is not None else json.dumps(payload or {}),
                                capture_output=True, text=True, env=self.env, timeout=10)
        return result, json.loads(result.stdout)

    def test_lists_real_schemas_and_preserves_tasks_across_calls(self):
        result, response = self.invoke(["--list"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("environment_exec", {tool["name"] for tool in response["tools"]})
        result, created = self.invoke(["task_open", "--session-id", "session-a"],
                                      {"action": "create", "goal": {"project": "test-only"}})
        self.assertEqual(result.returncode, 0, result.stderr)
        task = created["structuredContent"]
        self.assertTrue(Path(task["workspace"]).is_relative_to(self.home))
        _, fetched = self.invoke(["task_open"], {"action": "get", "task_id": task["id"]})
        self.assertEqual(fetched["structuredContent"]["id"], task["id"])
        _, listed = self.invoke(["task_open", "--session-id", "session-a"], {"action": "list"})
        self.assertEqual([r["id"] for r in listed["structuredContent"]["tasks"]], [task["id"]])
        _, other = self.invoke(["task_open", "--session-id", "session-b"], {"action": "list"})
        self.assertEqual(other["structuredContent"]["tasks"], [])

    def test_reports_tool_errors_and_invalid_json(self):
        for arguments, raw in ((["task_open"], '{"action":"get","task_id":"missing"}'),
                               (["not_a_tool"], '{}'), (["task_open"], 'not json'),
                               (["task_open"], '[]')):
            with self.subTest(arguments=arguments, raw=raw):
                result, response = self.invoke(arguments, raw=raw)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(response["isError"])
                self.assertIn("message", response["structuredContent"])

    def test_async_worker_survives_one_shot_call(self):
        sys.path.insert(0, str(PROJECT.parent / "runtime"))
        from store import Store
        fake = self.home / "fake-docker"
        fake.write_text("#!/bin/sh\nsleep 0.2\nprintf 'completed\\n'\n")
        fake.chmod(0o755)
        self.env["BCLA_DOCKER_BIN"] = str(fake)
        _, response = self.invoke(["task_open"], {"action": "create", "goal": {"project": "test-only"}})
        task = response["structuredContent"]
        environment_id = "env-" + "a" * 32
        Store(self.home).put_record("environments", task["id"], dict(
            id=environment_id, container="fake-helper", workspace=task["workspace"], variables={}))
        arguments = dict(task_id=task["id"], environment_id=environment_id,
                         command="test-only", request_key="one-shot-worker", timeout_seconds=5)
        result, launched = self.invoke(["environment_exec"], arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        job_id = launched["structuredContent"]["id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            _, polled = self.invoke(["execution_read"], dict(task_id=task["id"], execution_id=job_id))
            job = polled["structuredContent"]
            if job["execution"]["status"] not in {"STARTING", "RUNNING"}:
                break
            time.sleep(0.05)
        self.assertEqual(job["execution"]["status"], "SUCCEEDED")
        self.assertEqual(job["output"], "completed\n")
        _, repeated = self.invoke(["environment_exec"], arguments)
        self.assertEqual(repeated["structuredContent"]["id"], job_id)


class ProtocolTests(unittest.TestCase):
    def test_stdio_handshake_and_task_store_are_reused_across_connections(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = dict(os.environ, BCLA_HOME=temporary, PYTHONDONTWRITEBYTECODE="1")

            def exchange(messages):
                result = subprocess.run([sys.executable, str(PROJECT.parent / "runtime/server.py")],
                                        input="".join(json.dumps(m) + "\n" for m in messages),
                                        capture_output=True, text=True, env=env, check=True)
                return [json.loads(line) for line in result.stdout.splitlines()]

            responses = exchange([
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "task_open", "arguments": {
                    "action": "create", "session_id": "remote-test", "goal": {"repository": "test-only"}}}},
            ])
            self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "bcla")
            names = {tool["name"] for tool in responses[1]["result"]["tools"]}
            self.assertTrue({"task_open", "environment_exec", "execution_read"}.issubset(names))
            payload = responses[2]["result"]["structuredContent"]
            self.assertTrue(Path(payload["workspace"]).is_relative_to(temporary))
            task_id = payload["id"]
            resumed = exchange([{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
                "name": "task_open", "arguments": {"action": "get", "task_id": task_id}}}])
            self.assertEqual(resumed[0]["result"]["structuredContent"]["id"], task_id)
            self.assertTrue((Path(temporary) / "records.sqlite3").is_file())


if __name__ == "__main__":
    unittest.main()
