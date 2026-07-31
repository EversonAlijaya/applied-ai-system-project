# Model Card: PawPal+ AI Pet Care Planner

This model card describes the AI feature I added to my PawPal+ project, how it works, how well it works, its limitations, and how I collaborated with AI while building it.

## 1. System overview

PawPal+ AI is a Retrieval-Augmented Generation (RAG) planning system for pet care. The user describes their pets' needs in plain English, and the system produces a validated daily schedule. It combines three parts I built (a retriever, an AI planner, and a guardrail validator) with the original PawPal+ scheduling engine.

The AI model at the center is Google Gemini (`gemini-3.6-flash`), accessed through the Google AI Studio free tier. I pinned a fixed model version so my results stay reproducible.

## 2. Intended use and purpose

The system is meant to help a busy pet owner turn a messy, natural description of their day into an organized schedule. It is a planning aid, not a source of veterinary advice. The pet-care facts it retrieves are simplified, general guidelines. Anything involving a pet's health should be confirmed with a real veterinarian.

## 3. Data: the knowledge base

The retrieval source is a small knowledge base I wrote by hand: 70 short pet-care facts across 9 Markdown files in `knowledge/` (dog walking, feeding, senior and puppy care, grooming and health, cat care, hydration, training and enrichment, health and vet signs, and weather and safety). Each fact is written to be short and specific, so it can influence a scheduling decision (for example, a fact about senior dogs needing shorter walks).

The knowledge base is small and general on purpose. Its bias is that it reflects common, mainstream pet-care advice, and it does not cover exotic pets, breed-specific medical needs, or regional differences.

## 4. How the system works (plain language)

1. The retriever breaks the request into words, reduces them to root forms (so "walking" and "walks" match), maps a few obvious synonyms (so "feed" matches "meals"), and scores each fact by how many words it shares with the request. Only facts scoring at least 2 are kept.
2. The planner puts the request, the retrieved facts, and the list of pets into a prompt and asks Gemini to return a JSON list of tasks. The facts are included in the prompt, so they shape the plan.
3. The guardrails check every task: known pet, positive duration, valid time, valid priority and frequency, all required fields present. Bad tasks are rejected with a clear reason.
4. The accepted tasks are attached to the pets, and the original `Scheduler` builds the time-ordered plan under the time budget and reports conflicts.

## 5. RAG impact: before and after

The retriever went through real tuning. The clearest example is the request "how often to feed a puppy."

Before tuning (whole-word matching only), the retriever returned dog-walking facts and completely missed the correct fact, because "puppy" did not match "puppies" and "feed" did not match "meals":

```
Request: 'how often to feed a puppy'
  [1] Adult dogs generally need 30 to 60 minutes of walking...
  [1] Puppies need about 5 minutes of walking per month of age...
  [1] High-energy breeds often need more than 60 minutes...
```

After adding stemming, a synonym list, and a minimum score, it returns the correct fact at the top:

```
Request: 'how often to feed a puppy'
  [2] Puppies need more frequent meals, usually three to four times a day...
```

This shows retrieval directly improving output quality: with the wrong facts, the planner would plan a puppy's feeding based on dog-walking guidance. With the right fact, it plans frequent meals.

## 6. Evaluation and testing results

I built an evaluation harness (`evaluate.py`) that runs the system on predefined inputs and prints a pass/fail summary. On the current system it reports **11 out of 11 checks passed**. The checks cover retriever precision (including empty and gibberish input), guardrail accept and reject behavior, scheduler budgeting, and three end-to-end properties: a senior dog gets a short walk, an off-topic request yields an empty plan, and tasks respect a chosen day window.

The original scheduling engine is also covered by 13 unit tests, all passing.

## 7. Limitations and biases

- **Keyword retrieval is shallow.** It matches words, not meaning. It only handles synonyms I listed by hand, so an unusual wording can still miss a relevant fact. Embeddings would fix this but add setup and cost.
- **It is a planner, not a chatbot.** If I ask a question like "is it okay for my old dog to walk a long time," the system does not answer in words; it converts the intent into a task. This can feel indirect.
- **Conflict detection is purely time-based.** It flags two tasks at the same time as a conflict, even when they could safely overlap (such as feeding two pets at once). It does not understand which tasks can happen together.
- **The day window is enforced by prompt, not by code.** The AI follows the instruction well, but there is no hard filter that rejects an out-of-window task, so a rare violation is possible.
- **The AI can still make mistakes.** The guardrails catch invalid structure, but they cannot catch a task that is valid in form yet poor in judgment.
- **Knowledge base bias.** The facts are general and mainstream, and do not cover every pet, breed, or medical situation.

## 8. Possible misuse and prevention

The main risk is someone treating the output as veterinary or medical advice. A wrong duration or a missed health need could harm a pet. I reduce this risk by grounding the plan in a reviewed knowledge base rather than free generation, by validating all output through guardrails, and by stating clearly (in the README and here) that this is a scheduling aid and not medical advice. A second risk is prompt abuse (feeding unrelated or harmful text). The system handles this by returning an empty plan for off-topic input and by rejecting anything that does not pass validation. If this were a real product, I would add rate limiting and content filtering on the input as well.

## 9. What surprised me while testing

The biggest surprise was how much of the difficulty was in retrieval, not in the AI model. I expected the language model to be the hard part, but Gemini handled the planning well from the start. The retriever was what needed round after round of fixing: word forms, then synonyms, then a consonant-doubling bug ("trimming" became "trimm"), then a score threshold to cut noise. Testing with more inputs kept exposing new edge cases, which taught me that the boring plumbing around the AI often matters more than the AI itself.

I was also surprised, in a good way, when the system refused a risky request. When I asked it to give my old dog a long walk, it retrieved the senior-dog fact and scheduled a short gentle walk instead. The retrieval acted as a safety check on the plan.

## 10. My collaboration with AI during development

I built this project while working closely with an AI coding assistant. I directed the design, tested every piece with my own inputs, and decided what to keep or change. The AI helped me write and debug code faster.

**One helpful AI suggestion.** When my retriever returned wrong facts, the AI assistant correctly diagnosed that the problem was word forms not matching (for example "puppy" versus "puppies") and suggested adding a small stemmer. That fix, plus a synonym list I asked for, solved the retrieval quality problem. It also quickly explained a confusing error ("Cannot send a request, as the client has been closed") as a garbage-collection issue and fixed it.

**One flawed AI suggestion.** The AI assistant first wrote my planner using a model name, `gemini-2.5-flash`, that Google had retired for new accounts. Running it failed with a 404 error. The suggestion looked correct but was out of date. I fixed it by listing the models my key could actually use and switching to a current one. This taught me not to trust a model name or API detail blindly, and to verify against the live service.

## 11. Future improvements

- Replace keyword retrieval with embeddings so the system understands meaning and synonyms automatically.
- Enforce the day window and other constraints in code as a hard guardrail, not only in the prompt.
- Make conflict detection aware of which task types can safely overlap.
- Add a question-answering mode so the system can respond in words, not only tasks.
- Handle temporary API errors (such as a 503 from high demand) gracefully with a clear message and a retry.
