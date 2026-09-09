from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

from .models import ActivityRecord, Outcome, ProjectRecord, ResultRecord, Role, TaskRecord, TaskStatus


APP_DIR_NAME = "AI Dev Team"


def app_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    root = Path(base) / APP_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_db_path() -> Path:
    return app_data_dir() / "aidevteam.db"


class Database:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
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

            CREATE TABLE IF NOT EXISTS agent_settings (
                role TEXT PRIMARY KEY,
                custom_instruction TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._ensure_column("projects", "description", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("projects", "workspace_path", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("projects", "repo_url", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("projects", "updated_at", "TEXT NOT NULL DEFAULT ''")
        self.conn.execute("UPDATE projects SET updated_at=created_at WHERE updated_at='' OR updated_at IS NULL")
        self.conn.commit()
        self.ensure_defaults()

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        names = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
        if column not in names:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def ensure_defaults(self) -> None:
        for role in Role:
            self.conn.execute(
                "INSERT OR IGNORE INTO browser_profiles(role, browser_exe, profile_dir, url) VALUES(?,?,?,?)",
                (role.value, "", "", "https://chatgpt.com/"),
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO agent_settings(role, custom_instruction) VALUES(?, '')",
                (role.value,),
            )
        defaults = {
            "history_limit": "8",
            "auto_copy_on_transition": "false",
            "auto_open_on_transition": "false",
        }
        for key, value in defaults.items():
            self.conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
        self.conn.commit()

    def list_projects(self) -> list[ProjectRecord]:
        rows = self.conn.execute("SELECT * FROM projects ORDER BY name COLLATE NOCASE").fetchall()
        return [self._project_from_row(r) for r in rows]

    def get_project(self, project_id: int) -> ProjectRecord:
        row = self.conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return self._project_from_row(row)

    def create_project(self, name: str, description: str = "", workspace_path: str = "", repo_url: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO projects(name,description,workspace_path,repo_url,updated_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",
            (name.strip(), description.strip(), workspace_path.strip(), repo_url.strip()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_project(self, project_id: int, name: str, description: str = "", workspace_path: str = "", repo_url: str = "") -> None:
        self.conn.execute(
            """UPDATE projects
               SET name=?, description=?, workspace_path=?, repo_url=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (name.strip(), description.strip(), workspace_path.strip(), repo_url.strip(), project_id),
        )
        self.conn.commit()

    def delete_project(self, project_id: int) -> None:
        self.conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        self.conn.commit()

    def get_profile(self, role: Role) -> sqlite3.Row:
        row = self.conn.execute(
            """SELECT bp.*, COALESCE(a.custom_instruction, '') AS custom_instruction
               FROM browser_profiles bp
               LEFT JOIN agent_settings a ON a.role=bp.role
               WHERE bp.role=?""",
            (role.value,),
        ).fetchone()
        assert row is not None
        return row

    def save_profile(self, role: Role, browser_exe: str, profile_dir: str, url: str, custom_instruction: str = "") -> None:
        self.conn.execute(
            "UPDATE browser_profiles SET browser_exe=?, profile_dir=?, url=? WHERE role=?",
            (browser_exe.strip(), profile_dir.strip(), url.strip() or "https://chatgpt.com/", role.value),
        )
        self.conn.execute(
            """INSERT INTO agent_settings(role,custom_instruction) VALUES(?,?)
               ON CONFLICT(role) DO UPDATE SET custom_instruction=excluded.custom_instruction""",
            (role.value, custom_instruction.strip()),
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

    def update_task_content(self, task_id: int, title: str, task_text: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET title=?, task_text=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (title.strip(), task_text.strip(), task_id),
        )
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def list_tasks(self, project_id: int) -> list[TaskRecord]:
        rows = self.conn.execute("SELECT * FROM tasks WHERE project_id=? ORDER BY id DESC", (project_id,)).fetchall()
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

    def reopen_task(self, task_id: int) -> TaskRecord:
        task = self.get_task(task_id)
        next_iteration = task.iteration + 1
        self.update_task_state(task_id, Role.DEVELOPER, next_iteration, TaskStatus.IN_PROGRESS)
        self.add_activity(task_id, Role.DEVELOPER, next_iteration, "Task reopened", "Returned to Developer")
        return self.get_task(task_id)

    def add_result(self, task_id: int, role: Role, iteration: int, outcome: Outcome, text: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO results(task_id,role,iteration,outcome,result_text) VALUES(?,?,?,?,?)",
            (task_id, role.value, iteration, outcome.value, text.strip()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_results(self, task_id: int) -> list[ResultRecord]:
        rows = self.conn.execute("SELECT * FROM results WHERE task_id=? ORDER BY id ASC", (task_id,)).fetchall()
        return [self._result_from_row(r) for r in rows]

    def latest_result(self, task_id: int, role: Optional[Role] = None) -> Optional[ResultRecord]:
        if role:
            row = self.conn.execute(
                "SELECT * FROM results WHERE task_id=? AND role=? ORDER BY id DESC LIMIT 1",
                (task_id, role.value),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT * FROM results WHERE task_id=? ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
        return self._result_from_row(row) if row else None

    def add_activity(self, task_id: int, role: Optional[Role], iteration: int, action: str, detail: str = "") -> None:
        self.conn.execute(
            "INSERT INTO activity(task_id,role,iteration,action,detail) VALUES(?,?,?,?,?)",
            (task_id, role.value if role else None, iteration, action, detail),
        )
        self.conn.commit()

    def list_activity(self, task_id: int) -> list[ActivityRecord]:
        rows = self.conn.execute("SELECT * FROM activity WHERE task_id=? ORDER BY id DESC", (task_id,)).fetchall()
        return [
            ActivityRecord(
                id=r["id"], task_id=r["task_id"], role=Role(r["role"]) if r["role"] else None,
                iteration=r["iteration"], action=r["action"], detail=r["detail"], created_at=r["created_at"],
            ) for r in rows
        ]

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """INSERT INTO settings(key,value) VALUES(?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, str(value)),
        )
        self.conn.commit()

    def history_limit(self) -> int:
        try:
            return max(1, min(50, int(self.get_setting("history_limit", "8"))))
        except ValueError:
            return 8

    def bool_setting(self, key: str, default: bool = False) -> bool:
        raw = self.get_setting(key, "true" if default else "false").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def backup_to(self, destination: Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup_conn = sqlite3.connect(destination)
        try:
            self.conn.backup(backup_conn)
        finally:
            backup_conn.close()
        return destination

    def portable_snapshot(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        tasks = self.list_tasks(project_id)
        return {
            "format": "AI Dev Team portable project",
            "version": 1,
            "project": {
                "name": project.name, "description": project.description, "workspace_path": project.workspace_path,
                "repo_url": project.repo_url, "created_at": project.created_at, "updated_at": project.updated_at,
            },
            "tasks": [
                {
                    "title": task.title, "task_text": task.task_text, "current_role": task.current_role.value,
                    "iteration": task.iteration, "status": task.status.value, "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "results": [
                        {"role": r.role.value, "iteration": r.iteration, "outcome": r.outcome.value,
                         "result_text": r.result_text, "created_at": r.created_at}
                        for r in self.list_results(task.id)
                    ],
                    "activity": [
                        {"role": a.role.value if a.role else None, "iteration": a.iteration, "action": a.action,
                         "detail": a.detail, "created_at": a.created_at}
                        for a in reversed(self.list_activity(task.id))
                    ],
                } for task in tasks
            ],
        }

    def export_project_json(self, project_id: int, destination: Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.portable_snapshot(project_id), indent=2, ensure_ascii=False), encoding="utf-8")
        return destination

    @staticmethod
    def _project_from_row(r: sqlite3.Row) -> ProjectRecord:
        return ProjectRecord(
            id=r["id"], name=r["name"], description=r["description"] if "description" in r.keys() else "",
            workspace_path=r["workspace_path"] if "workspace_path" in r.keys() else "",
            repo_url=r["repo_url"] if "repo_url" in r.keys() else "", created_at=r["created_at"],
            updated_at=(r["updated_at"] if "updated_at" in r.keys() else r["created_at"]) or r["created_at"],
        )

    @staticmethod
    def _task_from_row(r: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=r["id"], project_id=r["project_id"], title=r["title"], task_text=r["task_text"],
            current_role=Role(r["current_role"]), iteration=r["iteration"], status=TaskStatus(r["status"]),
            created_at=r["created_at"], updated_at=r["updated_at"],
        )

    @staticmethod
    def _result_from_row(r: sqlite3.Row) -> ResultRecord:
        return ResultRecord(
            id=r["id"], task_id=r["task_id"], role=Role(r["role"]), iteration=r["iteration"],
            outcome=Outcome(r["outcome"]), result_text=r["result_text"], created_at=r["created_at"],
        )
