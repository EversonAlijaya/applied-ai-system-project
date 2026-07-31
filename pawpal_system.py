"""PawPal+ core classes.

Generated from the UML draft in diagrams/uml.mmd, then implemented in Phase 2.

Data flows Owner -> Pet -> Task: an Owner manages multiple Pets, each Pet
owns its list of Tasks, and the Scheduler retrieves tasks by walking that
chain through the Owner rather than holding its own separate task list.
"""

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
VALID_FREQUENCIES = ("once", "daily", "weekly")


def is_valid_hhmm(value: str) -> bool:
    """Return True if value is a 24-hour time like '08:00' (or '8:00')."""
    parts = value.split(":")
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return False
    hours, minutes = int(parts[0]), int(parts[1])
    return 0 <= hours <= 23 and 0 <= minutes <= 59


@dataclass
class Task:
    """Represents a single care activity to be scheduled."""

    description: str
    duration: int
    due_time: str = ""  # 24-hour "HH:MM", e.g. "08:00"; empty means anytime
    priority: str = "medium"
    frequency: str = "once"  # "once", "daily", or "weekly"
    due_date: str = ""  # ISO "YYYY-MM-DD"; empty means today
    completed: bool = False

    def __post_init__(self) -> None:
        """Validate fields right after creation so bad data fails loudly.

        Runs automatically for every Task, including AI-generated ones, so a
        negative duration or an invalid time is rejected with a clear message
        instead of causing a subtle bug later.
        """
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string")
        # bool is a subtype of int in Python, so exclude it explicitly.
        if isinstance(self.duration, bool) or not isinstance(self.duration, int) or self.duration <= 0:
            raise ValueError(f"duration must be a positive whole number of minutes, got {self.duration!r}")
        if self.priority not in PRIORITY_ORDER:
            raise ValueError(f"priority must be one of {list(PRIORITY_ORDER)}, got {self.priority!r}")
        if self.frequency not in VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of {list(VALID_FREQUENCIES)}, got {self.frequency!r}")
        if self.due_time and not is_valid_hhmm(self.due_time):
            raise ValueError(f"due_time must be 24-hour 'HH:MM' or empty, got {self.due_time!r}")
        if self.due_date:
            try:
                date.fromisoformat(self.due_date)
            except ValueError:
                raise ValueError(f"due_date must be 'YYYY-MM-DD' or empty, got {self.due_date!r}")

    def edit(self, description: str = None, duration: int = None, priority: str = None) -> None:
        """Modify the task's details, leaving unspecified fields unchanged."""
        if description is not None:
            self.description = description
        if duration is not None:
            self.duration = duration
        if priority is not None:
            self.priority = priority

    def is_high_priority(self) -> bool:
        """Return whether this task is high priority."""
        return self.priority == "high"

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.completed = True

    def mark_incomplete(self) -> None:
        """Mark this task as not yet completed."""
        self.completed = False

    def next_occurrence(self) -> "Task | None":
        """Return a fresh copy of this task due one day/week later, or None if not recurring."""
        intervals = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}
        if self.frequency not in intervals:
            return None
        base = date.fromisoformat(self.due_date) if self.due_date else date.today()
        next_date = base + intervals[self.frequency]
        return replace(self, due_date=next_date.isoformat(), completed=False)


@dataclass
class Pet:
    """Represents a pet being cared for, along with its care tasks."""

    name: str
    species: str
    breed: str = ""
    notes: str = ""
    tasks: list[Task] = field(default_factory=list)

    def describe(self) -> str:
        """Return a short human-readable description of the pet."""
        breed_part = f", {self.breed}" if self.breed else ""
        return f"{self.name} ({self.species}{breed_part})"

    def update_notes(self, notes: str) -> None:
        """Update the pet's care notes."""
        self.notes = notes

    def add_task(self, task: Task) -> None:
        """Add a care task for this pet."""
        self.tasks.append(task)

    def remove_task(self, task: Task) -> None:
        """Remove a care task from this pet."""
        self.tasks.remove(task)

    def get_tasks(self) -> list[Task]:
        """Return this pet's tasks."""
        return self.tasks

    def complete_task(self, task: Task) -> Task | None:
        """Mark a task complete; if it recurs, add and return its next occurrence."""
        task.mark_complete()
        follow_up = task.next_occurrence()
        if follow_up is not None:
            self.tasks.append(follow_up)
        return follow_up


