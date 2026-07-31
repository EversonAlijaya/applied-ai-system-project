"""RAG retriever for PawPal+.

This module is the "Retrieval" part of Retrieval-Augmented Generation.
Given a plain-English request, it searches the pet-care knowledge base
(the Markdown files in knowledge/) and returns the most relevant facts.

The retrieved facts are later handed to the AI planner so its schedule is
grounded in real guidance instead of guesses. No AI model is used here:
this is deliberately simple keyword matching so it is easy to see WHY each
fact was chosen.
"""

from dataclasses import dataclass
from pathlib import Path

# Very common words that carry little meaning. We ignore them when scoring so
# that words like "the" or "my" do not make everything look relevant.
STOPWORDS = {
    "a", "an", "and", "the", "to", "of", "for", "my", "is", "are", "in",
    "on", "at", "with", "i", "me", "need", "needs", "please", "should",
    "every", "each", "some", "this", "that", "it", "be", "can", "do",
}

# Obvious pet-care synonyms, mapped onto a shared "concept" word. This is a
# hand-made shortcut so that, for example, a request to "feed" still matches a
# fact that talks about "meals". Keys and values are STEMMED forms (e.g. we
# write "meal", not "meals", because stemming runs first). It only covers words
# we listed by hand; embeddings would handle synonyms automatically.
SYNONYMS = {
    "meal": "feed",
    "food": "feed",
    "eat": "feed",
    "feeding": "feed",
    "stroll": "walk",
    "exercise": "walk",
    "brush": "groom",
    "old": "senior",
    "aging": "senior",
    "elderly": "senior",
}

DEFAULT_KNOWLEDGE_DIR = "knowledge"


@dataclass
class Fact:
    """A single retrieved piece of guidance from the knowledge base."""

    source: str   # which file it came from, e.g. "dog_walking.md"
    topic: str    # the file's heading, e.g. "Dog Walking Guidance"
    text: str     # the fact itself
    score: int = 0  # how many request words matched (filled in during search)


def _stem(word: str) -> str:
    """Chop a word down to a rough root so different word forms match.

    Examples: "walking" -> "walk", "dogs" -> "dog", "puppies" -> "puppy",
    "feeding" -> "feed". This is a simple hand-made stemmer (not perfect,
    but easy to understand). The length guard stops us over-shortening tiny
    words like "gas".
    """
    for suffix in ("ing", "ies", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            if suffix == "ies":
                return word[:-3] + "y"  # puppies -> puppy
            root = word[: -len(suffix)]
            # English doubles the final consonant before "-ing" (trim -> trimming,
            # run -> running). Undo that so "trimming" becomes "trim", not "trimm".
            # Only collapse doubled CONSONANTS, so "feeding" -> "feed" stays intact.
            if suffix == "ing" and len(root) >= 2 and root[-1] == root[-2] and root[-1] not in "aeiou":
                root = root[:-1]
            return root
    return word


def _tokens(text: str) -> set:
    """Turn text into a set of stemmed, meaningful words.

    Steps: lowercase and drop punctuation, remove stopwords, stem, then map
    synonyms onto a shared concept word.
    Example: "Feeding my elderly dogs!" -> {"feed", "senior", "dog"}
    """
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    result = set()
    for word in cleaned.split():
        if word in STOPWORDS:
            continue
        stem = _stem(word)
        result.add(SYNONYMS.get(stem, stem))  # swap in the concept word if we have one
    return result


def load_facts(knowledge_dir: str = DEFAULT_KNOWLEDGE_DIR) -> list:
    """Read every Markdown file in the knowledge folder into a list of Facts.

    Each bullet line ("- ...") becomes one Fact, tagged with its file name
    and the file's top heading ("# ...").
    """
    facts = []
    folder = Path(knowledge_dir)
    for path in sorted(folder.glob("*.md")):
        topic = path.stem  # fallback if no heading is found
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                topic = line[2:].strip()
            elif line.startswith("- "):
                facts.append(Fact(source=path.name, topic=topic, text=line[2:].strip()))
    return facts


def retrieve(query: str, facts: list, top_k: int = 3) -> list:
    """Return the top_k facts most relevant to the query.

    Relevance = how many meaningful words the fact shares with the query.
    Facts that share no words are dropped. Results are sorted best-first.
    """
    query_words = _tokens(query)
    scored = []
    for fact in facts:
        fact_words = _tokens(fact.text)
        overlap = len(query_words & fact_words)  # words in BOTH sets
        if overlap > 0:
            scored.append(Fact(fact.source, fact.topic, fact.text, score=overlap))
    scored.sort(key=lambda f: f.score, reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    # Quick manual check: run `python retriever.py` to see retrieval in action
    # without needing the AI model or an API key.
    all_facts = load_facts()
    print(f"Loaded {len(all_facts)} facts from the knowledge base.\n")

    for sample in ["walk my senior dog", "how often to feed a puppy", "cat litter box"]:
        print(f"Request: {sample!r}")
        for fact in retrieve(sample, all_facts):
            print(f"  [{fact.score}] ({fact.source}) {fact.text}")
        print()
