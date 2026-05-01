import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.core.state import CampaignState # <--- Importação necessária

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

def strategist_node(state: CampaignState):
    """
    Agente de Planejamento: Cria o Brief Estratégico.
    """
    print("--- [NODE] Strategist ---")
    
    req = state.request
    
    prompt = f"""
    Atue como Planejamento Estratégico.
    Campanha: {req.campaign_name}
    Tarefa: {req.task_name}
    Descrição: {req.description}
    
    Gere um Briefing curto (JSON):
    {{ "key_message": "...", "target_audience": "...", "tone": "..." }}
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        strategy = json.loads(response.content)
    except:
        strategy = {"key_message": req.description, "tone": "Standard"}
        
    return {"strategy_brief": strategy}