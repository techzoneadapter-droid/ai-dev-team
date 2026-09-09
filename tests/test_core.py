import json
import tempfile
import unittest
from pathlib import Path

from aidevteam.db import Database
from aidevteam.exporter import export_task_markdown
from aidevteam.models import Outcome, Role, TaskStatus
from aidevteam.prompts import build_prompt, detect_outcome
from aidevteam.services.browser_service import build_launch_command, validate_chat_url
from aidevteam.state_machine import allowed_outcomes, transition


class CoreWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.db")
        self.project_id = self.db.create_project("Test", "Notes", r"C:\\work", "https://github.com/example/repo")
        self.task_id = self.db.create_task(self.project_id, "Demo", "Build a calculator")

    def tearDown(self):
        self.db.close()
        self.tempdir.cleanup()

    def test_fail_loop_and_done(self):
        task = self.db.get_task(self.task_id)
        self.assertEqual(task.current_role, Role.DEVELOPER)
        self.assertIn("HANDOFF TO REVIEWER", build_prompt(self.db, task))
        dev = transition(Role.DEVELOPER, 1, Outcome.SUBMITTED)
        self.assertEqual(dev.next_role, Role.REVIEWER)
        fail = transition(Role.REVIEWER, 1, Outcome.FAIL)
        self.assertEqual((fail.next_role, fail.next_iteration), (Role.DEVELOPER, 2))
        review_pass = transition(Role.REVIEWER, 2, Outcome.PASS)
        self.assertEqual(review_pass.next_role, Role.TESTER)
        done = transition(Role.TESTER, 2, Outcome.PASS)
        self.assertEqual(done.task_status, TaskStatus.DONE)

    def test_outcome_validation(self):
        self.assertEqual(allowed_outcomes(Role.DEVELOPER), (Outcome.SUBMITTED,))
        with self.assertRaises(ValueError):
            transition(Role.REVIEWER, 1, Outcome.SUBMITTED)
        with self.assertRaises(ValueError):
            transition(Role.DEVELOPER, 0, Outcome.SUBMITTED)

    def test_detect_outcome(self):
        self.assertEqual(detect_outcome("PASS\nLooks good", Role.REVIEWER), Outcome.PASS)
        self.assertEqual(detect_outcome("  fail - broken", Role.TESTER), Outcome.FAIL)
        self.assertIsNone(detect_outcome("Looks okay", Role.REVIEWER))
        self.assertEqual(detect_outcome("some implementation", Role.DEVELOPER), Outcome.SUBMITTED)

    def test_custom_instruction_is_in_prompt(self):
        self.db.save_profile(Role.DEVELOPER, "", "Profile 1", "https://chatgpt.com/", "Use Python 3.12")
        prompt = build_prompt(self.db, self.db.get_task(self.task_id))
        self.assertIn("Use Python 3.12", prompt)
        self.assertIn("https://github.com/example/repo", prompt)

    def test_project_export_and_task_markdown(self):
        self.db.add_result(self.task_id, Role.DEVELOPER, 1, Outcome.SUBMITTED, "Implemented it")
        json_path = Path(self.tempdir.name) / "project.json"
        md_path = Path(self.tempdir.name) / "task.md"
        self.db.export_project_json(self.project_id, json_path)
        export_task_markdown(self.db, self.task_id, md_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["project"]["name"], "Test")
        self.assertEqual(payload["tasks"][0]["results"][0]["result_text"], "Implemented it")
        self.assertIn("Implemented it", md_path.read_text(encoding="utf-8"))

    def test_reopen_completed_task(self):
        self.db.update_task_state(self.task_id, Role.TESTER, 3, TaskStatus.DONE)
        reopened = self.db.reopen_task(self.task_id)
        self.assertEqual(reopened.current_role, Role.DEVELOPER)
        self.assertEqual(reopened.iteration, 4)
        self.assertEqual(reopened.status, TaskStatus.IN_PROGRESS)

    def test_backup(self):
        backup = Path(self.tempdir.name) / "backup.db"
        self.db.backup_to(backup)
        self.assertTrue(backup.exists())
        clone = Database(backup)
        try:
            self.assertEqual(clone.get_project(self.project_id).name, "Test")
        finally:
            clone.close()

    def test_browser_command_and_url_validation(self):
        fake = Path(self.tempdir.name) / "chrome.exe"
        fake.write_text("fake", encoding="utf-8")
        cmd = build_launch_command(str(fake), "Profile 2", "https://chatgpt.com/")
        self.assertIn("--profile-directory=Profile 2", cmd)
        self.assertEqual(cmd[-1], "https://chatgpt.com/")
        with self.assertRaises(ValueError):
            validate_chat_url("javascript:alert(1)")


if __name__ == "__main__":
    unittest.main()
