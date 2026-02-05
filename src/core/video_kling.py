import os
from typing import Any

from core.media_service import (
    download_to_file,
    duplicate_to_legacy_folder,
    save_bytes,
    slugify,
)

ALLOWED_AR = {"1:1", "4:5", "9:16", "16:9", "21:9"}


def _normalize_ar(ar_value: str) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    if ar_clean not in ALLOWED_AR:
        return "16:9"
    return ar_clean


def generate_video_kling(prompt: str, tenant_slug: str, ar: str = "16:9") -> str:
    """
    Gera vídeo usando Kling via Replicate.
    Salva em media/<slug>/ e DUPLICA em media/<tenant_original>/ (compatibilidade).
    Retorna path canônico (slug).
    """
    import replicate

    if not os.getenv("REPLICATE_API_TOKEN"):
        raise Exception("REPLICATE_API_TOKEN não configurado")

    safe_tenant = slugify(tenant_slug)
    ar = _normalize_ar(ar)

    model_id = os.getenv("KLING_MODEL_ID", "kwaivgi/kling-v1.6-standard")

    print(f"🎬 Kling: iniciando... tenant={safe_tenant} AR={ar}")

    output: Any = replicate.run(
        model_id,
        input={
            "prompt": prompt,
            "duration": 5,
            "cfg_scale": 0.5,
            "aspect_ratio": ar,
        },
    )

    local_path: str

    if isinstance(output, (bytes, bytearray)):
        local_path = save_bytes(bytes(output), tenant=safe_tenant, prefix="kling", ext=".mp4")
        duplicate_to_legacy_folder(local_path, legacy_tenant_raw=tenant_slug)
        return local_path

    if isinstance(output, list) and output:
        first = output[0]

        if isinstance(first, (bytes, bytearray)):
            local_path = save_bytes(bytes(first), tenant=safe_tenant, prefix="kling", ext=".mp4")
            duplicate_to_legacy_folder(local_path, legacy_tenant_raw=tenant_slug)
            return local_path

        if isinstance(first, str) and first.startswith(("http://", "https://")):
            local_path = download_to_file(
                first, tenant=safe_tenant, prefix="kling", default_ext=".mp4", timeout=300
            )
            duplicate_to_legacy_folder(local_path, legacy_tenant_raw=tenant_slug)
            return local_path

        if hasattr(first, "read"):
            local_path = save_bytes(first.read(), tenant=safe_tenant, prefix="kling", ext=".mp4")
            duplicate_to_legacy_folder(local_path, legacy_tenant_raw=tenant_slug)
            return local_path

        raise Exception(f"Retorno inesperado (lista): {type(first)}")

    if isinstance(output, str):
        if output.startswith(("http://", "https://")):
            local_path = download_to_file(
                output, tenant=safe_tenant, prefix="kling", default_ext=".mp4", timeout=300
            )
            duplicate_to_legacy_folder(local_path, legacy_tenant_raw=tenant_slug)
            return local_path
        raise Exception(f"Retorno string não-URL: {output[:120]}")

    if hasattr(output, "read"):
        local_path = save_bytes(output.read(), tenant=safe_tenant, prefix="kling", ext=".mp4")
        duplicate_to_legacy_folder(local_path, legacy_tenant_raw=tenant_slug)
        return local_path

    raise Exception(f"Retorno inesperado do Replicate: {type(output)}")
