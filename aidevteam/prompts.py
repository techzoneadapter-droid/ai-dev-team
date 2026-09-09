from __future__ import annotations

import re

from .db import Database
from .models import Outcome, Role, TaskRecord


_OUTCOME_RE = re.compile(r"^\s*(PASS|FAIL)\b", re.IGNORECASE)


def detect_outcome(text: str, role: Role) -> Outcome | None:
    if role == Role.DEVELOPER:
        return Outcome.SUBMITTED if text.strip() else None
    match = _OUTCOME_RE.match(text or "")
    if not match:
        return None
    return Outcome.PASS if match.group(1).upper() == "PASS" else Outcome.FAIL


def build_prompt(db: Database, task: TaskRecord) -> str:
    results = db.list_results(task.id)
    recent = results[-db.history_limit():]
    history = "\n\n".join(
        f"[{r.role.value} | iteration {r.iteration} | {r.outcome.value}]\n{r.result_text}"
        for r in recent
    ) or "(No previous results yet.)"

    project = db.get_project(task.project_id)
    profile = db.get_profile(task.current_role)
    custom = (profile["custom_instruction"] or "").strip()
    project_context = []
    if project.workspace_path:
        project_context.append(f"Local workspace: {project.workspace_path}")
    if project.repo_url:
        project_context.append(f"Repository: {project.repo_url}")
    if project.description:
        project_context.append(f"Project notes: {project.description}")

    common = f"""You are one member of a 3-agent software workflow called AI Dev Team.

PROJECT
Name: {project.name}
{chr(10).join(project_context) if project_context else '(No extra project metadata.)'}

TASK
Title: {task.title}
Original request:
{task.task_text}

WORKFLOW STATE
Iteration: {task.iteration}
Current role: {task.current_role.value}

RECENT HANDOFF HISTORY
{history}
"""

    if custom:
        common += f"\nROLE-SPECIFIC USER INSTRUCTION\n{custom}\n"

    if task.current_role == Role.DEVELOPER:
        return common + """
YOUR JOB — DEVELOPER
1. Implement or revise the solution based on the original request and the latest Reviewer/Tester feedback.
2. Treat blocking feedback as requirements for this iteration.
3. Be concrete: provide changed files, code, commands, patch notes, or implementation steps as appropriate.
4. Preserve working behavior outside the requested scope and avoid unrelated rewrites.
5. Do not claim tests passed unless you actually verified them.
6. End with a section exactly named `HANDOFF TO REVIEWER` containing:
   - What changed
   - Files/components touched
   - Verification performed
   - Known risks/TODOs
Return the work product and handoff without unrelated commentary.
"""

    if task.current_role == Role.REVIEWER:
        return common + """
YOUR JOB — REVIEWER
1. Review the Developer output against the original request and current iteration feedback.
2. Check correctness, maintainability, security, edge cases, regressions, and whether the implementation is actually actionable.
3. Separate blocking issues from optional improvements.
4. Your FIRST non-empty line MUST be exactly `PASS` or `FAIL`.
5. PASS only when the work is ready for Tester.
6. If FAIL, give precise fix instructions that Developer can execute next iteration.
7. If PASS, include a compact `TEST FOCUS` section for Tester.
"""

    return common + """
YOUR JOB — TESTER
1. Validate the implementation against the original task and Reviewer guidance.
2. Focus on reproducible checks, likely regressions, failure modes, and Windows usability where relevant.
3. Your FIRST non-empty line MUST be exactly `PASS` or `FAIL`.
4. If FAIL, provide exact reproduction steps, expected vs actual behavior, severity, and what Developer should fix.
5. If PASS, summarize verification performed and list only non-blocking caveats.
"""
