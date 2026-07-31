"""Guardrails: validate the AI planner's output before the system trusts it.

Large language models can make mistakes: inventing a pet you do not own,
returning a negative duration, or a nonsense time like "25:99". This module
checks each task the planner produced, keeps only the valid ones, and returns
clear warnings about anything it rejected.

Field-level rules (duration > 0, valid time, valid priority, ...) live in the
Task class (Task.__post_init__), so the app and the AI share one set of rules.
Here we add the checks that are specific to AI output: correct shape and no
invented pets.
"""

from pawpal_system import Task

# Every task dict the AI returns must contain these keys.
REQUIRED_FIELDS = ("pet", "description", "duration", "due_time", "priority", "frequency")


def validate_tasks(raw_tasks, pet_names: list) -> tuple:
    """Turn raw AI task dicts into validated Tasks, reporting what was rejected.

    Returns (accepted, warnings):
      accepted = list of (pet_name, Task) pairs that passed every check
      warnings = list of plain-language strings describing rejected tasks
    """
    accepted = []
    warnings = []

    if not isinstance(raw_tasks, list):
        return [], ["The AI did not return a list of tasks."]

    for index, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Task {index}: not a task object, skipped.")
            continue

        missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in item]
        if missing:
            warnings.append(f"Task {index}: missing fields {missing}, skipped.")
            continue

        label = item.get("description", "?")

        # Guard against the AI inventing a pet the owner does not have.
        if item["pet"] not in pet_names:
            warnings.append(f"Task {index}: '{label}' is for unknown pet '{item['pet']}', skipped.")
            continue

        # Building a Task runs Task.__post_init__, which enforces the field rules.
        try:
            task = Task(
                description=item["description"],
                duration=item["duration"],
                due_time=item["due_time"],
                priority=item["priority"],
                frequency=item["frequency"],
            )
        except (ValueError, TypeError) as error:
            warnings.append(f"Task {index}: '{label}' rejected ({error}).")
            continue

        accepted.append((item["pet"], task))

    return accepted, warnings
