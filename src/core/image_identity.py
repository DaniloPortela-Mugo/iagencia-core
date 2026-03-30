from __future__ import annotations

import base64
import os
import time
import uuid
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_AR = {"1:1", "4:5", "9:16", "16:9", "21:9"}

# ✅ FIX 2: Timeout centralizado para download de imagens remotas (em segundos)
HTTP_DOWNLOAD_TIMEOUT = 20


def _normalize_ar(ar_value: Optional[str]) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean if ar_clean in ALLOWED_AR else "16:9"


def _get_api_key() -> str:
    api_key = (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GENAI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "API KEY do Google não encontrada. "
            "Configure GOOGLE_API_KEY, GEMINI_API_KEY ou GENAI_API_KEY no .env"
        )
    return api_key


def _client(api_key: Optional[str] = None) -> genai.Client:
    return genai.Client(api_key=api_key or _get_api_key())


def _tenant_dir(tenant_id: str) -> Path:
    d = MEDIA_DIR / tenant_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_local_path(ref_img: str) -> Optional[Path]:
    """
    ✅ FIX 5: Extrai o path local de uma URL localhost de forma robusta.

    Em vez de usar split("/media/")[-1] — que quebra se houver dois segmentos
    "/media/" na URL — encontra o prefixo do MEDIA_DIR e extrai apenas o
    sufixo relativo correto.
    """
    try:
        # Remove o scheme+host: "http://localhost:8000/media/mugo/arquivo.png"
        # → "/media/mugo/arquivo.png"
        from urllib.parse import urlparse
        parsed = urlparse(ref_img)
        url_path = parsed.path  # ex: "/media/mugo/arquivo.png"

        # O MEDIA_DIR absoluto é, por exemplo, "/app/media"
        # Queremos o sufixo após "/media/", que é "mugo/arquivo.png"
        media_marker = "/media/"
        idx = url_path.find(media_marker)
        if idx == -1:
            return None

        relative = url_path[idx + len(media_marker):]  # "mugo/arquivo.png"
        full_path = MEDIA_DIR / relative
        return full_path if full_path.exists() else None
    except Exception:
        return None


# ==========================================
# ESCUDO ANTI-FALHAS (CRIADOR DE PARTS SEGURO)
# ==========================================
def _safe_part(ref_img: str) -> Optional[types.Part]:
    """
    Tenta carregar a imagem de referência.
    Se o link estiver morto ou inválido, retorna None sem quebrar o servidor.
    """
    if not ref_img:
        return None


def _safe_image(ref_img: str) -> Optional[types.Image]:
    """
    Tenta carregar a imagem de referência para APIs que exigem types.Image (VEO).
    Retorna None se inválida ou indisponível.
    """
    if not ref_img:
        return None

    try:
        # --- Base64 inline ---
        if ref_img.startswith("data:"):
            header, b64 = ref_img.split(",", 1)
            mime = header.split(";")[0].replace("data:", "").strip() or "image/png"
            return types.Image(image_bytes=base64.b64decode(b64), mime_type=mime)

        # --- URL HTTP/HTTPS ---
        if ref_img.startswith("http://") or ref_img.startswith("https://"):

            # URL local (localhost / 127.0.0.1): lê do disco
            if "localhost:" in ref_img or "127.0.0.1:" in ref_img:
                local_path = _resolve_local_path(ref_img)
                if local_path:
                    return types.Image(
                        image_bytes=local_path.read_bytes(), mime_type="image/png"
                    )
                print(f"⚠️ [AVISO] Arquivo local não encontrado para: {ref_img[:80]}")
                return None

            # URL remota: baixa com timeout
            req = urllib.request.Request(ref_img, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=HTTP_DOWNLOAD_TIMEOUT) as response:
                return types.Image(
                    image_bytes=response.read(),
                    mime_type=response.headers.get_content_type() or "image/png",
                )

        # --- URI de arquivo Google (gs:// ou similar) ---
        return types.Image.from_file(location=ref_img, mime_type="image/png")

    except Exception as e:
        print(
            f"⚠️ [AVISO] Imagem ignorada (link morto ou inválido): "
            f"{ref_img[:60]}... Erro: {e}"
        )
        return None

    try:
        # --- Base64 inline ---
        if ref_img.startswith("data:"):
            header, b64 = ref_img.split(",", 1)
            mime = header.split(";")[0].replace("data:", "").strip() or "image/png"
            return types.Part.from_bytes(data=base64.b64decode(b64), mime_type=mime)

        # --- URL HTTP/HTTPS ---
        if ref_img.startswith("http://") or ref_img.startswith("https://"):

            # URL local (localhost / 127.0.0.1): lê do disco
            if "localhost:" in ref_img or "127.0.0.1:" in ref_img:
                # ✅ FIX 5: usa _resolve_local_path em vez de split("/media/")[-1]
                local_path = _resolve_local_path(ref_img)
                if local_path:
                    return types.Part.from_bytes(
                        data=local_path.read_bytes(), mime_type="image/png"
                    )
                print(f"⚠️ [AVISO] Arquivo local não encontrado para: {ref_img[:80]}")
                return None

            # URL remota: baixa com timeout
            # ✅ FIX 2: timeout definido para não bloquear o servidor indefinidamente
            req = urllib.request.Request(ref_img, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=HTTP_DOWNLOAD_TIMEOUT) as response:
                return types.Part.from_bytes(
                    data=response.read(),
                    mime_type=response.headers.get_content_type() or "image/png",
                )

        # --- URI de arquivo Google (gs:// ou similar) ---
        return types.Part.from_uri(file_uri=ref_img, mime_type="image/png")

    except Exception as e:
        print(
            f"⚠️ [AVISO] Imagem ignorada (link morto ou inválido): "
            f"{ref_img[:60]}... Erro: {e}"
        )
        return None


