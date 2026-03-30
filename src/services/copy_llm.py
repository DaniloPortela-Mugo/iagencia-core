import os
from pathlib import Path
from openai import OpenAI
from src.services.tenant_keys import get_tenant_api_key

def get_client(tenant_slug: str | None = None):
    api_key = None
    if tenant_slug:
        api_key = get_tenant_api_key(tenant_slug, "openai")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY não encontrada no .env ou tenant.")
    return OpenAI(api_key=api_key)

# --- NOVO: Carregador de Contexto do Tenant ---
def load_brand_context(tenant_slug: str) -> str:
    """
    Lê o arquivo brand_guide.md específico do cliente (tenant).
    Isso é o que diferencia a iagência do ChatGPT comum.
    """
    try:
        # Caminho: iagencia-core/tenants_context/{slug}/brand_guide.md
        # Ajuste o caminho base conforme a estrutura da sua pasta
        base_path = Path(__file__).resolve().parent.parent.parent 
        context_path = base_path / "tenants_context" / tenant_slug / "brand_guide.md"
        
        if context_path.exists():
            with open(context_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível carregar contexto para {tenant_slug}: {e}")
        return ""

def generate_copy_content(data: dict) -> str:
    """
    Gera texto publicitário injetando o DNA da marca (Tenant Context).
    """
    client = get_client(tenant_slug)
    
    # Extração de dados
    tenant_slug = data.get('tenant_slug', 'mugo') # Padrão para Mugô se não vier nada
    fmt = data.get('format', 'Post Social Media')
    title = data.get('title', '')
    duration = data.get('duration', '')
    topic = data.get('topic', '')
    tone = data.get('tone', 'Profissional')
    framework = data.get('framework', 'Livre')
    target = data.get('target_audience', 'Público Geral')

    # 1. CARREGA O DNA DA MARCA (O Diferencial da iagência)
    brand_context = load_brand_context(tenant_slug)
    
    if not brand_context:
        brand_context = "Você é um copywriter profissional."

    # Identifica se é roteiro
    is_script = any(x in fmt for x in ["Roteiro", "TV", "Rádio", "Vídeo"])

    # 2. Construção do System Prompt "Turbinado"
    system_prompt = f"""
    {brand_context}
    
    ---
    
    SUA MISSÃO ATUAL:
    Atue como um Redator Sênior especialista no framework {framework}.
    O formato solicitado é: {fmt}.
    Público-alvo específico desta peça: {target}.
    Tom de voz ajustado para esta campanha: {tone}.
    """

    if is_script:
        system_prompt += (
            f"\n\nREGRAS DE FORMATAÇÃO (RIGOROSO):"
            "\n1. O formato é um ROTEIRO DE VÍDEO/ÁUDIO."
            "\n2. Responda APENAS com uma Tabela Markdown contendo as colunas: | TEMPO | VÍDEO (Visual) | ÁUDIO (Fala/SFX) |."
            f"\n3. Duração estimada total: {duration} segundos."
            "\n4. Seja detalhista na descrição visual (coluna VÍDEO)."
        )
    else:
        system_prompt += (
            f"\n\nREGRAS DE FORMATAÇÃO:"
            "\n1. Use formatação Markdown (negrito, tópicos)."
            "\n2. Se for post, inclua sugestões de emojis e hashtags pertinentes à marca."
            "\n3. Foque em copywriting persuasivo."
        )

    # 3. Construção do User Prompt
    user_prompt = f"BRIEFING DA TAREFA:\nTema: {topic}\n"
    if title:
        user_prompt += f"Título/Campanha: {title}\n"
    
    user_prompt += "\nEscreva o conteúdo agora seguindo rigorosamente o guia da marca acima."

    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Erro OpenAI: {e}")
        return f"Erro ao gerar copy: {str(e)}"

def chat_with_agent(current_text: str, user_msg: str, active_agent: str) -> str:
    """
    Chat interativo (Co-piloto) que mantém o contexto.
    """
    client = get_client(tenant_slug)

    system_prompt = (
        f"Você é o {active_agent}, um editor sênior da iagência."
        "Seu objetivo é refinar o texto do usuário mantendo a voz da marca."
        "Seja direto, prestativo e faça os ajustes solicitados no texto."
    )

    user_prompt = (
        f"TEXTO ORIGINAL:\n---\n{current_text}\n---\n\n"
        f"PEDIDO DE ALTERAÇÃO: {user_msg}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro no chat: {str(e)}"
