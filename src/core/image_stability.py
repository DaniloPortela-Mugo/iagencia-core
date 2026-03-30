import base64
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
STABILITY_API_URL = os.getenv(
    "STABILITY_API_URL",
    "https://api.stability.ai/v2beta/stable-image/generate/core",
)

VALID_AR = {"21:9", "16:9", "3:2", "5:4", "1:1", "4:5", "2:3", "9:16", "9:21"}


def _normalize_ar(ar_value: Optional[str]) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean if ar_clean in VALID_AR else "16:9"


def _auth_header(api_key: str) -> str:
    # Stability v2beta usa header "authorization" com a chave (sem Bearer)
    return api_key if api_key.lower().startswith("bearer ") else api_key


def generate_image_stability(
    *,
    prompt: str,
    tenant_id: str,
    ar: str = "16:9",
    negative_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    output_format: str = "png",
) -> str:
    key = api_key or STABILITY_API_KEY
    if not key:
        raise ValueError("STABILITY_API_KEY não encontrado no .env")

    ar = _normalize_ar(ar)

    headers = {
        "authorization": _auth_header(key),
        "accept": "application/json",
    }

    data = {
        "prompt": prompt,
        "aspect_ratio": ar,
        "output_format": output_format,
    }
    if negative_prompt:
        data["negative_prompt"] = negative_prompt

    resp = requests.post(STABILITY_API_URL, headers=headers, data=data, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"Stability error ({resp.status_code}): {resp.text}")

    payload = resp.json()
    image_b64 = payload.get("image")
    if not image_b64:
        raise RuntimeError(f"Stability: resposta sem imagem. payload={payload}")

    img_bytes = base64.b64decode(image_b64)
    ext = "png" if output_format.lower() not in ("jpg", "jpeg", "webp") else output_format.lower()
    tenant_dir = MEDIA_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    filename = f"stability_{int(time.time())}_{uuid.uuid4().hex[:10]}.{ext}"
    out_path = tenant_dir / filename
    out_path.write_bytes(img_bytes)
    return str(out_path.resolve())
