"""Interactive tester for the PawPal+ AI assistant.

Type pet-care requests in your OWN words and watch the full pipeline run:
RAG facts -> AI plan -> guardrails -> schedule -> conflict check.

Run:  python3 ai_cli.py
Type 'quit' (or 'q') to exit.
"""

from ai_assistant import plan_from_request
from pawpal_system import Owner, Pet


def build_owner() -> Owner:
    """Let the user define pets, or press Enter for defaults."""
    print("Set up your pets. Format: name:species, separated by commas.")
    print("Example:  Rocky:dog, Luna:cat")
    line = input("Your pets (or press Enter for defaults Mochi:dog, Biscuit:cat):\n> ").strip()

    owner = Owner("You", available_minutes=120)
    if not line:
        owner.add_pet(Pet("Mochi", "dog", "senior mixed breed"))
        owner.add_pet(Pet("Biscuit", "cat"))
    else:
        for chunk in line.split(","):
            parts = chunk.split(":")
            name = parts[0].strip()
            species = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "pet"
            if name:
                owner.add_pet(Pet(name, species))

    print("\nPets on file:", ", ".join(pet.describe() for pet in owner.pets))
    print("(Tip: the AI can only make tasks for these pets; others are rejected by the guardrails.)")
    return owner


def show(result) -> None:
    """Print the four pipeline stages for one request."""
    print("\n  STEP 1 - Facts retrieved (RAG):")
    for fact in result.facts:
        print(f"    - {fact.text}")

    print("\n  STEP 2 - Tasks accepted by guardrails:")
    if not result.accepted:
        print("    (none)")
    for pet_name, task in result.accepted:
        print(f"    {pet_name}: {task.description} ({task.duration} min, {task.due_time or 'anytime'}, {task.priority})")
    for warning in result.warnings:
        print(f"    REJECTED: {warning}")

    print("\n  STEP 3 - Scheduled plan:")
    print("   " + result.explanation.replace("\n", "\n   "))

    print("\n  STEP 4 - Conflict check:")
    if result.conflicts:
        for conflict in result.conflicts:
            print(f"    ! {conflict}")
    else:
        print("    No conflicts found.")


def main() -> None:
    owner = build_owner()
    print("\nNow type a pet-care request in your own words.")

    while True:
        try:
            request = input("\nRequest > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if request.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break
        if not request:
            continue

        # Reset tasks so each request is tested on its own.
        for pet in owner.pets:
            pet.tasks.clear()

        print("...thinking...")
        result = plan_from_request(owner, request)
        show(result)


if __name__ == "__main__":
    main()
