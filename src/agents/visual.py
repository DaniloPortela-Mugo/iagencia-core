import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.core.state import CampaignState  # <--- A IMPORTAÇÃO QUE FALTAVA
from src.config.templates import TEMPLATES_PLATAFORMA
from src.config.constants import CAMERA_MOVEMENTS, OPCOES_CORES

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

def art_director_node(state: CampaignState):
    """
    Agente DA: Define o estilo visual baseado no pedido e no cliente.
    """
    print("--- [NODE] Art Director ---")
    
    # Pega configs do request (Pág 9 do PDF: inputs visuais da UI)
    visual_config = state.request.visual_config or {}
    
    # Se o usuário não preencheu na UI, o DA sugere
    system_prompt = f"""
    Você é um Diretor de Arte Sênior.
    Tarefa: Definir Direção de Arte para campanha: "{state.request.campaign_name}".
    Peça: "{state.request.task_name}" - {state.request.description}.
    
    Inputs da UI (Respeite se existir):
    - Iluminação: {visual_config.get('lighting', 'A definir pelo DA')}
    - Câmera: {visual_config.get('camera', 'A definir pelo DA')}
    
    Retorne JSON: {{ "style": "...", "palette": "...", "composition": "..." }}
    """
    
    try:
        response = llm.invoke([SystemMessage(content=system_prompt)])
        art_data = json.loads(response.content)
    except:
        art_data = {"style": "Cinematic", "palette": "Neutral", "composition": "Wide"}

    return {"art_direction": art_data}


def prompt_drafter_node(state: CampaignState):
    """
    Gera o prompt em PT para a tela de aprovação (Pág 10).
    """
    print("--- [NODE] Prompt Drafter (PT) ---")
    
    req = state.request
    art = state.art_direction or {}
    # Novo padrão Hierárquico
    tenant_id = state.user.tenant_id
    client_id = state.user.client_id
    
    # Escolhe template genérico por enquanto (pode ser refinado pelo deliverable)
    template = TEMPLATES_PLATAFORMA.get("Midjourney (v6/v7)", [])
    
    prompt_instruction = f"""
    Atue como Prompt Engineer.
    Crie um prompt visual detalhado em PORTUGUÊS para: "{req.description}".
    Estilo: {art.get('style')}.
    Iluminação: {art.get('palette')}.
    
    IMPORTANTE: O output será lido por um humano na tela de aprovação.
    Retorne APENAS o texto do prompt, sem JSON.
    """
    
    response = llm.invoke([HumanMessage(content=prompt_instruction)])
    
    # Atualiza o campo correto do novo State (prompt_draft_pt)
    return {
        "prompt_draft_pt": response.content.strip(),
        "kanban_status": "IN_APPROVAL"
    }


def prompt_translator_node(state: CampaignState):
    """
    Traduz o prompt (que pode ter sido editado pelo humano) para Inglês Técnico.
    """
    print("--- [NODE] Prompt Translator (EN) ---")
    
    # Pega o texto que pode ter vindo da edição manual da UI
    text_pt = state.prompt_draft_pt
    
    prompt = f"""
    Traduza para Inglês Técnico de IA Generativa (Midjourney/Sora).
    Texto: "{text_pt}"
    
    Retorne apenas o prompt em inglês.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    return {
        "final_prompt_en": response.content.strip()
    }