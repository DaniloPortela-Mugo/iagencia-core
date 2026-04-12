import os
from openai import OpenAI

from src.services.brand_context import build_brand_context_text
from src.services.tenant_keys import get_tenant_api_key

<<<<<<< HEAD
=======

def _clean_key(value: str | None):
    if not value:
        return None
    key = value.strip()
    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
        key = key[1:-1].strip()
    return key or None

>>>>>>> 7b559d8 (Atualização: novos arquivos e ajustes no projeto)
def get_client(tenant_slug: str | None = None):
    """Recupera o cliente OpenAI com a chave do tenant (fallback .env)."""
    api_key = None
    if tenant_slug:
        api_key = get_tenant_api_key(tenant_slug, "openai")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
<<<<<<< HEAD
=======
    api_key = _clean_key(api_key)
>>>>>>> 7b559d8 (Atualização: novos arquivos e ajustes no projeto)
    return OpenAI(api_key=api_key) if api_key else None

def load_tenant_context(tenant_slug: str) -> str:
    """O 'Veneno': Lê o DNA real da marca para evitar respostas genéricas."""
    try:
        brand_dna = build_brand_context_text(tenant_slug)
        if brand_dna:
            print(f"🧬 DNA carregado: {tenant_slug}")
            return brand_dna
        return f"Marca {tenant_slug}. Atue como um estrategista focado em autoridade e conversão."
    except Exception as e:
        print(f"❌ Erro ao ler DNA: {e}")
        return "Atue como um estrategista de marketing de elite."

def chat_with_planner(history: list, current_grid_context: str, tenant_slug: str = "mugo") -> str:
    """Conversa estratégica considerando o Brand Guide e o Grid atual."""
    client = get_client(tenant_slug)
    if not client: return "Erro: API Key não configurada."

    brand_dna = load_tenant_context(tenant_slug)

    system_prompt = f"""
    VOCÊ É O HEAD DE ESTRATÉGIA DA IAGÊNCIA.
    Sua missão é criar conteúdo que gere autoridade imediata. 
    Esqueça clichês de marketing. Seja direto, provocativo e estratégico.
    
    === DNA DA MARCA (DIRETRIZES RÍGIDAS) ===
    {brand_dna}
    =========================================

    REGRAS DE OURO:
    1. PROIBIDO: Usar palavras como 'alavancar', 'jornada', 'transformar' ou 'descubra'.
    2. Se o usuário pedir algo vago, exija clareza ou sugira algo disruptivo.
    3. Mantenha o tom de voz do Brand Guide acima em 100% do tempo.
    4. Responda em Markdown, focando em estruturar o conteúdo para o Grid:
    {current_grid_context},
    5. Não use === 
    6. Separe os tópicos em parágrafos.

    """

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        if isinstance(msg, dict):
            messages.append({"role": msg["role"], "content": str(msg["content"])})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.6 # Equilíbrio entre precisão e criatividade
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro cognitivo: {str(e)}"
