"""Listado completo de estaciones (CSV en latin-1 separado por `;`)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import requests


@dataclass
class Station:
    code: str
    name: str
    lat: float | None
    lon: float | None
    address: str
    postal_code: str
    town: str
    province: str
    cercanias: bool
    ancho_metrico: bool


def fetch(session: requests.Session, url: str) -> list[Station]:
    resp = session.get(url)
    resp.raise_for_status()
    return parse(resp.content)


def parse(data: bytes) -> list[Station]:
    text = _decode(data)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    out = []
    for row in reader:
        row = {(k or "").strip().upper(): (v or "").strip() for k, v in row.items()}
        if not row.get("CODIGO"):
            continue
        out.append(
            Station(
                code=row["CODIGO"],
                name=_title(row.get("DESCRIPCION", "")),
                lat=_float(row.get("LATITUD")),
                lon=_float(row.get("LONGITUD")),
                address=row.get("DIRECION") or row.get("DIRECCION", ""),
                postal_code=row.get("CP", ""),
                town=_title(row.get("POBLACION", "")),
                province=_title(row.get("PROVINCIA", "")),
                cercanias=row.get("CERCANIAS", "").upper() == "SI",
                ancho_metrico=row.get("ANCHO MÉTRICO", "").upper() == "SI",
            )
        )
    return out


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


_LOWER = {"de", "del", "la", "las", "el", "los", "y", "i", "d'", "l'"}


def _title(value: str) -> str:
    """`MADRID-PUERTA DE ATOCHA` -> `Madrid-Puerta de Atocha`."""
    words = []
    for i, word in enumerate(value.lower().split(" ")):
        parts = [p.capitalize() for p in word.split("-")]
        word = "-".join(parts)
        words.append(word.lower() if i and word.lower() in _LOWER else word)
    return " ".join(words)


def _float(value: str | None) -> float | None:
    try:
        return round(float((value or "").replace(",", ".")), 6)
    except ValueError:
        return None
