from __future__ import annotations

from dataclasses import dataclass

from .models import Outcome, Role, TaskStatus


@dataclass(frozen=True)
class Transition:
    next_role: Role
    next_iteration: int
    task_status: TaskStatus
    detail: str


def allowed_outcomes(role: Role, status: TaskStatus = TaskStatus.IN_PROGRESS) -> tuple[Outcome, ...]:
    if status == TaskStatus.DONE:
        return ()
    if role == Role.DEVELOPER:
        return (Outcome.SUBMITTED,)
    return (Outcome.PASS, Outcome.FAIL)


def transition(role: Role, iteration: int, outcome: Outcome) -> Transition:
    if iteration < 1:
        raise ValueError("Iteration must be >= 1")
    if outcome not in allowed_outcomes(role):
        expected = ", ".join(o.value for o in allowed_outcomes(role))
        raise ValueError(f"{role.value} outcome must be: {expected}")

    if role == Role.DEVELOPER:
        return Transition(Role.REVIEWER, iteration, TaskStatus.IN_PROGRESS, "Developer submitted work → Reviewer")

    if role == Role.REVIEWER:
        if outcome == Outcome.PASS:
            return Transition(Role.TESTER, iteration, TaskStatus.IN_PROGRESS, "Reviewer PASS → Tester")
        return Transition(Role.DEVELOPER, iteration + 1, TaskStatus.IN_PROGRESS, "Reviewer FAIL → Developer revision")

    if role == Role.TESTER:
        if outcome == Outcome.PASS:
            return Transition(Role.TESTER, iteration, TaskStatus.DONE, "Tester PASS → Done")
        return Transition(Role.DEVELOPER, iteration + 1, TaskStatus.IN_PROGRESS, "Tester FAIL → Developer revision")

    raise ValueError(f"Unsupported role: {role}")
