import os
import json
import time
from pathlib import Path

# --- CONFIGURAÇÃO DE CAMINHOS ---
# Caminho: core -> src -> iagencia-core -> data
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LIBRARY_FILE = DATA_DIR / "library.json"

def init_db():
    """Garante que o arquivo JSON da biblioteca existe"""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    if not LIBRARY_FILE.exists():
        try:
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
            print(f"✅ (Database) Biblioteca iniciada em: {LIBRARY_FILE}")
        except Exception as e:
            print(f"❌ (Database) Erro ao criar library.json: {e}")

def save_asset(asset_data: dict):
    """Salva um novo item no arquivo library.json"""
    init_db() # Garante que o arquivo existe antes de tentar ler
    
    # Adiciona Metadados (ID único baseado no tempo e Data)
    asset_data["id"] = int(time.time() * 1000)
    asset_data["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Lê o arquivo atual
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            assets = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        assets = []
        
    # 2. Adiciona o novo asset no topo da lista (ou no fim, depois ordenamos)
    assets.append(asset_data)
    
    # 3. Salva de volta
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(assets, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Asset salvo: {asset_data.get('title')} (ID: {asset_data['id']})")
    return asset_data["id"]

def list_assets(tenant_slug: str, asset_type: str = "all"):
    """Lista os itens filtrando por cliente"""
    init_db()
    
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            assets = json.load(f)
    except:
        return []
        
    # Filtra por Tenant (Cliente)
    # Se tenant_slug for "all" ou vazio, traz tudo (opcional, mas seguro filtrar)
    filtered = [
        a for a in assets 
        if str(a.get("tenant_slug")).lower() == str(tenant_slug).lower()
    ]
    
    # Filtra por Tipo (imagem, video, copy)
    if asset_type and asset_type != "all":
        filtered = [a for a in filtered if a.get("type") == asset_type]
        
    # Retorna ordenado do mais recente para o mais antigo
    return sorted(filtered, key=lambda x: x["id"], reverse=True)