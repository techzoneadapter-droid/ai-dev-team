from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Role(str, Enum):
    DEVELOPER = "Developer"
    REVIEWER = "Reviewer"
    TESTER = "Tester"


class AgentStatus(str, Enum):
    WAITING = "Waiting"
    ACTIVE = "Active"
    PASSED = "Passed"
    FAILED = "Failed"
    DONE = "Done"


class TaskStatus(str, Enum):
    IN_PROGRESS = "In Progress"
    DONE = "Done"


class Outcome(str, Enum):
    SUBMITTED = "Submitted"
    PASS = "Pass"
    FAIL = "Fail"


@dataclass
class BrowserProfile:
    role: Role
    browser_exe: str
    profile_dir: str
    url: str = "https://chatgpt.com/"


@dataclass
class TaskRecord:
    id: int
    project_id: int
    title: str
    task_text: str
    current_role: Role
    iteration: int
    status: TaskStatus
    created_at: str
    updated_at: str


@dataclass
class ResultRecord:
    id: int
    task_id: int
    role: Role
    iteration: int
    outcome: Outcome
    result_text: str
    created_at: str


@dataclass
class ActivityRecord:
    id: int
    task_id: int
    role: Optional[Role]
    iteration: int
    action: str
    detail: str
    created_at: str
