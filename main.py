from __future__ import annotations
import os
import json
import uuid
import requests
import hmac
import hashlib
import urllib.parse
import random
import re
import base64
import time
import traceback
import shutil
from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime
from pathlib import Path
import asyncio
import sys
import os
from src.services.planning_agent import load_tenant_context, get_client
from src.services.video_logic import generate_cinematic_script
from src.services.crypto_utils import encrypt_secret, decrypt_secret

# Framework & Libs
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from prompt_refiner import refine_prompt_for_flux
from pathlib import Path
try:
    from deep_translator import GoogleTranslator
    _GOOGLE_TRANSLATOR_AVAILABLE = True
except ImportError:
    _GOOGLE_TRANSLATOR_AVAILABLE = False
from src.services.prompt_video_refiner import refine_and_translate_video

app = FastAPI()

# Agentes

from src.services.planning_agent import load_tenant_context, get_client
from src.services.atendimento_logic import process_atendimento_briefing
from src.services.copywriting_logic import generate_elite_copy
from src.services.planning_agent import chat_with_planner
from src.services.social_agent import get_social_intelligence, generate_social_grid
from typing import Dict, Optional, List
from starlette.concurrency import run_in_threadpool
# ✅ CRIE O APP ANTES DE QUALQUER app.mount / app.add_middleware
app = FastAPI()

# ==========================================
# ⚙️ CONFIGURAÇÃO & INICIALIZAÇÃO
# ==========================================
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
google_key = os.getenv("GOOGLE_API_KEY")
google_cx = os.getenv("GOOGLE_SEARCH_CX")

client = OpenAI(api_key=api_key) if api_key else None

# ==========================================
# 💳 CREDITOS API (Wallets + Logs)
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

GOOGLE_DRIVE_CLIENT_ID = os.getenv("GOOGLE_DRIVE_CLIENT_ID")
GOOGLE_DRIVE_CLIENT_SECRET = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET")
GOOGLE_DRIVE_REDIRECT_URI = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")
GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID")
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET") or os.getenv("FLASK_SECRET_KEY") or "change-me"

GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
]

API_CREDITS_COST_IMAGE = float(os.getenv("API_CREDITS_COST_IMAGE", "0") or "0")
API_CREDITS_COST_VIDEO = float(os.getenv("API_CREDITS_COST_VIDEO", "0") or "0")

def _supabase_headers() -> Optional[dict]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

def _supabase_get(url: str) -> dict:
    headers = _supabase_headers()
    if not headers:
        raise Exception("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY não configurados.")
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code >= 300:
        raise Exception(f"Supabase GET {resp.status_code}: {resp.text}")
    return resp.json()

def _supabase_post(url: str, payload: dict) -> dict:
    headers = _supabase_headers()
    if not headers:
        raise Exception("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY não configurados.")
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 300:
        raise Exception(f"Supabase POST {resp.status_code}: {resp.text}")
    return resp.json()

