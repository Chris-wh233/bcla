#!/usr/bin/env python3
"""Opt-in integration check using one temporary task and a locally present image."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from store import Store
from runtime import Runtime


def wait(runtime, task_id, job):
    offset = 0
    while True:
        result = runtime.poll(task_id, job["id"], offset=offset)
        if result["output"]:
            print(result["output"], end="", flush=True)
        offset = result["next_offset"]
        if result["execution"]["status"] not in {"STARTING", "RUNNING"} and not result["has_more"]:
            if result["execution"]["status"] != "SUCCEEDED":
                raise RuntimeError(str(result["execution"]))
            return
        time.sleep(.2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Existing local Linux LoongArch image")
    parser.add_argument("--bootstrap", action="store_true", help="Install baseline packages in the temporary helper")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="bcla-smoke-") as directory:
        store = Store(directory)
        task = store.create({"purpose": "runtime smoke test"})
        runtime = Runtime(store)
        environment = None
        try:
            environment = runtime.ensure(task["id"], "smoke", args.image, {"BCLA_SMOKE": "overlay-ok"})
            if args.bootstrap:
                wait(runtime, task["id"], runtime.bootstrap(task["id"], environment["id"], "bootstrap"))
            job = runtime.execute(task["id"], environment["id"],
                                  'set -eu; test "$(uname -m)" = loongarch64; test "$BCLA_SMOKE" = overlay-ok; '
                                  'test "$(ulimit -n)" -ge 65536; test -S /var/run/docker.sock; '
                                  'test "$PWD" = "' + task["workspace"] + '"; printf "container smoke passed\\n"',
                                  "smoke", timeout_seconds=30,
                                  checkpoint=dict(expected_revision=task["revision"], changes=dict(
                                      checkpoint={"next": "verify helper runtime"})))
            wait(Runtime(Store(directory)), task["id"], job)
            assert job["task_revision"] == 2
            recovered = Store(directory)
            assert job["id"] in {item["id"] for item in recovered.context(task["id"])["unreviewed"]}
            recovered.checkpoint(task["id"], recovered.get(task["id"])["revision"], dict(
                execution_reviews={job["id"]: "Helper platform, overlay, nofile, socket and workspace checks passed"},
                checkpoint={"accomplished": "runtime probe passed"}))
            assert job["id"] not in {item["id"] for item in recovered.context(task["id"])["unreviewed"]}
            assert recovered.get(task["id"])["status"] == "ACTIVE"
            print("Task context and execution reconciliation passed; task success was not inferred.")
            if args.bootstrap:
                wait(runtime, task["id"], runtime.execute(task["id"], environment["id"],
                     "git --version; curl --version; docker version --format '{{.Server.Arch}}'", "tools", timeout_seconds=30))
        finally:
            if environment:
                subprocess.run([runtime.docker, "rm", "-f", environment["container"]], check=True)
                print("Removed temporary smoke-test container; no image was removed.")


if __name__ == "__main__":
    main()
