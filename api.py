import os
import uuid
import re
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from openai import OpenAI
import replicate
from elevenlabs.client import ElevenLabs
from google import genai
from google.genai import types

# ✅ IMPORTA sua geração local (Flux -> salva em /media)
from src.core.image_flux import generate_image_flux  # ajuste se seu import for diferente

load_dotenv()

# =========================
# Helpers
# =========================
def slugify(value: str) -> str:
    if not value:
        return "default"
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "default"


# ✅ base público do backend (o que o front consegue acessar)
API_PUBLIC_BASE = os.getenv("API_PUBLIC_BASE", "http://localhost:8000").rstrip("/")

# ✅ diretórios absolutos
BASE_DIR = Path(__file__).resolve().parent  # iagencia-core/
MEDIA_DIR = BASE_DIR / "media"
STATIC_DIR = BASE_DIR / "static"

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# Clients
# =========================
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client_eleven = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Cliente Google (Inicialização segura)
try:
    client_google = genai.Client(
        api_key=os.getenv("GOOGLE_API_KEY"),
        vertexai=True,
        project=os.getenv("GOOGLE_PROJECT_ID"),
        location="us-central1",
    )
    HAS_GOOGLE = True
except Exception:
    HAS_GOOGLE = False
    print("⚠️ Google Veo não configurado corretamente. Modo Prime desativado.")

app = FastAPI()

# =========================
# Static mounts
# =========================
# ✅ Agora o navegador acessa:
# - http://localhost:8000/static/...
# - http://localhost:8000/media/...
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Tenants / Voices
# =========================
TENANTS = {
    "pontogov": {
        "name": "Candidato João",
        "brand_color": "#2563eb",
        "voice_style": "serious",
        "video_style": "realistic, news footage, 4k",
    },
    "voy-saude": {
        "name": "Voy Saúde",
        "brand_color": "#ec4899",
        "voice_style": "energetic",
        "video_style": "social media aesthetic, clean",
    },
    "mugo": {
        "name": "Agência Mugô",
        "brand_color": "#000000",
        "voice_style": "professional",
        "video_style": "high end advertising",
    },
}

VOICES_DB = {
    "pontogov": [{"id": "JBFqnCBsd6RMkjVDRZzb", "name": "Candidato João (Clone)", "category": "cloned"}],
    "voy-saude": [{"id": "EXAVITQu4vr4xnSDxMaL", "name": "Dra. Ana (Oficial)", "category": "stock"}],
    "mugo": [{"id": "EXAVITQu4vr4xnSDxMaL", "name": "Padrão Agência", "category": "stock"}],
}

# =========================
# AI Classes
# =========================
class BrainAI:
    @staticmethod
    def generate_text(prompt, system_role):
        try:
            response = client_openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception:
            return "Erro Texto"


class VisionAI:
    @staticmethod
    def generate_video_kling(prompt, style_suffix):
        """
        Mantive seu Kling/Luma aqui como fallback.
        Retorna o output como vem do Replicate (pode ser URL/string/list).
        """
        try:
            print("🎬 Gerando Vídeo (Standard/Kling)...")
            output = replicate.run(
                "luma/ray",
                input={
                    "prompt": f"{prompt}, {style_suffix}",
                    "aspect_ratio": "16:9",
                    "loop": False,
                },
            )
            return output
        except Exception:
            return None


class AudioAI:
    @staticmethod
    def generate_speech_url(text, voice_id):
        return "https://www2.cs.uic.edu/~i101/SoundFiles/StarWars3.wav"  # Mock


class MusicAI:
    @staticmethod
    def generate_track(prompt):
        return "https://actions.google.com/sounds/v1/ambiences/coffee_shop.ogg"  # Mock


