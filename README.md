# PawPal+ AI: A Natural-Language Pet Care Planner

PawPal+ AI turns a plain-English description of your pets' needs into a validated, time-ordered daily care schedule. You type something like "walk my senior dog every morning and feed my cat twice a day," and the system looks up real pet-care guidance, uses an AI model to draft concrete tasks, checks those tasks for safety, and fits them into your available time while flagging any conflicts.

This project extends my earlier PawPal+ scheduler by adding a Retrieval-Augmented Generation (RAG) planning feature on top of the original scheduling engine.

## Why this matters

The original PawPal+ required the user to enter every task by hand: description, duration, time, priority, and how often it repeats. That is precise but slow and unfriendly for a busy owner. PawPal+ AI removes that friction: you describe your day in your own words, and the system produces a sensible, grounded schedule. The AI does not just guess at durations, it retrieves pet-care facts first (for example, that senior dogs need shorter walks) and plans around them, so its output is grounded in guidance rather than invented.

## The base project I extended

My base project is **PawPal+**, built in an earlier module. PawPal+ is a pet-care planning assistant with a clean logic layer (`pawpal_system.py`) of four classes: `Task`, `Pet`, `Owner`, and `Scheduler`. It can generate a daily plan under a time budget (high priority first), sort tasks by time, filter by pet or status, detect scheduling conflicts, and handle daily or weekly recurring tasks. It shipped with a Streamlit web app (`app.py`), a CLI demo (`main.py`), and a pytest suite.

PawPal+ AI keeps that entire engine unchanged and adds a new AI layer in front of it. The AI produces the tasks; the original `Scheduler` still does the scheduling, conflict detection, and time budgeting. This means the new feature is genuinely integrated, not a separate demo.

## The new AI feature

The new feature is a three-part pipeline that sits in front of the original scheduler:

1. **Retriever (RAG), `retriever.py`.** Searches a small pet-care knowledge base (`knowledge/`, 70 facts across 9 topic files) and returns the facts most relevant to the request. It uses keyword matching with stemming and a small synonym list, and a minimum relevance score so weak, unrelated matches are dropped.
2. **Planner (the AI brain), `ai_planner.py`.** Sends the request, the retrieved facts, and the list of the owner's pets to Google Gemini (`gemini-3.6-flash`), and asks for a structured JSON list of tasks. The retrieved facts are injected into the prompt, so retrieval actively shapes the plan.
3. **Guardrails, `guardrails.py`.** Validates every task the AI returns before the system trusts it. It rejects invented pets, invalid times, non-positive durations, and missing fields. Field rules live in `Task.__post_init__`, so the app and the AI share one set of validation rules.

An orchestrator (`ai_assistant.py`) runs these in order, attaches the accepted tasks to the pets, and hands everything to the original `Scheduler`.

## Architecture overview

The full data flow is in [`diagrams/architecture.mmd`](diagrams/architecture.mmd) (Mermaid source). In words:

```
your request
   -> input handling (CLI / demo)
   -> RAG retriever  (searches knowledge/ for relevant facts)
   -> AI planner     (Gemini turns request + facts into JSON tasks)
   -> guardrails     (validate and filter the AI's tasks)
   -> Scheduler      (original PawPal+: plan, budget, find conflicts)
   -> plan + conflict warnings shown to you
```

The retriever and planner are the new AI layer. The guardrails are the reliability layer. The `Scheduler`, `Owner`, `Pet`, and `Task` classes are the original PawPal+ system, reused unchanged except for added input validation.

## Setup

You need Python 3 and a free Google Gemini API key.

```bash
# 1. Clone and enter the project
git clone https://github.com/EversonAlijaya/applied-ai-system-project.git
cd applied-ai-system-project

# 2. Install dependencies
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip3 install -r requirements.txt

# 3. Get a free Gemini API key at https://aistudio.google.com (Get API key)
# 4. Create your .env file and paste the key into it
cp .env.example .env             # then edit .env and set GEMINI_API_KEY

# 5. Confirm the key works
python3 verify_gemini.py
```

The `.env` file is git-ignored, so your key never leaves your computer.

## Running it

