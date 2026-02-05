import mimetypes
import os
import re
import shutil
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Optional

import requests


def get_project_root() -> Path:
    """
    Estrutura esperada:
    iagencia-core/
      main.py
      media/
      src/
        core/
          media_service.py
    """
    return Path(__file__).resolve().parents[2]


def get_media_dir() -> Path:
    media_dir = get_project_root() / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


def slugify(value: str) -> str:
    """
    Converte nomes com acento/espaços em slug ASCII seguro para URL e filesystem.
    Ex: "Mugô" -> "mugo", "Voy Saúde" -> "voy-saude"
    """
    if not value:
        return "default"

    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "default"


def get_tenant_dir(tenant: str) -> Path:
    """
    Diretório CANÔNICO: sempre slugificado.
    """
    tenant_slug = slugify(tenant)
    tenant_dir = get_media_dir() / tenant_slug
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return tenant_dir


def get_legacy_tenant_dir(tenant_raw: str) -> Path:
    """
    Diretório LEGACY: usa o valor original (pode ter acento).
    Isso existe só para compatibilidade com front/URLs antigas.
    """
    tenant_raw = (tenant_raw or "").strip()
    if not tenant_raw:
        tenant_raw = "default"
    tenant_dir = get_media_dir() / tenant_raw
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return tenant_dir


def guess_extension_from_content_type(content_type: Optional[str]) -> str:
    if not content_type:
        return ""
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
    return ext or ""


def guess_extension_from_url(url: str) -> str:
    clean = url.split("?")[0]
    ext = os.path.splitext(clean)[1].lower()
    return ext if ext.startswith(".") and len(ext) <= 8 else ""


def build_filename(prefix: str, ext: str) -> str:
    ext = ext if ext.startswith(".") else f".{ext}" if ext else ""
    ts = int(time.time())
    uid = uuid.uuid4().hex[:10]
    return f"{prefix}_{ts}_{uid}{ext}"


def save_bytes(data: bytes, tenant: str, prefix: str, ext: str) -> str:
    tenant_dir = get_tenant_dir(tenant)
    filename = build_filename(prefix, ext)
    filepath = tenant_dir / filename
    filepath.write_bytes(data)
    return str(filepath)


def download_to_file(
    url: str,
    tenant: str,
    prefix: str,
    default_ext: str,
    timeout: int = 120,
) -> str:
    """
    Baixa um arquivo e salva no diretório canônico:
    iagencia-core/media/<tenant_slug>/
    """
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()

        ext = guess_extension_from_url(url) or guess_extension_from_content_type(
            r.headers.get("Content-Type")
        )
        if not ext:
            ext = default_ext

        tenant_dir = get_tenant_dir(tenant)
        filename = build_filename(prefix, ext)
        filepath = tenant_dir / filename

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    return str(filepath)


def duplicate_to_legacy_folder(local_path: str, legacy_tenant_raw: str) -> None:
    """
    Compatibilidade: se o tenant veio como "Mugô", mas o canônico é "mugo",
    criamos também uma cópia em media/Mugô/<mesmo_arquivo>.

    Isso resolve 404 quando o front tenta abrir /media/Mug%C3%B4/...
    """
    if not legacy_tenant_raw:
        return

    legacy_tenant_raw = legacy_tenant_raw.strip()
    if not legacy_tenant_raw:
        return

    # se legacy e slug forem "iguais", não faz nada
    if slugify(legacy_tenant_raw) == legacy_tenant_raw:
        return

    try:
        src = Path(local_path)
        if not src.exists():
            return

        legacy_dir = get_legacy_tenant_dir(legacy_tenant_raw)
        dst = legacy_dir / src.name

        # copia somente se não existir ainda
        if not dst.exists():
            shutil.copy2(src, dst)
    except Exception as e:
        # não quebra o fluxo por causa da compatibilidade
        print(f"⚠️ Falha ao duplicar em legacy folder: {e}")
