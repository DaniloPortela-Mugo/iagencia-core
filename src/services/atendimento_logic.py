from datetime import datetime
import json
from src.services.planning_agent import get_client
from src.services.brand_context import build_brand_context_text

async def process_atendimento_briefing(
    tenant_slug: str, 
    title: str, 
    raw_input: str,
    objective: str = "",
    target_audience: str = "",
    cta: str = "",
    restrictions: str = "",
    boldness: int = 3,
    references: str = ""
):
    """Transforma o caos do pedido em um briefing técnico de elite."""
    client = get_client(tenant_slug)
    if not client: 
        raise Exception("OpenAI Client não inicializado.")
    
    brand_dna = build_brand_context_text(tenant_slug)
    data_atual = datetime.now().strftime("%d/%m/%Y") # ✅ Definindo a data aqui dentro

    boldness_map = { 
        1: "Conservador", 
        2: "Sério", 
        3: "Equilibrado", 
        4: "Arrojado", 
        5: "Disruptivo" 
    }

    # 🚨 O segredo: A palavra 'JSON' deve aparecer nas instruções
    system_prompt = f"""
    Você é o Head de Estratégia da IAgência. 
    Sua tarefa é gerar um BRIEFING TÉCNICO DE ELITE em formato JSON.
    
    === DNA DA MARCA ===
    {brand_dna}
    ====================

    DIRETRIZES ESTRATÉGICAS:
    - OBJETIVO: {objective}
    - PÚBLICO: {target_audience}
    - CTA: {cta}
    - OUSADIA: {boldness_map.get(boldness, "Equilibrado")}
    - REFERÊNCIAS: {references}

    TÍTULO: {title}
    DATA: {data_atual}
    PEDIDO BRUTO: {raw_input}

    IMPORTANTE: Você deve responder exclusivamente em formato JSON, seguindo rigorosamente a estrutura abaixo:
    {{
      "summary": "Resumo focado no entregável.",
      "tone": "Tom derivado do Brand Guide.",
      "objective": "O que queremos alcançar.",
      "key_message": "Mensagem central.",
      "deliverables": ["Item 1", "Item 2"],
      "tech_requirements": "Specs e formatos."
    }}
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}],
            response_format={"type": "json_object"}, # ✅ Agora ele vai aceitar!
            temperature=0.3
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erro Atendimento Logic: {e}")
        raise e