```bash
# Interactive assistant (type your own requests):
python3 ai_cli.py

# One fixed end-to-end demo:
python3 ai_assistant.py

# Evaluation harness (pass/fail summary):
python3 evaluate.py

# Original PawPal+ unit tests:
python3 -m pytest
```

## Sample interactions

All outputs below are real runs of the current system. The command that produced each example is shown above it, so each run can be reproduced.

### Example A: a senior dog gets a shorter walk (RAG in action)

**Command:** `python3 ai_assistant.py`

```
REQUEST: Walk Mochi every morning, he is a senior dog, and feed Biscuit at 8am and 6pm.

STEP 1 - Facts the AI retrieved (RAG):
  - Senior dogs benefit from shorter, gentler walks, usually around 15 to 20 minutes, to protect aging joints.
  - Senior dogs may need help with mobility and should avoid long or strenuous exercise.

STEP 2 - Tasks accepted by the guardrails:
  Mochi: Morning walk (15 min, 07:30, medium)
  Biscuit: Morning feeding (10 min, 08:00, high)
  Biscuit: Evening feeding (10 min, 18:00, high)

STEP 3 - Scheduled plan (from the original PawPal+ Scheduler):
Today's plan (120 minutes available):
- 07:30 — Morning walk for Mochi (15 min, medium priority)
- 08:00 — Morning feeding for Biscuit (10 min, high priority)
- 18:00 — Evening feeding for Biscuit (10 min, high priority)

STEP 4 - Conflict check:
  No conflicts found.
```

The walk is 15 minutes, not the default 30 to 60, because the retriever supplied the senior-dog fact and the planner used it. I never typed "15 minutes."

### Example B: multiple pets, multiple tasks

**Command:** `python3 ai_cli.py` (pets: `Bella:dog, Milo:cat`, then type the request below)

```
REQUEST: Bella needs two walks and dinner, and Milo needs playtime and his litter box cleaned.

RAG facts used:
  - Adult dogs generally need 30 to 60 minutes of walking or active exercise each day, often split into two walks.
  - Two shorter walks are usually better than one very long walk, giving the dog more chances for bathroom breaks and sniffing.

Accepted tasks:
  Bella: Morning walk (25 min, 08:00, high)
  Milo: Scoop litter box (5 min, 08:30, high)
  Bella: Evening walk (25 min, 17:30, high)
  Bella: Dinner (10 min, 18:00, high)
  Milo: Playtime (15 min, 18:30, medium)

Plan:
Today's plan (180 minutes available):
- 08:00 — Morning walk for Bella (25 min, high priority)
- 08:30 — Scoop litter box for Milo (5 min, high priority)
- 17:30 — Evening walk for Bella (25 min, high priority)
- 18:00 — Dinner for Bella (10 min, high priority)
- 18:30 — Playtime for Milo (15 min, medium priority)

Conflicts: none
```

### Example C: tasks kept inside a chosen day window

**Command:** `python3 ai_cli.py` (pet: `Rocky:dog`, day start `09:00`, day end `11:00`, then type the request below)

```
REQUEST: Rocky is a puppy, feed him a few times and give him short walks and training.
(Day window: 09:00 to 11:00, 180 min available)

RAG facts used:
  - Puppies need more frequent meals, usually three to four times a day, because they have small stomachs and high energy needs.
  - Puppy training sessions should be short, about 5 to 10 minutes, because young dogs have short attention spans.

Accepted tasks:
  Rocky: Morning meal (10 min, 09:00, high)
  Rocky: Short morning walk (15 min, 09:20, high)
  Rocky: Short puppy training session (10 min, 09:50, medium)
  Rocky: Mid-morning meal (10 min, 10:30, high)

Plan:
Today's plan (180 minutes available):
- 09:00 — Morning meal for Rocky (10 min, high priority)
- 09:20 — Short morning walk for Rocky (15 min, high priority)
- 09:50 — Short puppy training session for Rocky (10 min, medium priority)
- 10:30 — Mid-morning meal for Rocky (10 min, high priority)

Conflicts: none
```

