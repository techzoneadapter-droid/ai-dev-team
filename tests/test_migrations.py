import sqlite3
import tempfile
import unittest
from pathlib import Path

from aidevteam.db import Database


class MigrationTests(unittest.TestCase):
    def test_old_mvp_database_is_upgraded(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.db"
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE browser_profiles (role TEXT PRIMARY KEY, browser_exe TEXT NOT NULL DEFAULT '', profile_dir TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT 'https://chatgpt.com/');
                CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, title TEXT NOT NULL, task_text TEXT NOT NULL, current_role TEXT NOT NULL, iteration INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE results (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, role TEXT NOT NULL, iteration INTEGER NOT NULL, outcome TEXT NOT NULL, result_text TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE activity (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, role TEXT, iteration INTEGER NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO projects(name) VALUES('Legacy');
                """
            )
            conn.commit()
            conn.close()
            db = Database(path)
            try:
                project = db.list_projects()[0]
                self.assertEqual(project.name, "Legacy")
                self.assertEqual(project.description, "")
                self.assertEqual(db.get_setting("history_limit"), "8")
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
