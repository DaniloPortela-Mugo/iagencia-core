import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# --- localizar e carregar .env da raiz ---
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

# --- validar chave ---
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("GOOGLE_API_KEY não encontrada no ambiente")

# --- cliente Gemini oficial ---
client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-1.5-pro",
    contents="Say hello in English."
)

print(response.text)