Every task lands between 09:00 and 11:00 because the day window was passed into the planner's prompt. The tasks are also short, matching the retrieved puppy facts.

## Reliability and guardrails

The guardrails reject bad AI output before it reaches the scheduler. Running `python3 guardrails.py` feeds a deliberately messy AI response through the validator:

```
ACCEPTED tasks:
  Mochi: Morning walk (15 min, 08:00, medium)

WARNINGS (rejected):
  - Task 2: 'Walk Rex' is for unknown pet 'Rex', skipped.
  - Task 3: 'Feeding' rejected (duration must be a positive whole number of minutes, got -5).
  - Task 4: 'Late feeding' rejected (due_time must be 24-hour 'HH:MM' or empty, got '25:99').
  - Task 5: missing fields ['frequency'], skipped.
```

The one valid task is kept; the invented pet, negative duration, invalid time, and missing field are each rejected with a clear reason.

## Testing summary

The evaluation harness (`evaluate.py`) runs the system on predefined inputs and prints a pass/fail summary. It has component checks (no API key needed: retriever and guardrails) and end-to-end checks (calling Gemini). Because AI output varies, the end-to-end checks test properties that should always hold (for example, a senior dog's walk is short), not exact wording.

**Command:** `python3 evaluate.py`

```
PawPal+ evaluation harness

COMPONENT CHECKS (no API key needed)
  PASS - retriever finds a senior-dog fact
  PASS - retriever handles feed/meals synonym for puppy
  PASS - retriever returns nothing for empty input
  PASS - retriever returns nothing for gibberish
  PASS - retriever keeps only strong matches (score >= 2)
  PASS - guardrails accept exactly the 1 valid task
  PASS - guardrails reject the 4 bad tasks
  PASS - scheduler keeps the high-priority task within budget

END-TO-END CHECKS (calling Gemini)
  PASS - senior dog gets a short walk (<= 25 min)
  PASS - off-topic request yields an empty plan
  PASS - tasks respect the 09:00-11:00 day window

SUMMARY: 11/11 checks passed.
```

The original PawPal+ scheduler logic is also covered by 13 unit tests (`python3 -m pytest`), all passing. What worked well: the RAG grounding reliably changes durations, and the guardrails catch every category of bad output I tested. What was harder: keyword retrieval needed several rounds of tuning (stemming, synonyms, a score threshold) before it stopped returning unrelated facts. That tuning story is written up in `model_card.md`.

## Design decisions and trade-offs

- **Keyword RAG instead of embeddings.** I used keyword matching with stemming and synonyms rather than vector embeddings. The trade-off: it is simple, free, and easy to explain, but it cannot match synonyms it was not told about. I chose transparency and zero setup over maximum recall.
- **Validation in the class, not just the AI layer.** Field rules live in `Task.__post_init__`, so both the app and the AI go through the same checks. This also addressed feedback from my earlier project about adding input validation.
- **The scheduler detects conflicts but does not resolve them.** I kept the original human-in-the-loop design: the system flags a clash and leaves the fix to the user. I added a prompt rule so the AI staggers task times to avoid most accidental overlaps.
- **A fixed model name.** I pinned `gemini-3.6-flash` rather than a "latest" alias so sample outputs stay reproducible.

## Limitations and reflection

Known limitations and my full reflection (including how I used AI during development, one helpful and one flawed AI suggestion, and future improvements) are in [`model_card.md`](model_card.md).

## Repository structure

```
knowledge/            pet-care knowledge base (RAG source, 9 files)
retriever.py          RAG retriever (search + stemming + synonyms)
ai_planner.py         AI planner (Gemini, structured JSON output)
guardrails.py         validates and filters AI output
ai_assistant.py       orchestrator: request -> plan
ai_cli.py             interactive command-line tester
evaluate.py           evaluation harness (pass/fail summary)
pawpal_system.py      original PawPal+ engine (Task, Pet, Owner, Scheduler)
app.py, main.py       original Streamlit app and CLI demo
tests/                original pytest suite (13 tests)
diagrams/             architecture.mmd and UML source
verify_gemini.py      one-off API key check
```

## Demo video (optional)

A short Loom walkthrough: _(add link here if recorded)_
