# ARQUIVO: src/core/video_veo.py
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai.types import GenerateVideosConfig
from google.cloud import storage


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # src/core/video_veo.py → core→src→iagencia-core→meu_app
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_AR = {"1:1", "4:5", "9:16", "16:9", "21:9"}


def _normalize_ar(ar_value: Optional[str]) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean if ar_clean in ALLOWED_AR else "16:9"


def _parse_gs_uri(gs_uri: str) -> tuple[str, str]:
    if not gs_uri.startswith("gs://"):
        raise ValueError(f"URI inválida (esperado gs://...): {gs_uri}")
    no_scheme = gs_uri.replace("gs://", "", 1)
    bucket, _, blob = no_scheme.partition("/")
    if not bucket or not blob:
        raise ValueError(f"URI GCS inválida: {gs_uri}")
    return bucket, blob


def _download_from_gcs(gs_uri: str, dest_path: Path) -> None:
    bucket_name, blob_name = _parse_gs_uri(gs_uri)

    client = storage.Client()  # usa ADC
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(dest_path))


def generate_video_veo(
    prompt: str,
    tenant_slug: str,
    ar: str = "16:9",
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait_seconds: int = 900,
    poll_seconds: int = 15,
) -> str:
    """
    Gera vídeo via Veo (Vertex AI oficial).
    Retorna o caminho local do .mp4 salvo em /media/<tenant>/...

    Requisitos:
    - GOOGLE_GENAI_USE_VERTEXAI=True
    - GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION
    - VEO_OUTPUT_GCS_URI definido (gs://bucket/prefix)
    - ADC configurado (gcloud auth application-default login)
    """
    ar = _normalize_ar(ar)
    model_id = model or os.getenv("VEO_MODEL", "veo-3.0-generate-001")

    output_gcs_uri = os.getenv("VEO_OUTPUT_GCS_URI")
    if not output_gcs_uri:
        raise ValueError("VEO_OUTPUT_GCS_URI não definido no .env (ex: gs://bucket/prefix)")

    # Cliente do genai: usa api_key se fornecida, senão ADC/Vertex
    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    operation = client.models.generate_videos(
        model=model_id,
        prompt=prompt,
        config=GenerateVideosConfig(
            aspect_ratio=ar,
            output_gcs_uri=output_gcs_uri,
        ),
    )

    start = time.time()
    while not operation.done:
        if time.time() - start > max_wait_seconds:
            raise TimeoutError("Timeout esperando o Veo finalizar a geração.")
        time.sleep(poll_seconds)
        operation = client.operations.get(operation)

    if not operation.response or not operation.result.generated_videos:
        raise RuntimeError("Veo não retornou vídeo (response vazio).")

    video_uri = operation.result.generated_videos[0].video.uri
    if not video_uri:
        raise RuntimeError("Veo retornou sem URI de vídeo.")

    # Baixa do GCS e salva localmente no /media
    ts = int(time.time())
    out_dir = MEDIA_DIR / tenant_slug
    out_path = out_dir / f"veo_{ts}.mp4"

    _download_from_gcs(video_uri, out_path)
    return str(out_path)
