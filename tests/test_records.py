import concurrent.futures
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from store import Store
from runtime import Runtime
from server import Server


class RecordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = Store(temporary.name)
        self.task = self.store.create({"project": "example", "targets": ["server", "agent"]})
        self.task_id = self.task["id"]

    def checkpoint(self, changes):
        return self.store.checkpoint(self.task_id, self.store.get(self.task_id)["revision"], changes)

    def execution(self, suffix="a", status="FAILED"):
        job = dict(id="exec-" + suffix * 32, status=status, exit_code=1, ended_at="now")
        return self.store.reserve_execution(self.task_id, job)

    def test_historical_graph_does_not_gate_resume_or_lose_evidence(self):
        original = dict(self.task, nodes={"asset": {"facts": ["validated archive"], "dependencies": ["missing"]}},
                        focus_stack=["missing"], status="WAITING_FOR_USER",
                        waiting=dict(node_id="missing", need="archive", reason="external build",
                                     validation=["version"], resume_at="package image"))
        with self.store.connect() as db:
            db.execute("UPDATE tasks SET body=? WHERE id=?", (json.dumps(original), self.task_id))
        self.assertTrue(self.store.context(self.task_id)["legacy_notes_available"])
        self.assertEqual(self.store.get(self.task_id), original)
        saved = self.checkpoint({"status": "ACTIVE", "waiting": None,
                                 "resources": [{"artifact": "archive", "evidence": "validated"}]})
        self.assertEqual(saved["nodes"], original["nodes"])
        self.assertEqual(saved["focus_stack"], original["focus_stack"])
        job = self.execution()
        self.assertNotIn("node_id", job)
        self.assertEqual(self.store.context(self.task_id)["resources"], saved["resources"])

    def test_failed_reservation_rolls_back_bundled_checkpoint(self):
        job = self.execution()
        before = self.store.get(self.task_id)
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.reserve_execution(self.task_id, dict(job), checkpoint=dict(
                expected_revision=1, changes={"checkpoint": {"next": "must roll back"}}))
        self.assertEqual(self.store.get(self.task_id), before)
        self.assertEqual(len(self.store.events(self.task_id)), 1)

    def test_finished_results_remain_pending_until_interpreted(self):
        first = self.execution()
        second = self.execution("b", "SUCCEEDED")
        server = Server(self.store)
        read = server.call("task_open", {"action": "get", "task_id": self.task_id})
        self.assertEqual(read["context"]["unreviewed_count"], 2)
        self.checkpoint({"execution_reviews": {first["id"]: "Missing prerequisite; tracked under root issue"}})
        self.assertEqual(self.store.context(self.task_id)["unreviewed"][0]["id"], second["id"])
        self.assertEqual(self.store.get(self.task_id)["status"], "ACTIVE")
        self.assertEqual(self.store.get(self.task_id)["resources"], [])
        self.store.update_execution(self.task_id, first["id"], {"status": "UNKNOWN"})
        self.assertEqual(self.store.context(self.task_id)["unreviewed_count"], 2)

    def test_review_rejects_running_or_foreign_execution_without_losing_notes(self):
        job = self.execution(status="RUNNING")
        for key in (job["id"], "exec-" + "f" * 32):
            with self.assertRaises(ValueError):
                self.checkpoint(dict(checkpoint={"issue": "must roll back"}, execution_reviews={key: "done"}))
            self.assertEqual(self.store.get(self.task_id)["checkpoint"], {})

    def test_idempotent_bundled_launch_does_not_apply_checkpoint_twice(self):
        runtime = Runtime(self.store)
        bundled = dict(expected_revision=1, changes={"checkpoint": {"next": "build asset"}})
        # Force a launcher failure after reservation; the retry must return that record, not relaunch.
        with patch("runtime.subprocess.Popen", side_effect=OSError("test launcher unavailable")) as popen:
            first = runtime.launch(self.task_id, ["test"], "stable-key", checkpoint=bundled)
            self.checkpoint({"checkpoint": {"next": "inspect result"}})
            second = runtime.launch(self.task_id, ["test"], "stable-key", checkpoint=bundled)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["task_revision"], 2)
        self.assertEqual(self.store.get(self.task_id)["revision"], 3)

    def test_stale_bundled_revision_never_launches(self):
        self.checkpoint({"checkpoint": {"next": "prepare"}})
        with patch("runtime.subprocess.Popen") as popen:
            with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
                Runtime(self.store).launch(self.task_id, ["test"], "stale", checkpoint=dict(expected_revision=1, changes={}))
        popen.assert_not_called()
        self.assertEqual(self.store.records("executions", self.task_id), [])

    def test_parallel_checkpoint_edits_conflict_instead_of_overwriting(self):
        self.checkpoint({"checkpoint": {"next": "prepare"}})
        revision = self.store.get(self.task_id)["revision"]
        def update(key):
            try:
                self.store.checkpoint(self.task_id, revision, {"checkpoint": {"issue": key}})
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(update, ["server", "agent"])), 1)

    def test_pending_context_is_bounded_and_read_only(self):
        for index in range(15):
            self.store.reserve_execution(self.task_id, dict(id=f"exec-{index:032x}", status="FAILED"))
        before = self.store.get(self.task_id)
        context = Server(self.store).call("task_context", {"task_id": self.task_id})
        self.assertEqual(context["unreviewed_count"], 15)
        self.assertEqual(len(context["unreviewed"]), 10)
        self.assertEqual(self.store.get(self.task_id), before)

    def test_context_previews_do_not_truncate_persisted_facts(self):
        facts = [{"evidence": "x" * 1200} for _ in range(12)]
        self.checkpoint({"resources": facts})
        context = self.store.context(self.task_id)
        self.assertEqual(context["resources"][-1], {"omitted_items": 7})
        self.assertIn("truncated", context["resources"][0]["evidence"])
        self.assertEqual(self.store.get(self.task_id)["resources"], facts)

    def test_lost_worker_update_cannot_overwrite_completed_result(self):
        job = self.execution(status="SUCCEEDED")
        self.store.update_execution(self.task_id, job["id"], {"status": "UNKNOWN"},
                                    only_if_status={"STARTING", "RUNNING"})
        self.assertEqual(self.store.record("executions", self.task_id, job["id"])["status"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
