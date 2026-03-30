from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.tenant_loader import load_tenant_context

BASE_CONTEXT_PATH = Path(__file__).resolve().parent.parent.parent / "tenants_context"
TENANT_CONTEXT_PATH = Path(__file__).resolve().parent.parent.parent / "tenant_context"


def _read_text(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def _format_pillars(pillars: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for p in pillars:
        name = str(p.get("name") or "").strip()
        desc = str(p.get("description") or "").strip()
        if name and desc:
            parts.append(f"{name} {desc}")
        elif name:
            parts.append(name)
        elif desc:
            parts.append(desc)
    return "; ".join([p for p in parts if p])


def _format_brand_block(brand: Dict[str, Any]) -> str:
    name = str(brand.get("name") or "").strip()
    tone = str(brand.get("tone_of_voice") or "").strip()
    values = brand.get("core_values") or []
    pillars = brand.get("brand_pillars") or []

    lines: List[str] = []
    if name:
        lines.append(f"Marca {name}.")
    if tone:
        lines.append(f"Tom de voz {tone}.")
    if values:
        lines.append("Valores centrais " + ", ".join([str(v).strip() for v in values if str(v).strip()]) + ".")
    if pillars:
        pillar_text = _format_pillars(pillars)
        if pillar_text:
            lines.append("Pilares de marca " + pillar_text + ".")
    return "\n".join([l for l in lines if l]).strip()


def _sanitize_prompt_text(text: str) -> str:
    cleaned = re.sub(r"[\\[\\]\\(\\):]", " ", text or "")
    return re.sub(r"\\s+", " ", cleaned).strip()


def build_brand_context_text(tenant_slug: str) -> str:
    """
    Retorna um bloco de DNA de marca consolidado (brand_guide + brand.json).
    Útil para prompts de atendimento/redação/planejamento.
    """
    safe_slug = (tenant_slug or "mugo").strip().lower()

    brand_guide = _read_text(BASE_CONTEXT_PATH / safe_slug / "brand_guide.md") or ""

    ctx = load_tenant_context(safe_slug, TENANT_CONTEXT_PATH)
    brand = ctx.get("brand") or {}
    structured = _format_brand_block(brand)

    if brand_guide and structured:
        return f"{brand_guide}\n\n{structured}".strip()
    return (brand_guide or structured).strip()


def build_brand_context_pt(tenant_slug: str) -> str:
    """
    Retorna contexto em PT sem colchetes/parênteses/dois pontos.
    Ideal para anexar em prompts de imagem/vídeo.
    """
    safe_slug = (tenant_slug or "mugo").strip().lower()
    ctx = load_tenant_context(safe_slug, TENANT_CONTEXT_PATH)
    brand = ctx.get("brand") or {}
    text = _format_brand_block(brand)
    return _sanitize_prompt_text(text)
