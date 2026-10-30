"""Volumen de viajeros por franja horaria en estaciones de Cercanías (año 2018)."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Any

import requests

from .stations import title_case


def fetch(session: requests.Session, url: str) -> list[dict[str, str]]:
    resp = session.get(url)
    resp.raise_for_status()
    return parse(resp.content)


def parse(data: bytes) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def summarize(rows: list[dict[str, str]], top: int = 10) -> list[dict[str, Any]]:
    """Perfil horario y estaciones con más viajeros de cada núcleo.

    Devuelve una entrada por núcleo ordenada por viajeros totales, con:
    - `profile`: subidas y bajadas por franja de media hora.
    - `stations`: las `top` estaciones con más viajeros (subidas + bajadas).
    """
    profile: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    stations: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        nucleo = _nucleo_label(row.get("NUCLEO_CERCANIAS", ""))
        slot = row.get("TRAMO_HORARIO", "")
        up, down = _int(row.get("VIAJEROS_SUBIDOS")), _int(row.get("VIAJEROS_BAJADOS"))
        if not nucleo or not slot:
            continue
        profile[nucleo][slot][0] += up
        profile[nucleo][slot][1] += down
        stations[nucleo][title_case(" ".join(row.get("NOMBRE_ESTACION", "").split()))] += up + down

    out = []
    for nucleo, slots in profile.items():
        ordered = sorted(slots.items(), key=lambda kv: kv[0])
        out.append(
            {
                "nucleo": nucleo,
                "total": sum(u + d for u, d in slots.values()),
                "profile": [{"slot": s, "up": u, "down": d} for s, (u, d) in ordered],
                "stations": [
                    {"name": n, "total": t}
                    for n, t in sorted(stations[nucleo].items(), key=lambda kv: -kv[1])[:top]
                ],
            }
        )
    return sorted(out, key=lambda n: -n["total"])


def _nucleo_label(value: str) -> str:
    value = value.strip()
    if value.endswith(" AM"):
        value = value[:-3] + " (ancho métrico)"
    return value[:1] + value[1:].lower() if value else value


def _int(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0
