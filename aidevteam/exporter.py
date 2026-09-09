from __future__ import annotations

from pathlib import Path

from .db import Database


def export_task_markdown(db: Database, task_id: int, destination: Path) -> Path:
    task = db.get_task(task_id)
    project = db.get_project(task.project_id)
    lines = [
        f"# {task.title}",
        "",
        f"**Project:** {project.name}",
        f"**Status:** {task.status.value}",
        f"**Current role:** {task.current_role.value}",
        f"**Iteration:** {task.iteration}",
        f"**Created:** {task.created_at}",
        f"**Updated:** {task.updated_at}",
        "",
        "## Original task",
        "",
        task.task_text,
        "",
        "## Results / handoffs",
        "",
    ]
    results = db.list_results(task.id)
    if not results:
        lines.append("_No recorded results yet._")
    else:
        for result in results:
            lines.extend(
                [
                    f"### Iteration {result.iteration} — {result.role.value} — {result.outcome.value}",
                    "",
                    result.result_text,
                    "",
                ]
            )
    lines.extend(["## Activity", ""])
    for rec in reversed(db.list_activity(task.id)):
        role = rec.role.value if rec.role else "System"
        lines.append(f"- `{rec.created_at}` — Iteration {rec.iteration} — **{role}** — {rec.action}: {rec.detail}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return destination
