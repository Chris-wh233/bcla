"""Task context and execution-review reminders, without workflow scheduling."""


TERMINAL_EXECUTIONS = {"SUCCEEDED", "FAILED", "TIMED_OUT", "UNKNOWN"}


def upgrade(task):
    task.setdefault("record_version", 1)
    task.setdefault("execution_reviews", {})
    return task


def execution_stamp(job):
    return {key: job.get(key) for key in ("status", "exit_code", "ended_at")}


def preview(value):
    """Bound automatically injected context, never the durable source record."""
    if isinstance(value, str):
        return value if len(value) <= 600 else value[:600] + " [truncated; read task_open]"
    if isinstance(value, list):
        items = [preview(item) for item in value[:5]]
        return items + ([{"omitted_items": len(value) - 5}] if len(value) > 5 else [])
    if isinstance(value, dict):
        items = list(value.items())
        result = {key: preview(item) for key, item in items[:10]}
        if len(items) > 10:
            result["omitted_fields"] = len(items) - 10
        return result
    return value


def context(task, jobs):
    pending = []
    running = []
    for job in jobs:
        item = {key: job.get(key) for key in ("id", "status", "exit_code")}
        if job["status"] in TERMINAL_EXECUTIONS:
            review = task["execution_reviews"].get(job["id"], {})
            if review.get("observed") != execution_stamp(job):
                pending.append(item)
        else:
            running.append(item)
    return dict(revision=task["revision"], goal=task["goal"], status=task["status"],
                checkpoint=preview(task["checkpoint"]), decisions=preview(task["decisions"]),
                resources=preview(task["resources"]),
                legacy_notes_available=bool(task.get("nodes")),
                waiting=task["waiting"], unreviewed_count=len(pending), unreviewed=pending[:10],
                running_count=len(running), running=running[:10],
                reminder="Interpret unreviewed results at the next meaningful checkpoint; exit codes do not certify artifacts."
                if pending else None)
