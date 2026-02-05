import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.core.state import CampaignState
from src.core.security import SecurityManager  # <--- Importar

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def copywriter_node(state: CampaignState):
    print("--- [NODE] Copywriter ---")
    
    req = state.request
    # Novo padrão Hierárquico
    tenant_id = state.user.tenant_id
    client_id = state.user.client_id

# Passa os DOIS IDs para o SecurityManager navegar nas pastas
    prompt = SecurityManager.get_agent_prompt(tenant_id, client_id, "copywriter")
    
    # 1. CARREGA A PERSONALIDADE ESPECÍFICA DO CLIENTE
    # Aqui a mágica acontece. Se for varejo, carrega o "Vendedoraço". 
    # Se for moda, carrega o "Curador".
    system_persona = SecurityManager.get_agent_prompt(tenant_id, client_id, "copywriter")
    
    # 2. Monta o Prompt final injetando o pedido atual
    full_prompt = f"""
        {system_persona}
    
    --- TAREFA ATUAL ---
    Tarefa: {req.task_name}
    Descrição: {req.description}
    Plataforma: {req.deliverables}
    
    Gere o JSON de resposta com headline e body.
    """
    
    try:
        response = llm.invoke([HumanMessage(content=full_prompt)])
        copy_data = json.loads(response.content)
    except:
        copy_data = {"body": response.content}
        
    return {"copy_deck": copy_data}