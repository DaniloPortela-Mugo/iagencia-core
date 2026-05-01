import os
import io
import json
import uuid
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles # <--- IMPORTANTE PARA VEO
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from openai import OpenAI
import replicate
from elevenlabs.client import ElevenLabs
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from google import genai
from google.genai import types

load_dotenv()
API_PUBLIC_BASE = os.getenv("API_PUBLIC_BASE", "http://localhost:8000")

# Clientes
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client_eleven = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Cliente Google (Inicialização segura)
try:
    client_google = genai.Client(
        api_key=os.getenv("GOOGLE_API_KEY"),
        vertexai=True, 
        project=os.getenv("GOOGLE_PROJECT_ID"), 
        location="us-central1"
    )
    HAS_GOOGLE = True
except:
    HAS_GOOGLE = False
    print("⚠️ Google Veo não configurado corretamente. Modo Prime desativado.")

app = FastAPI()

# --- CONFIGURAÇÃO DE ARQUIVOS ESTÁTICOS (PARA VEO) ---
# Cria a pasta se não existir
if not os.path.exists("static"):
    os.makedirs("static")

# Permite que o navegador acesse http://localhost:8000/static/video.mp4
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (Mantenha os dicionários TENANTS e VOICES_DB iguais ao anterior) ...
TENANTS = {
    "pontogov": {"name": "Candidato João", "brand_color": "#2563eb", "voice_style": "serious", "video_style": "realistic, news footage, 4k"},
    "voy-saude": {"name": "Voy Saúde", "brand_color": "#ec4899", "voice_style": "energetic", "video_style": "social media aesthetic, clean"},
    "mugo": {"name": "Agência Mugô", "brand_color": "#000000", "voice_style": "professional", "video_style": "high end advertising"}
}
VOICES_DB = {
    "pontogov": [{"id": "JBFqnCBsd6RMkjVDRZzb", "name": "Candidato João (Clone)", "category": "cloned"}],
    "voy-saude": [{"id": "EXAVITQu4vr4xnSDxMaL", "name": "Dra. Ana (Oficial)", "category": "stock"}],
    "mugo": [{"id": "EXAVITQu4vr4xnSDxMaL", "name": "Padrão Agência", "category": "stock"}]
}

# ... (Mantenha BrainAI, VisionAI (Flux/Kling), AudioAI, MusicAI, DeckBuilder iguais) ...

class BrainAI:
    @staticmethod
    def generate_text(prompt, system_role):
        try:
            response = client_openai.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_role}, {"role": "user", "content": prompt}])
            return response.choices[0].message.content
        except: return "Erro Texto"

class VisionAI: # Kling & Flux
    @staticmethod
    def generate_image(prompt, ar="16:9"):
        try:
            output = replicate.run("black-forest-labs/flux-schnell", input={"prompt": prompt, "aspect_ratio": ar, "output_format": "jpg"})
            return output[0]
        except: return "https://via.placeholder.com/800x450?text=Erro+Flux"

    @staticmethod
    def generate_video_kling(prompt, style_suffix):
        try:
            print(f"🎬 Gerando Vídeo (Standard/Kling)...")
            output = replicate.run("luma/ray", input={"prompt": f"{prompt}, {style_suffix}", "aspect_ratio": "16:9", "loop": False})
            return output
        except: return None

class AudioAI:
    @staticmethod
    def generate_speech_url(text, voice_id):
        return "https://www2.cs.uic.edu/~i101/SoundFiles/StarWars3.wav" # Mock

class MusicAI:
    @staticmethod
    def generate_track(prompt):
        return "https://actions.google.com/sounds/v1/ambiences/coffee_shop.ogg" # Mock

# --- CLASSE NOVA: GOOGLE VEO ---
class GoogleVeoAI:
    @staticmethod
    def generate_video(prompt: str):
        if not HAS_GOOGLE: return None
        try:
            print(f"💎 Gerando Vídeo PRIME (Google Veo): {prompt}")
            
            # Chamada Oficial ao Veo
            response = client_google.models.generate_video(
                model='veo-001', # Ou 'video-generation-001'
                prompt=prompt,
                config=types.GenerateVideoConfig(
                    aspect_ratio="16:9",
                    duration_seconds=6
                )
            )
            
            # Salva o arquivo localmente
            video_bytes = response.generated_video.bytes
            filename = f"veo_{uuid.uuid4()}.mp4"
            filepath = os.path.join("static", filename)
            
            with open(filepath, "wb") as f:
                f.write(video_bytes)
            
            # Retorna URL local
            print("✅ Veo gerado com sucesso!")
            return f"{API_PUBLIC_BASE}/static/{filename}"

        except Exception as e:
            print(f"❌ Erro Google Veo: {e}")
            return None # Retorna None para ativar o Fallback

# --- ROTAS ---

@app.post("/creation/list-voices")
async def list_voices(request: Request):
    data = await request.json()
    tenant = data.get('tenant_slug', 'mugo')
    return {"voices": VOICES_DB.get(tenant, VOICES_DB['mugo'])}

@app.post("/creation/generate-image")
async def generate_asset(request: Request):
    data = await request.json()
    prompt = data.get('prompt_en', '')
    media_type = data.get('media_type', 'image')
    tenant_slug = data.get('tenant_slug', 'mugo')
    quality_mode = data.get('quality_mode', 'standard') # 'standard' ou 'prime'
    
    settings = TENANTS.get(tenant_slug, TENANTS['mugo'])

    if media_type == 'video':
        video_url = None
        
        # 1. Tenta VEO se for Prime
        if quality_mode == 'prime':
            video_url = GoogleVeoAI.generate_video(f"{prompt}, {settings['video_style']}")
        
        # 2. Fallback para Kling (Se Veo falhar ou for Standard)
        if not video_url:
            if quality_mode == 'prime': print("⚠️ Caindo para Kling (Fallback)...")
            video_url = VisionAI.generate_video_kling(prompt, settings['video_style'])
            
        # Áudio
        default_voice = VOICES_DB.get(tenant_slug, VOICES_DB['mugo'])[0]['id']
        audio_url = AudioAI.generate_speech_url(prompt, default_voice)
        
        return {"url": video_url, "audio_url": audio_url, "type": "video", "provider": "veo" if quality_mode == 'prime' and video_url else "kling"}
    
    elif media_type == 'image':
        image_url = VisionAI.generate_image(prompt)
        return {"url": image_url, "type": "image"}

# ... (Manter rotas de Music, Avatar, PPTX, Production iguais) ...
@app.post("/creation/generate-music")
async def generate_music(request: Request): return {"url": MusicAI.generate_track("")}
@app.post("/creation/generate-avatar")
async def generate_avatar(request: Request): return {"url": "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"}
@app.post("/planning/export-pptx") # Copiar do código anterior
async def export_pptx(request: Request): return {"status": "ok"} # Simplificado aqui, use o completo

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)