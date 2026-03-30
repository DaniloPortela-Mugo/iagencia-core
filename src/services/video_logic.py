from src.services.planning_agent import get_client
from src.services.brand_context import build_brand_context_text
import json

async def generate_cinematic_script(tenant_slug: str, briefing_data: dict):
    """
    Transforma o briefing em um roteiro de vídeo decupado cena a cena.
    Injeta o DNA da marca para definir o ritmo e a estética.
    """
    client = get_client(tenant_slug)
    brand_dna = build_brand_context_text(tenant_slug)

    system_prompt = f"""
    VOCÊ É UM ROTEIRISTA E DIRETOR DE CINEMA PUBLICITÁRIO SÊNIOR.
    Sua missão é criar roteiros de alta conversão para a IAgência.

    === DNA DA MARCA (OBRIGATÓRIO) ===
    {brand_dna}
    ==================================

    === ESTRUTURA DO BRIEFING ===
    - Objetivo: {briefing_data.get('objective')}
    - Público: {briefing_data.get('target_audience')}
    - Ousadia: {briefing_data.get('boldness')}
    - Referências: {briefing_data.get('references')}

    REGRAS DE OURO:
    1. DECUPE POR CENAS: Cada cena deve ter descrição visual, áudio e comando de câmera.
    2. RITMO: Se o DNA for 'Luxo' (Ssavon), use planos lentos e luz suave. Se for 'Tecnologia' (Hoover), use cortes rápidos e ângulos dinâmicos.
    3. LINGUAGEM: Proibido clichês. Use o tom de voz do Brand Guide.

    SAÍDA OBRIGATÓRIA (JSON STRICT):
    {{
      "video_title": "Título do Comercial",
      "concept": "A ideia central por trás do vídeo",
      "scenes": [
        {{
          "number": 1,
          "visual_prompt": "Descrição detalhada para gerador de vídeo (Inglês)",
          "audio": "Texto da locução ou descrição da trilha",
          "camera_direction": "Instrução técnica de movimento (ex: Slow Zoom In)",
          "duration": "Tempo estimado em segundos"
        }}
      ],
      "music_style": "Sugestão de trilha sonora"
    }}
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erro no Roteirista RTV: {e}")
        raise e