def _guess_ext(mime_type: str, fallback: str) -> str:
    mt = (mime_type or "").lower()
    if "png" in mt:
        return ".png"
    if "jpeg" in mt or "jpg" in mt:
        return ".jpg"
    return fallback


def _try_extract_inline_bytes(resp) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Extrai os bytes de imagem inline da resposta do modelo.

    ✅ FIX 3: Substituído bare `except:` por `except Exception` para não
    engolir KeyboardInterrupt, SystemExit e outros sinais do sistema.

    ✅ FIX 7: Removido o fallback que tentava base64.b64decode em bytes
    arbitrários — isso corrompia silenciosamente imagens em formato desconhecido.
    Agora apenas os dois casos conhecidos e seguros são tratados.
    """
    try:
        candidates = getattr(resp, "candidates", None) or []
        if not candidates:
            return None, None

        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []

        for part in parts:
            inline = getattr(part, "inline_data", None)
            if not inline:
                continue

            raw_data = getattr(inline, "data", None)
            if not raw_data:
                continue

            mime = getattr(inline, "mime_type", None) or ""

            # Caso 1: bytes brutos com assinatura PNG ou JPEG — usa direto
            if isinstance(raw_data, bytes) and (
                raw_data.startswith(b"\x89PNG") or raw_data.startswith(b"\xff\xd8")
            ):
                return raw_data, mime

            # Caso 2: string base64 — decodifica
            if isinstance(raw_data, str):
                try:
                    return base64.b64decode(raw_data), mime
                except Exception as decode_err:
                    print(f"⚠️ Falha ao decodificar base64 da resposta: {decode_err}")
                    continue

            # ✅ FIX 7: Formato desconhecido — loga e pula, não tenta
            # base64.b64decode em bytes arbitrários (causaria corrupção silenciosa)
            print(
                f"⚠️ inline_data em formato desconhecido "
                f"(type={type(raw_data).__name__}, mime={mime}). Part ignorado."
            )

    except Exception as e:
        # ✅ FIX 3: except Exception (não bare except) — preserva sinais do sistema
        print(f"⚠️ Erro ao extrair bytes da resposta: {e}")

    return None, None




def generate_video_identity_veo(
    *,
    prompt: str,
    ref_image: Optional[str],
    tenant_id: str,
    ar: str = "16:9",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout_s: int = 900,
    poll_every_s: float = 2.0,
) -> str:
    ar = _normalize_ar(ar)
    client = _client(api_key)
    veo_model = model or os.getenv("VEO_MODEL", "models/veo-3.0-generate-001")
    image_part = _safe_image(ref_image) if ref_image else None

    op = client.models.generate_videos(
        model=veo_model,
        prompt=prompt,
        image=image_part,
        config=types.GenerateVideosConfig(aspect_ratio=ar),
    )

    start = time.time()
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 5

    while not getattr(op, "done", False):
        elapsed = time.time() - start

        if elapsed > timeout_s:
            raise TimeoutError(
                f"Veo: timeout de {timeout_s}s excedido. "
                "A geração pode ter travado no servidor Google."
            )

        time.sleep(poll_every_s)

        # ✅ FIX 4: Tratamento de erro na atualização da operação
        # Se a chamada falhar, conta erros consecutivos antes de desistir.
        # Sem isso, o loop continua com o 'op' antigo para sempre até o timeout.
        try:
            op = client.operations.get(op)
            consecutive_errors = 0  # sucesso — reseta o contador
        except Exception as poll_err:
            consecutive_errors += 1
            print(
                f"⚠️ Veo: erro ao checar operação "
                f"({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {poll_err}"
            )
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                raise RuntimeError(
                    f"Veo: {MAX_CONSECUTIVE_ERRORS} erros consecutivos ao checar "
                    f"o status da geração. Último erro: {poll_err}"
                )

    resp = getattr(op, "response", None)
    videos = getattr(resp, "generated_videos", None) if resp else None
    if not videos:
        raise RuntimeError(
            "Veo: geração concluída mas nenhum vídeo foi retornado. "
            f"Resposta completa: {resp}"
        )

    video_file = videos[0].video
    out_path = (
        _tenant_dir(tenant_id)
        / f"veo_{int(time.time())}_{uuid.uuid4().hex[:10]}.mp4"
    )
    client.files.download(file=video_file, destination=str(out_path))
    return str(out_path.resolve())


def generate_image_identity_nana(
    *,
    prompt: str,
    ref_image: Optional[str] = None,
    face_image: Optional[str] = None,
    body_image: Optional[str] = None,
    product_image: Optional[str] = None,
    clothing_image: Optional[str] = None,
    style_image: Optional[str] = None,
    tenant_id: str,
    ar: str = "16:9",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    # ✅ FIX 1: ar normalizado e guardado em variável nomeada (não em "_")
    # para ser passado ao modelo logo abaixo
    ar = _normalize_ar(ar)

    client = _client(api_key)
    nana_model = model or os.getenv("NANA_MODEL", "models/nano-banana-pro-preview")

    build_contents = ["Return ONLY the final image output (not just text)."]

    p_ref = _safe_part(ref_image)
    if p_ref:
        build_contents.append(p_ref)

    p_face = _safe_part(face_image)
    if p_face:
        build_contents.extend(["Reference @img1 (Face identity):", p_face])

    p_body = _safe_part(body_image)
    if p_body:
        build_contents.extend(["Reference @img2 (Structure/Pose):", p_body])

    p_prod = _safe_part(product_image)
    if p_prod:
        build_contents.extend(["Reference @img3 (Product to insert):", p_prod])

    p_cloth = _safe_part(clothing_image)
    if p_cloth:
        build_contents.extend(["Reference @img4 (Exact Garment/Clothing):", p_cloth])

    p_style = _safe_part(style_image)
    if p_style:
        build_contents.extend(["Reference @img5 (Lighting and Style):", p_style])

    # Instrui o modelo sobre o aspect ratio (Nana não tem config nativa de AR)
    ar_instruction = f"Output image aspect ratio: {ar}."
    build_contents.insert(0, ar_instruction)
    build_contents.append(prompt)

    # ✅ FIX: parâmetro correto é `config` (não generation_config)
    resp = client.models.generate_content(
        model=nana_model,
        contents=build_contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    img_bytes, mime = _try_extract_inline_bytes(resp)
    if not img_bytes:
        raise RuntimeError(
            "Nana: modelo não retornou imagem inline. "
            "Verifique se o modelo suporta geração de imagens e se o prompt está correto."
        )

    ext = _guess_ext(mime or "image/png", ".png")
    out_path = (
        _tenant_dir(tenant_id)
        / f"nana_{int(time.time())}_{uuid.uuid4().hex[:10]}{ext}"
    )
    out_path.write_bytes(img_bytes)
    return str(out_path.resolve())


def generate_identity(
    *,
    prompt: str,
    ref_image: Optional[str] = None,
    face_image: Optional[str] = None,
    body_image: Optional[str] = None,
    product_image: Optional[str] = None,
    clothing_image: Optional[str] = None,
    style_image: Optional[str] = None,
    tenant_id: str,
    media_type: str,
    ar: str = "16:9",
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Tuple[str, str, str]:

    mt = (media_type or "image").strip().lower()
    prov = (provider or "").strip().lower()

    if mt == "video" or prov == "veo":
        # ✅ FIX 6: Aviso explícito quando o usuário envia referências extras
        # que o Veo não suporta, em vez de descartá-las silenciosamente
        ignored_refs = [
            name
            for name, val in [
                ("body_image", body_image),
                ("product_image", product_image),
                ("clothing_image", clothing_image),
                ("style_image", style_image),
            ]
            if val
        ]
        if ignored_refs:
            print(
                f"⚠️ Veo: as seguintes referências foram ignoradas pois o Veo "
                f"suporta apenas uma imagem de referência (face/ref): "
                f"{', '.join(ignored_refs)}"
            )

        path = generate_video_identity_veo(
            prompt=prompt,
            ref_image=(face_image or ref_image),
            tenant_id=tenant_id,
            ar=ar,
            api_key=api_key,
        )
        return "video", path, "veo/google"

    path = generate_image_identity_nana(
        prompt=prompt,
        ref_image=ref_image,
        face_image=face_image,
        body_image=body_image,
        product_image=product_image,
        clothing_image=clothing_image,
        style_image=style_image,
        tenant_id=tenant_id,
        ar=ar,
        api_key=api_key,
    )
    return "image", path, "nana/google"
