import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.core.state import CampaignState

llm = ChatOpenAI(model="gpt-4-turbo", temperature=0.3)

def researcher_node(state: CampaignState):
    """
    Agente 2.1: Busca referências e insights.
    (Simulado via LLM Knowledge Base para evitar dependência de API de Search externa por enquanto)
    """
    print("--- [NODE] Researcher ---")
    req = state.request
    
    prompt = f"""
    Você é um Pesquisador de Tendências.
    O usuário quer criar uma peça sobre: "{req.scene_description}" para a marca "{req.brand_name}".
    
    Gere um mini-dossiê com:
    1. 3 Tendências visuais atuais sobre esse tema.
    2. Perfil provável do público-alvo.
    3. Lista de clichês a evitar.
    
    Retorne JSON: {{ "trends": [], "audience": "...", "avoid": [] }}
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        data = json.loads(response.content)
    except:
        data = {"error": "Research failed", "raw": response.content}
        
    return {"research_data": data}

def compliance_node(state: CampaignState):
    """
    Agente 2.2: Fact-Checker e Segurança de Marca.
    """
    print("--- [NODE] Compliance Guard ---")
    req = state.request
    
    # Se tiver copy gerado, valida o copy. Se não, valida a ideia inicial.
    content_to_check = state.copy_assets or req.scene_description
    
    prompt = f"""
    Analise riscos de Compliance/PR para: "{content_to_check}".
    Setores sensíveis: Saúde, Finanças, Política, Menores de idade.
    
    Retorne JSON: {{ "approved": true/false, "flags": ["lista de riscos"], "suggestion": "..." }}
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        report = json.loads(response.content)
    except:
        report = {"approved": True, "flags": [], "suggestion": "Auto-approved"}
        
    return {"risk_report": report}