class Owner:
    """Represents the pet owner, their pets, and their daily constraints."""

    def __init__(self, name: str, available_minutes: int, preferences: dict | None = None):
        self.name = name
        self.available_minutes = available_minutes
        self.preferences = preferences if preferences is not None else {}
        self.pets: list[Pet] = []

    def update_availability(self, minutes: int) -> None:
        """Change the owner's daily time budget."""
        self.available_minutes = minutes

    def set_preference(self, key: str, value) -> None:
        """Record an owner preference."""
        self.preferences[key] = value

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's care."""
        self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner's care."""
        self.pets.remove(pet)

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of this owner's pets."""
        return [task for pet in self.pets for task in pet.tasks]


class Scheduler:
    """Retrieves tasks from an Owner's pets, organizes them, and builds a plan."""

    def __init__(self, owner: Owner):
        self.owner = owner
        self.plan: list[Task] = []

    def get_all_tasks(self) -> list[Task]:
        """Retrieve all tasks across the owner's pets."""
        return self.owner.get_all_tasks()

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Order tasks by priority (high first), then by shorter duration."""
        return sorted(tasks, key=lambda task: (PRIORITY_ORDER.get(task.priority, 1), task.duration))

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Order tasks by due time (earliest first); tasks with no time go last."""
        return sorted(tasks, key=lambda task: (task.due_time == "", task.due_time))

    def filter_by_status(self, completed: bool) -> list[Task]:
        """Return every task across all pets matching the given completion status."""
        return [task for task in self.get_all_tasks() if task.completed == completed]

    def filter_by_pet(self, pet_name: str) -> list[Task]:
        """Return the tasks belonging to the pet with the given name."""
        for pet in self.owner.pets:
            if pet.name == pet_name:
                return list(pet.tasks)
        return []

    def find_conflicts(self) -> list[str]:
        """Return warning messages for incomplete tasks scheduled at the same date and time."""
        today = date.today().isoformat()
        by_slot: dict[tuple[str, str], list[tuple[str, Task]]] = {}
        for pet in self.owner.pets:
            for task in pet.tasks:
                if not task.completed and task.due_time:
                    slot = (task.due_date or today, task.due_time)
                    by_slot.setdefault(slot, []).append((pet.name, task))

        warnings = []
        for (due_date, due_time), entries in sorted(by_slot.items()):
            if len(entries) > 1:
                names = " and ".join(f"'{task.description}' ({pet_name})" for pet_name, task in entries)
                day = "" if due_date == today else f" on {due_date}"
                warnings.append(f"Conflict at {due_time}{day}: {names} are scheduled at the same time.")
        return warnings

    def generate_plan(self) -> list[Task]:
        """Fit today's incomplete tasks into available time and produce the daily plan."""
        today = date.today().isoformat()
        candidates = [
            task
            for task in self.get_all_tasks()
            if not task.completed and (not task.due_date or task.due_date <= today)
        ]
        ordered = self.sort_tasks(candidates)

        plan = []
        minutes_left = self.owner.available_minutes
        for task in ordered:
            if task.duration <= minutes_left:
                plan.append(task)
                minutes_left -= task.duration

        self.plan = self.sort_by_time(plan)
        return self.plan

    def _pet_for_task(self, task: Task) -> str:
        """Return the name of the pet that owns this exact task object.

        Matches by identity ('is'), not equality, because two different pets
        can have value-identical tasks (e.g. both have a "Morning meal").
        """
        for pet in self.owner.pets:
            if any(owned is task for owned in pet.tasks):
                return pet.name
        return ""

    def explain_plan(self) -> str:
        """Return a human-readable explanation of why the plan was chosen."""
        if not self.plan:
            return "No tasks fit into today's plan."

        lines = [f"Today's plan ({self.owner.available_minutes} minutes available):"]
        for task in self.plan:
            when = task.due_time if task.due_time else "anytime"
            pet_name = self._pet_for_task(task)
            who = f" for {pet_name}" if pet_name else ""
            lines.append(f"- {when} — {task.description}{who} ({task.duration} min, {task.priority} priority)")
        return "\n".join(lines)
