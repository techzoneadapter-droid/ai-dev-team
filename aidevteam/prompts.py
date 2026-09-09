from __future__ import annotations

from .models import Role, TaskRecord
from .db import Database


def build_prompt(db: Database, task: TaskRecord) -> str:
    results = db.list_results(task.id)
    recent = results[-6:]
    history = "\n\n".join(
        f"[{r.role.value} | iteration {r.iteration} | {r.outcome.value}]\n{r.result_text}"
        for r in recent
    ) or "(No previous results yet.)"

    common = f"""You are working inside a 3-agent software workflow called AI Dev Team.
Project task:
{task.task_text}

Current iteration: {task.iteration}
Current role: {task.current_role.value}

Recent workflow history:
{history}
"""

    if task.current_role == Role.DEVELOPER:
        return common + """
Your job as Developer:
1. Implement or revise the solution based on the task and any Reviewer/Tester feedback above.
2. Be concrete: provide changed files, code, commands, or implementation notes as appropriate.
3. Do not claim tests passed unless you actually verified them.
4. End with a compact handoff section named `HANDOFF TO REVIEWER` containing:
   - what changed
   - files/components touched
   - known risks or TODOs
   - how to verify
Return only the work product and handoff; avoid unrelated commentary.
"""

    if task.current_role == Role.REVIEWER:
        return common + """
Your job as Reviewer:
1. Review the Developer output for correctness, maintainability, security, edge cases, and fit to the requested scope.
2. Identify blocking issues separately from optional improvements.
3. Decide PASS only if the work is good enough to proceed to testing.
4. Your first line MUST be exactly `PASS` or `FAIL`.
5. If FAIL, provide precise fix instructions for the Developer. If PASS, provide a concise test focus for the Tester.
"""

    return common + """
Your job as Tester:
1. Validate the proposed implementation against the original task and Reviewer guidance.
2. Focus on reproducible checks, likely regressions, failure modes, and Windows usability where relevant.
3. Your first line MUST be exactly `PASS` or `FAIL`.
4. If FAIL, provide exact reproduction steps, expected vs actual behavior, and what Developer should fix.
5. If PASS, summarize the verification performed and any non-blocking caveats.
"""
