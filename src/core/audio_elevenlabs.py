import os
import requests
import uuid
from pathlib import Path

# --- CONFIGURAÇÃO DE CAMINHOS ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent 
MEDIA_DIR = BASE_DIR / "media" 
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# --- CONFIGURAÇÃO API ---
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
CHUNK_SIZE = 1024

def generate_audio_tts(text: str, voice_id: str, tenant_slug: str) -> str:
    """
    Gera áudio a partir de texto usando ElevenLabs Multilingual v2.
    Retorna o caminho absoluto do arquivo salvo.
    """
    
    if not ELEVENLABS_API_KEY:
        print("⚠️ Sem chave ElevenLabs. Impossível gerar áudio.")
        return ""

    # URL para Text-to-Speech
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream" # Adicionado /stream para garantir MP3 direto

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }

    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2", # Melhor modelo para PT-BR
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    try:
        print(f"🎙️ Gerando áudio ElevenLabs ({len(text)} chars)...")
        # IMPORTANTÍSSIMO: stream=True evita que o áudio venha corrompido ou como ruído
        response = requests.post(url, json=data, headers=headers, stream=True)
        
        if response.status_code != 200:
            print(f"❌ Erro ElevenLabs ({response.status_code}): {response.text}")
            raise Exception(f"Erro na API: {response.text}")

        # Salvar Arquivo
        tenant_dir = MEDIA_DIR / tenant_slug
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"audio_{uuid.uuid4().hex}.mp3"
        filepath = tenant_dir / filename

        # Gravação em chunks para garantir integridade do binário
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

        print(f"✅ Áudio salvo e íntegro: {filepath}")
        return str(filepath)

    except Exception as e:
        print(f"❌ Falha crítica no Audio Core: {e}")
        return ""