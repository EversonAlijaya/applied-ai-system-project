"""End-to-end AI assistant for PawPal+ (the orchestrator).

This ties all the pieces together so a plain-English request becomes a
validated, scheduled, conflict-checked care plan:

  request -> ai_planner (RAG retrieve + Gemini)   # generate tasks
          -> guardrails (validate / filter)        # trust nothing blindly
          -> attach accepted tasks to the pets     # feed the existing system
          -> Scheduler (generate_plan, conflicts)  # reuse original PawPal+ logic

The orchestrator itself contains no AI or scheduling logic; it only calls the
existing pieces in order, which keeps each part simple and testable.
"""

from dataclasses import dataclass

from ai_planner import plan_tasks
from guardrails import validate_tasks
from pawpal_system import Owner, Pet, Scheduler


@dataclass
class PlanResult:
    """Everything produced by one request, bundled for easy display."""

    facts: list        # Fact objects the retriever supplied to the AI
    accepted: list     # (pet_name, Task) pairs that passed the guardrails
    warnings: list     # plain-language messages about rejected AI tasks
    plan: list         # the Tasks that fit into the time budget, time-ordered
    conflicts: list    # warnings about tasks clashing at the same time
    explanation: str   # human-readable summary of the plan


def _find_pet(owner: Owner, name: str) -> Pet | None:
    """Return the owner's pet with this name, or None."""
    for pet in owner.pets:
        if pet.name == name:
            return pet
    return None


def plan_from_request(owner: Owner, request: str, top_k: int = 4) -> PlanResult:
    """Run the full pipeline for one request and return a PlanResult."""
    pet_names = [pet.name for pet in owner.pets]

    # 1. AI proposes tasks, grounded in retrieved facts.
    raw_tasks, facts = plan_tasks(request, pet_names, top_k=top_k)

    # 2. Guardrails keep only the valid tasks.
    accepted, warnings = validate_tasks(raw_tasks, pet_names)

    # 3. Attach the accepted tasks to the matching pets.
    for pet_name, task in accepted:
        pet = _find_pet(owner, pet_name)
        if pet is not None:
            pet.add_task(task)

    # 4. Hand off to the ORIGINAL PawPal+ scheduler.
    scheduler = Scheduler(owner)
    plan = scheduler.generate_plan()
    conflicts = scheduler.find_conflicts()
    explanation = scheduler.explain_plan()

    return PlanResult(facts, accepted, warnings, plan, conflicts, explanation)


if __name__ == "__main__":
    # Full end-to-end demo. Costs one small (free-tier) Gemini call.
    owner = Owner("Everson", available_minutes=120)
    owner.add_pet(Pet("Mochi", "dog", "senior mixed breed"))
    owner.add_pet(Pet("Biscuit", "cat"))

    request = "Walk Mochi every morning, he is a senior dog, and feed Biscuit at 8am and 6pm."
    print(f"REQUEST: {request}\n")

    result = plan_from_request(owner, request)

    print("STEP 1 - Facts the AI retrieved (RAG):")
    for fact in result.facts:
        print(f"  - {fact.text}")

    print("\nSTEP 2 - Tasks accepted by the guardrails:")
    for pet_name, task in result.accepted:
        print(f"  {pet_name}: {task.description} ({task.duration} min, {task.due_time or 'anytime'}, {task.priority})")
    if result.warnings:
        print("  Rejected:")
        for warning in result.warnings:
            print(f"    - {warning}")

    print("\nSTEP 3 - Scheduled plan (from the original PawPal+ Scheduler):")
    print(result.explanation)

    print("\nSTEP 4 - Conflict check:")
    if result.conflicts:
        for conflict in result.conflicts:
            print(f"  ! {conflict}")
    else:
        print("  No conflicts found.")
