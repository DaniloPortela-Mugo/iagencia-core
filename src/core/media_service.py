from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from src.services.prompt_refiner import analyze_reference_image, refine_prompt_for_flux
from src.core.image_flux import generate_image_flux
from src.core.video_kling import generate_video_kling
from src.core.image_identity import generate_identity  # <- identity engine


ALLOWED_AR = {"1:1", "4:5", "9:16", "16:9", "21:9"}


def _normalize_ar(ar_value: Optional[str]) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean if ar_clean in ALLOWED_AR else "16:9"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def sanitize_prompt(text: str) -> str:
    """
    Sanitização leve e segura para evitar:
    - ", ," / " ."
    - múltiplos espaços
    - pontuação duplicada no final
    """
    if not text:
        return ""

    text = text.replace(" ,", ",").replace(" .", ".")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"([,\.])\s*\1+", r"\1", text)  # remove ",," e ".."
    text = text.strip(" ,.")
    return text.strip()


def _format_persona(persona_raw: Any) -> str:
    if not persona_raw:
        return ""

    if isinstance(persona_raw, str):
        return persona_raw.strip()

    if isinstance(persona_raw, list):
        parts = [_safe_str(p) for p in persona_raw if _safe_str(p)]
        return " + ".join(parts).strip()

    if isinstance(persona_raw, dict):
        details = []
        for key, value in persona_raw.items():
            k = _safe_str(key)
            if not k:
                continue

            if isinstance(value, str) and value.strip():
                details.append(f"{k}: {value.strip()}")
            elif isinstance(value, list):
                items = [_safe_str(x) for x in value if _safe_str(x)]
                if items:
                    details.append(f"{k}: {', '.join(items)}")
            elif value is not None:
                details.append(f"{k}: {_safe_str(value)}")

        return " | ".join(details).strip()

    return _safe_str(persona_raw)


def _extract_form_fields(raw_data: Optional[Dict[str, Any]]) -> Tuple[str, str, str, str, str]:
    if not raw_data:
        return "Cinematic", "", "", "", ""

    style = _safe_str(raw_data.get("style")) or "Cinematic"

    idea = (
        _safe_str(raw_data.get("idea"))
        or _safe_str(raw_data.get("ideia_principal"))
        or _safe_str(raw_data.get("prompt"))
        or ""
    )

    scenario = _safe_str(raw_data.get("scenario")) or _safe_str(raw_data.get("cenario")) or ""
    action = _safe_str(raw_data.get("action")) or _safe_str(raw_data.get("acao_cena")) or ""

    persona_raw = raw_data.get("persona") or raw_data.get("personas")
    persona_text = _format_persona(persona_raw)

    chars = (raw_data or {}).get("characters") or []
    has_character = len(chars) > 0


    return style, idea, persona_text, action, scenario


