from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data: Any) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def grid_path(base: Path, tenant_slug: str, year: int, month: int) -> Path:
    return base / tenant_slug / "socialmedia" / f"grid_{year}_{month:02d}.json"


def events_path(base: Path, tenant_slug: str, year: int, month: int) -> Path:
    return base / tenant_slug / "socialmedia" / f"events_{year}_{month:02d}.json"


def load_grid(base: Path, tenant_slug: str, year: int, month: int) -> List[Dict[str, Any]]:
    return _read_json(grid_path(base, tenant_slug, year, month), default=[])


def save_grid(base: Path, tenant_slug: str, year: int, month: int, grid: List[Dict[str, Any]]) -> None:
    _write_json(grid_path(base, tenant_slug, year, month), {"grid": grid})


def load_events(base: Path, tenant_slug: str, year: int, month: int) -> List[Dict[str, Any]]:
    data = _read_json(events_path(base, tenant_slug, year, month), default={"events": []})
    events = data.get("events", [])
    if not isinstance(events, list):
        return []
    return events


def save_events(base: Path, tenant_slug: str, year: int, month: int, events: List[Dict[str, Any]]) -> None:
    _write_json(events_path(base, tenant_slug, year, month), {"events": events})
