import os
import time
import uuid
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

FLUX_API_KEY = os.getenv("REPLICATE_API_TOKEN")
FLUX_API_URL = os.getenv("FLUX_API_URL", "https://api.replicate.com/v1/predictions")


def _normalize_ar(ar_value: Optional[str]) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean or "16:9"


def generate_image_flux(prompt: str, tenant_id: str, ar: str = "16:9") -> str:
    if not FLUX_API_KEY:
        raise ValueError("REPLICATE_API_TOKEN não encontrado no .env")

    ar = _normalize_ar(ar)

    headers = {
        "Authorization": f"Bearer {FLUX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        # Se isso falhar, o Replicate vai responder 422 com detalhe.
        "version": "black-forest-labs/flux-1.1-pro",
        "input": {
            "prompt": prompt,
            "aspect_ratio": ar,
            "output_format": "png",
            "output_quality": 90,
            "safety_tolerance": 2,
        },
    }

    print(f"🎨 Flux: enviando prompt... tenant={tenant_id} AR={ar}")

    try:
        response = requests.post(FLUX_API_URL, headers=headers, json=payload, timeout=60)
        if response.status_code != 201:
            try:
                body = response.json()
            except Exception:
                body = response.text

            raise Exception(
                f"Erro Replicate ({response.status_code}). "
                f"body={body}"
    )

    except Exception as e:
        raise Exception(f"Falha HTTP ao chamar Replicate: {e}")

    if response.status_code != 201:
        # Mostra o erro REAL do Replicate
        try:
            body = response.json()
        except Exception:
            body = response.text

        raise Exception(
            f"Erro Replicate ({response.status_code}). "
            f"URL={FLUX_API_URL} | body={body}"
        )

    data = response.json()
    get_url = data.get("urls", {}).get("get")
    raw_output = data.get("output")

    if get_url and not raw_output:
        print("⏳ Flux: processando (polling)...")
        for _ in range(120):
            r = requests.get(get_url, headers=headers, timeout=30)
            j = r.json()
            status = j.get("status")

            if status == "succeeded":
                raw_output = j.get("output")
                break

            if status == "failed":
                raise Exception(f"Flux falhou no Replicate: {j}")

            time.sleep(1)

    image_url = None
    if raw_output:
        if isinstance(raw_output, list) and raw_output:
            image_url = raw_output[0]
        elif isinstance(raw_output, str):
            image_url = raw_output

    if not image_url:
        raise Exception(f"Não obtive URL da imagem. Resposta Replicate: {data}")

    print(f"⬇️ Flux: baixando imagem... {image_url[:80]}")

    img_resp = requests.get(image_url, timeout=180)
    img_resp.raise_for_status()
    img_bytes = img_resp.content

    tenant_dir = MEDIA_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    filename = f"flux_{int(time.time())}_{uuid.uuid4().hex[:10]}.png"
    filepath = tenant_dir / filename
    filepath.write_bytes(img_bytes)

    print(f"✅ Flux: imagem salva em {filepath}")
    return str(filepath)