def _supabase_patch(url: str, payload: dict) -> dict:
    headers = _supabase_headers()
    if not headers:
        raise Exception("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY não configurados.")
    resp = requests.patch(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 300:
        raise Exception(f"Supabase PATCH {resp.status_code}: {resp.text}")
    return resp.json()

def _guess_content_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".json":
        return "application/json"
    if ext == ".md":
        return "text/markdown"
    if ext == ".txt":
        return "text/plain"
    if ext == ".csv":
        return "text/csv"
    if ext in [".yml", ".yaml"]:
        return "text/yaml"
    return "application/octet-stream"

def _is_probably_text(data: bytes) -> bool:
    sample = data[:1024]
    if b"\x00" in sample:
        return False
    nontext = 0
    for b in sample:
        if b < 9 or (b > 13 and b < 32):
            nontext += 1
    return (nontext / max(len(sample), 1)) < 0.1

def _walk_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            files.append(p)
    return files

def _build_oauth_state(tenant_slug: str) -> str:
    payload = {
        "t": tenant_slug,
        "n": uuid.uuid4().hex,
        "ts": int(time.time()),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(OAUTH_STATE_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"

def _verify_oauth_state(state: str) -> dict:
    try:
        body, sig = state.split(".", 1)
        expected = hmac.new(OAUTH_STATE_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError("Invalid state signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        return payload
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid state: {e}")

def _get_tenant_storage_config(tenant_slug: str) -> dict:
    if not SUPABASE_URL:
        return {"provider": "gdrive", "config": {}}
    url = f"{SUPABASE_URL}/rest/v1/tenant_storage_config?select=provider,config&tenant_slug=eq.{tenant_slug}&limit=1"
    data = _supabase_get(url)
    if data and isinstance(data, list) and len(data) > 0:
        return data[0]
    return {"provider": "gdrive", "config": {}}

def _get_drive_tokens(tenant_slug: str) -> Optional[dict]:
    if not SUPABASE_URL:
        return None
    url = f"{SUPABASE_URL}/rest/v1/tenant_drive_tokens?select=*&tenant_slug=eq.{tenant_slug}&limit=1"
    data = _supabase_get(url)
    if data and isinstance(data, list) and len(data) > 0:
        row = data[0]
        if isinstance(row, dict):
            if "access_token" in row:
                row["access_token"] = decrypt_secret(row.get("access_token")) or row.get("access_token")
            if "refresh_token" in row:
                row["refresh_token"] = decrypt_secret(row.get("refresh_token")) or row.get("refresh_token")
        return row
    return None

def _upsert_drive_tokens(tenant_slug: str, payload: dict) -> dict:
    if not SUPABASE_URL:
        return {}
    url = f"{SUPABASE_URL}/rest/v1/tenant_drive_tokens?on_conflict=tenant_slug"
    safe_payload = dict(payload or {})
    if "access_token" in safe_payload:
        safe_payload["access_token"] = encrypt_secret(safe_payload.get("access_token")) or safe_payload.get("access_token")
    if "refresh_token" in safe_payload:
        safe_payload["refresh_token"] = encrypt_secret(safe_payload.get("refresh_token")) or safe_payload.get("refresh_token")
    body = {"tenant_slug": tenant_slug, **safe_payload}
    return _supabase_post(url, body)

def _refresh_drive_access_token(refresh_token: str) -> dict:
    if not GOOGLE_DRIVE_CLIENT_ID or not GOOGLE_DRIVE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google Drive OAuth não configurado.")
    token_url = "https://oauth2.googleapis.com/token"
    resp = requests.post(
        token_url,
        data={
            "client_id": GOOGLE_DRIVE_CLIENT_ID,
            "client_secret": GOOGLE_DRIVE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"Drive refresh error: {resp.text}")
    return resp.json()

def _ensure_drive_folder(access_token: str, tenant_slug: str, existing_folder_id: Optional[str] = None) -> str:
    if existing_folder_id:
        return existing_folder_id
    headers = {"Authorization": f"Bearer {access_token}"}
    parent_query = ""
    if GOOGLE_DRIVE_ROOT_FOLDER_ID:
        parent_query = f" and '{GOOGLE_DRIVE_ROOT_FOLDER_ID}' in parents"
    q = f"mimeType='application/vnd.google-apps.folder' and name='{tenant_slug}' and trashed=false{parent_query}"
    params = {"q": q, "fields": "files(id,name)"}
    resp = requests.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=params, timeout=30)
    if resp.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"Drive list error: {resp.text}")
    files = resp.json().get("files") or []
    if files:
        return files[0]["id"]

    metadata = {
        "name": tenant_slug,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if GOOGLE_DRIVE_ROOT_FOLDER_ID:
        metadata["parents"] = [GOOGLE_DRIVE_ROOT_FOLDER_ID]
    resp = requests.post("https://www.googleapis.com/drive/v3/files", headers={**headers, "Content-Type": "application/json"}, json=metadata, timeout=30)
    if resp.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"Drive create folder error: {resp.text}")
    return resp.json()["id"]

def _drive_upload_file(access_token: str, folder_id: str, filename: str, mime_type: str, file_bytes: bytes) -> str:
    metadata = {
        "name": filename,
        "parents": [folder_id],
    }
    boundary = f"===============_{uuid.uuid4().hex}_=="
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    }
    resp = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers=headers,
        data=body,
        timeout=120,
    )
    if resp.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"Drive upload error: {resp.text}")
    return resp.json()["id"]

def _list_required_default_paths(base_dir: Path) -> List[str]:
    default_dir = base_dir / "_default"
    if not default_dir.exists():
        return []
    paths: List[str] = []
    for f in _walk_files(default_dir):
        if f.name == ".DS_Store":
            continue
        rel = f.relative_to(default_dir).as_posix()
        paths.append(rel)
    return sorted(paths)

def _validate_disk_context(tenant_slug: str) -> Dict[str, Any]:
    base_dir = Path(__file__).resolve().parent / "tenant_context"
    required = set(_list_required_default_paths(base_dir))
    tenant_dir = base_dir / tenant_slug
    if not tenant_dir.exists():
        return {
            "tenant_slug": tenant_slug,
            "source": "disk",
            "required_count": len(required),
            "found_count": 0,
            "missing": sorted(required),
            "extra": [],
        }
    found = set()
    for f in _walk_files(tenant_dir):
        if f.name == ".DS_Store":
            continue
        found.add(f.relative_to(tenant_dir).as_posix())
    return {
        "tenant_slug": tenant_slug,
        "source": "disk",
        "required_count": len(required),
        "found_count": len(found),
        "missing": sorted(required - found),
        "extra": sorted(found - required),
    }

def _validate_supabase_context(tenant_slug: str) -> Dict[str, Any]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise Exception("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY não configurados.")
    headers = _supabase_headers()
    if not headers:
        raise Exception("Cabeçalhos Supabase inválidos.")
    default_url = f"{SUPABASE_URL}/rest/v1/tenant_context?select=source_path&tenant_slug=eq._default"
    tenant_url = f"{SUPABASE_URL}/rest/v1/tenant_context?select=source_path&tenant_slug=eq.{tenant_slug}"
    dres = requests.get(default_url, headers=headers, timeout=30)
    tres = requests.get(tenant_url, headers=headers, timeout=30)
    if dres.status_code != 200:
        raise Exception(f"Erro ao ler _default: {dres.status_code} {dres.text}")
    if tres.status_code != 200:
        raise Exception(f"Erro ao ler tenant: {tres.status_code} {tres.text}")
    required = set([r.get("source_path") for r in dres.json() if r.get("source_path")])
    found = set([r.get("source_path") for r in tres.json() if r.get("source_path")])
    return {
        "tenant_slug": tenant_slug,
        "source": "supabase",
        "required_count": len(required),
        "found_count": len(found),
        "missing": sorted(required - found),
        "extra": sorted(found - required),
    }

def _sync_tenant_context(tenant_slug: Optional[str] = None, *, validate: bool = True, force: bool = False) -> Dict[str, Any]:
    """
    Sincroniza arquivos de iagencia-core/tenant_context para a tabela tenant_context no Supabase.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise Exception("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY não configurados.")

    base_dir = Path(__file__).resolve().parent / "tenant_context"
    if not base_dir.exists():
        raise Exception(f"Pasta tenant_context não encontrada: {base_dir}")

    tenant_dirs = [d for d in base_dir.iterdir() if d.is_dir()]
    if tenant_slug:
        tenant_dirs = [d for d in tenant_dirs if d.name == tenant_slug]

    headers = _supabase_headers()
    if not headers:
        raise Exception("Cabeçalhos Supabase inválidos.")

    total = 0
    synced: Dict[str, int] = {}
    validations: Dict[str, Any] = {}
    for tdir in tenant_dirs:
        if validate:
            v = _validate_disk_context(tdir.name)
            validations[tdir.name] = v
            if v.get("missing") and not force:
                raise Exception(f"Contexto incompleto para {tdir.name}. Faltando {len(v.get('missing', []))} arquivo(s).")

        rows = []
        for f in _walk_files(tdir):
            if f.name == ".DS_Store":
                continue
            rel = f.relative_to(tdir).as_posix()
            data = f.read_bytes()
            is_text = _is_probably_text(data)
            content = data.decode("utf-8", errors="ignore") if is_text else base64.b64encode(data).decode("utf-8")
            rows.append({
                "tenant_slug": tdir.name,
                "source_path": rel,
                "content": content,
                "is_binary": (not is_text),
                "content_type": _guess_content_type(rel),
                "size_bytes": len(data),
                "updated_at": datetime.utcnow().isoformat(),
            })

        batch_size = 200
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            url = f"{SUPABASE_URL}/rest/v1/tenant_context"
            res = requests.post(url, headers=headers, data=json.dumps(batch), timeout=30)
            if res.status_code not in (200, 201, 204):
                raise Exception(f"Erro sync ({res.status_code}): {res.text}")

        synced[tdir.name] = len(rows)
        total += len(rows)

    return {"total": total, "synced": synced, "validation": validations}

def _apply_credit_delta(tenant_slug: str, amount: float, feature: str, description: str) -> None:
    if amount == 0:
        return
    headers = _supabase_headers()
    if not headers:
        print("⚠️ Créditos: SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY não configurados.")
        return
    try:
        # Prefer RPC (atômico) se existir
        rpc_url = f"{SUPABASE_URL}/rest/v1/rpc/credit_apply"
        payload = {
            "p_tenant_slug": tenant_slug,
            "p_amount": amount,
            "p_feature": feature,
            "p_description": description,
        }
        rpc = requests.post(rpc_url, headers=headers, data=json.dumps(payload), timeout=10)
        if rpc.status_code in (200, 204):
            return
        # Fallback não atômico se RPC não existir
        if rpc.status_code == 404:
            pass
        else:
            print(f"⚠️ Créditos: RPC falhou ({rpc.status_code}): {rpc.text}")

        wallet_url = f"{SUPABASE_URL}/rest/v1/tenants_wallets?select=credit_balance&tenant_slug=eq.{tenant_slug}&limit=1"
        wres = requests.get(wallet_url, headers=headers, timeout=10)
        current = 0.0
        if wres.status_code == 200 and wres.json():
            current = float(wres.json()[0].get("credit_balance") or 0)
            update_url = f"{SUPABASE_URL}/rest/v1/tenants_wallets?tenant_slug=eq.{tenant_slug}"
            requests.patch(update_url, headers=headers, data=json.dumps({
                "credit_balance": current + amount,
            }), timeout=10)
        else:
            insert_url = f"{SUPABASE_URL}/rest/v1/tenants_wallets"
            requests.post(insert_url, headers=headers, data=json.dumps({
                "tenant_slug": tenant_slug,
                "credit_balance": amount,
                "plan_type": "standard",
            }), timeout=10)

        log_url = f"{SUPABASE_URL}/rest/v1/credit_logs"
        requests.post(log_url, headers=headers, data=json.dumps({
            "tenant_slug": tenant_slug,
            "amount": amount,
            "feature": feature,
            "description": description,
        }), timeout=10)

    except Exception as e:
        print(f"⚠️ Créditos: falha ao registrar uso: {e}")

def _get_tenant_api_key(tenant_slug: str, provider: str) -> Optional[str]:
    try:
        headers = _supabase_headers()
        if not headers:
            return None
        url = f"{SUPABASE_URL}/rest/v1/tenant_api_keys?select=api_key&tenant_slug=eq.{tenant_slug}&provider=eq.{provider}&limit=1"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
        data = res.json()
        if not data:
            return None
        key = data[0].get("api_key")
        if isinstance(key, str) and key.strip():
            return decrypt_secret(key) or None
        return None
    except Exception:
        return None

def _resolve_provider_key(tenant_slug: str, providers: list[str]) -> Optional[str]:
    for p in providers:
        key = _get_tenant_api_key(tenant_slug, p)
        if key:
            return key
    return None

# ✅ BASE/MEDIA_DIR precisam existir antes do StaticFiles
BASE_DIR = Path(__file__).resolve().parent.parent  # iagencia-core/main.py → parent=iagencia-core → parent=meu_app
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ✅ Agora pode montar /media
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://iagencia.ia.br",
        "https://api.iagencia.ia.br",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AtendimentoRequest(BaseModel):
    tenant_slug: str
    client: str
    title: str
    raw_input: str

class AtendimentoAgentRequest(BaseModel):
    tenant_slug: str
    client: str = ""
    title: str
    raw_input: str
    objective: str = ""
    target_audience: str = ""
    cta: str = ""
    restrictions: str = ""
    boldness: int = 3
    references: str = ""

data_hoje = datetime.now().strftime("%d/%m/%Y")

# --- IMPORTAÇÃO DOS MOTORES ---
try:
    from src.core.media_service import MediaService
except ImportError:
    MediaService = None

try:
    from src.core.image_flux import generate_image_flux
    from src.core.video_kling import generate_video_kling
    from src.core.video_veo import generate_video_veo
    from src.core.image_identity import generate_identity
    from src.core.image_stability import generate_image_stability
except ImportError as e:
    print(f"⚠️  ERRO DE IMPORTAÇÃO: {e}")

    def generate_image_flux(*args, **kwargs):  # type: ignore
        raise Exception("Módulo Flux não carregado.")

    def generate_video_kling(*args, **kwargs):  # type: ignore
        raise Exception("Módulo Kling não carregado.")

    def generate_video_veo(*args, **kwargs):  # type: ignore
        raise Exception("Módulo Veo não carregado.")

    def generate_identity(*args, **kwargs):  # type: ignore
        raise Exception("Módulo Identity não carregado.")

    def generate_image_stability(*args, **kwargs):  # type: ignore
        raise Exception("Módulo Stability não carregado.")

# ==========================================
# 💾 BANCOS DE DADOS (MOCK EM MEMÓRIA - APRESENTAÇÃO MUGÔ)
# ==========================================
CHAT_HISTORY_DB: List[Dict[str, Any]] = []

TICKETS_DB = [
    {"id": 1, "tenant_slug": "mugo", "client": "Mugô", "title": "Campanha Aspirador Hoover - Dia das Mães", "status": "doing", "priority": "high", "briefing": "Focar na potência, silêncio e design minimalista para a nova linha.", "created_at": "Hoje, 09:15"},
    {"id": 2, "tenant_slug": "mugo", "client": "Mugô (Ssavon)", "title": "Ajuste Rótulo Velas Aromáticas", "status": "todo", "priority": "medium", "briefing": "Mudança na paleta de cores para tons terrosos.", "created_at": "Ontem, 14:30"},
    {"id": 3, "tenant_slug": "mugo", "client": "Mugô Institucional", "title": "Rebranding Redes Sociais", "status": "done", "priority": "normal", "briefing": "Novos templates para carrossel e stories.", "created_at": "25 Fev, 10:00"},
]

APPROVALS_DB = [
    {
        "id": 1, "tenant_slug": "mugo", "client": "Mugô", "task_id": 1,
        "campaign": "Lançamento Ssavon", "type": "image", "platform": "instagram",
        "title": "Post Instagram - Lifestyle Vela Aromática", "version": "V2", "date": "Hoje, 10:30",
        # Imagem linda de vela aromática e decoração minimalista
        "content_url": "https://images.unsplash.com/photo-1602928321679-560bb453f190?q=80&w=1000&auto=format&fit=crop",
        "versions": ["V1", "V2"], "status": "pending", 
        "general_notes": [
            {"id": 101, "user": "Atendimento", "text": "A imagem ficou linda, a luz está perfeita!", "date": "Hoje, 10:35"}
        ], 
        "audit_log": []
    },
    {
        "id": 2, "tenant_slug": "mugo", "client": "Mugô (Hoover)", "task_id": 2,
        "campaign": "Sustentação", "type": "image", "platform": "linkedin",
        "title": "Banner LinkedIn - Design e Tecnologia", "version": "V1", "date": "Ontem, 16:45",
        # Imagem de um ambiente moderno/clean
        "content_url": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?q=80&w=1000&auto=format&fit=crop",
        "versions": ["V1"], "status": "approved", 
        "general_notes": [], 
        "audit_log": []
    }
]

ASSETS_DB = [
    {"id": 1, "tenant_slug": "mugo", "title": "Logo Mugô Premium", "type": "image", "url": "https://images.unsplash.com/photo-1611162617474-5b21e879e113?q=80&w=400&auto=format&fit=crop", "client": "Mugô Institucional", "campaign": "Brandbook", "tags": ["logo", "oficial"]},
    {"id": 2, "tenant_slug": "mugo", "title": "Foto Embalagem Velas (Oficial)", "type": "image", "url": "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?q=80&w=400&auto=format&fit=crop", "client": "Mugô (Ssavon)", "campaign": "Lançamento Inverno", "tags": ["produto", "vela"]},
    {"id": 3, "tenant_slug": "mugo", "title": "Reel Lifestyle Casa", "type": "video", "url": "https://www.w3schools.com/html/mov_bbb.mp4", "client": "Mugô", "campaign": "Campanha 2026", "tags": ["video", "institucional"]},
]

# ==========================================
# 🛠️ FERRAMENTAS & UTILITÁRIOS
# ==========================================
def search_google(query: str):
    if not google_key or not google_cx:
        return "Sem chaves Google configuradas."
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        resp = requests.get(url, params={"key": google_key, "cx": google_cx, "q": query, "num": 3}, timeout=20)
        data = resp.json()
        if "items" not in data:
            return "Nenhum resultado."
        return "\n".join([f"- {i['title']}: {i['snippet']} ({i['link']})" for i in data["items"]])
    except Exception as e:
        return f"Erro busca: {e}"

def clean_aspect_ratio(ar_string: str) -> str:
    match = re.search(r"(\d+:\d+)", ar_string or "")
    if match:
        return match.group(1)
    mapping = {"Horizontal": "16:9", "Vertical": "9:16", "Quadrado": "1:1", "Feed": "4:5", "Ultrawide": "21:9"}
    for k, v in mapping.items():
        if k in (ar_string or ""):
            return v
    return "16:9"

def save_base64_image(base64_str: str, tenant_slug: str) -> str:
    """
    Mantive sua função para biblioteca/aprovação.
    (Para o estúdio, você vai usar /api/media/upload-base64, que devolve {url:"/media/..."} )
    """
    if "," in base64_str:
        base64_str = base64_str.split(",", 1)[1]
    img_data = base64.b64decode(base64_str)
    filename = f"final_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
    tenant_dir = MEDIA_DIR / tenant_slug
    tenant_dir.mkdir(parents=True, exist_ok=True)
    filepath = tenant_dir / filename
    filepath.write_bytes(img_data)
    return f"http://localhost:8000/media/{tenant_slug}/{filename}"

# ==========================================
# ✅ UPLOAD BASE64 PRA NÃO SUMIR NA TROCA DE PÁGINA
# ==========================================
class UploadBase64Request(BaseModel):
    tenant_slug: str
    data_url: str
    filename_prefix: Optional[str] = "draft"

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[-\w.+/]+);base64,(?P<data>.+)$", re.DOTALL)

def _sanitize_tenant_slug(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "", (value or "").strip().lower())
    return safe or "default"

def _mime_to_ext(mime: str) -> str:
    mime = (mime or "").lower().strip()
    if mime in ("image/png", "png"):
        return ".png"
    if mime in ("image/jpeg", "image/jpg", "jpeg", "jpg"):
        return ".jpg"
    if mime in ("image/webp", "webp"):
        return ".webp"
    return ".png"


# ROTA ESTÚDIO DE VÍDEO

class VideoScriptRequest(BaseModel):
    tenant_slug: str
    briefing_data: dict


@app.post("/creation/generate-video")
async def generate_video_endpoint(req: dict):
    refiner_data = req.get("refiner_data", {}) or {}
    tenant_slug = req.get("tenant_slug", "mugo")
    engine = (req.get("engine") or refiner_data.get("engine") or "kling").lower()

    if engine == "veo" and bool(req.get("preview_veo_json")):
        refiner_data = dict(refiner_data)
        refiner_data["veo_preview_pt"] = True
        final_preview = await refine_and_translate_video(refiner_data)
        if not final_preview or (isinstance(final_preview, str) and final_preview.lower().startswith("error")):
            raise HTTPException(status_code=400, detail=final_preview or "Erro ao gerar JSON PT")
        return {"prompt_pt_json": final_preview}

    refiner_data = dict(refiner_data)
    refiner_data["tenant_slug"] = tenant_slug
    final_prompt_or_json = await refine_and_translate_video(refiner_data)
    if not final_prompt_or_json:
        raise HTTPException(status_code=400, detail="Prompt de vídeo vazio.")
    if isinstance(final_prompt_or_json, str) and final_prompt_or_json.lower().startswith("error"):
        raise HTTPException(status_code=400, detail=final_prompt_or_json)

    config = refiner_data.get("config", {}) or {}
    ar = clean_aspect_ratio(config.get("format", "16:9"))
    refs = refiner_data.get("refs", {}) or {}
    reference_images = [
        refs.get("img1_face"),
        refs.get("img2_body"),
        refs.get("img3_product"),
        refs.get("img4_clothing"),
        refs.get("img5_style"),
    ]
    reference_images = [r for r in reference_images if isinstance(r, str) and r.strip()]
    start_image = reference_images[0] if reference_images else None
    negative_prompt = str(refiner_data.get("negative_prompt", "") or "")

    print(f"🎬 Prompt Finalizado ({engine}): {str(final_prompt_or_json)[:280]}")

    try:
        if "kling" in engine:
            local_path = await run_in_threadpool(
                generate_video_kling,
                prompt=final_prompt_or_json,
                tenant_id=tenant_slug,
                ar=ar,
                start_image=start_image,
                reference_images=reference_images,
                duration=5,
                negative_prompt=negative_prompt,
                generate_audio=False,
            )
            if API_CREDITS_COST_VIDEO > 0:
                _apply_credit_delta(
                    tenant_slug=tenant_slug,
                    amount=-API_CREDITS_COST_VIDEO,
                    feature="video",
                    description="Geração de vídeo (kling)",
                )
            return {
                "url": f"http://localhost:8000/media/{tenant_slug}/{Path(local_path).name}",
                "provider": "kling",
                "prompt": final_prompt_or_json,
            }

        if "veo" in engine:
            if start_image:
                try:
                    _, local_path, provider_used = await run_in_threadpool(
                        generate_identity,
                        prompt=final_prompt_or_json,
                        ref_image=start_image,
                        tenant_id=tenant_slug,
                        media_type="video",
                        provider="veo",
                        ar=ar,
                    )
                except Exception as e:
                    print(f"❌ Erro VEO (com referência): {type(e).__name__}: {e}")
                    raise
                if API_CREDITS_COST_VIDEO > 0:
                    _apply_credit_delta(
                        tenant_slug=tenant_slug,
                        amount=-API_CREDITS_COST_VIDEO,
                        feature="video",
                        description="Geração de vídeo (veo)",
                    )
                return {
                    "url": f"http://localhost:8000/media/{tenant_slug}/{Path(local_path).name}",
                    "provider": provider_used,
                    "prompt": final_prompt_or_json,
                }

            try:
                local_path = await run_in_threadpool(
                    generate_video_veo,
                    prompt=final_prompt_or_json,
                    tenant_slug=tenant_slug,
                    ar=ar,
                )
            except Exception as e:
                print(f"❌ Erro VEO (sem referência): {type(e).__name__}: {e}")
                raise
            if API_CREDITS_COST_VIDEO > 0:
                _apply_credit_delta(
                    tenant_slug=tenant_slug,
                    amount=-API_CREDITS_COST_VIDEO,
                    feature="video",
                    description="Geração de vídeo (veo)",
                )
            return {
                "url": f"http://localhost:8000/media/{tenant_slug}/{Path(local_path).name}",
                "provider": "veo",
                "prompt": final_prompt_or_json,
            }

        raise HTTPException(status_code=400, detail=f"Engine de vídeo não suportado: {engine}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Falha na geração de vídeo: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Falha na geração de vídeo: {str(e)}")
    
# Endpoint para o Dashboard de Inteligência
@app.post("/planning/dashboard-data")
async def dashboard_data_endpoint(req: dict):
    tenant_slug = req.get("tenant_slug", "mugo")
    return get_social_intelligence(tenant_slug)

# Endpoint para a geração mágica do Grid
@app.post("/SocialMedia/grid/generate")
async def generate_grid_endpoint(req: dict):
    tenant_slug = req.get("tenant_slug", "mugo")
    context = req.get("context", "")
    grid_data = await generate_social_grid(tenant_slug, context)
    return {"grid": grid_data}


@app.post("/SocialMedia/chat")
async def social_media_chat(req: dict):
    response = chat_with_planner(
        history=req.get("history", []),
        current_grid_context=req.get("grid_context", ""),
        tenant_slug=req.get("tenant_slug", "mugo")
    )
    return {"response": response}



async def generate_elite_copy(tenant_slug: str, briefing_data: dict):
    """
    O Redator de Elite da IAgência: Transforma o briefing técnico em 
    copy de alta conversão injetando o DNA da marca.
    """
    client = get_client()
    brand_dna = load_tenant_context(tenant_slug)

    # Extração e fallback de segurança para o briefing
    summary = briefing_data.get("summary", "Sem resumo disponível")
    key_message = briefing_data.get("key_message", "Focar na autoridade da marca")
    tone = briefing_data.get("tone", "Profissional e Direto")
    deliverables = briefing_data.get("deliverables", ["Post para Redes Sociais"])
    tech_specs = briefing_data.get("tech_requirements", "Linguagem natural")

    system_prompt = f"""
    VOCÊ É O REDATOR-CHEFE (COPYWRITER SÊNIOR) DA IAGÊNCIA.
    Sua missão é destruir o amadorismo e clichês de marketing.
    Você escreve textos que geram desejo imediato e autoridade inquestionável.

    === DNA DA MARCA (O MANIFESTO) ===
    {brand_dna}
    ==================================

    === ESTRUTURA ESTRATÉGICA (O VENENO 40/30/30) ===
    Você deve equilibrar o texto da seguinte forma:
    1. 40% AUTORIDADE: Mostre domínio, dados, provas ou posicionamento forte. Não peça permissão para ser o melhor.
    2. 30% CONEXÃO: Fale da dor real do humano do outro lado. Use empatia tática, não clichês.
    3. 30% VENDA/AÇÃO: Uma chamada clara e magnética. O próximo passo deve ser inevitável.

    === REGRAS DE OURO DA REDAÇÃO ===
    - PROIBIDO: 'No post de hoje', 'Fique por dentro', 'Alavancar', 'Jornada', 'Desvendar', 'Transformar'.
    - RITMO: Use frases curtas. Alterne o tamanho das sentenças para criar 'punch' (efeito staccato).
    - ESTILO: Parágrafos de no máximo 3 linhas. Sem 'encher linguiça'.
    - TONE: Respeite rigorosamente o tom '{tone}' definido no briefing.

    === BRIEFING TÉCNICO ===
    - Título/Tema: {summary}
    - Mensagem Central: {key_message}
    - Requisitos Técnicos: {tech_specs}
    - Entregável final: {', '.join(deliverables)}
    """

    user_message = f"Com base no briefing, escreva o texto final para os seguintes formatos: {', '.join(deliverables)}."

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.75 # Equilíbrio entre precisão estratégica e brilho criativo
        )
        
        # O retorno agora é o texto refinado e pronto para o redator humano
        return completion.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"❌ Erro na engine de redação da IAgência: {e}")
        raise e 
    
    except Exception as e:
        # 1. Log visual para você ver no terminal do servidor
        print(f"❌ Erro Crítico na Redação IAgência: {str(e)}") 
        
        # 2. (Opcional) Print do erro completo para debug profundo
        # import traceback
        # traceback.print_exc() 

        # 3. Relança a exceção original preservando o rastro (stack trace)
        raise


DATA_DIR = Path("data/social")
DATA_DIR.mkdir(parents=True, exist_ok=True)
INITIAL_CONTENT_GRID: list = []

def _grid_path(tenant_slug: str, year: int, month: int) -> Path:
    safe = "".join([c for c in tenant_slug if c.isalnum() or c in ("-", "_")]) or "default"
    return DATA_DIR / f"grid_{safe}_{year}_{month}.json"

@app.get("/SocialMedia/grid")
async def get_grid(tenant_slug: str, year: int, month: int):
    path = _grid_path(tenant_slug, year, month)
    if not path.exists():
        return {"grid": INITIAL_CONTENT_GRID}  # ou [] se preferir
    return {"grid": json.loads(path.read_text(encoding="utf-8"))}

@app.post("/SocialMedia/grid/save")
async def save_grid(req: dict):
    tenant_slug = req.get("tenant_slug", "mugo")
    year = int(req.get("year"))
    month = int(req.get("month"))
    grid = req.get("grid", [])

    if not isinstance(grid, list):
        raise HTTPException(status_code=400, detail="grid deve ser lista")

    path = _grid_path(tenant_slug, year, month)
    path.write_text(json.dumps(grid, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}

@app.post("/api/media/upload-base64")
async def upload_base64(req: UploadBase64Request):
    if not req.data_url:
        raise HTTPException(status_code=400, detail="data_url vazio.")

    m = _DATA_URL_RE.match(req.data_url.strip())
    if not m:
        raise HTTPException(status_code=400, detail="data_url inválido (esperado data:<mime>;base64,...)")

    mime = m.group("mime")
    b64_data = m.group("data")

    allowed = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    if (mime or "").lower() not in allowed:
        raise HTTPException(status_code=415, detail=f"Mime não suportado: {mime}")

    try:
        file_bytes = base64.b64decode(b64_data, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Base64 inválido.")

    tenant = _sanitize_tenant_slug(req.tenant_slug)
    out_dir = MEDIA_DIR / tenant
    out_dir.mkdir(parents=True, exist_ok=True)

    prefix = re.sub(r"[^a-zA-Z0-9_-]+", "", (req.filename_prefix or "draft").strip().lower()) or "draft"
    ext = _mime_to_ext(mime)

    filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:10]}{ext}"
    out_path = out_dir / filename
    out_path.write_bytes(file_bytes)

    return {"url": f"/media/{tenant}/{filename}"}


def _events_path(tenant_slug: str, year: int, month: int) -> Path:
    safe = "".join([c for c in tenant_slug if c.isalnum() or c in ("-", "_")]) or "default"
    return DATA_DIR / f"events_{safe}_{year}_{month}.json"

@app.get("/SocialMedia/events")
async def get_events(tenant_slug: str, year: int, month: int):
    path = _events_path(tenant_slug, year, month)
    if not path.exists():
        return {"events": []}
    return {"events": json.loads(path.read_text(encoding="utf-8"))}

@app.post("/SocialMedia/events/update-day")
async def update_event_day(req: dict):
    tenant_slug = req.get("tenant_slug", "mugo")
    year = int(req.get("year"))
    month = int(req.get("month"))
    event_id = int(req.get("event_id"))
    day = int(req.get("day"))

    path = _events_path(tenant_slug, year, month)
    events = []
    if path.exists():
        events = json.loads(path.read_text(encoding="utf-8"))

    updated = False
    for ev in events:
        if int(ev.get("id")) == event_id:
            ev["day"] = day
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="event_id não encontrado")

    path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}

@app.post("/SocialMedia/events/save")
async def save_events(req: dict):
    tenant_slug = req.get("tenant_slug", "mugo")
    year = int(req.get("year"))
    month = int(req.get("month"))
    events = req.get("events") or []
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="events deve ser uma lista")
    path = _events_path(tenant_slug, year, month)
    path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(events)}

# ==========================================
# 🗂️ MODELOS (PYDANTIC)
# ==========================================
class SaveAssetRequest(BaseModel):
    tenant_slug: str
    client: str
    title: str
    image_base64: str

class SaveApprovalRequest(BaseModel):
    tenant_slug: str
    client: str
    campaign: str
    title: str
    image_base64: str

class Ticket(BaseModel):
    id: int
    tenant_slug: str
    client: str
    title: str
    status: str
    priority: str
    briefing: str
    created_at: str

class ChatRequest(BaseModel):
    tenant_slug: str
    message: str
    brief_context: str

class WidgetChatMsg(BaseModel):
    contact_id: int
    sender: str
    content: str

class BriefingRequest(BaseModel):
    client: str
    title: str
    raw_input: str

class StrategyRequest(BaseModel):
    brand: str
    objective: str
    target_audience: str

class PlanningChatRequest(BaseModel):
    brand: str
    message: str
    current_strategy: str
    history: List[Dict[str, Any]]

class SocialRequest(BaseModel):
    client: str
    focus: str
    platform: str

class CopyChatRequest(BaseModel):
    client: str
    message: str
    briefing: str
    history: List[Dict[str, Any]]

class ArtChatRequest(BaseModel):
    client: str
    message: str
    briefing: str
    history: List[Dict[str, Any]]

class PromptPreviewRequest(BaseModel):
    tenant_slug: str
    media_type: str
    raw_data: Dict

class GenerateMediaRequest(BaseModel):
    tenant_slug: str
    media_type: str  # "image" | "video"
    engine: str
    prompt: str
    negative_prompt: Optional[str] = ""

    width: int
    height: int

    # ✅ Referência principal (usada para vídeo Veo como 1º frame)
    ref_image: Optional[str] = None

    # ✅ Multi-imagem (Nana Banana)
    face_image: Optional[str] = None
    body_image: Optional[str] = None
    product_image: Optional[str] = None
    clothing_image: Optional[str] = None
    style_image: Optional[str] = None

    # ✅ Áudio (Veo) (por enquanto não roteando; só armazenado)
    audio_base64: Optional[str] = None
    tts_text: Optional[str] = None
    tts_voice: Optional[str] = None
    tts_tone: Optional[str] = None

    translate: bool = False
    refiner_data: Optional[Dict[str, Any]] = None

# ==========================================
# 🔄 ROTAS: BIBLIOTECA E APROVAÇÃO
# ==========================================
@app.get("/library/assets")
async def get_library_assets(tenant_slug: str = "all"):
    print(f"📁 Buscando arquivos para o cliente: {tenant_slug}")
    if tenant_slug == "all":
        return {"assets": ASSETS_DB}
    tenant_assets = [asset for asset in ASSETS_DB if asset["tenant_slug"] == tenant_slug]
    return {"assets": tenant_assets}

@app.get("/drive/oauth/start")
async def drive_oauth_start(tenant_slug: str):
    if not GOOGLE_DRIVE_CLIENT_ID or not GOOGLE_DRIVE_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Google Drive OAuth não configurado.")
    state = _build_oauth_state(tenant_slug)
    params = {
        "client_id": GOOGLE_DRIVE_CLIENT_ID,
        "redirect_uri": GOOGLE_DRIVE_REDIRECT_URI,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": " ".join(GOOGLE_DRIVE_SCOPES),
        "state": state,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"auth_url": url}

@app.get("/drive/oauth/callback")
async def drive_oauth_callback(code: str, state: str):
    payload = _verify_oauth_state(state)
    tenant_slug = payload.get("t")
    if not tenant_slug:
        raise HTTPException(status_code=400, detail="Tenant inválido.")
    if not GOOGLE_DRIVE_CLIENT_ID or not GOOGLE_DRIVE_CLIENT_SECRET or not GOOGLE_DRIVE_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Google Drive OAuth não configurado.")

    token_url = "https://oauth2.googleapis.com/token"
    resp = requests.post(
        token_url,
        data={
            "code": code,
            "client_id": GOOGLE_DRIVE_CLIENT_ID,
            "client_secret": GOOGLE_DRIVE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_DRIVE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"Drive token error: {resp.text}")
    token_data = resp.json()

    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token")
    expires_in = int(token_data.get("expires_in", 3600))
    expires_at = int(time.time()) + expires_in

    existing = _get_drive_tokens(tenant_slug)
    if not refresh_token and existing:
        refresh_token = existing.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token ausente. Refaça o consentimento.")

    folder_id = _ensure_drive_folder(access_token, tenant_slug, existing.get("drive_folder_id") if existing else None)

    _upsert_drive_tokens(tenant_slug, {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "drive_folder_id": folder_id,
        "updated_at": datetime.utcnow().isoformat(),
    })

    return JSONResponse({"ok": True, "tenant_slug": tenant_slug, "drive_folder_id": folder_id})

@app.post("/library/upload")
async def library_upload(
    tenant_slug: str = Form(...),
    file: UploadFile = File(...),
):
    cfg = _get_tenant_storage_config(tenant_slug)
    provider = (cfg.get("provider") or "gdrive").lower()

    if provider not in ["gdrive", "r2", "s3"]:
        raise HTTPException(status_code=400, detail="Provider inválido.")

    if provider != "gdrive":
        raise HTTPException(status_code=400, detail="Provider ainda não configurado. Use Google Drive por enquanto.")

    tokens = _get_drive_tokens(tenant_slug)
    if not tokens:
        raise HTTPException(status_code=400, detail="Google Drive não conectado para este tenant.")

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_at = int(tokens.get("expires_at") or 0)
    if not access_token or (expires_at - int(time.time()) < 60):
        refreshed = _refresh_drive_access_token(refresh_token)
        access_token = refreshed.get("access_token")
        expires_in = int(refreshed.get("expires_in", 3600))
        expires_at = int(time.time()) + expires_in
        _upsert_drive_tokens(tenant_slug, {
            "access_token": access_token,
            "expires_at": expires_at,
            "updated_at": datetime.utcnow().isoformat(),
        })

    folder_id = tokens.get("drive_folder_id") or _ensure_drive_folder(access_token, tenant_slug)

    content = await file.read()
    file_id = _drive_upload_file(access_token, folder_id, file.filename, file.content_type or "application/octet-stream", content)

    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Supabase não configurado.")
    insert_url = f"{SUPABASE_URL}/rest/v1/library"
    _supabase_post(insert_url, {
        "tenant_slug": tenant_slug,
        "url": f"gdrive:{file_id}",
        "type": "video" if (file.content_type or "").startswith("video/") else "image",
        "title": file.filename,
        "provider": "gdrive",
        "created_at": datetime.utcnow().isoformat(),
    })

    return {"ok": True, "file_id": file_id, "provider": "gdrive"}

@app.post("/library/delete")
async def library_delete(asset_id: int = Form(...)):
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Supabase não configurado.")
    fetch_url = f"{SUPABASE_URL}/rest/v1/library?select=id,tenant_slug,url,provider&id=eq.{asset_id}&limit=1"
    data = _supabase_get(fetch_url)
    if not data:
        raise HTTPException(status_code=404, detail="Asset não encontrado.")
    asset = data[0]
    provider = (asset.get("provider") or "gdrive").lower()
    url = asset.get("url") or ""

    if provider == "gdrive" and url.startswith("gdrive:"):
        tokens = _get_drive_tokens(asset["tenant_slug"])
        if tokens:
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            expires_at = int(tokens.get("expires_at") or 0)
            if not access_token or (expires_at - int(time.time()) < 60):
                refreshed = _refresh_drive_access_token(refresh_token)
                access_token = refreshed.get("access_token")
            file_id = url.split("gdrive:", 1)[1]
            requests.delete(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

    del_url = f"{SUPABASE_URL}/rest/v1/library?id=eq.{asset_id}"
    requests.delete(del_url, headers=_supabase_headers(), timeout=30)
    return {"ok": True}

@app.get("/approval/jobs")
async def get_approval_jobs(tenant_slug: str = "all"):
    print("📋 Buscando lista de aprovações...")
    if tenant_slug == "all":
        return APPROVALS_DB
    return [job for job in APPROVALS_DB if job.get("tenant_slug") == tenant_slug]

@app.post("/library/assets")
async def save_library_asset(req: SaveAssetRequest):
    print(f"💾 Salvando arte final na biblioteca: {req.client}")
    image_url = save_base64_image(req.image_base64, req.tenant_slug)
    new_asset = {
        "id": int(time.time()),
        "tenant_slug": req.tenant_slug,
        "title": req.title,
        "type": "image",
        "url": image_url,
        "client": req.client,
        "campaign": "Geral",
        "tags": ["Arte Final", "Studio"],
    }
    ASSETS_DB.insert(0, new_asset)
    return {"status": "success", "asset": new_asset}

@app.post("/approval/jobs")
async def save_approval_job(req: SaveApprovalRequest):
    print(f"🚀 Enviando arte para aprovação do cliente: {req.client}")
    image_url = save_base64_image(req.image_base64, req.tenant_slug)
    now_str = time.strftime("%d %b, %H:%M")
    new_job = {
        "id": int(time.time()),
        "tenant_slug": req.tenant_slug,
        "client": req.client,
        "campaign": req.campaign,
        "type": "image",
        "platform": "instagram",
        "title": req.title,
        "version": "V1",
        "date": now_str,
        "content_url": image_url,
        "versions": ["V1"],
        "status": "pending",
        "general_notes": [],
        "audit_log": [{"action": "Arte Finalizada", "user": "Criação (Agência)", "date": now_str}],
    }
    APPROVALS_DB.insert(0, new_job)
    return {"status": "success", "job": new_job}

@app.get("/atendimento/tickets")
async def get_tickets(tenant_slug: str = "all"):
    if tenant_slug == "all":
        return {"tickets": TICKETS_DB}
    return {"tickets": [t for t in TICKETS_DB if t["tenant_slug"] == tenant_slug]}

@app.post("/atendimento/tickets")
async def create_ticket(ticket: Ticket):
    new_t = ticket.model_dump()
    new_t["id"] = len(TICKETS_DB) + 1
    TICKETS_DB.append(new_t)
    return {"status": "created", "ticket": new_t}

@app.post("/atendimento/agent")
async def atendimento_agent(req: AtendimentoAgentRequest):
    try:
        result = await process_atendimento_briefing(
            tenant_slug=req.tenant_slug,
            title=req.title,
            raw_input=req.raw_input,
            objective=req.objective,
            target_audience=req.target_audience,
            cta=req.cta,
            restrictions=req.restrictions,
            boldness=req.boldness,
            references=req.references,
        )
        return result
    except Exception as e:
        import traceback
        print("❌ Erro no /atendimento/agent:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/sync-tenant-context")
async def sync_tenant_context(req: Optional[Dict[str, Any]] = None):
    try:
        tenant_slug = None
        validate = True
        force = False
        if req and isinstance(req, dict):
            tenant_slug = req.get("tenant_slug") or None
            validate = bool(req.get("validate", True))
            force = bool(req.get("force", False))
        result = _sync_tenant_context(tenant_slug=tenant_slug, validate=validate, force=force)
        return {"status": "ok", **result}
    except Exception as e:
        msg = str(e)
        if "Contexto incompleto" in msg:
            return JSONResponse(status_code=409, content={"status": "error", "error": "incomplete_context", "message": msg})
        raise HTTPException(status_code=500, detail=msg)

@app.post("/admin/tenant-context/validate")
async def validate_tenant_context(req: Optional[Dict[str, Any]] = None):
    try:
        tenant_slug = None
        source = "disk"
        if req and isinstance(req, dict):
            tenant_slug = req.get("tenant_slug") or None
            source = (req.get("source") or "disk").lower().strip()
        if not tenant_slug:
            raise HTTPException(status_code=400, detail="tenant_slug é obrigatório.")
        if source == "supabase":
            data = _validate_supabase_context(tenant_slug)
        else:
            data = _validate_disk_context(tenant_slug)
        return {"status": "ok", **data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/tenant-context/duplicate")
async def duplicate_tenant_context(req: Optional[Dict[str, Any]] = None):
    try:
        if not req or not isinstance(req, dict):
            raise HTTPException(status_code=400, detail="Body inválido.")
        tenant_slug = (req.get("tenant_slug") or "").strip()
        from_slug = (req.get("from_slug") or "_default").strip()
        force = bool(req.get("force", False))
        if not tenant_slug:
            raise HTTPException(status_code=400, detail="tenant_slug é obrigatório.")

        headers = _supabase_headers()
        if not headers:
            raise Exception("Cabeçalhos Supabase inválidos.")

        # Bloqueia overwrite não intencional
        if not force:
            check_url = f"{SUPABASE_URL}/rest/v1/tenant_context?select=id&tenant_slug=eq.{tenant_slug}&limit=1"
            check = requests.get(check_url, headers=headers, timeout=30)
            if check.status_code == 200 and check.json():
                raise HTTPException(status_code=409, detail="Tenant já possui contexto. Use force=true para sobrescrever.")

        # Garante que o source exista no Supabase
        source_url = f"{SUPABASE_URL}/rest/v1/tenant_context?select=source_path,content,is_binary,content_type,size_bytes&tenant_slug=eq.{from_slug}"
        source = requests.get(source_url, headers=headers, timeout=30)
        if source.status_code != 200:
            raise Exception(f"Erro ao ler contexto fonte: {source.status_code} {source.text}")
        source_rows = source.json() or []
        if len(source_rows) == 0 and from_slug == "_default":
            _sync_tenant_context(tenant_slug="_default", validate=False, force=True)
            source = requests.get(source_url, headers=headers, timeout=30)
            source_rows = source.json() or []

        if len(source_rows) == 0:
            raise HTTPException(status_code=404, detail="Contexto de origem vazio.")

        rows = []
        now = datetime.utcnow().isoformat()
        for r in source_rows:
            rows.append({
                "tenant_slug": tenant_slug,
                "source_path": r.get("source_path"),
                "content": r.get("content"),
                "is_binary": r.get("is_binary", False),
                "content_type": r.get("content_type"),
                "size_bytes": r.get("size_bytes"),
                "updated_at": now,
            })

        batch_size = 200
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            url = f"{SUPABASE_URL}/rest/v1/tenant_context"
            res = requests.post(url, headers=headers, data=json.dumps(batch), timeout=30)
            if res.status_code not in (200, 201, 204):
                raise Exception(f"Erro duplicando contexto ({res.status_code}): {res.text}")

        return {"status": "ok", "tenant_slug": tenant_slug, "from_slug": from_slug, "files": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/tenant-context/create-disk")
async def create_tenant_context_disk(req: Optional[Dict[str, Any]] = None):
    try:
        if not req or not isinstance(req, dict):
            raise HTTPException(status_code=400, detail="Body inválido.")
        tenant_slug = (req.get("tenant_slug") or "").strip()
        from_slug = (req.get("from_slug") or "_default").strip()
        force = bool(req.get("force", False))
        if not tenant_slug:
            raise HTTPException(status_code=400, detail="tenant_slug é obrigatório.")

        base_dir = Path(__file__).resolve().parent / "tenant_context"
        src_dir = base_dir / from_slug
        dst_dir = base_dir / tenant_slug

        if not src_dir.exists():
            raise HTTPException(status_code=404, detail=f"Contexto de origem não encontrado: {from_slug}")

        if dst_dir.exists():
            if not force:
                raise HTTPException(status_code=409, detail="Pasta já existe. Use force=true para sobrescrever.")
            shutil.rmtree(dst_dir)

        shutil.copytree(src_dir, dst_dir)
        return {"status": "ok", "tenant_slug": tenant_slug, "from_slug": from_slug}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 🧠 AGENTES DE PLANEJAMENTO E ESTRATÉGIA
# ==========================================
@app.post("/planning/agent")
async def planning_agent(req: StrategyRequest):
    print(f"🧠 CSO Agent desenhando a master strategy para: {req.brand}")

    if client is None:
        return {
            "big_idea": "Offline",
            "insight": "OPENAI_API_KEY não configurada.",
            "tone": "N/A",
            "channels": [],
            "kpis": [],
        }

    system_prompt = f"""
Você é o Chief Strategy Officer (CSO) de uma agência de publicidade global multipremiada.
Sua missão é criar uma estratégia de marca implacável, baseada em comportamento humano real e tensão cultural, não em achismos corporativos.

CLIENTE (MARCA): {req.brand}
OBJETIVO DE NEGÓCIO: {req.objective}
PÚBLICO-ALVO: {req.target_audience}

DIRETRIZES DE PENSAMENTO (O VENENO):
1. INSIGHT VERDADEIRO: Um insight não é um dado estatístico. É uma verdade humana não dita.
2. TENSÃO CULTURAL: Encontre a fricção entre o que a sociedade cobra e o que o público realmente vive ou deseja secretamente.
3. BIG IDEA: Um conceito criativo guarda-chuva, curto e memorável.
4. ZERO CLICHÊS DE IA: proibido usar: "Desvende", "Jornada", "Mergulhe", "Embarque", "Revolucionário", "No cenário atual", "A sinergia".

FORMATO (JSON STRICT):
{{
  "insight": "...",
  "big_idea": "...",
  "tone": "...",
  "channels": ["..."],
  "kpis": ["..."]
}}
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "Gere o plano estratégico."}],
            response_format={"type": "json_object"},
            temperature=0.85,
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erro no CSO Agent: {e}")
        return {
            "big_idea": "Falha na Matriz",
            "insight": "O servidor perdeu a conexão com o núcleo criativo. Tente novamente.",
            "tone": "N/A",
            "channels": [],
            "kpis": [],
        }

