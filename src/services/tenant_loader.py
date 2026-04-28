from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TenantPaths:
    root: Path
    default_dir: Path
    tenant_dir: Path

    @staticmethod
    def from_slug(root: Path, tenant_slug: str) -> "TenantPaths":
        default_dir = root / "_default"
        tenant_dir = root / tenant_slug
        return TenantPaths(root=root, default_dir=default_dir, tenant_dir=tenant_dir)


def _read_text(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    content = _read_text(path)
    if content is None:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON inválido em: {path.as_posix()} ({e})")
        return None


def _merge_dict(base: Dict[str, Any], override: Any) -> Dict[str, Any]:
    """
    Merge recursivo: override ganha do base.
    Se override não for dict, substitui tudo (evita crash com listas).
    Listas são substituídas (não concatenadas) por padrão.
    """
    if not isinstance(override, dict):
        return override if override is not None else base
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def load_tenant_context(
    tenant_slug: str,
    tenant_root: Path,
) -> Dict[str, Any]:
    """
    Lê tenant_context/{tenant_slug} com fallback em tenant_context/_default.
    Retorna um dicionário único com tudo para o tenant.
    """
    paths = TenantPaths.from_slug(tenant_root, tenant_slug)

    if not paths.default_dir.exists():
        raise FileNotFoundError(f"Pasta _default não existe: {paths.default_dir.as_posix()}")

    # arquivos base
    default_brand = _read_json(paths.default_dir / "brand.json") or {}
    default_ui = _read_json(paths.default_dir / "ui.json") or {}
    default_social = _read_json(paths.default_dir / "socialmedia.json") or {}

    default_system_md = _read_text(paths.default_dir / "prompts" / "system.md") or ""
    default_social_md = _read_text(paths.default_dir / "prompts" / "socialmedia.md") or ""

    default_forbidden = _read_text(paths.default_dir / "rules" / "forbidden.txt") or ""
    default_claims = _read_json(paths.default_dir / "rules" / "claims.json") or {}

    # tenant override (se não existir, fica só no default)
    tenant_brand = _read_json(paths.tenant_dir / "brand.json") or {}
    tenant_ui = _read_json(paths.tenant_dir / "ui.json") or {}
    tenant_social = _read_json(paths.tenant_dir / "socialmedia.json") or {}

    tenant_system_md = _read_text(paths.tenant_dir / "prompts" / "system.md")
    tenant_social_md = _read_text(paths.tenant_dir / "prompts" / "socialmedia.md")

    tenant_forbidden = _read_text(paths.tenant_dir / "rules" / "forbidden.txt")
    tenant_claims = _read_json(paths.tenant_dir / "rules" / "claims.json")

    brand = _merge_dict(default_brand, tenant_brand)
    ui = _merge_dict(default_ui, tenant_ui)
    socialmedia = _merge_dict(default_social, tenant_social)

    prompts = {
        "system": tenant_system_md if tenant_system_md is not None else default_system_md,
        "socialmedia": tenant_social_md if tenant_social_md is not None else default_social_md,
    }

    rules = {
        "forbidden": (tenant_forbidden if tenant_forbidden is not None else default_forbidden).splitlines(),
        "claims": _merge_dict(default_claims, tenant_claims or {}),
    }

    # Corrige nome exibido "Ssavon" independentemente
    if brand.get("slug") == "ssavon":
        brand["name"] = "Ssavon"

    return {
        "brand": brand,
        "ui": ui,
        "socialmedia": socialmedia,
        "prompts": prompts,
        "rules": rules,
    }


def list_tenants(tenant_root: Path) -> List[Dict[str, Any]]:
    """
    Lista tenants (pastas) com campos mínimos pro seletor do front.
    """
    tenants: List[Dict[str, Any]] = []
    for p in tenant_root.iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith("_"):
            continue

        brand = _read_json(p / "brand.json") or {}
        ui = _read_json(p / "ui.json") or {}

        slug = brand.get("slug") or p.name
        name = brand.get("name") or p.name
        if slug == "ssavon":
            name = "Ssavon"

        client_ui = ui.get("client", {})
        tenants.append(
            {
                "id": slug,
                "name": name,
                "logo": client_ui.get("logo", name[:1].upper()),
                "color": client_ui.get("color", "bg-zinc-500"),
                "border": client_ui.get("border", "border-zinc-500"),
            }
        )

    # ordena, mas mantém consistência
    tenants.sort(key=lambda x: x["id"])
    return tenants
