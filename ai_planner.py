"""AI planner for PawPal+ (the generation step of the system).

This is where the "AI" lives. It combines:
  1. the owner's plain-English request,
  2. the pet-care facts retrieved from the knowledge base (RAG), and
  3. the list of the owner's known pets,
then asks Google Gemini to return a structured list of care tasks as JSON.

The retrieved facts are fed INTO the prompt so the AI's plan is grounded in
real guidance (for example, giving a senior dog a shorter walk). The planner
only PRODUCES tasks; validating them happens later in guardrails.py.
"""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from retriever import load_facts, retrieve

# The Gemini model we use. "flash" is the fast, free-tier-friendly tier.
MODEL = "gemini-3.6-flash"

load_dotenv()  # load GEMINI_API_KEY from .env


# Created once and reused. Keeping it in a module-level variable stops Python
# from cleaning it up (and closing its connection) between calls.
_CLIENT = None


def _client() -> genai.Client:
    """Return the Gemini client, creating it once, or fail clearly if no key."""
    global _CLIENT
    if _CLIENT is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key or api_key == "your-key-goes-here":
            raise RuntimeError(
                "No GEMINI_API_KEY found. Copy .env.example to .env and paste your key."
            )
        _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


def build_prompt(request: str, facts: list, pet_names: list) -> str:
    """Assemble the full instruction text we send to Gemini.

    The retrieved facts and the known pet names are injected here, which is
    what makes this Retrieval-Augmented Generation rather than a plain guess.
    """
    facts_text = "\n".join(f"- {f.text}" for f in facts) or "- (no relevant facts found)"
    pets_text = ", ".join(pet_names) if pet_names else "(no pets on file)"
    return f"""You are PawPal+, a careful pet-care planning assistant.
Turn the owner's request into a list of concrete daily care tasks.

Known pets: {pets_text}

Relevant pet-care guidance (use this to choose sensible durations and priorities):
{facts_text}

Owner's request: "{request}"

Return ONLY a JSON list of task objects. Each task object must have exactly:
- "pet": the pet this task is for (MUST be one of the known pets above)
- "description": a short task name, e.g. "Morning walk"
- "duration": whole number of minutes, greater than 0
- "due_time": 24-hour time as "HH:MM", or "" if any time is fine
- "priority": one of "high", "medium", "low"
- "frequency": one of "once", "daily", "weekly"

Rules:
- Use the guidance above to set durations (e.g. senior dogs get shorter walks).
- Do NOT invent pets that are not in the known pets list.
- If the request is unclear or unrelated to pet care, return an empty list [].
"""


def plan_tasks(request: str, pet_names: list, top_k: int = 4) -> tuple:
    """Turn a request into (list of task dicts, list of facts used by RAG).

    Steps: retrieve facts -> build prompt -> ask Gemini -> parse JSON.
    Returns the raw task dicts (NOT yet validated) plus the facts that were
    retrieved, so callers can show what guidance the plan was based on.
    """
    facts = retrieve(request, load_facts(), top_k=top_k)
    prompt = build_prompt(request, facts, pet_names)

    client = _client()  # keep a named reference so it stays open during the call
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",  # force valid JSON back
            temperature=0.2,  # low = focused and consistent
        ),
    )

    tasks = json.loads(response.text)
    return tasks, facts


if __name__ == "__main__":
    # Manual demo. Costs one small (free-tier) Gemini call.
    pets = ["Mochi", "Biscuit"]
    request = (
        "Walk Mochi every morning, he is a senior dog, "
        "and feed Biscuit at 8am and 6pm."
    )

    print(f"Request: {request}\n")
    planned, used_facts = plan_tasks(request, pets)

    print("RAG facts the plan used:")
    for fact in used_facts:
        print(f"  - {fact.text}")

    print("\nPlanned tasks (raw AI output, not yet validated):")
    for task in planned:
        print(f"  {task}")
