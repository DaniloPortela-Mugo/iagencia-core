import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any

# Define onde o banco ficará salvo (na raiz iagencia-core, subindo 3 níveis)
# arquivo atual -> core -> src -> iagencia-core
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "iagencia.db"

def get_db_connection():
    # Garante que o diretório pai existe antes de conectar
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Permite acessar colunas por nome
    return conn

def init_db():
    """Cria a tabela se não existir"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Tabela de Ativos (Assets)
        c.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_slug TEXT NOT NULL,
                title TEXT,
                type TEXT NOT NULL, -- image, video, audio
                url TEXT NOT NULL,
                client TEXT,
                campaign TEXT,
                tags TEXT, -- JSON string
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"🗄️ Banco de dados inicializado em: {DB_PATH}")
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")

def save_asset(data: Dict[str, Any]):
    """Salva um novo ativo gerado"""
    conn = get_db_connection()
    c = conn.cursor()
    
    tags_json = json.dumps(data.get('tags', []))
    
    c.execute('''
        INSERT INTO assets (tenant_slug, title, type, url, client, campaign, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['tenant_slug'],
        data.get('title', 'Sem título'),
        data['type'],
        data['url'],
        data.get('client', 'Geral'),
        data.get('campaign', 'Drafts'),
        tags_json
    ))
    
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id

def list_assets(tenant_slug: str, asset_type: str = None):
    """Lista ativos para a Biblioteca"""
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT * FROM assets WHERE tenant_slug = ?"
    params = [tenant_slug]
    
    if asset_type and asset_type != 'all':
        query += " AND type = ?"
        params.append(asset_type)
        
    query += " ORDER BY created_at DESC"
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    # Converte para lista de dicts
    results = []
    for row in rows:
        r = dict(row)
        # Parse das tags JSON de volta para lista
        try:
            r['tags'] = json.loads(r['tags'])
        except:
            r['tags'] = []
        results.append(r)
        
    return results