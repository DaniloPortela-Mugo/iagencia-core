import os
import json
from pathlib import Path
from openai import OpenAI

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS
# ==============================================================================
# Define o caminho base para a pasta 'tenants_context' na raiz do projeto.
# Lógica: O arquivo está em src/services/planning_agent.py
# .parent (services) -> .parent (src) -> .parent (iagencia-core) -> / tenants_context
BASE_CONTEXT_PATH = Path(__file__).resolve().parent.parent.parent / "tenants_context"

def get_client():
    """Recupera o cliente OpenAI com a chave configurada no ambiente."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Erro: OPENAI_API_KEY não encontrada no .env")
        return None
    return OpenAI(api_key=api_key)

def load_tenant_context(tenant_slug: str) -> str:
    """
    Lê o arquivo brand_guide.md do cliente específico para dar contexto à IA.
    Se não encontrar, retorna um contexto genérico de segurança.
    """
    # Garante segurança no caminho (remove caracteres perigosos do slug)
    safe_slug = os.path.basename(tenant_slug.strip().lower())
    file_path = BASE_CONTEXT_PATH / safe_slug / "brand_guide.md"

    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                print(f"📂 Contexto carregado para: {safe_slug}")
                return f.read()
        else:
            print(f"⚠️ Arquivo de contexto não encontrado em: {file_path}")
            return f"Você é um estrategista de marketing digital atendendo a marca {safe_slug}."
    except Exception as e:
        print(f"❌ Erro ao ler contexto do tenant: {e}")
        return "Você é um assistente de marketing criativo."

def chat_with_planner(history: list, current_grid_context: str, tenant_slug: str = "mugo") -> str:
    """
    Agente de Planejamento que conversa com o usuário considerando o Brand Guide do tenant (cliente) e o Grid atual.
    """
    client = get_client()
    
    if not client:
        return "Erro: API Key da OpenAI não configurada no backend."

    # 1. Carrega o contexto dinâmico do cliente
    brand_context = load_tenant_context(tenant_slug)

    # 2. Monta o Prompt do Sistema
    system_prompt = f"""
    Você é um estrategista de conteúdo especializado em planejamento, posicionamento e autoridade digital,
    especialista em construção de valor e credibilidade. 
    Seu foco é criar ideias originais de conteúdo alinhadas com o Brand Guide e o Grid Tático de
    mídias sociais. Seu papel é estruturar um perfil para ser percebido como referência no nicho, 
    independente do número de seguidores.
    
    === CONHECIMENTO DA MARCA (BRAND GUIDE) ===
    {brand_context}
    ===========================================

    SEU OBJETIVO:
    Ajudar o usuário a preencher o Calendário Tático.
    Seja criativo, direto, estratégico e mantenha rigorosamente o tom de voz descrito acima.
    
    CONTEXTO ATUAL DO GRID (O que o usuário já planejou):
    {current_grid_context}

    REGRAS DE RESPOSTA:
    1. Se o usuário pedir ideias, sugira com base nos Pilares da marca.
    2. Se o grid estiver vazio, sugira uma semana modelo equilibrada.
    3. Responda em Markdown, usando negrito para destacar ideias principais.
    4. Sempre alinhe suas sugestões com o Brand Guide carregado.
    5. Não use linguagem genérica ou clichês de marketing.
    6. Não use emojis em excesso, apenas se o tom de voz permitir.
    7. Separe as ideias por tópicos claros e numerados.
    8. Se o usuário pedir para gerar o JSON do grid, obedeça estritamente o formato solicitado na mensagem do usuário.
    """

    # 3. Prepara as mensagens para a API
    messages = [{"role": "system", "content": system_prompt}]
    
    # Adiciona histórico recente (últimas 6 mensagens para manter o contexto da conversa)
    # Filtramos para garantir que só objetos válidos sejam passados
    for msg in history[-6:]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": str(msg["content"])})

    try:
        print(f"🧠 Planner ({tenant_slug}): Pensando...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7 # Criatividade moderada
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Erro no cérebro do Planner: {e}")
        return f"Tive um problema cognitivo momentâneo (Erro OpenAI): {str(e)}"