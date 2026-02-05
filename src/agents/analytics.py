import json
import os
import requests
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

def fetch_instagram_data():
    """
    Busca métricas reais do Instagram Graph API usando as chaves do .env.
    Retorna um dicionário com os dados ou None se falhar.
    """
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")

    if not token or not account_id:
        print("⚠️ Chaves do Instagram não configuradas no .env. Usando dados simulados.")
        return None

    try:
        # Endpoint para pegar dados básicos da conta (Seguidores, etc)
        url = f"https://graph.facebook.com/v19.0/{account_id}?fields=followers_count,media_count,name,biography&access_token={token}"
        response = requests.get(url)
        data = response.json()
        
        if "error" in data:
            print(f"❌ Erro API Instagram: {data['error']['message']}")
            return None
            
        # Opcional: Buscar insights de alcance (requer permissões extras)
        # Por enquanto, vamos retornar os dados básicos do perfil
        return {
            "followers": str(data.get("followers_count", 0)),
            "posts": str(data.get("media_count", 0)),
            "account_name": data.get("name", "Mugô")
        }
    except Exception as e:
        print(f"❌ Erro de conexão Instagram: {e}")
        return None

def generate_performance_insights(metrics_provided: dict, brand_context: str):
    """
    Lê os números (reais ou simulados) e gera um insight estratégico.
    """
    
    # 1. Tenta buscar dados reais
    real_data = fetch_instagram_data()
    
    # 2. Decide quais dados usar (Reais > Providenciados pelo Frontend > Simulados)
    if real_data:
        metrics_final = real_data
        source_msg = "(Baseado em DADOS REAIS do Instagram)"
    else:
        metrics_final = metrics_provided
        source_msg = "(Baseado em dados simulados)"

    print(f"📊 Gerando insights com: {metrics_final}")

    prompt = f"""
    Você é um Analista de Dados de Marketing Sênior da agência Mugô.
    Analise as métricas de performance abaixo:
    
    CONTEXTO DA MARCA: {brand_context[:200]}...
    MÉTRICAS ATUAIS: {json.dumps(metrics_final)}
    
    Gere UMA frase curta, estratégica e motivadora (max 25 palavras) com um insight ou recomendação.
    Não mencione que são dados simulados. Seja direto.
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        insight_text = response.content.strip().replace('"', '')
        return f"{insight_text}" 
    except:
        return "Métricas estáveis. Continue monitorando o engajamento e a constância nos Stories."