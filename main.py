import sys
import os
import shutil
import uuid
import json
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import traceback

# --- 1. CONFIGURAÇÃO DE AMBIENTE ---
load_dotenv()

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

print("✅ .env usado em:", ENV_PATH)

# --- 2. CONFIGURAÇÃO DE CAMINHOS (CRUCIAL ESTAR AQUI) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "src"))

# --- 3. PERSISTÊNCIA DE TAREFAS (AGORA FUNCIONA PORQUE current_dir EXISTE) ---
TASKS_FILE = os.path.join(current_dir, "data", "tasks.json")
Path(os.path.join(current_dir, "data")).mkdir(parents=True, exist_ok=True)

# Cria o arquivo se não existir
if not os.path.exists(TASKS_FILE):
    with open(TASKS_FILE, "w") as f:
        json.dump([], f)

def load_tasks_from_db():
    try:
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    except: return []

def save_tasks_to_db(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

# --- 4. BANCO DE USUÁRIOS (SIMULADO) ---
USERS_DB = {
    "julia@iagencia.br": {"id": "julia", "name": "Julia", "role": "Plan", "password": "123"},
    "danilo@iagencia.br": {"id": "danilo", "name": "Danilo", "role": "Art", "password": "123"},
    "kleber@iagencia.br": {"id": "kleber", "name": "Kleber", "role": "Admin", "password": "123"},
    "monica@iagencia.br": {"id": "monica", "name": "Mônica", "role": "Copy", "password": "123"},
    "rodrigo@iagencia.br": {"id": "rodrigo", "name": "Rodrigo", "role": "Media", "password": "123"},
}

# --- 5. IMPORTS DOS SERVIÇOS ---
from services.prompt_logic import generate_prompt_payload
from core.image_flux import generate_image_flux
from core.video_kling import generate_video_kling
from core.audio_elevenlabs import generate_audio_tts
from core.database import init_db, save_asset, list_assets
from services.copy_llm import generate_copy_content, chat_with_agent

# Imports de Planejamento e Agentes
from src.services.planning_agent import chat_with_planner, load_tenant_context
from src.agents.research import get_market_trends
from src.agents.strategy import analyze_competitors_radar
from src.agents.analytics import generate_performance_insights


# =========================
# Lifespan (startup/shutdown)
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

MEDIA_DIR = Path(__file__).resolve().parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

def file_path_to_media_url(filepath: str) -> str:
    p = Path(filepath).resolve()
    media_root = MEDIA_DIR.resolve()
    rel = p.relative_to(media_root).as_posix()
    return f"/media/{quote(rel)}"

def _public_media_url(tenant_slug: str, filename: str) -> str:
    tenant_safe = quote(tenant_slug, safe="")
    return f"http://localhost:8000/media/{tenant_safe}/{filename}"

# --- CORS (API) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CORS EXTRA PARA /media ---
@app.middleware("http")
async def add_cors_headers_for_media(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/media/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response


# --- MODELOS (PYDANTIC) ---

class LoginRequest(BaseModel):
    email: str
    password: str

class TaskItem(BaseModel):
    id: int
    title: str
    description: str
    client: str
    status: str # todo, doing, done
    assignees: List[str] = []
    formats: List[str] = []
    tone: str

class PlanningChatRequest(BaseModel):
    message: str
    history: list
    grid_context: str
    tenant_slug: str = "mugo"

class DashboardRequest(BaseModel):
    tenant_slug: str
    current_metrics: Optional[Dict[str, Any]] = None 

class GenerationRequest(BaseModel):
    tenant_slug: str
    media_type: str = "image"
    quality_mode: Optional[str] = "standard"
    ar: str = "16:9"
    prompt_en: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    ref_image: Optional[str] = None

class AudioRequest(BaseModel):
    text: str
    voice_id: str
    tenant_slug: str

class SaveAssetRequest(BaseModel):
    tenant_slug: str
    title: str
    type: str
    url: str
    client: str
    campaign: str
    tags: list = []

class CopyRequest(BaseModel):
    format: str
    client: str
    sub_client: Optional[str] = ""
    title: Optional[str] = ""
    duration: Optional[str] = ""
    topic: str
    tone: str
    framework: str
    target_audience: Optional[str] = ""

class ChatRequest(BaseModel):
    current_text: str
    user_message: str
    active_agent: str

# --- HELPERS ---
ALLOWED_AR = {"1:1", "4:5", "9:16", "16:9", "21:9"}
def _normalize_ar(ar_value: str) -> str:
    if not ar_value: return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean if ar_clean in ALLOWED_AR else "16:9"

# =========================
# ROTAS
# =========================

# 1) LOGIN
@app.post("/auth/login")
async def login_endpoint(req: LoginRequest):
    user = USERS_DB.get(req.email)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return {"user": user}

# 2) TAREFAS (GET)
@app.get("/planning/tasks")
async def get_tasks_endpoint(client_id: Optional[str] = None):
    all_tasks = load_tasks_from_db()
    if not client_id or client_id == 'all':
        return {"tasks": all_tasks}
    filtered = [t for t in all_tasks if t.get("client") == client_id]
    return {"tasks": filtered}

# 3) TAREFAS (SAVE)
@app.post("/planning/tasks/save")
async def save_task_endpoint(task: TaskItem):
    all_tasks = load_tasks_from_db()
    existing_idx = next((index for (index, d) in enumerate(all_tasks) if d["id"] == task.id), None)
    task_dict = task.dict()
    if existing_idx is not None:
        all_tasks[existing_idx] = task_dict
    else:
        all_tasks.append(task_dict)
    save_tasks_to_db(all_tasks)
    return {"status": "success", "task": task_dict}

# 4) TAREFAS (DELETE)
@app.delete("/planning/tasks/{task_id}")
async def delete_task_endpoint(task_id: int):
    all_tasks = load_tasks_from_db()
    all_tasks = [t for t in all_tasks if t["id"] != task_id]
    save_tasks_to_db(all_tasks)
    return {"status": "deleted"}

# 5) DASHBOARD
@app.post("/planning/dashboard-data")
async def get_dashboard_intelligence(req: DashboardRequest):
    try:
        context = load_tenant_context(req.tenant_slug)
        print(f"🔍 [Dashboard] Buscando inteligência para {req.tenant_slug}...")
        trends = get_market_trends(context)
        competitors = analyze_competitors_radar(context)
        metrics_to_pass = req.current_metrics if req.current_metrics else {}
        insight = generate_performance_insights(metrics_to_pass, context)
        return { "trends": trends, "competitors": competitors, "performance_insight": insight }
    except Exception as e:
        print(f"❌ Erro Dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar inteligência: {str(e)}")

# 6) CHAT PLANEJAMENTO
@app.post("/planning/chat")
async def planning_chat_endpoint(req: PlanningChatRequest):
    try:
        response = chat_with_planner(req.history, req.grid_context, tenant_slug=req.tenant_slug)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 7) REDAÇÃO
@app.post("/creation/generate-copy")
async def generate_copy_endpoint(req: CopyRequest):
    try:
        text_result = generate_copy_content(req.dict())
        return {"status": "success", "prompt_pt": text_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 8) CHAT CREATION
@app.post("/creation/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        response_text = chat_with_agent(req.current_text, req.user_message, req.active_agent)
        return {"message": response_text, "agent": req.active_agent}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 9) GERAÇÃO MÍDIA
@app.post("/creation/generate-image")
async def generate_media_endpoint(req: GenerationRequest):
    try:
        media_type = (req.media_type or "image").lower().strip()
        ar = _normalize_ar(req.ar)
        payload_data = { "raw_data": req.raw_data, "ar": ar, "media_type": media_type, "target_platform": "veo" if req.quality_mode == "prime" else "flux" }
        processed = generate_prompt_payload(payload_data)
        prompt_final = processed.get("prompt")
        
        if not prompt_final: raise HTTPException(status_code=400, detail="Prompt vazio.")

        if media_type == "video":
            local_path = generate_video_kling(prompt_final, req.tenant_slug, ar=ar)
            return { "url": file_path_to_media_url(local_path), "type": "video", "prompt": prompt_final, "provider": "kling/replicate", "ar": ar }

        local_path = generate_image_flux(prompt_final, req.tenant_slug, ar=ar)
        return { "url": file_path_to_media_url(local_path), "type": "image", "prompt": prompt_final, "provider": "flux/replicate", "ar": ar }
    except Exception as e:
        print("❌ Erro Media:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))

# 10) ÁUDIO
@app.post("/creation/generate-audio")
async def generate_audio_endpoint(req: AudioRequest):
    try:
        local_path_str = generate_audio_tts(req.text, req.voice_id, req.tenant_slug)
        if not local_path_str: raise HTTPException(status_code=500, detail="Erro ElevenLabs.")
        filename = Path(local_path_str).name
        return {"status": "success", "audio_url": _public_media_url(req.tenant_slug, filename)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 11) UPLOAD
@app.post("/upload")
async def upload_file(file: UploadFile = File(...), tenant_slug: str = Form(...)):
    try:
        tenant_dir = MEDIA_DIR / tenant_slug
        tenant_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename).suffix
        filename = f"upload_{uuid.uuid4().hex}{ext}"
        with open(tenant_dir / filename, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        return {"url": _public_media_url(tenant_slug, filename)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 12) LIBRARY SAVE
@app.post("/library/save")
async def save_asset_endpoint(req: SaveAssetRequest):
    try:
        asset_id = save_asset(req.dict())
        return {"status": "success", "id": asset_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 13) LIBRARY LIST
@app.get("/library/assets")
async def get_assets_endpoint(tenant_slug: str, type: str = "all"):
    try:
        assets = list_assets(tenant_slug, type)
        return {"assets": assets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)