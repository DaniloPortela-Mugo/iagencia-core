import json
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0.6)

# --- FUNÇÃO PARA O DASHBOARD (PLANNING.TSX) ---
def analyze_competitors_radar(brand_context: str):
    """
    Gera uma análise simulada de concorrentes para o widget 'Radar'.
    """
    prompt = f"""
    Atue como Estrategista de Marca. Analise o contexto da marca abaixo e simule o que 3 concorrentes genéricos (ou reais se citados) estariam fazendo de relevante nas redes sociais agora.

    CONTEXTO DA MARCA:
    {brand_context}

    Retorne APENAS um JSON estrito com esta lista:
    [
        {{ "name": "Nome Concorrente", "post": "Descrição curta do post destaque deles (ex: Reels sobre X)", "likes": "1.2K", "comments": "45" }},
        ... (total 3 itens)
    ]
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.replace('```json', '').replace('```', '').strip()
        return json.loads(content)
    except Exception as e:
        print(f"Erro em Radar: {e}")
        return [
            { "name": "Concorrente A", "post": "Análise de Mercado", "likes": "N/A", "comments": "0" }
        ]

# --- FUNÇÃO DO FLUXO DE CAMPANHA (MANTIDA) ---
def strategist_node(state):
    # ... (seu código original) ...
    pass