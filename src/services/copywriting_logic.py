from src.services.planning_agent import get_client
from src.services.brand_context import build_brand_context_text
import json

async def generate_elite_copy(tenant_slug: str, briefing_data: dict):
    """
    O Redator de Elite: Transforma o briefing técnico em texto final 
    usando o DNA da marca para garantir originalidade.
    """
    client = get_client(tenant_slug)
    brand_dna = build_brand_context_text(tenant_slug)

    # Extraímos os pilares do briefing gerado no Atendimento
    summary = briefing_data.get("summary", "")
    key_message = briefing_data.get("key_message", "")
    tone = briefing_data.get("tone", "Profissional")

    system_prompt = f"""
    VOCÊ É O REDATOR CHEFE DA IAGÊNCIA.
    Sua escrita é magnética, curta e focada em resultados. 
    Você escreve para humanos, não para algoritmos, mas entende de SEO e persuasão.

    === DNA DA MARCA (DIRETRIZES DE ESTILO) ===
    {brand_dna}
    ===========================================

    BRIEFING DO JOB:
    - Resumo: {summary}
    - Mensagem Chave: {key_message}
    - Tom Sugerido: {tone}

    REGRAS DE OURO DA IAGÊNCIA (O VENENO):
    1. PROIBIDO clichês: 'alavancar', 'jornada', 'transformar', 'descubra o segredo', 'fique por dentro'.
    2. Use a técnica 40/30/30 (Autoridade, Conexão, Venda) de forma orgânica.
    3. Frases curtas. Parágrafos de no máximo 3 linhas.
    4. Se for para redes sociais, inclua uma CTA (Chamada para Ação) forte no final.
    5. O tom deve ser IDÊNTICO ao Brand Guide fornecido acima.
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Escreva o texto final baseado no briefing acima."}
            ],
            temperature=0.8 # Um pouco mais de criatividade para a redação
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Erro na Redação: {e}")
        raise e
