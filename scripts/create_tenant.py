#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TENANT_CONTEXT_DIR = BASE_DIR / "tenant_context"
TENANTS_CONTEXT_DIR = BASE_DIR / "tenants_context"


def _slugify(raw: str) -> str:
    slug = raw.strip().lower()
    slug = re.sub(r"[^a-z0-9-_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _create_tenant_context(tenant_slug: str, tenant_name: str) -> None:
    tenant_dir = TENANT_CONTEXT_DIR / tenant_slug
    rules_dir = tenant_dir / "rules"
    prompts_dir = tenant_dir / "prompts"

    _ensure_dir(rules_dir)
    _ensure_dir(prompts_dir)

    _write_json(tenant_dir / "brand.json", {"name": tenant_name, "slug": tenant_slug})
    _write_json(tenant_dir / "ui.json", {})
    _write_json(tenant_dir / "socialmedia.json", {})

    (rules_dir / "forbidden.txt").write_text("", encoding="utf-8")
    _write_json(rules_dir / "claims.json", {})

    (prompts_dir / "system.md").write_text("", encoding="utf-8")
    (prompts_dir / "socialmedia.md").write_text("", encoding="utf-8")


def _create_legacy_context(tenant_slug: str, tenant_name: str) -> None:
    tenant_dir = TENANTS_CONTEXT_DIR / tenant_slug
    _ensure_dir(tenant_dir)
    (tenant_dir / "brand_guide.md").write_text(
        f"# {tenant_name}\n\nDescreva aqui o DNA da marca.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria estrutura de tenant e gera SQL.")
    parser.add_argument("--name", required=True, help="Nome do cliente/tenant")
    parser.add_argument("--slug", help="Slug do tenant (default: slugify(name))")
    parser.add_argument(
        "--modules",
        default="dashboard,atendimento,planning,creation,image_studio,library,approvals",
        help="Lista separada por vírgula de módulos permitidos",
    )
    parser.add_argument(
        "--legacy-context",
        action="store_true",
        help="Cria também tenants_context/<slug>/brand_guide.md (legado)",
    )

    args = parser.parse_args()
    name = args.name.strip()
    slug = _slugify(args.slug or name)
    modules = [m.strip() for m in args.modules.split(",") if m.strip()]

    if not TENANT_CONTEXT_DIR.exists():
        raise SystemExit(f"Pasta tenant_context não encontrada: {TENANT_CONTEXT_DIR}")

    _create_tenant_context(slug, name)

    if args.legacy_context or TENANTS_CONTEXT_DIR.exists():
        _create_legacy_context(slug, name)

    modules_sql = ", ".join([f"'{m}'" for m in modules])
    sql = (
        "INSERT INTO tenants (id, name, slug, allowed_modules) VALUES\n"
        f"(uuid_generate_v4(), '{name}', '{slug}', array[{modules_sql}])\n"
        "ON CONFLICT (slug) DO UPDATE\n"
        "SET name = EXCLUDED.name,\n"
        "    allowed_modules = EXCLUDED.allowed_modules;"
    )

    print("\n✅ Tenant criado em tenant_context/")
    print("\nSQL para o Supabase:\n")
    print(sql)


if __name__ == "__main__":
    main()
