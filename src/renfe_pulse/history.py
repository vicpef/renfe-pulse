"""Serie histórica de indicadores, acumulada entre ejecuciones.

GitHub Pages no guarda estado: en cada build descargamos `data/history.json` del sitio
publicado, le añadimos el punto actual y lo volvemos a publicar.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

RETENTION_SECONDS = 30 * 24 * 3600


def load_previous(session: requests.Session, site_url: str | None) -> list[dict[str, Any]]:
    if not site_url:
        return []
    url = f"{site_url.rstrip('/')}/data/history.json"
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        points = resp.json().get("points", [])
        return [p for p in points if isinstance(p, dict) and isinstance(p.get("t"), int)]
    except (requests.RequestException, ValueError) as exc:
        log.warning("No se pudo leer el histórico previo (%s): %s", url, exc)
        return []


def append(
    points: list[dict[str, Any]], point: dict[str, Any], retention: int = RETENTION_SECONDS
) -> list[dict[str, Any]]:
    """Añade `point` (con clave `t` en segundos) y descarta duplicados y puntos antiguos."""
    by_time = {p["t"]: p for p in points}
    by_time[point["t"]] = point
    cutoff = point["t"] - retention
    return [by_time[t] for t in sorted(by_time) if t >= cutoff]
