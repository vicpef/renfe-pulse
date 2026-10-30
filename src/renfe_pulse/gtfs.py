"""Lectura selectiva de los GTFS estáticos de Renfe.

Solo leemos las tablas pequeñas (`routes`, `stops`, `trips`) directamente del zip: el
`stop_times.txt` de Cercanías ocupa ~300 MB descomprimido y no lo necesitamos.
Los ficheros de Renfe rellenan los campos con espacios, así que se recortan siempre.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

import requests


@dataclass
class Route:
    route_id: str
    short_name: str
    long_name: str
    color: str
    text_color: str


@dataclass
class Stop:
    stop_id: str
    name: str
    lat: float
    lon: float


@dataclass
class Gtfs:
    routes: dict[str, Route] = field(default_factory=dict)
    stops: dict[str, Stop] = field(default_factory=dict)
    trip_routes: dict[str, str] = field(default_factory=dict)  # trip_id -> route_id


def download(session: requests.Session, url: str) -> bytes:
    resp = session.get(url)
    resp.raise_for_status()
    return resp.content


def read_table(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with archive.open(name) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
        for row in reader:
            yield {(k or "").strip(): (v or "").strip() for k, v in row.items()}


def load(data: bytes, tables: Iterable[str] = ("routes", "stops", "trips")) -> Gtfs:
    gtfs = Gtfs()
    wanted = set(tables)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if "routes" in wanted:
            for r in read_table(archive, "routes.txt"):
                gtfs.routes[r["route_id"]] = Route(
                    route_id=r["route_id"],
                    short_name=r.get("route_short_name", ""),
                    long_name=" ".join(r.get("route_long_name", "").split()),
                    color=_color(r.get("route_color"), "6B7280"),
                    text_color=_color(r.get("route_text_color"), "FFFFFF"),
                )
        if "stops" in wanted:
            for r in read_table(archive, "stops.txt"):
                try:
                    lat, lon = float(r["stop_lat"]), float(r["stop_lon"])
                except (KeyError, ValueError):
                    continue
                gtfs.stops[r["stop_id"]] = Stop(r["stop_id"], r.get("stop_name", ""), lat, lon)
        if "trips" in wanted:
            for r in read_table(archive, "trips.txt"):
                gtfs.trip_routes[r["trip_id"]] = r["route_id"]
    return gtfs


def ld_endpoints(route_id: str) -> tuple[str, str] | None:
    """En el GTFS de AV/LD el `route_id` empieza por los códigos de origen y destino.

    `1700037606GL023` -> ("17000", "37606"): Madrid-Chamartín → Badajoz.
    """
    if len(route_id) >= 10 and route_id[:10].isdigit():
        return route_id[:5], route_id[5:10]
    return None


def _color(value: str | None, default: str) -> str:
    value = (value or "").strip().lstrip("#")
    return value.upper() if len(value) == 6 else default
