import tempfile
import unittest
from pathlib import Path

from aidevteam.db import Database
from aidevteam.models import Outcome, Role, TaskStatus
from aidevteam.prompts import build_prompt
from aidevteam.state_machine import transition


class CoreWorkflowTests(unittest.TestCase):
    def test_fail_loop_and_done(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "test.db")
            project_id = db.create_project("Test")
            task_id = db.create_task(project_id, "Demo", "Build a calculator")
            task = db.get_task(task_id)
            self.assertEqual(task.current_role, Role.DEVELOPER)
            self.assertIn("HANDOFF TO REVIEWER", build_prompt(db, task))

            dev = transition(Role.DEVELOPER, 1, Outcome.SUBMITTED)
            self.assertEqual(dev.next_role, Role.REVIEWER)

            fail = transition(Role.REVIEWER, 1, Outcome.FAIL)
            self.assertEqual((fail.next_role, fail.next_iteration), (Role.DEVELOPER, 2))

            review_pass = transition(Role.REVIEWER, 2, Outcome.PASS)
            self.assertEqual(review_pass.next_role, Role.TESTER)

            done = transition(Role.TESTER, 2, Outcome.PASS)
            self.assertEqual(done.task_status, TaskStatus.DONE)
            db.close()


if __name__ == "__main__":
    unittest.main()
