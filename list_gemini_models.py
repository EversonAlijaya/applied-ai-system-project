"""List the Gemini models your key can use.

We use this to find a current model name (Google retires old ones).
Run:  python3 list_gemini_models.py
"""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

print("Models that support text generation:\n")
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or []
    if "generateContent" in actions:
        print(f"  {model.name}")
