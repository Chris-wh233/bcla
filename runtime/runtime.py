"""Container convenience tools. No workflow, resource graph, or build budget."""

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from store import identifier, now


PROXY_KEYS = {"http_proxy", "https_proxy", "all_proxy", "no_proxy",
              "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}

BOOTSTRAP = """set -eu
if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends git ca-certificates curl docker-cli ripgrep
elif command -v apk >/dev/null; then
  apk add --no-cache git ca-certificates curl docker-cli ripgrep
elif command -v dnf >/dev/null; then
  dnf install -y git ca-certificates curl docker-cli
elif command -v yum >/dev/null; then
  yum install -y git ca-certificates curl docker-cli
else
  echo 'No supported package manager; supply an environment with the baseline tools.' >&2
  exit 1
fi
command -v git
command -v curl
docker --version
test -r /etc/ssl/certs/ca-certificates.crt || test -r /etc/pki/tls/certs/ca-bundle.crt
"""


class Runtime:
    def __init__(self, store, docker=None):
        self.store = store
        self.docker = docker or os.environ.get("BCLA_DOCKER_BIN", "docker")

    @contextlib.contextmanager
    def lock(self, task_id):
        self.store.get(task_id)
        with (self.store.directory(task_id) / "runtime.lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def docker_call(self, *args):
        result = subprocess.run([self.docker, *args], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError(result.stderr.strip() or result.stdout.strip() or "Docker command failed")
        return result.stdout

    def launch(self, task_id, argv, request_key, timeout_seconds=3600, checkpoint=None, **metadata):
        if not isinstance(request_key, str) or not request_key:
            raise ValueError("request_key is required; reuse it to recover the same execution")
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 604800:
            raise ValueError("timeout_seconds must be between 1 and 604800")
        fingerprint = hashlib.sha256(json.dumps([argv, timeout_seconds], sort_keys=True).encode()).hexdigest()
        with self.lock(task_id):
            for job in self.store.records("executions", task_id):
                if job["request_key"] == request_key:
                    if job["fingerprint"] != fingerprint:
                        raise ValueError("request_key already used for a different command")
                    return job
            execution_id = identifier("exec")
            job = dict(id=execution_id, task_id=task_id, request_key=request_key,
                       fingerprint=fingerprint, argv=argv, status="STARTING", created_at=now(),
                       timeout_seconds=timeout_seconds, log_path=str(self.store.directory(task_id) / "executions" / (execution_id + ".log")),
                       **metadata)
            self.store.reserve_execution(task_id, job, checkpoint=checkpoint)
            try:
                with open(os.devnull, "wb") as sink:
                    worker = subprocess.Popen([sys.executable, str(Path(__file__).with_name("worker.py")),
                                              str(self.store.home), task_id, execution_id],
                                             stdin=subprocess.DEVNULL, stdout=sink, stderr=sink,
                                             start_new_session=True)
                    threading.Thread(target=worker.wait, daemon=True).start()
                    self.store.update_execution(task_id, execution_id, {"worker_pid": worker.pid})
            except OSError as error:
                job.update(status="FAILED", error=str(error))
                self.store.put_record("executions", task_id, job)
            return job

    def pull(self, task_id, image, request_key, checkpoint=None):
        if not image or image.startswith("-"):
            raise ValueError("Invalid image reference")
        return self.launch(task_id, [self.docker, "pull", "--platform", "linux/loong64", image],
                           request_key, 1800, kind="image_pull", checkpoint=checkpoint)

    @staticmethod
    def variables(variables):
        if not isinstance(variables, dict):
            raise ValueError("environment must be an object")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or not isinstance(value, str)
               or "\0" in value for key, value in variables.items()):
            raise ValueError("Environment names and string values are invalid")
        return variables

    def ensure(self, task_id, name, image, variables=None, container=None):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name):
            raise ValueError("Use a short lowercase environment name")
        variables = self.variables(variables or {})
        adopted_container = container
        task = self.store.get(task_id)
        with self.lock(task_id):
            environments = self.store.records("environments", task_id)
            existing = next((e for e in environments if e["name"] == name), None)
            if existing and (existing["image"] != image or existing["variables"] != variables
                             or existing.get("adopted_container") != container):
                raise ValueError("Name already identifies a different environment; choose a new name")
            if existing:
                if existing.get("cleaned_at"):
                    raise ValueError("Environment was cleaned; use a new environment name and bootstrap it")
                info = json.loads(self.docker_call("inspect", existing["container"]))[0]
                if not info["State"]["Running"]:
                    self.docker_call("start", existing["container"])
                return existing
            if container:
                info = json.loads(self.docker_call("inspect", container))[0]
                image_info = json.loads(self.docker_call("image", "inspect", info["Image"]))[0]
                mounts = info.get("Mounts", [])
                if not any(m.get("Source") == task["workspace"] and m.get("Destination") == task["workspace"]
                           and m.get("RW") for m in mounts):
                    raise ValueError("Supplied container must mount this task workspace read-write at the same absolute path")
                if not info["State"]["Running"]:
                    raise ValueError("Supplied container is not running")
            else:
                image_info = json.loads(self.docker_call("image", "inspect", image))[0]
            if image_info.get("Architecture") not in {"loong64", "loongarch64"} or image_info.get("Os") != "linux":
                raise ValueError("Expected a Linux LoongArch64 image")
            if not container:
                container = f"bcla-{task_id[5:17]}-{name}"
                # A deterministic name allows recovery if create succeeded but the MCP response was lost.
                found = subprocess.run([self.docker, "inspect", container], capture_output=True, text=True, timeout=30)
                if found.returncode == 0:
                    info = json.loads(found.stdout)[0]
                    if info.get("Config", {}).get("Labels", {}).get("bcla.task") != task_id or info["Image"] != image_info["Id"]:
                        raise ValueError("Container name collision")
                else:
                    self.docker_call("create", "--name", container, "--label", "bcla.task=" + task_id,
                                     "--ulimit", "nofile=1048576:1048576", "--user", "0:0",
                                     "--mount", f"type=bind,source={task['workspace']},target={task['workspace']}",
                                     "--mount", "type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock",
                                     "--workdir", task["workspace"], "--entrypoint", "/bin/sh",
                                     image_info["Id"], "-c", "while :; do sleep 3600; done")
                self.docker_call("start", container)
            environment = dict(id=identifier("env"), task_id=task_id, name=name, image=image,
                               image_id=image_info["Id"], container=container, variables=variables,
                               adopted_container=adopted_container,
                               created_at=now(), workspace=task["workspace"])
            self.store.put_record("environments", task_id, environment)
            info = json.loads(self.docker_call("inspect", container))[0]
            environment["container_id"] = info["Id"]
            self.store.put_record("environments", task_id, environment)
            return environment

    def cleanup(self, task_id):
        """Remove only registered task-owned helpers; leave task files intact."""
        task = self.store.get(task_id)
        results = []
        with self.lock(task_id):
            for environment in self.store.records("environments", task_id):
                item = dict(environment_id=environment["id"], container=environment["container"])
                results.append(item)
                if environment.get("adopted_container"):
                    item["status"] = "skipped_external"
                    continue
                if environment.get("cleaned_at"):
                    item["status"] = "already_cleaned"
                    continue
                try:
                    # Inventory lookup distinguishes absence from daemon/inspect failure.
                    ids = self.docker_call("ps", "-aq", "--no-trunc").split()
                    recorded_id = environment.get("container_id")
                    if recorded_id and recorded_id not in ids:
                        item["status"] = "already_absent"
                    else:
                        if not recorded_id:
                            matches = self.docker_call("ps", "-aq", "--no-trunc", "--filter",
                                                       "name=^/" + re.escape(environment["container"]) + "$").split()
                            if not matches:
                                item["status"] = "already_absent"
                            elif len(matches) != 1:
                                raise ValueError("Ambiguous legacy container identity")
                            else:
                                recorded_id = matches[0]
                        if recorded_id:
                            info = json.loads(self.docker_call("inspect", recorded_id))[0]
                            if (info["Id"] != recorded_id or
                                    info.get("Config", {}).get("Labels", {}).get("bcla.task") != task_id or
                                    info["Image"] != environment["image_id"]):
                                raise ValueError("Container ownership does not match environment record")
                            environment["container_id"] = recorded_id
                            self.store.put_record("environments", task_id, environment)
                            self.docker_call("stop", "--time", "10", recorded_id)
                            self.docker_call("rm", recorded_id)
                            item.update(status="removed", container_id=recorded_id)
                    environment["cleaned_at"] = now()
                    environment["cleanup_status"] = item["status"]
                    self.store.put_record("environments", task_id, environment)
                except (ValueError, OSError, subprocess.SubprocessError, KeyError) as error:
                    item.update(status="failed", error=str(error))
        return dict(task_id=task_id, workspace=task["workspace"], workspace_preserved=True,
                    environments=results)

    def execute(self, task_id, environment_id, command, request_key, cwd=None,
                variables=None, direct=False, timeout_seconds=3600, checkpoint=None):
        environment = self.store.record("environments", task_id, environment_id)
        if not isinstance(command, str) or not command or "\0" in command:
            raise ValueError("command must be a nonempty shell script")
        merged = dict(environment["variables"])
        merged.update(self.variables(variables or {}))
        if direct:
            merged.update({key: "" for key in PROXY_KEYS})
        # A fresh Docker client config prevents host proxy configuration from being forwarded into builds.
        merged.setdefault("DOCKER_CONFIG", "/tmp/bcla-docker-client")
        argv = [self.docker, "exec", "--workdir", cwd or environment["workspace"]]
        for key, value in sorted(merged.items()):
            argv.extend(["--env", f"{key}={value}"])
        argv.extend([environment["container"], "/bin/sh", "-c", command])
        return self.launch(task_id, argv, request_key, timeout_seconds,
                           checkpoint=checkpoint,
                           kind="container_exec", environment_id=environment_id, command=command,
                           cwd=cwd or environment["workspace"], direct=direct,
                           transient_environment_keys=sorted(merged))

    def bootstrap(self, task_id, environment_id, request_key, direct=False):
        return self.execute(task_id, environment_id, BOOTSTRAP, request_key,
                            direct=direct, timeout_seconds=1800)

    def poll(self, task_id, execution_id, offset=0, limit=12000):
        job = self.store.record("executions", task_id, execution_id)
        path = Path(job["log_path"])
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be nonnegative")
        data = b""
        if path.exists():
            with path.open("rb") as handle:
                handle.seek(offset)
                data = handle.read(max(1, min(limit, 64000)))
        if job["status"] in {"STARTING", "RUNNING"} and job.get("worker_pid"):
            try:
                os.kill(job["worker_pid"], 0)
            except ProcessLookupError:
                # A worker may have finished between the database read and process check.
                job = self.store.record("executions", task_id, execution_id)
                if job["status"] in {"STARTING", "RUNNING"}:
                    self.store.update_execution(task_id, execution_id,
                                                dict(status="UNKNOWN", warning="Worker disappeared; inspect container before rerunning."),
                                                only_if_status={"STARTING", "RUNNING"})
                    job = self.store.record("executions", task_id, execution_id)
        public = {key: value for key, value in job.items() if key != "argv"}
        return dict(execution=public, output=data.decode("utf-8", errors="replace"),
                    next_offset=offset + len(data), has_more=path.exists() and path.stat().st_size > offset + len(data))
