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


if __name__ == "__main__":
    # Demo: feed a deliberately messy AI response and watch the guardrail
    # keep the good task and reject the bad ones. Run: python3 guardrails.py
    pet_names = ["Mochi", "Biscuit"]
    messy_ai_output = [
        {"pet": "Mochi", "description": "Morning walk", "duration": 15, "due_time": "08:00", "priority": "medium", "frequency": "daily"},
        {"pet": "Rex", "description": "Walk Rex", "duration": 20, "due_time": "09:00", "priority": "low", "frequency": "daily"},
        {"pet": "Biscuit", "description": "Feeding", "duration": -5, "due_time": "18:00", "priority": "high", "frequency": "daily"},
        {"pet": "Biscuit", "description": "Late feeding", "duration": 10, "due_time": "25:99", "priority": "high", "frequency": "daily"},
        {"pet": "Mochi", "description": "Play", "duration": 10, "due_time": "17:00", "priority": "medium"},
    ]

    accepted, warnings = validate_tasks(messy_ai_output, pet_names)

    print("ACCEPTED tasks:")
    for pet, task in accepted:
        print(f"  {pet}: {task.description} ({task.duration} min, {task.due_time}, {task.priority})")

    print("\nWARNINGS (rejected):")
    for warning in warnings:
        print(f"  - {warning}")
