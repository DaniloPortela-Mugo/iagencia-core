from __future__ import annotations

import base64
import mimetypes
import os
import time
import uuid
import urllib.request
from pathlib import Path
from typing import Optional, Tuple
# ✅ FIX 3: urllib.parse importado no topo do arquivo, não dentro da função
from urllib.parse import urlparse

from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_AR = {"1:1", "4:5", "9:16", "16:9", "21:9"}

HTTP_DOWNLOAD_TIMEOUT = 20

# ✅ FIX 4: Mapa de extensão → MIME para arquivos locais
# Usado ao servir arquivos do disco com o tipo correto
EXTENSION_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


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


def _client() -> genai.Client:
    return genai.Client(api_key=_get_api_key())


def _tenant_dir(tenant_id: str) -> Path:
    d = MEDIA_DIR / tenant_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mime_from_path(path: Path) -> str:
    """
    ✅ FIX 4: Detecta o MIME type real pelo sufixo do arquivo.
    Evita marcar JPEGs como image/png, o que pode causar rejeição pelo modelo.
    """
    ext = path.suffix.lower()
    # Tenta primeiro no mapa explícito, depois no mimetypes do sistema
    return (
        EXTENSION_TO_MIME.get(ext)
        or mimetypes.guess_type(str(path))[0]
        or "image/png"  # fallback apenas se realmente desconhecido
    )


def _resolve_local_path(ref_img: str) -> Optional[Path]:
    """
    Extrai o path local de uma URL localhost de forma robusta.

    ✅ FIX 3: urlparse agora importado no topo do módulo.

    ✅ FIX 5: Usa os.path.relpath contra MEDIA_DIR para garantir que
    o match só acontece quando o path realmente começa com o diretório
    de mídia — evita falsos positivos com caminhos como /social-media/.
    """
    try:
        parsed = urlparse(ref_img)
        url_path = parsed.path  # ex: "/media/mugo/arquivo.png"

        # ✅ FIX 5: Constrói o path absoluto esperado e verifica se está
        # dentro do MEDIA_DIR, evitando match em substrings como /social-media/
        # url_path começa com "/" — juntamos com BASE_DIR para resolver
        candidate = (BASE_DIR / url_path.lstrip("/")).resolve()

        # Verifica se o arquivo existe E está dentro do MEDIA_DIR
        try:
            candidate.relative_to(MEDIA_DIR.resolve())  # lança ValueError se fora
        except ValueError:
            print(
                f"⚠️ [AVISO] Path '{candidate}' está fora do MEDIA_DIR. "
                "Possível tentativa de path traversal ou URL inesperada."
            )
            return None

        return candidate if candidate.exists() else None

    except Exception:
        return None


def _safe_part(ref_img: str) -> Optional[types.Part]:
    """
    Tenta carregar a imagem de referência.
    Se o link estiver morto ou inválido, retorna None sem quebrar o servidor.
    """
    if not ref_img:
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
                local_path = _resolve_local_path(ref_img)
                if local_path:
                    # ✅ FIX 4: MIME detectado pela extensão real do arquivo
                    mime = _mime_from_path(local_path)
                    return types.Part.from_bytes(
                        data=local_path.read_bytes(), mime_type=mime
                    )
                print(f"⚠️ [AVISO] Arquivo local não encontrado para: {ref_img[:80]}")
                return None

            # URL remota: baixa com timeout
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
    Trata apenas os dois casos conhecidos e seguros (bytes PNG/JPEG e base64 string).
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

            print(
                f"⚠️ inline_data em formato desconhecido "
                f"(type={type(raw_data).__name__}, mime={mime}). Part ignorado."
            )

    except Exception as e:
        print(f"⚠️ Erro ao extrair bytes da resposta: {e}")

    return None, None


def generate_video_identity_veo(
    *,
    prompt: str,
    ref_image: Optional[str],
    tenant_id: str,
    ar: str = "16:9",
    model: Optional[str] = None,
    timeout_s: int = 900,
    poll_every_s: float = 2.0,
) -> str:
    ar = _normalize_ar(ar)
    client = _client()
    veo_model = model or os.getenv("VEO_MODEL", "models/veo-3.0-generate-001")
    image_part = _safe_part(ref_image) if ref_image else None

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

        try:
            op = client.operations.get(op)
            consecutive_errors = 0
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
) -> str:
    ar = _normalize_ar(ar)
    client = _client()
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

    build_contents.append(prompt)

    # ✅ FIX 1: parâmetro correto é `config=`, não `generation_config=`
    # `generation_config=` não existe no SDK google-genai e lança TypeError
    #
    # ✅ FIX 2: aspect_ratio injetado no prompt como instrução explícita
    # pois GenerateContentConfig não possui campo aspect_ratio para este modelo —
    # esse parâmetro só existe em ImageGenerationConfig (Imagen).
    # A forma mais confiável de controlar o formato no Nana é via instrução textual.
    ar_instruction = f"Output image aspect ratio: {ar}."
    build_contents.insert(0, ar_instruction)

    resp = client.models.generate_content(
        model=nana_model,
        contents=build_contents,
        # ✅ FIX 1: `config=` é o parâmetro correto no SDK google-genai
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
) -> Tuple[str, str, str]:

    mt = (media_type or "image").strip().lower()
    prov = (provider or "").strip().lower()

    if mt == "video" or prov == "veo":
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
    )
    return "image", path, "nana/google"