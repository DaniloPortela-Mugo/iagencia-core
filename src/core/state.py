from typing import List, Optional, Dict, Literal, Any
from pydantic import BaseModel, Field

# Contexto do Usuário (Quem está logado)
class UserContext(BaseModel):
    user_id: str
    email: str
    role: str       # ex: 'redator', 'planejamento', 'midia'
    tenant_id: str  # ex: 'agencia_mugo'
    client_id: str  # ex: 'cliente_varejo'

# Definição da Tarefa (O que veio do Input da Pág 3)
class TaskRequest(BaseModel):
    campaign_name: str          # "Nome da campanha"
    task_name: str              # "3 posts de lançamento"
    description: str            # "PIT / Descrição"
    
    # Checkboxes da UI (Pág 3/4)
    departments_involved: List[str] = []  # ["criacao", "midia", "producao"]
    
    # Checkboxes de Peças (Pág 5)
    deliverables: List[str] = []          # ["imagem", "video", "avatar"]
    
    # Configuração Visual (Pág 9)
    visual_config: Optional[Dict[str, Any]] = {} # Iluminação, Câmera, etc.

class CampaignState(BaseModel):
    # Contextos Base
    user: UserContext
    client_config: Optional[Dict] = None
    
    # Dados da Tarefa
    request: TaskRequest
    
    # Kanban e Status (Pág 6)
    kanban_status: str = "TODO" # TODO -> IN_PROGRESS -> IN_APPROVAL -> DONE
    kanban_history: List[str] = []
    
    # Memória do "Brain" (Chat Pág 8)
    brain_history: List[str] = []
    
    # Artefatos Gerados pelos Agentes
    research_data: Optional[Dict] = None      # Planejamento
    strategy_brief: Optional[Dict] = None     # Planejamento
    copy_deck: Optional[Dict] = None          # Criação (Redator)
    art_direction: Optional[Dict] = None      # Criação (DA)
    prompt_draft_pt: Optional[str] = None     # Criação (DA)
    final_prompt_en: Optional[str] = None     # Criação (DA)
    
    # Produção (Mídia/Produção)
    generated_assets: List[Dict] = []         # Links das imagens/vídeos finais
    
    # Controle Financeiro
    current_cost: float = 0.0
    financial_approved: bool = False
    
    # Flags de Controle de Fluxo
    next_step: str = "INIT"