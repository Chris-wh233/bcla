"""Detached execution worker: survives MCP restart and records a real exit status."""

import os
from pathlib import Path
import signal
import subprocess
import sys

from store import Store, now


def run(home, task_id, execution_id):
    store = Store(home)
    job = store.record("executions", task_id, execution_id)
    process = None
    job.update(status="RUNNING", started_at=now(), worker_pid=os.getpid())
    store.put_record("executions", task_id, job)
    try:
        with Path(job["log_path"]).open("ab", buffering=0) as output:
            process = subprocess.Popen(job["argv"], stdout=output, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            job["process_pid"] = process.pid
            store.put_record("executions", task_id, job)
            try:
                code = process.wait(timeout=job["timeout_seconds"])
                job.update(status="SUCCEEDED" if code == 0 else "FAILED", exit_code=code)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                # Killing a docker client does not prove the container process stopped.
                job.update(status="TIMED_OUT", exit_code=None,
                           warning="Inspect container processes before retrying; the workload may still be running.")
    except Exception as error:
        job.update(status="FAILED", exit_code=None, error=str(error))
    job["ended_at"] = now()
    store.put_record("executions", task_id, job)


if __name__ == "__main__":
    run(*sys.argv[1:])
