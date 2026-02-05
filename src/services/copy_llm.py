import os
from openai import OpenAI

def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY não encontrada no .env")
    return OpenAI(api_key=api_key)

def generate_copy_content(data: dict) -> str:
    """
    Gera texto publicitário ou roteiro usando OpenAI (GPT-4o ou 3.5).
    """
    client = get_client()
    
    # Extração de dados
    fmt = data.get('format', 'Post Social Media')
    c_client = data.get('client', 'Marca Genérica')
    sub_client = data.get('sub_client', '')
    title = data.get('title', '')
    duration = data.get('duration', '')
    topic = data.get('topic', '')
    tone = data.get('tone', 'Profissional')
    framework = data.get('framework', 'Livre')
    target = data.get('target_audience', 'Público Geral')

    # Identifica se é roteiro (para forçar tabela)
    is_script = any(x in fmt for x in ["Roteiro", "TV", "Rádio", "Vídeo"])

    # 1. Construção do System Prompt
    system_prompt = (
        f"Você é um Copywriter Sênior especialista em {framework}."
        f"Seu tom de voz é {tone}."
        f"Você está escrevendo para o cliente: {c_client} {f'({sub_client})' if sub_client else ''}."
        f"Público-alvo: {target}."
    )

    if is_script:
        system_prompt += (
            "\nIMPORTANTE: O formato é um ROTEIRO DE VÍDEO/ÁUDIO."
            "\nVocê DEVE responder APENAS com uma Tabela Markdown com as colunas: | TEMPO | ÁUDIO | VÍDEO |."
            "\nNão coloque texto antes ou depois da tabela."
            f"\nDuração estimada: {duration} segundos."
        )
    else:
        system_prompt += (
            f"\nFormato de saída: {fmt}."
            "\nUse emojis estrategicamente se o tom permitir."
            "\nFoque em conversão e engajamento."
        )

    # 2. Construção do User Prompt
    user_prompt = f"O tema/briefing é: {topic}."
    if title:
        user_prompt += f"\nTítulo da peça: {title}."
    
    user_prompt += "\nCrie o conteúdo agora."

    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Ou "gpt-4-turbo" / "gpt-3.5-turbo" dependendo da sua cota
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

def chat_with_agent(current_text: str, user_msg: str, agent_name: str) -> str:
    """
    Chat interativo para refinar o texto (Co-piloto).
    """
    client = get_client()

    system_prompt = (
        f"Você é o {agent_name}, um assistente editorial inteligente."
        "O usuário vai pedir alterações em um texto existente."
        "Responda de forma direta e útil."
        "Se o usuário pedir para reescrever, forneça a nova versão."
        "Se for apenas uma dúvida, responda a dúvida."
    )

    user_prompt = (
        f"TEXTO ATUAL:\n---\n{current_text}\n---\n\n"
        f"SOLICITAÇÃO DO USUÁRIO: {user_msg}"
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