from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .models import ActivityRecord, Outcome, ResultRecord, Role, TaskRecord, TaskStatus


def default_db_path() -> Path:
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    root = Path(base) / "AI Dev Team"
    root.mkdir(parents=True, exist_ok=True)
    return root / "aidevteam.db"


class Database:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or default_db_path()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS browser_profiles (
                role TEXT PRIMARY KEY,
                browser_exe TEXT NOT NULL DEFAULT '',
                profile_dir TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT 'https://chatgpt.com/'
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                task_text TEXT NOT NULL,
                current_role TEXT NOT NULL,
                iteration INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                result_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                role TEXT,
                iteration INTEGER NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()
        self.ensure_default_profiles()

    def ensure_default_profiles(self) -> None:
        for role in Role:
            self.conn.execute(
                "INSERT OR IGNORE INTO browser_profiles(role, browser_exe, profile_dir, url) VALUES(?,?,?,?)",
                (role.value, "", "", "https://chatgpt.com/"),
            )
        self.conn.commit()

    def list_projects(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM projects ORDER BY name COLLATE NOCASE"))

    def create_project(self, name: str) -> int:
        cur = self.conn.execute("INSERT INTO projects(name) VALUES(?)", (name.strip(),))
        self.conn.commit()
        return int(cur.lastrowid)

    def get_profile(self, role: Role) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM browser_profiles WHERE role=?", (role.value,)).fetchone()
        assert row is not None
        return row

    def save_profile(self, role: Role, browser_exe: str, profile_dir: str, url: str) -> None:
        self.conn.execute(
            "UPDATE browser_profiles SET browser_exe=?, profile_dir=?, url=? WHERE role=?",
            (browser_exe.strip(), profile_dir.strip(), url.strip() or "https://chatgpt.com/", role.value),
        )
        self.conn.commit()

    def create_task(self, project_id: int, title: str, task_text: str) -> int:
        cur = self.conn.execute(
            """INSERT INTO tasks(project_id,title,task_text,current_role,iteration,status)
               VALUES(?,?,?,?,?,?)""",
            (project_id, title.strip(), task_text.strip(), Role.DEVELOPER.value, 1, TaskStatus.IN_PROGRESS.value),
        )
        task_id = int(cur.lastrowid)
        self.conn.execute(
            "INSERT INTO activity(task_id,role,iteration,action,detail) VALUES(?,?,?,?,?)",
            (task_id, Role.DEVELOPER.value, 1, "Task created", "Developer activated"),
        )
        self.conn.commit()
        return task_id

    def list_tasks(self, project_id: int) -> list[TaskRecord]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE project_id=? ORDER BY id DESC", (project_id,)
        ).fetchall()
        return [self._task_from_row(r) for r in rows]

    def get_task(self, task_id: int) -> TaskRecord:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._task_from_row(row)

    def update_task_state(self, task_id: int, current_role: Role, iteration: int, status: TaskStatus) -> None:
        self.conn.execute(
            """UPDATE tasks SET current_role=?, iteration=?, status=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (current_role.value, iteration, status.value, task_id),
        )
        self.conn.commit()

    def add_result(self, task_id: int, role: Role, iteration: int, outcome: Outcome, text: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO results(task_id,role,iteration,outcome,result_text) VALUES(?,?,?,?,?)",
            (task_id, role.value, iteration, outcome.value, text.strip()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_results(self, task_id: int) -> list[ResultRecord]:
        rows = self.conn.execute(
            "SELECT * FROM results WHERE task_id=? ORDER BY id ASC", (task_id,)
        ).fetchall()
        return [
            ResultRecord(
                id=r["id"], task_id=r["task_id"], role=Role(r["role"]), iteration=r["iteration"],
                outcome=Outcome(r["outcome"]), result_text=r["result_text"], created_at=r["created_at"]
            )
            for r in rows
        ]

    def latest_result(self, task_id: int, role: Optional[Role] = None) -> Optional[ResultRecord]:
        if role:
            row = self.conn.execute(
                "SELECT * FROM results WHERE task_id=? AND role=? ORDER BY id DESC LIMIT 1",
                (task_id, role.value),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM results WHERE task_id=? ORDER BY id DESC LIMIT 1", (task_id,)
            ).fetchone()
        if row is None:
            return None
        return ResultRecord(
            id=row["id"], task_id=row["task_id"], role=Role(row["role"]), iteration=row["iteration"],
            outcome=Outcome(row["outcome"]), result_text=row["result_text"], created_at=row["created_at"]
        )

    def add_activity(self, task_id: int, role: Optional[Role], iteration: int, action: str, detail: str = "") -> None:
        self.conn.execute(
            "INSERT INTO activity(task_id,role,iteration,action,detail) VALUES(?,?,?,?,?)",
            (task_id, role.value if role else None, iteration, action, detail),
        )
        self.conn.commit()

    def list_activity(self, task_id: int) -> list[ActivityRecord]:
        rows = self.conn.execute(
            "SELECT * FROM activity WHERE task_id=? ORDER BY id DESC", (task_id,)
        ).fetchall()
        return [
            ActivityRecord(
                id=r["id"], task_id=r["task_id"], role=Role(r["role"]) if r["role"] else None,
                iteration=r["iteration"], action=r["action"], detail=r["detail"], created_at=r["created_at"]
            )
            for r in rows
        ]

    @staticmethod
    def _task_from_row(r: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=r["id"], project_id=r["project_id"], title=r["title"], task_text=r["task_text"],
            current_role=Role(r["current_role"]), iteration=r["iteration"], status=TaskStatus(r["status"]),
            created_at=r["created_at"], updated_at=r["updated_at"]
        )
