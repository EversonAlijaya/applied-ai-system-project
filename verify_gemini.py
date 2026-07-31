"""Quick one-off check that your Gemini API key works.

This is NOT part of the app. It just confirms the plumbing is correct before
we build the real planner on top of it.

Run it with:  python verify_gemini.py
"""

import os

from dotenv import load_dotenv
from google import genai

# Read the .env file and load GEMINI_API_KEY into the environment.
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key or api_key == "your-key-goes-here":
    raise SystemExit(
        "No real GEMINI_API_KEY found.\n"
        "Create a file named .env (copy .env.example) and paste your key after the =."
    )

# Create the client (the object that talks to Gemini) using your key.
client = genai.Client(api_key=api_key)

# Send one tiny request. If the key is valid, we get a reply back.
response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Reply with exactly this sentence: PawPal AI connection works.",
)

print("Gemini replied:", response.text.strip())
print("\nSuccess: your key works and we can build the planner.")
