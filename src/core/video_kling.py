from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, List

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # src/core/video_kling.py → core→src→iagencia-core→meu_app
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# ✅ Kling de verdade (Replicate)
# Ex: "kwaivgi/kling-v3-omni-video" (modelo Omni com referência) :contentReference[oaicite:3]{index=3}
KLING_MODEL = os.getenv("KLING_MODEL", "kwaivgi/kling-v3-omni-video")

REPLICATE_BASE = os.getenv("REPLICATE_API_URL", "https://api.replicate.com/v1")

ALLOWED_AR = {"1:1", "4:5", "9:16", "16:9", "21:9"}


def _normalize_ar(ar_value: Optional[str]) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean if ar_clean in ALLOWED_AR else "16:9"


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    token = api_key or REPLICATE_API_TOKEN
    if not token:
        raise ValueError("REPLICATE_API_TOKEN não encontrado no .env")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _create_prediction_kling(
    model_owner_name: str,
    prompt: str,
    ar: str,
    *,
    api_key: Optional[str] = None,
    start_image: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    duration: int = 5,
    mode: str = "standard",
    negative_prompt: str = "",
    generate_audio: bool = False,
) -> Dict[str, Any]:
    """
    Chama Replicate via endpoint /v1/models/{owner}/{name}/predictions
    (não precisa de version_id).
    """
    if "/" not in model_owner_name:
        raise ValueError("KLING_MODEL deve estar no formato 'owner/name' (ex: kwaivgi/kling-v3-omni-video)")

    owner, name = model_owner_name.split("/", 1)
    url = f"{REPLICATE_BASE}/models/{owner}/{name}/predictions"

    input_payload: Dict[str, Any] = {
        "prompt": prompt,
        "aspect_ratio": ar,
        "duration": int(duration),
        "mode": mode,
    }

    if negative_prompt:
        input_payload["negative_prompt"] = negative_prompt

    # ✅ start_image: anima a imagem como primeiro frame
    if start_image:
        input_payload["start_image"] = start_image

    # ✅ reference_images: consistência/estilo/personagem (até 7) :contentReference[oaicite:4]{index=4}
    if reference_images:
        # remove vazios
        refs = [r for r in reference_images if isinstance(r, str) and r.strip()]
        if refs:
            input_payload["reference_images"] = refs

    # ✅ áudio nativo (se quiser usar)
    input_payload["generate_audio"] = bool(generate_audio)

    payload = {"input": input_payload}

    resp = requests.post(url, headers=_headers(api_key), json=payload, timeout=60)

    if resp.status_code != 201:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(f"Erro Replicate ({resp.status_code}). body={body}")

    return resp.json()


def _poll_prediction(get_url: str, max_wait_s: int = 900, poll_s: int = 2, api_key: Optional[str] = None) -> Dict[str, Any]:
    start = time.time()
    while time.time() - start < max_wait_s:
        r = requests.get(get_url, headers=_headers(api_key), timeout=30)
        j = r.json()
        status = j.get("status")

        if status == "succeeded":
            return j

        if status == "failed":
            raise RuntimeError(f"Vídeo falhou no Replicate: {j}")

        time.sleep(poll_s)

    raise TimeoutError("Timeout aguardando o Replicate finalizar o vídeo.")


def _extract_output_url(output: Any) -> Optional[str]:
    if not output:
        return None
    if isinstance(output, list) and output:
        return output[0]
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        for k in ("url", "output", "video", "file"):
            v = output.get(k)
            if isinstance(v, str) and v:
                return v
    return None


def generate_video_kling(
    prompt: str,
    tenant_id: str,
    ar: str = "16:9",
    *,
    api_key: Optional[str] = None,
    start_image: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    duration: int = 5,
    mode: str = "standard",
    negative_prompt: str = "",
    generate_audio: bool = False,
) -> str:
    """
    Gera vídeo via Kling (Replicate) e salva em:
      media/<tenant_id>/kling_<timestamp>_<id>.mp4
    Retorna o path absoluto como string.
    """
    ar = _normalize_ar(ar)

    print(f"🎬 Kling: enviando prompt... tenant={tenant_id} AR={ar} model={KLING_MODEL}")

    pred = _create_prediction_kling(
        KLING_MODEL,
        prompt,
        ar,
        api_key=api_key,
        start_image=start_image,
        reference_images=reference_images,
        duration=duration,
        mode=mode,
        negative_prompt=negative_prompt,
        generate_audio=generate_audio,
    )

    get_url = (pred.get("urls") or {}).get("get")
    raw_output = pred.get("output")

    if get_url and not raw_output:
        print("⏳ Kling: processando (polling)...")
        final = _poll_prediction(get_url, max_wait_s=900, poll_s=2, api_key=api_key)
        raw_output = final.get("output")

    video_url = _extract_output_url(raw_output)
    if not video_url and get_url:
        final = _poll_prediction(get_url, max_wait_s=60, poll_s=2, api_key=api_key)
        video_url = _extract_output_url(final.get("output"))

    if not video_url:
        raise RuntimeError(f"Não obtive URL do vídeo. Resposta Replicate: {pred}")

    print(f"⬇️ Kling: baixando vídeo... {str(video_url)[:90]}")

    resp = requests.get(video_url, timeout=300)
    resp.raise_for_status()
    video_bytes = resp.content

    tenant_dir = MEDIA_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    filename = f"kling_{int(time.time())}_{uuid.uuid4().hex[:10]}.mp4"
    filepath = tenant_dir / filename
    filepath.write_bytes(video_bytes)

    print(f"✅ Kling: vídeo salvo em {filepath}")
    return str(filepath)
