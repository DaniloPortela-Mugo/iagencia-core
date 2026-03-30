import os
import json
import argparse
import requests
from typing import Any, Dict, List

from dotenv import load_dotenv

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.crypto_utils import encrypt_secret


def must_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing env: {name}")
    return value


def supabase_headers() -> Dict[str, str]:
    key = must_env("SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def get_rows(base_url: str, table: str, select: str) -> List[Dict[str, Any]]:
    url = f"{base_url}/rest/v1/{table}?select={select}"
    res = requests.get(url, headers=supabase_headers(), timeout=30)
    if res.status_code >= 300:
        raise RuntimeError(f"GET {table} failed: {res.status_code} {res.text}")
    return res.json() or []


def patch_row(base_url: str, table: str, filter_qs: str, payload: Dict[str, Any], dry_run: bool) -> None:
    url = f"{base_url}/rest/v1/{table}?{filter_qs}"
    if dry_run:
        print(f"[dry-run] PATCH {table} {filter_qs} -> {payload}")
        return
    res = requests.patch(url, headers=supabase_headers(), data=json.dumps(payload), timeout=30)
    if res.status_code >= 300:
        raise RuntimeError(f"PATCH {table} failed: {res.status_code} {res.text}")


def recrypt_api_keys(base_url: str, dry_run: bool) -> int:
    rows = get_rows(base_url, "tenant_api_keys", "id,tenant_slug,provider,api_key")
    updated = 0
    for row in rows:
        key = row.get("api_key") or ""
        if not isinstance(key, str) or not key or key.startswith("enc:"):
            continue
        encrypted = encrypt_secret(key)
        if not encrypted or encrypted == key:
            continue
        patch_row(base_url, "tenant_api_keys", f"id=eq.{row['id']}", {"api_key": encrypted}, dry_run)
        updated += 1
        print(f"tenant_api_keys: {row.get('tenant_slug')}:{row.get('provider')} -> encrypted")
    return updated


def recrypt_drive_tokens(base_url: str, dry_run: bool) -> int:
    rows = get_rows(base_url, "tenant_drive_tokens", "tenant_slug,access_token,refresh_token")
    updated = 0
    for row in rows:
        access = row.get("access_token")
        refresh = row.get("refresh_token")
        payload: Dict[str, Any] = {}
        if isinstance(access, str) and access and not access.startswith("enc:"):
            payload["access_token"] = encrypt_secret(access)
        if isinstance(refresh, str) and refresh and not refresh.startswith("enc:"):
            payload["refresh_token"] = encrypt_secret(refresh)
        if not payload:
            continue
        patch_row(base_url, "tenant_drive_tokens", f"tenant_slug=eq.{row['tenant_slug']}", payload, dry_run)
        updated += 1
        print(f"tenant_drive_tokens: {row.get('tenant_slug')} -> encrypted")
    return updated


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Re-encrypt tenant secrets in Supabase.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    base_url = must_env("SUPABASE_URL")
    # Ensure crypto key is loaded
    must_env("IAGENCIA_CRYPTO_KEY")

    dry_run = not args.apply
    print("Recrypting secrets (dry-run)" if dry_run else "Recrypting secrets (apply)")

    total = 0
    total += recrypt_api_keys(base_url, dry_run)
    total += recrypt_drive_tokens(base_url, dry_run)
    print(f"Done. Updated rows: {total}")


if __name__ == "__main__":
    main()
