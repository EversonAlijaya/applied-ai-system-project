"""Evaluation harness for PawPal+.

Runs the system on predefined inputs and prints a PASS/FAIL summary, so the
system's reliability can be checked without manually reading every run.

Two sections:
  1. Component checks  - no API key needed (retriever + guardrails). Always run.
  2. End-to-end checks - need GEMINI_API_KEY (full request -> plan pipeline).

Because AI output varies, the end-to-end checks test PROPERTIES that should
always hold (e.g. a senior dog's walk is short), not exact wording.

Run:  python3 evaluate.py
"""

import os

from dotenv import load_dotenv

from retriever import load_facts, retrieve
from guardrails import validate_tasks
from pawpal_system import Owner, Pet, Task, Scheduler

load_dotenv()


class Results:
    """Tallies checks and prints each one as it runs."""

    def __init__(self):
        self.passed = 0
        self.total = 0

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  PASS - {name}")
        else:
            print(f"  FAIL - {name}" + (f"  ({detail})" if detail else ""))


def _minutes(hhmm: str) -> int:
    """Convert 'HH:MM' to minutes since midnight (for range checks)."""
    hours, mins = hhmm.split(":")
    return int(hours) * 60 + int(mins)


def component_checks(r: Results) -> None:
    """Checks that need no API key: retriever and guardrails."""
    print("\nCOMPONENT CHECKS (no API key needed)")
    facts = load_facts()

    # Retriever: finds the right fact, and filters noise / bad input.
    senior = retrieve("walk my senior dog", facts)
    r.check("retriever finds a senior-dog fact",
            bool(senior) and any("senior" in f.text.lower() for f in senior))

    puppy = retrieve("how often to feed a puppy", facts)
    r.check("retriever handles feed/meals synonym for puppy",
            any("meal" in f.text.lower() for f in puppy))

    r.check("retriever returns nothing for empty input", retrieve("", facts) == [])
    r.check("retriever returns nothing for gibberish", retrieve("xyzzy qwerty", facts) == [])
    r.check("retriever keeps only strong matches (score >= 2)",
            all(f.score >= 2 for f in senior))

    # Guardrails: accept good tasks, reject bad ones.
    messy = [
        {"pet": "Mochi", "description": "Walk", "duration": 15, "due_time": "08:00", "priority": "medium", "frequency": "daily"},
        {"pet": "Rex", "description": "Walk Rex", "duration": 20, "due_time": "09:00", "priority": "low", "frequency": "daily"},
        {"pet": "Mochi", "description": "Feed", "duration": -5, "due_time": "18:00", "priority": "high", "frequency": "daily"},
        {"pet": "Mochi", "description": "Late", "duration": 10, "due_time": "25:99", "priority": "high", "frequency": "daily"},
        {"pet": "Mochi", "description": "Play", "duration": 10, "due_time": "17:00", "priority": "medium"},
    ]
    accepted, warnings = validate_tasks(messy, ["Mochi"])
    r.check("guardrails accept exactly the 1 valid task", len(accepted) == 1, f"got {len(accepted)}")
    r.check("guardrails reject the 4 bad tasks", len(warnings) == 4, f"got {len(warnings)}")

    # Scheduler: respects the time budget, keeps high priority when tight.
    owner = Owner("You", available_minutes=20)
    pet = Pet("Mochi", "dog")
    owner.add_pet(pet)
    pet.add_task(Task("Important", 15, "08:00", "high", "daily"))
    pet.add_task(Task("Optional", 30, "09:00", "low", "daily"))
    plan = Scheduler(owner).generate_plan()
    r.check("scheduler keeps the high-priority task within budget",
            len(plan) == 1 and plan[0].description == "Important", f"plan={[t.description for t in plan]}")


def end_to_end_checks(r: Results) -> None:
    """Checks that run the full AI pipeline (need an API key)."""
    print("\nEND-TO-END CHECKS (calling Gemini)")
    if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") == "your-key-goes-here":
        print("  SKIPPED - no GEMINI_API_KEY set (component checks above still ran).")
        return

    from ai_assistant import plan_from_request  # imported here so no key = no import cost

    # Case 1: a senior dog's walk should be short (RAG effect).
    owner = Owner("You", available_minutes=180)
    owner.add_pet(Pet("Mochi", "dog", "senior mixed breed"))
    res = plan_from_request(owner, "Walk Mochi, he is a senior dog.")
    walks = [t for name, t in res.accepted if name == "Mochi" and "walk" in t.description.lower()]
    r.check("senior dog gets a short walk (<= 25 min)",
            bool(walks) and all(t.duration <= 25 for t in walks),
            f"walks={[(t.description, t.duration) for t in walks]}")

    # Case 2: off-topic request should produce no tasks.
    owner2 = Owner("You", available_minutes=120)
    owner2.add_pet(Pet("Mochi", "dog"))
    res2 = plan_from_request(owner2, "What is the weather today?")
    r.check("off-topic request yields an empty plan", len(res2.accepted) == 0,
            f"accepted={len(res2.accepted)}")

    # Case 3: all tasks stay inside the owner's day window.
    owner3 = Owner("You", available_minutes=180)
    owner3.set_preference("day_start", "09:00")
    owner3.set_preference("day_end", "11:00")
    owner3.add_pet(Pet("Mochi", "dog"))
    res3 = plan_from_request(owner3, "Feed Mochi twice and give him a walk.")
    timed = [t for _, t in res3.accepted if t.due_time]
    in_window = all(_minutes("09:00") <= _minutes(t.due_time) <= _minutes("11:00") for t in timed)
    r.check("tasks respect the 09:00-11:00 day window", bool(timed) and in_window,
            f"times={[t.due_time for t in timed]}")


def main() -> None:
    print("PawPal+ evaluation harness")
    r = Results()
    component_checks(r)
    end_to_end_checks(r)
    print(f"\nSUMMARY: {r.passed}/{r.total} checks passed.")


if __name__ == "__main__":
    main()