@app.post("/planning/chat")
async def planning_chat_agent(req: PlanningChatRequest):
    print(f"🥊 CSO Copilot debatendo para: {req.brand}")

    if client is None:
        return {"response": "OPENAI_API_KEY não configurada."}

    system_prompt = f"""
Você é um Diretor de Planejamento brilhante, provocativo e implacável.
CLIENTE: {req.brand}
ESTRATÉGIA ATUAL: {req.current_strategy}

REGRAS:
1. Não seja puxassaco.
2. Faça as perguntas difíceis.
3. Pense lateral.
4. Zero cheiro de IA.
"""

    safe_history = []
    for msg in req.history:
        content = msg.get("content", "...")
        role = msg.get("role", "user")
        if role not in ["user", "assistant", "system"]:
            role = "user"
        safe_history.append({"role": role, "content": str(content)})

    messages = [{"role": "system", "content": system_prompt}] + safe_history + [{"role": "user", "content": req.message or "E aí?"}]

    try:
        completion = client.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.8)
        return {"response": completion.choices[0].message.content}
    except Exception as e:
        print(f"❌ Erro no Copilot: {repr(e)}")
        return {"response": "Estou offline da API. Me reconecte para continuarmos."}

@app.post("/social/agent")
async def social_agent(req: SocialRequest):
    print(f"📱 Social Agent criando pauta estratégica para: {req.client}")

    if client is None:
        return {"week_plan": [{"day": "Erro", "format": "Offline", "idea": "OPENAI_API_KEY não configurada.", "caption_hook": "Configure a chave."}]}

    system_prompt = f"""Você é um Expert em Marketing Digital.

CLIENTE: {req.client}
FOCO: {req.focus}
PLATAFORMA: {req.platform}

Retorne JSON STRICT:
{{
  "week_plan": [
    {{
      "day": "Segunda-feira",
      "format": "Reels/Carrossel/etc",
      "idea": "Descrição",
      "caption_hook": "Gancho"
    }}
  ]
}}
"""
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",  # ✅ corrigido (você tinha "ChatGPT 5.2" que quebra)
            messages=[{"role": "system", "content": system_prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erro no Social Agent: {e}")
        return {"week_plan": [{"day": "Erro", "format": "Aviso", "idea": "Falha no servidor.", "caption_hook": "Tente novamente."}]}

@app.post("/copy/chat")
async def copy_chat_agent(req: CopyChatRequest):
    print(f"✍️ Criando Copy para a marca: {req.client}")

    if client is None:
        return {"response": "OPENAI_API_KEY não configurada."}

    system_prompt = f"""
Você é o Head de Copy.
Cliente: {req.client}
Data: {data_hoje}

Regras: zero clichês de IA, linguagem casual.
"""

    safe_history = [{"role": m.get("role", "user"), "content": str(m.get("content", "..."))} for m in req.history]
    messages = [{"role": "system", "content": system_prompt}] + safe_history + [{"role": "user", "content": req.message or "Escreva"}]

    try:
        completion = client.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.85)
        return {"response": completion.choices[0].message.content.replace("```html", "").replace("```", "")}
    except Exception as e:
        return {"response": f"Erro API: {str(e)}"}

# 1. RESOLVENDO IMPORTAÇÃO (Garante que o main.py enxergue o refiner na mesma pasta)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from prompt_refiner import refine_prompt_for_flux

# ==========================================
# 🎨 CONSTANTES DE QUALIDADE (DNA DA AGÊNCIA)
# ==========================================
SKIN_PROTOCOL = (
    "raw photography, hyper-realistic skin texture, visible pores, natural skin imperfections, "
    "moles, freckles, peach fuzz on face, unpolished finish, hard focus, shot on 35mm, "
    "Kodak Portra 400 film grain, no makeup look, not airbrushed, not plasticky, "
    "detailed iris, subsurface scattering"
)

ANTI_PLASTIC = "wax skin, plastic skin, airbrushed, smooth skin, cartoonish, cgi face, doll like, blur, low resolution, flat lighting"
ANTI_TEXT_OVERLAY = (
    "text, words, letters, typography, watermark, logo, signature, subtitles, captions, poster text, signage"
)
IDENTITY_LOCK_REFERENCE = (
    "Identity lock for reference image. Use the reference image as the only identity source. "
    "Preserve the same person with facial structure, eye shape, nose, lips, skin tone, hairstyle, hairline, eyebrows, and overall likeness. "
    "Do not change age, gender presentation, ethnicity, or distinctive features. "
    "Keep identity consistent across outputs."
)
IDENTITY_LOCK_NEGATIVE = (
    "Do not change face, swap identity, alter facial proportions, beautify, de age, change skin tone, "
    "change eye color, change hairstyle, add or remove facial hair, or stylize into cartoon or anime."
)

# ==========================================
# 🌐 TRADUÇÃO FIEL PT → EN
# ==========================================
def translate_prompt_to_english(pt_prompt: str) -> str:
    """
    Traduz o prompt de PT para EN usando GPT-4o-mini com instrução especializada
    em terminologia de fotografia e cinema. Fallback para GoogleTranslator se necessário.
    """
    client = get_client()
    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise translator specialized in photography, cinematography, "
                            "and visual production terminology. "
                            "Translate the following Portuguese image generation prompt to English. "
                            "Rules:\n"
                            "- Translate faithfully and literally — do NOT paraphrase, summarize, or rewrite.\n"
                            "- Preserve every detail: physical descriptions, clothing, colors, expressions, actions, spatial relationships, scene context.\n"
                            "- Preserve photography terms accurately: lens types, lighting styles, camera angles, shot framing, visual styles.\n"
                            "- Keep proper names (people, places, brands) as-is.\n"
                            "- Do NOT add, remove, or interpret any information.\n"
                            "- Output only the translated text, no explanations."
                        ),
                    },
                    {"role": "user", "content": pt_prompt},
                ],
                temperature=0.1,
            )
            translated = response.choices[0].message.content.strip()
            print(f"🌐 Tradução completa (GPT-4o-mini) [{len(translated)} chars]:\n{translated}\n")
            return translated
        except Exception as e:
            print(f"⚠️  Tradução GPT falhou: {e}. Usando fallback.")

    if _GOOGLE_TRANSLATOR_AVAILABLE:
        try:
            return GoogleTranslator(source="auto", target="en").translate(pt_prompt)
        except Exception as e:
            print(f"⚠️  GoogleTranslator falhou: {e}. Usando prompt original.")

    return pt_prompt


