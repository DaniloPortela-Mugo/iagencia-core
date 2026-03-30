from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from src.services.tenant_loader import list_tenants
from src.services.socialmedia_store import load_events, load_grid, save_events, save_grid


router = APIRouter()

TENANT_ROOT = Path("tenant_context")  # ajuste se precisar
DATA_ROOT = Path("static/data")       # ajuste se precisar


@router.get("/tenants")
def get_tenants() -> Dict[str, Any]:
    try:
        tenants = list_tenants(TENANT_ROOT)
        return {"tenants": tenants}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/SocialMedia/grid")
def get_socialmedia_grid(
    tenant_slug: str = Query(...),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
) -> Dict[str, Any]:
    grid_data = load_grid(DATA_ROOT, tenant_slug, year, month)
    # store salva {"grid": [...]}; se vier list vazia, normaliza:
    if isinstance(grid_data, dict) and "grid" in grid_data:
        return {"grid": grid_data["grid"]}
    if isinstance(grid_data, list):
        return {"grid": grid_data}
    return {"grid": []}


@router.post("/SocialMedia/grid/save")
def post_socialmedia_grid_save(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    tenant_slug = payload.get("tenant_slug")
    year = payload.get("year")
    month = payload.get("month")
    grid = payload.get("grid")

    if not tenant_slug or not isinstance(tenant_slug, str):
        raise HTTPException(status_code=400, detail="tenant_slug obrigatório")
    if not isinstance(year, int) or not isinstance(month, int):
        raise HTTPException(status_code=400, detail="year/month inválidos")
    if not isinstance(grid, list):
        raise HTTPException(status_code=400, detail="grid precisa ser lista")

    save_grid(DATA_ROOT, tenant_slug, year, month, grid)
    return {"ok": True}


@router.get("/SocialMedia/events")
def get_socialmedia_events(
    tenant_slug: str = Query(...),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
) -> Dict[str, Any]:
    events = load_events(DATA_ROOT, tenant_slug, year, month)
    return {"events": events}


@router.post("/SocialMedia/events/save")
def post_socialmedia_events_save(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    tenant_slug = payload.get("tenant_slug")
    year = payload.get("year")
    month = payload.get("month")
    events = payload.get("events")

    if not tenant_slug or not isinstance(tenant_slug, str):
        raise HTTPException(status_code=400, detail="tenant_slug obrigatório")
    if not isinstance(year, int) or not isinstance(month, int):
        raise HTTPException(status_code=400, detail="year/month inválidos")
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="events precisa ser lista")

    save_events(DATA_ROOT, tenant_slug, year, month, events)
    return {"ok": True}