class GoogleVeoAI:
    @staticmethod
    def generate_video(prompt: str):
        if not HAS_GOOGLE:
            return None

        try:
            print(f"💎 Gerando Vídeo PRIME (Google Veo): {prompt}")

            response = client_google.models.generate_video(
                model="veo-001",
                prompt=prompt,
                config=types.GenerateVideoConfig(aspect_ratio="16:9", duration_seconds=6),
            )

            video_bytes = response.generated_video.bytes
            filename = f"veo_{uuid.uuid4().hex}.mp4"
            filepath = STATIC_DIR / filename
            filepath.write_bytes(video_bytes)

            print("✅ Veo gerado com sucesso!")
            return f"{API_PUBLIC_BASE}/static/{filename}"
        except Exception as e:
            print(f"❌ Erro Google Veo: {e}")
            return None


# =========================
# Helpers: local path -> URL pública
# =========================
def file_path_to_media_url(filepath_str: str) -> str:
    """
    Recebe um path absoluto (ou relativo) e devolve URL pública /media/...
    """
    p = Path(filepath_str).resolve()
    try:
        rel = p.relative_to(MEDIA_DIR.resolve())
    except Exception:
        # fallback: tenta achar o "media" no caminho
        # (melhor do que quebrar)
        parts = p.parts
        if "media" in parts:
            idx = parts.index("media")
            rel = Path(*parts[idx + 1 :])
        else:
            rel = p.name

    rel_url = str(rel).replace("\\", "/")
    return f"{API_PUBLIC_BASE}/media/{rel_url}"


# =========================
# Routes
# =========================
@app.post("/creation/list-voices")
async def list_voices(request: Request):
    data = await request.json()
    tenant = slugify(data.get("tenant_slug", "mugo"))
    return {"voices": VOICES_DB.get(tenant, VOICES_DB["mugo"])}


@app.post("/creation/generate-image")
async def generate_asset(request: Request):
    data = await request.json()

    prompt = data.get("prompt_en", "") or ""
    media_type = data.get("media_type", "image")
    tenant_slug = slugify(data.get("tenant_slug", "mugo"))
    quality_mode = data.get("quality_mode", "standard")  # 'standard' ou 'prime'
    ar = data.get("ar", "16:9")  # ✅ se o front enviar

    settings = TENANTS.get(tenant_slug, TENANTS["mugo"])

    # ---------- VIDEO ----------
    if media_type == "video":
        video_url = None

        # 1) Tenta VEO (prime)
        if quality_mode == "prime":
            video_url = GoogleVeoAI.generate_video(f"{prompt}, {settings['video_style']}")

        # 2) Fallback Kling
        if not video_url:
            if quality_mode == "prime":
                print("⚠️ Caindo para Kling (Fallback)...")
            video_url = VisionAI.generate_video_kling(prompt, settings["video_style"])

        default_voice = VOICES_DB.get(tenant_slug, VOICES_DB["mugo"])[0]["id"]
        audio_url = AudioAI.generate_speech_url(prompt, default_voice)

        return {
            "url": video_url,
            "audio_url": audio_url,
            "type": "video",
            "provider": "veo" if quality_mode == "prime" and video_url else "kling",
        }

    # ---------- IMAGE ----------
    # ✅ Agora a imagem é gerada e salva localmente em /media/<tenant_slug>/
    filepath = generate_image_flux(prompt=prompt, tenant_id=tenant_slug, ar=ar)
    public_url = file_path_to_media_url(filepath)

    return {"url": public_url, "type": "image", "provider": "flux-local"}


@app.post("/creation/generate-music")
async def generate_music(request: Request):
    return {"url": MusicAI.generate_track("")}


@app.post("/creation/generate-avatar")
async def generate_avatar(request: Request):
    return {
        "url": "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
    }


@app.post("/planning/export-pptx")
async def export_pptx(request: Request):
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    # ✅ host 0.0.0.0 ok pra subir, mas NUNCA use isso em URL de retorno.
    uvicorn.run(app, host="0.0.0.0", port=8000)