def _build_user_input(prompt_en: str, raw_data: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    prompt_en = _safe_str(prompt_en)
    style, idea, persona_text, action, scenario = _extract_form_fields(raw_data)

    parts = []
    if idea:
        parts.append(f"CORE IDEA: {idea}")
    if persona_text:
        parts.append(f"CHARACTER: {persona_text}")
    if action:
        parts.append(f"ACTION: {action}")
    if scenario:
        parts.append(f"SETTING: {scenario}")

    user_input = " | ".join(parts).strip()
    if not user_input or len(user_input) < 3:
        user_input = prompt_en or "A high quality professional image"

    return user_input, style


def enrich_video_prompt(prompt: str, raw_data: Dict[str, Any]) -> str:
    """
    Adiciona semântica temporal/cinematográfica para vídeo (Kling/VEO).
    Não depende do front ser perfeito: é resiliente.
    """
    prompt = sanitize_prompt(prompt)
    raw_data = raw_data or {}

    movement = _safe_str(raw_data.get("camera_movement"))
    pacing = _safe_str(raw_data.get("pacing")) or "natural"
    duration = _safe_str(raw_data.get("duration"))  # opcional
    fps = _safe_str(raw_data.get("fps"))  # opcional

    extras = [
        "Cinematic motion",
        "natural movement",
        "realistic timing",
        "smooth camera flow",
        "no jitter",
        "no flicker",
        "stable subject identity across frames",
    ]

    if movement:
        extras.append(f"camera movement: {movement}")
    if pacing:
        extras.append(f"pacing: {pacing}")
    if duration:
        extras.append(f"duration: {duration}")
    if fps:
        extras.append(f"fps: {fps}")

    extra_str = ", ".join([e for e in extras if e])
    return sanitize_prompt(f"{prompt}. {extra_str}.")


def _get_public_base_url() -> str:
    return os.getenv("API_PUBLIC_BASE", "http://localhost:8000").rstrip("/")


def _project_root_dir() -> Path:
    # iagencia-core/src/core/media_service.py -> iagencia-core/
    return Path(__file__).resolve().parents[2]


def _media_root_dir() -> Path:
    media_dir = _project_root_dir() / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


def file_path_to_media_url(filepath: str) -> str:
    p = Path(filepath).resolve()
    media_root = _media_root_dir().resolve()

    try:
        rel = p.relative_to(media_root).as_posix()
    except Exception:
        rel = p.name

    rel_q = "/".join(quote(part) for part in rel.split("/"))
    return f"{_get_public_base_url()}/media/{rel_q}"


@dataclass(frozen=True)
class MediaResult:
    url: str
    type: str
    prompt: str
    provider: str
    ar: str


class MediaService:
    """
    Pipeline central e determinístico:
    - Monta input (user_input)
    - Vision opcional (ref_image)
    - Refiner (prompt técnico)
    - Preview-only OU geração (Flux/Kling/Identity engine)
    """

    @staticmethod
    def generate(
        *,
        tenant_slug: str,
        media_type: str,
        quality_mode: str,
        ar: str,
        prompt_en: str,
        raw_data: Optional[Dict[str, Any]] = None,
        ref_image: Optional[str] = None,
        preview_only: bool = False,
        identity_lock: bool = False,
    ) -> MediaResult:
        media_type = (_safe_str(media_type) or "image").lower()
        quality_mode = (_safe_str(quality_mode) or "standard").lower()
        ar = _normalize_ar(ar)
        tenant_slug = _safe_str(tenant_slug) or "mugo"

        raw_data = raw_data or {}

        # prioridade: flag explícita do endpoint; fallback: raw_data
        identity_lock = bool(identity_lock or raw_data.get("identity_lock"))

        user_input, style = _build_user_input(prompt_en, raw_data)

        # 1) Vision (se houver referência)
        ref_description = ""
        if ref_image:
            ref_description = analyze_reference_image(ref_image)

        # 2) Refiner (prompt técnico)
        optimized_prompt = refine_prompt_for_flux(
            user_prompt=user_input,
            style=style,
            reference_description=ref_description,
            has_character=has_character,
        )


        prompt_final = optimized_prompt.strip() if optimized_prompt else user_input
        if not prompt_final or len(prompt_final) < 5:
            prompt_final = user_input

        prompt_final = sanitize_prompt(prompt_final)

        # 2.1) Se for vídeo, enriquece (Kling/VEO-friendly)
        if media_type == "video":
            prompt_final = enrich_video_prompt(prompt_final, raw_data)

        # 3) Preview-only (não gera mídia)
        if preview_only:
            return MediaResult(
                url="",
                type="prompt",
                prompt=prompt_final,
                provider="refiner/preview",
                ar=ar,
            )

        # 4) Identity Lock (engine especializado)
        if identity_lock:
            if not ref_image:
                raise ValueError("identity_lock requer ref_image.")

            result_type, local_path, provider_used = generate_identity(
                prompt=prompt_final,
                ref_image=ref_image,
                tenant_id=tenant_slug,
                media_type=media_type,  # "image" | "video"
                ar=ar,
            )

            url = file_path_to_media_url(local_path)
            return MediaResult(
                url=url,
                type=result_type,
                prompt=prompt_final,
                provider=f"identity/{provider_used}",
                ar=ar,
            )

        # 5) Geração padrão (sem identity lock)
        if media_type == "video":
            local_path = generate_video_kling(prompt_final, tenant_slug, ar=ar)
            url = file_path_to_media_url(local_path)
            return MediaResult(
                url=url,
                type="video",
                prompt=prompt_final,
                provider="kling/replicate",
                ar=ar,
            )

        local_path = generate_image_flux(prompt=prompt_final, tenant_id=tenant_slug, ar=ar)
        url = file_path_to_media_url(local_path)
        return MediaResult(
            url=url,
            type="image",
            prompt=prompt_final,
            provider="flux/replicate",
            ar=ar,
        )