# ==========================================
# 🧠 LÓGICA DE REFINAMENTO (CENTRALIZADA)
# ==========================================
def prepare_refined_prompt(req_data: dict, media_type: str) -> str:
    """
    Ponte entre os dados brutos do React e o Prompt Refiner Profissional.
    Transforma listas em prosa cinematográfica.
    """
    prompt_override = (req_data.get("prompt") or "").strip()
    refiner_data = req_data.get("refiner_data") or {}
    negative_prompt = str(
        req_data.get("negative_prompt")
        or refiner_data.get("negative_prompt")
        or ""
    ).strip()
    idea = (refiner_data.get("idea") or "").strip()
    scene_basis = idea or prompt_override
    config = (
        refiner_data.get("technical")
        or refiner_data.get("config")
        or req_data.get("config")
        or {}
    )
    chars = (
        refiner_data.get("characters")
        or req_data.get("characters")
        or []
    )

    # ✅ MODO LIMPO: prepara prompt base (PT). A tradução ocorre depois no fluxo principal.
    if media_type == "image":
        pt_prompt = scene_basis or prompt_override or ""
        if negative_prompt:
            pt_prompt = f"{pt_prompt} A imagem não deve conter {negative_prompt}."
        pt_prompt = pt_prompt.replace(":", " ").replace("[", " ").replace("]", " ").replace("(", " ").replace(")", " ")
        pt_prompt = " ".join(pt_prompt.split())
        return pt_prompt

    # fallback para outros media types
    if not refiner_data:
        return req_data.get("prompt", "")
    raw_parts = [f"Cenário principal {scene_basis}."]

    for i, c in enumerate(chars):
        # Support both new free-text fields (physical, clothing) and legacy dropdowns
        physical = str(c.get("physical") or c.get("physical_details") or "").strip()
        clothing = str(c.get("clothing") or c.get("clothing_details") or "").strip()
        # Legacy field fallback: build physical from individual fields if present
        if not physical:
            legacy_parts = [
                c.get("age", ""), c.get("gender", ""), c.get("ethnicity", ""),
                c.get("body", ""), c.get("hair", ""), c.get("eyes", ""),
            ]
            physical = ", ".join(p for p in legacy_parts if p)
        if not clothing:
            clothing = ", ".join(filter(None, [c.get("makeup", ""), c.get("accessories", "")]))
        raw_parts.append(
            " ".join(
                [
                    f"Sujeito {i+1}",
                    f"nome {c.get('name', 'Pessoa')}",
                    f"físico {physical}",
                    f"vestimenta {clothing}",
                    f"expressão {c.get('expression', '')}",
                    f"ação {c.get('action', '')}",
                ]
            )
        )

    style = config.get("style", "Photorealistic")
    tech_bits = [
        f"style={style}",
        f"lighting={config.get('lighting', '')}",
        f"camera={config.get('camera', '')}",
        f"view={config.get('view', '')}",
        f"angle={config.get('angle', '')}",
        f"format={config.get('format', '')}",
    ]
    raw_parts.append("Parâmetros técnicos " + ", ".join([b for b in tech_bits if "=" in b and b.split("=", 1)[1]]))

    if prompt_override and prompt_override != scene_basis:
        raw_parts.append(f"Direção textual final do usuário {prompt_override}.")

    has_face_ref = bool(req_data.get("face_image") or req_data.get("ref_image"))
    has_other_refs = any(
        [
            req_data.get("body_image"),
            req_data.get("product_image"),
            req_data.get("clothing_image"),
            req_data.get("style_image"),
        ]
    )
    reference_description = ""
    if has_face_ref:
        reference_description = (
            "Use provided visual references for identity, body, product, clothing, and style consistency. "
            f"{IDENTITY_LOCK_REFERENCE} {IDENTITY_LOCK_NEGATIVE}"
        )
    elif has_other_refs:
        reference_description = (
            "Use provided visual references for body pose, product, clothing and style consistency. "
            "Preserve the subject characteristics defined in the prompt."
        )

    raw_input = " ".join([p for p in raw_parts if p and p.strip()])
    has_character = bool(refiner_data.get("has_character", False)) or len(chars) > 0
    lower_raw_input = raw_input.lower()
    clean_shaven_lock = any(
        token in lower_raw_input
        for token in ["sem barba", "rosto liso", "clean-shaven", "clean shaven"]
    )
    off_camera_gaze_lock = any(
        token in lower_raw_input
        for token in [
            "olhando o movimento",
            "olhando o movimento das pessoas",
            "olhando as pessoas",
            "observando o movimento",
            "observando as pessoas",
            "assistindo o movimento",
        ]
    )

    constraints = {
        "clean_shaven": clean_shaven_lock,
        "off_camera_gaze": off_camera_gaze_lock,
        "avoid_text_overlay": media_type == "image",
        "negative_prompt": negative_prompt,
    }
    refiner_data["constraints"] = constraints
    if reference_description:
        refiner_data["reference_description"] = reference_description

    # CHAMA O SEU PROMPT_REFINER.PY (A mágica acontece aqui)
    refined = refine_prompt_for_flux(
        user_prompt=raw_input,
        style=style,
        refiner_data=refiner_data,
        reference_description=reference_description,
        has_character=has_character,
    )
    
    return refined

