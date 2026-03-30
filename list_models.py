import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("GOOGLE_API_KEY não encontrada no ambiente")

client = genai.Client(api_key=api_key)

models = client.models.list()

for m in models:
    name = getattr(m, "name", "")
    supported = getattr(m, "supported_actions", None) or getattr(m, "supportedMethods", None)
    print(f"- {name} | supported: {supported}")
