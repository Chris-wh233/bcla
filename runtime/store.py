"""Transactional records, without workflow scheduling or route validation."""

import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import uuid

from records import TERMINAL_EXECUTIONS, context, execution_stamp, upgrade


STATUSES = {"ACTIVE", "WAITING_FOR_USER", "PAUSED", "SUCCEEDED", "CANCELLED"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def identifier(prefix):
    return prefix + "-" + uuid.uuid4().hex


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z]+-[0-9a-f]{32}", value):
        raise ValueError("Invalid record ID")
    return value


class Store:
    def __init__(self, home=None):
        self.home = Path(home or os.environ.get("BCLA_HOME", "~/.local/share/bcla")).expanduser().resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS environments (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS executions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, body TEXT NOT NULL);
            """)

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.home / "records.sqlite3", timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def directory(self, task_id):
        return self.home / "tasks" / valid_id(task_id)

    def create(self, goal, session_id=None):
        if not isinstance(goal, dict) or not goal:
            raise ValueError("goal must be a nonempty object")
        task_id = identifier("bcla")
        directory = self.directory(task_id)
        for name in ("workspace", "executions", "accepted"):
            (directory / name).mkdir(parents=True, exist_ok=True)
        task = dict(id=task_id, revision=1, status="ACTIVE", goal=goal,
                    session_id=session_id, created_at=now(), updated_at=now(),
                    workspace=str(directory / "workspace"), checkpoint={},
                    waiting=None, decisions=[], resources=[], build_definitions=[], result={})
        upgrade(task)
        with self.connect() as db:
            db.execute("INSERT INTO tasks VALUES (?, ?, ?)", (task_id, 1, json.dumps(task)))
            self.event(db, task_id, "created", {"goal": goal})
        return task

    @staticmethod
    def event(db, task_id, kind, details):
        db.execute("INSERT INTO events(task_id, body) VALUES (?, ?)",
                   (task_id, json.dumps(dict(at=now(), kind=kind, details=details))))

    def get(self, task_id):
        valid_id(task_id)
        with self.connect() as db:
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("Task not found")
        return upgrade(json.loads(row[0]))

    def list(self, session_id=None):
        with self.connect() as db:
            tasks = [json.loads(row[0]) for row in db.execute("SELECT body FROM tasks ORDER BY rowid DESC")]
        return [dict(id=t["id"], status=t["status"], goal=t["goal"], session_id=t["session_id"],
                     revision=t["revision"], updated_at=t["updated_at"])
                for t in tasks if session_id is None or t["session_id"] == session_id]

    def checkpoint(self, task_id, expected_revision, changes, note=""):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._checkpoint(db, task_id, expected_revision, changes, note)

    def _checkpoint(self, db, task_id, expected_revision, changes, note=""):
        allowed = {"status", "goal", "checkpoint", "waiting", "decisions", "resources", "build_definitions", "result",
                   "execution_reviews"}
        if not isinstance(changes, dict) or set(changes) - allowed:
            raise ValueError("Unsupported checkpoint field")
        row = db.execute("SELECT revision, body FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("Task not found")
        if row[0] != expected_revision:
            raise ValueError(f"REVISION_CONFLICT: current revision is {row[0]}; reread before merging")
        task = upgrade(json.loads(row[1]))
        if "goal" in changes and changes["goal"] != task["goal"] and not note.strip():
            raise ValueError("Goal changes require a note identifying clarification or user revision")
        task.update({key: value for key, value in changes.items()
                     if key != "execution_reviews"})
        reviews = changes.get("execution_reviews", {})
        if not isinstance(reviews, dict):
            raise ValueError("execution_reviews must map execution IDs to interpretations")
        for execution_id, review in reviews.items():
            if not isinstance(review, str) or not review.strip():
                raise ValueError("Each execution review requires a nonempty interpretation")
            record = db.execute("SELECT body FROM executions WHERE task_id=? AND id=?", (task_id, execution_id)).fetchone()
            if record is None:
                raise ValueError("Cannot review an execution outside this task")
            job = json.loads(record[0])
            if job["status"] not in TERMINAL_EXECUTIONS:
                raise ValueError("Review finished executions; inspect running work before interpreting completion")
            task["execution_reviews"][execution_id] = dict(interpretation=review, observed=execution_stamp(job))
        if task["status"] not in STATUSES:
            raise ValueError("Invalid task status")
        for key in ("goal", "checkpoint", "result"):
            if not isinstance(task[key], dict):
                raise ValueError(f"{key} must be an object")
        for key in ("decisions", "resources", "build_definitions"):
            if not isinstance(task[key], list):
                raise ValueError(f"{key} must be an array")
        if task["waiting"] is not None and not isinstance(task["waiting"], dict):
            raise ValueError("waiting must be null or an object")
        if task["status"] == "WAITING_FOR_USER":
            wait = task["waiting"] or {}
            if not all(wait.get(k) for k in ("need", "reason", "validation", "resume_at")):
                raise ValueError("Waiting requires need, reason, validation, resume_at")
        task.update(revision=row[0] + 1, updated_at=now())
        db.execute("UPDATE tasks SET revision=?, body=? WHERE id=?",
                   (task["revision"], json.dumps(task), task_id))
        self.event(db, task_id, "checkpoint", dict(revision=task["revision"], changes=changes, note=note))
        return task

    def reserve_execution(self, task_id, job, checkpoint=None):
        """Commit the decision and its execution reservation before any subprocess starts."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if checkpoint is not None:
                if not isinstance(checkpoint, dict) or set(checkpoint) - {"expected_revision", "changes", "note"}:
                    raise ValueError("Invalid bundled checkpoint")
                task = self._checkpoint(db, task_id, **checkpoint)
            else:
                row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
                if row is None:
                    raise ValueError("Task not found")
                task = upgrade(json.loads(row[0]))
            job.update(task_revision=task["revision"])
            db.execute("INSERT INTO executions VALUES (?, ?, ?)", (job["id"], task_id, json.dumps(job)))
        return job

    def context(self, task_id):
        with self.connect() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise ValueError("Task not found")
            jobs = [json.loads(r[0]) for r in db.execute("SELECT body FROM executions WHERE task_id=? ORDER BY rowid", (task_id,))]
            return context(upgrade(json.loads(row[0])), jobs)

    def put_record(self, table, task_id, record):
        if table not in {"environments", "executions"}:
            raise ValueError("Invalid table")
        self.get(task_id)
        with self.connect() as db:
            db.execute(f"INSERT INTO {table} VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                       (record["id"], task_id, json.dumps(record)))

    def records(self, table, task_id):
        if table not in {"environments", "executions"}:
            raise ValueError("Invalid table")
        self.get(task_id)
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(f"SELECT body FROM {table} WHERE task_id=? ORDER BY rowid", (task_id,))]

    def update_execution(self, task_id, execution_id, changes, only_if_status=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM executions WHERE id=? AND task_id=?", (execution_id, task_id)).fetchone()
            if row is None:
                raise ValueError("Execution not found")
            record = json.loads(row[0])
            if only_if_status is not None and record["status"] not in only_if_status:
                return
            record.update(changes)
            db.execute("UPDATE executions SET body=? WHERE id=?", (json.dumps(record), execution_id))

    def record(self, table, task_id, record_id):
        for record in self.records(table, task_id):
            if record["id"] == record_id:
                return record
        raise ValueError("Record does not belong to this task")

    def events(self, task_id, after=0, limit=50):
        self.get(task_id)
        with self.connect() as db:
            return [dict(sequence=row[0], **json.loads(row[1])) for row in db.execute(
                "SELECT sequence, body FROM events WHERE task_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (task_id, after, max(1, min(limit, 200))))]

    def save_file(self, task_id, name, content):
        self.get(task_id)
        if not isinstance(content, str) or len(content.encode()) > 2_000_000:
            raise ValueError("Accepted text files must be at most 2 MB")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."}:
            raise ValueError("Use a simple filename")
        data = content.encode()
        digest = hashlib.sha256(data).hexdigest()
        path = self.directory(task_id) / "accepted" / digest / name
        path.parent.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise ValueError("Accepted file content mismatch")
        finally:
            temporary.unlink(missing_ok=True)
        return dict(path=str(path), sha256=digest, name=name)
