from src.core.state import CampaignState

def router_node(state: CampaignState):
    """
    Roteador Lógico baseado nos Checkboxes da UI.
    Não usa LLM para adivinhar, usa a definição explícita da tarefa.
    """
    print(f"--- [ROUTER] Analisando Checkboxes: {state.request.departments_involved} ---")
    
    deps = state.request.departments_involved
    next_steps = []

    # Lógica de Dependência:
    # Planejamento sempre vem primeiro se estiver marcado
    if "planejamento" in deps and not state.strategy_brief:
        return {"next_step": "strategist"}
    
    # Se Criação estiver marcada e ainda não temos copy
    if "criacao" in deps and not state.copy_deck:
        return {"next_step": "copywriter"}

    # Se Criação estiver marcada, temos copy, mas não temos arte
    if "criacao" in deps and not state.art_direction:
        return {"next_step": "art_director"}

    # Se Mídia/Produção estiver marcada (Geração final)
    if ("midia" in deps or "producao" in deps) and state.final_prompt_en:
        return {"next_step": "production"}
        
    # Se chegou aqui, ou acabou ou falta info
    return {"next_step": "approval_check"}