# ==========================================
# 🧩 PROTOCOLOS DE QUALIDADE (SKIN / ANTI_PLASTIC)
# ==========================================
SKIN_PROTOCOL = (
    "raw photography, hyper-realistic skin texture, visible pores, natural skin imperfections, "
    "moles, freckles, unpolished finish, hard focus, shot on 35mm, "
    "Kodak Portra 400 film grain, no makeup look, not airbrushed, not plasticky, "
    "detailed iris, subsurface scattering"
)

ANTI_PLASTIC = (
    "wax skin, plastic skin, airbrushed, smooth skin, cartoonish, cgi face, "
    "blur, low resolution, flat lighting"
)

def _inject_quality_protocols(prompt: str) -> str:
    if not prompt:
        return prompt
    SKIN_MARKER = "##SKIN_PROTOCOL##"
    ANTI_PLASTIC_MARKER = "##ANTI_PLASTIC##"
    if SKIN_MARKER in prompt and ANTI_PLASTIC_MARKER in prompt:
        return prompt
    final_prompt = prompt
    lower_prompt = final_prompt.lower()
    human_keywords = [
        "person", "human", "face", "skin", "portrait", "model", "man", "woman",
        "girl", "boy", "hands", "eyes", "teeth", "smile", "selfie"
    ]
    is_human = any(k in lower_prompt for k in human_keywords)
    if is_human and SKIN_MARKER not in final_prompt:
        final_prompt = f"{final_prompt}, {SKIN_PROTOCOL} {SKIN_MARKER}"
    if ANTI_PLASTIC_MARKER not in final_prompt:
        final_prompt = f"{final_prompt}. Avoid {ANTI_PLASTIC}. {ANTI_PLASTIC_MARKER}"
    return final_prompt
