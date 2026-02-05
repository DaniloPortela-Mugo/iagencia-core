import json
import os
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
# Se estiver usando o state em outro lugar, mantenha o import, senão pode remover se for só API
# from src.core.state import CampaignState 

llm = ChatOpenAI(model="gpt-4-turbo", temperature=0.5)

# --- FUNÇÃO PARA O DASHBOARD (PLANNING.TSX) ---
def get_market_trends(brand_context: str):
    """
    Gera tendências de mercado baseadas no nicho do cliente (Brand Guide).
    Usado no widget 'Trends' do Dashboard.
    """
    prompt = f"""
    Atue como um Coolhunter (Pesquisador de Tendências) sênior.
    Com base no perfil da marca abaixo, identifique 3 tendências de conteúdo (formatos, áudios ou tópicos) que estão em alta nesta semana.

    PERFIL DA MARCA:
    {brand_context}

    Retorne APENAS um JSON estrito (sem markdown) com esta lista:
    [
        {{ "topic": "Nome da Trend", "growth": "Alta" | "Média", "sentiment": "positive" | "neutral" }},
        ... (total 3 itens)
    ]
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        # Limpeza básica de markdown caso a IA mande ```json
        content = response.content.replace('```json', '').replace('```', '').strip()
        return json.loads(content)
    except Exception as e:
        print(f"Erro em Trends: {e}")
        # Fallback para não quebrar a tela
        return [
            { "topic": "Vídeos Curtos (Shorts)", "growth": "Alta", "sentiment": "positive" },
            { "topic": "Conteúdo Humanizado", "growth": "Média", "sentiment": "positive" },
            { "topic": "IA Generativa", "growth": "Alta", "sentiment": "neutral" }
        ]

# --- FUNÇÃO DO FLUXO DE CAMPANHA (MANTIDA) ---
def researcher_node(state): 
    """
    Busca referências visuais para um job específico.
    """
    print("--- [NODE] Researcher ---")
    # ... (seu código original aqui) ...
    return {"research_data": {}}