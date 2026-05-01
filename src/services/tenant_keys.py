import os
import requests
from typing import Optional

from .crypto_utils import decrypt_secret


def _clean_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    key = value.strip()
    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
        key = key[1:-1].strip()
    return key or None

def _supabase_headers() -> Optional[dict]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def get_tenant_api_key(tenant_slug: str, provider: str) -> Optional[str]:
    """
    Busca a API key por tenant/provider no Supabase (tabela tenant_api_keys).
    Retorna None se não houver ou se a configuração estiver ausente.
    """
    if not tenant_slug or not provider:
        return None
    headers = _supabase_headers()
    if not headers:
        return None
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        return None
    url = (
        f"{supabase_url}/rest/v1/tenant_api_keys"
        f"?select=api_key&tenant_slug=eq.{tenant_slug}&provider=eq.{provider}&limit=1"
    )
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
        data = res.json()
        if not data:
            return None
        key = data[0].get("api_key")
        if isinstance(key, str) and key.strip():
            decrypted = decrypt_secret(key)
            return _clean_key(decrypted)
        return None
    except Exception:
        return None