# ==========================================
# 🎨 ENDPOINTS DE GERAÇÃO
# ==========================================

@app.post("/creation/preview-prompt")
async def preview_prompt_agent(req: PromptPreviewRequest):
    """Gera o preview visual do prompt refinado antes de gastar créditos."""
    optimized = prepare_refined_prompt(req.dict(), req.media_type)
    return {"prompt": optimized}

@app.post("/creation/generate-image")
async def generate_media(req: GenerateMediaRequest):
    print(f"🚀 Iniciando Geração: {req.engine} | Tipo: {req.media_type}")

    # --- 1. REFINAMENTO DE PROMPT (O FIM DO CÓDIGO DE MÁQUINA) ---
    final_prompt = prepare_refined_prompt(req.dict(), req.media_type)

    # --- 1.1 TRADUÇÃO OBRIGATÓRIA (EN) PARA IMAGEM/VÍDEO ---
    if req.media_type in ["image", "video"]:
        final_prompt = translate_prompt_to_english(final_prompt)

    # --- 1.2 PROTOCOLOS DE QUALIDADE (SKIN/ANTI_PLASTIC) ---
    if req.media_type in ["image", "video"]:
        final_prompt = _inject_quality_protocols(final_prompt)

    # --- 2. CÁLCULO DE ASPECT RATIO ---
    ratio = (req.width / req.height) if (req.width and req.height) else 1.0
    ar_map = {0.56: "9:16", 0.75: "3:4", 0.8: "4:5", 1.0: "1:1", 1.77: "16:9", 2.33: "21:9"}
    # Busca o AR mais próximo (lógica simplificada para o exemplo)
    ar_string = "16:9"
    if ratio < 0.7: ar_string = "9:16"
    elif ratio < 0.9: ar_string = "4:5"
    elif ratio > 2.0: ar_string = "21:9"

    print(f"📝 Prompt Final (EN): {final_prompt}")

    def to_url(path_str: str) -> str:
        return f"http://localhost:8000/media/{req.tenant_slug}/{Path(path_str).name}"

    try:
        # Resolve chaves por tenant (para imagem/vídeo)
        google_key = _resolve_provider_key(req.tenant_slug, ["google", "gemini", "veo", "nana"])
        replicate_key = _resolve_provider_key(req.tenant_slug, ["replicate", "flux", "kling"])
        stability_key = _resolve_provider_key(req.tenant_slug, ["stability"])

        # --- 🎬 FLUXO DE VÍDEO (Kling / Veo) ---
        if req.media_type == "video":
            if "kling" in req.engine:
                start_image = getattr(req, "ref_image", None)
                local_path = await run_in_threadpool(
                    generate_video_kling,
                    prompt=final_prompt,
                    tenant_id=req.tenant_slug,
                    ar=ar_string,
                    api_key=replicate_key,
                    start_image=start_image,
                    duration=5
                )
                return {"url": to_url(local_path), "provider": "kling", "prompt": final_prompt}

            if "veo" in req.engine:
                local_path = await run_in_threadpool(
                    generate_video_veo,
                    prompt=final_prompt,
                    tenant_slug=req.tenant_slug,
                    ar=ar_string,
                    api_key=google_key,
                )
                return {"url": to_url(local_path), "provider": "veo", "prompt": final_prompt}

        # --- 🖼️ FLUXO DE IMAGEM (Nana / Flux / MJ) ---
        has_face_ref = bool(getattr(req, "face_image", None) or getattr(req, "ref_image", None))
        use_nana = req.engine == "nana" or has_face_ref

        if req.engine in ["stability", "stable", "stablediffusion"]:
            local_path = await run_in_threadpool(
                generate_image_stability,
                prompt=final_prompt,
                tenant_id=req.tenant_slug,
                ar=ar_string,
                negative_prompt=req.negative_prompt,
                api_key=stability_key,
            )
            if API_CREDITS_COST_IMAGE > 0:
                _apply_credit_delta(
                    tenant_slug=req.tenant_slug,
                    amount=-API_CREDITS_COST_IMAGE,
                    feature="image",
                    description="Geracao de imagem (stability)",
                )
            return {"url": to_url(local_path), "provider": "stability", "prompt": final_prompt}

        if use_nana or req.engine in ["gemini", "nana", "nano-banana"]:
            print("🍌 Nana Banana: Processando Identidade Visual...")
            _, local_path, prov = await run_in_threadpool(
                generate_identity,
                prompt=final_prompt,
                ref_image=getattr(req, "ref_image", None),
                face_image=getattr(req, "face_image", None),
                body_image=getattr(req, "body_image", None),
                product_image=getattr(req, "product_image", None),
                clothing_image=getattr(req, "clothing_image", None),
                style_image=getattr(req, "style_image", None),
                tenant_id=req.tenant_slug,
                media_type="image",
                provider="nana",
                ar=ar_string,
                api_key=google_key,
            )
            if API_CREDITS_COST_IMAGE > 0:
                _apply_credit_delta(
                    tenant_slug=req.tenant_slug,
                    amount=-API_CREDITS_COST_IMAGE,
                    feature="image",
                    description=f"Geração de imagem ({prov})",
                )
            return {"url": to_url(local_path), "provider": prov, "prompt": final_prompt}

        if "flux" in req.engine:
            media_result = await run_in_threadpool(
                generate_image_flux,
                prompt=final_prompt,
                tenant_id=req.tenant_slug,
                ar=ar_string,
                api_key=replicate_key,
            )
            if API_CREDITS_COST_IMAGE > 0:
                _apply_credit_delta(
                    tenant_slug=req.tenant_slug,
                    amount=-API_CREDITS_COST_IMAGE,
                    feature="image",
                    description="Geração de imagem (flux)",
                )
            return {
                "url": to_url(media_result) if not str(media_result).startswith("http") else media_result,
                "provider": "flux-1.1-pro",
                "prompt": final_prompt,
            }

        raise HTTPException(status_code=400, detail="Engine não suportada.")

    except Exception as e:
        print(f"❌ Erro Crítico: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ROTAS DE PRODUÇÃO ---
@app.get("/library/suppliers")
async def get_suppliers(tenant_slug: str = "mugo"):
    return [
        {"id": 1, "name": "Locadora Luz e Cia", "specialty": "Iluminação"},
        {"id": 2, "name": "Câmera & Ação", "specialty": "Lentes e Câmeras"},
        {"id": 3, "name": "Van do João", "specialty": "Transporte/Logística"},
        {"id": 4, "name": "Catering Sabor", "specialty": "Alimentação"},
        {"id": 5, "name": "Mega Estruturas", "specialty": "Tendas e Palcos"},
    ]

@app.post("/production/plan")
async def generate_production_plan(req: PlanRequest):
    print(f"🎬 Gerando plano de produção para data: {req.date}")

    if client is None:
        return {"error": "OPENAI_API_KEY não configurada."}

    system_prompt = f"""
Você é um Produtor Executivo Sênior.
BRIEF: {req.brief}
DATA: {req.date}

Retorne JSON STRICT com:
timeline, staff_needs, budget_lines, risks
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "Gere o plano em JSON."}],
            temperature=0.7,
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Erro na IA de Produção: {e}")
        return {"error": str(e)}

@app.post("/production/chat")
async def production_chat(req: ProdChatRequest):
    if client is None:
        return {"response": "OPENAI_API_KEY não configurada."}

    system_prompt = f"""
Você é o Assistente de Produção RTV/Eventos.
Contexto: {req.brief_context}
Responda direto, focado em logística e orçamento.
"""
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": req.message}],
        )
        return {"response": completion.choices[0].message.content}
    except Exception as e:
        return {"response": f"Erro: {str(e)}"}

# =====================================
# ROTAS DASHBOARD
# =====================================
@app.get("/health")
async def health_check():
    return {"status": "online"}

# =====================================
# ROTAS DE MIDIA
# =====================================
@app.get("/media/dashboard/{tenant_slug}")
async def get_media_dashboard(tenant_slug: str):
    # ✅ seu exemplo tinha meta_data/google_data não definidos -> stub seguro
    return {
        "exec_data": [
            {"id": "meta", "canal": "Meta", "invest": 0, "rec": 0, "roas": 0, "status": "🟡"},
            {"id": "google", "canal": "Google", "invest": 0, "rec": 0, "roas": 0, "status": "🟡"},
        ]
    }

# ==========================================
# 🗑️ ROTAS DE EXCLUSÃO (BIBLIOTECA E APROVAÇÃO)
# ==========================================
@app.delete("/approval/jobs/{job_id}")
async def delete_approval_job(job_id: int):
    global APPROVALS_DB
    APPROVALS_DB = [job for job in APPROVALS_DB if job.get("id") != job_id]
    return {"status": "success", "message": "Arte excluída das Aprovações!"}

@app.delete("/library/assets/{asset_id}")
async def delete_library_asset(asset_id: str):
    # ✅ você usava LIBRARY_DB que não existe -> usando ASSETS_DB
    global ASSETS_DB
    ASSETS_DB = [asset for asset in ASSETS_DB if str(asset.get("id")) != str(asset_id)]
    return {"status": "success", "message": "Arte excluída da Biblioteca!"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
