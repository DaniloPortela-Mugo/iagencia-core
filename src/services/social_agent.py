import os
import json
from pathlib import Path
from openai import OpenAI
from src.services.planning_agent import get_client
from src.services.tenant_loader import load_tenant_context

def get_social_intelligence(tenant_slug: str):
    """Retorna dados de tendências e radar para o dashboard."""
    # Simulação de inteligência para marcas como Mugô, Voy e Ssavon
    return {
        "trends": [
            {"topic": "Humanização com IA", "growth": "+92%"},
            {"topic": "Conteúdo 'Raw' e Bastidores", "growth": "+45%"},
            {"topic": "Autoridade Técnica em Vídeo", "growth": "+38%"}
        ],
        "competitors": [
            {"name": "Principal Player", "post": "Foco em carrosséis educativos"},
            {"name": "Novo Entrante", "post": "Reels com tom disruptivo"}
        ],
        "performance_insight": f"A estratégia da {tenant_slug.upper()} deve priorizar autoridade na Semana 2."
    }

async def generate_social_grid(tenant_slug: str, context: str = ""):
    client = get_client(tenant_slug)
    tenant_root = Path(__file__).resolve().parent.parent.parent / "tenant_context"
    ctx = load_tenant_context(tenant_slug, tenant_root)
    brand = ctx.get("brand", {})
    social = ctx.get("socialmedia", {})
    pillars = social.get("content_pillars") or []
    platform_focus = social.get("platform_focus") or []
    hashtags = social.get("hashtags") or []

    # Normalizações defensivas
    if isinstance(pillars, str):
        pillars = [p.strip() for p in pillars.split(",") if p.strip()]
    if isinstance(platform_focus, str):
        platform_focus = [p.strip() for p in platform_focus.split(",") if p.strip()]
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]

    system_prompt = (
        "Você é Social Media Manager Senior da IAgência. Responda em pt-BR.\n"
        "ESTILO (obrigatório):\n"
        "- Direto ao ponto.\n"
        "- Sem frases de simpatia (ex.: 'claro', 'posso ajudar', 'por favor').\n"
        "- Não repita/parafraseie o pedido do usuário.\n"
        "- Não diga o que vai fazer; faça.\n"
        "- Se faltar dado essencial, faça no máximo 1 pergunta objetiva.\n"
        "SAÍDA (obrigatório): retornar APENAS JSON válido, sem markdown.\n"
    )

    brand_header = f"Marca: {brand.get('name') or tenant_slug}"
    pillar_lines = []
    for p in pillars:
        if isinstance(p, dict):
            category = p.get("category") or p.get("name") or "Pilar"
            weight = p.get("weight") or ""
            topics = p.get("topics") or []
            if isinstance(topics, str):
                topics = [t.strip() for t in topics.split(",") if t.strip()]
            topics_txt = ", ".join([t for t in topics if t])
            line = f"- {category}"
            if weight:
                line += f": {weight}"
            if topics_txt:
                line += f" | {topics_txt}"
            pillar_lines.append(line)
        elif isinstance(p, str):
            pillar_lines.append(f"- {p}")
    pillars_txt = "\n".join(pillar_lines) or "Nenhum pilar definido."
    platform_txt = ", ".join(platform_focus) if platform_focus else "Sem foco definido."
    hashtags_txt = ", ".join(hashtags) if hashtags else "Sem hashtags definidas."

    user_prompt = (
        f"{brand_header}\n"
        f"Pilares de conteúdo (obrigatório):\n{pillars_txt}\n\n"
        f"Plataformas foco: {platform_txt}\n"
        f"Hashtags sugeridas: {hashtags_txt}\n\n"
        f"Contexto adicional (se houver):\n{context}\n\n"
        "Gere um JSON no formato EXATO:\n"
        "{\n"
        '  "grid": [\n'
        "    {\n"
        '      "platform": "Instagram (Feed)|Instagram (Stories)|TikTok / Reels|LinkedIn",\n'
        '      "pillar": "string curta",\n'
        '      "w1": "texto", "w2": "texto", "w3": "texto", "w4": "texto"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Regras do conteúdo:\n"
        "- 4 semanas (w1..w4), com ideias específicas.\n"
        "- Texto curto e acionável.\n"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
        grid = data.get("grid", [])
        return grid if isinstance(grid, list) else []
    except Exception as e:
        print(f"❌ Erro ao gerar Grid: {e}")
        return []
