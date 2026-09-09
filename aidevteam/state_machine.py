from __future__ import annotations

from dataclasses import dataclass

from .models import Outcome, Role, TaskStatus


@dataclass(frozen=True)
class Transition:
    next_role: Role
    next_iteration: int
    task_status: TaskStatus
    detail: str


def transition(role: Role, iteration: int, outcome: Outcome) -> Transition:
    if role == Role.DEVELOPER:
        return Transition(Role.REVIEWER, iteration, TaskStatus.IN_PROGRESS, "Developer submitted work → Reviewer")

    if role == Role.REVIEWER:
        if outcome == Outcome.PASS:
            return Transition(Role.TESTER, iteration, TaskStatus.IN_PROGRESS, "Reviewer PASS → Tester")
        if outcome == Outcome.FAIL:
            return Transition(Role.DEVELOPER, iteration + 1, TaskStatus.IN_PROGRESS, "Reviewer FAIL → Developer revision")
        raise ValueError("Reviewer result must be Pass or Fail")

    if role == Role.TESTER:
        if outcome == Outcome.PASS:
            return Transition(Role.TESTER, iteration, TaskStatus.DONE, "Tester PASS → Done")
        if outcome == Outcome.FAIL:
            return Transition(Role.DEVELOPER, iteration + 1, TaskStatus.IN_PROGRESS, "Tester FAIL → Developer revision")
        raise ValueError("Tester result must be Pass or Fail")

    raise ValueError(f"Unsupported role: {role}")
