"""Transforma los datos de Renfe en las estructuras que pintan las páginas.

Todo lo de este módulo es puro (sin red), para poder probarlo con datos de ejemplo.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from . import gtfs, nucleos
from .realtime import Alert, TripUpdate, VehiclePosition

MADRID = ZoneInfo("Europe/Madrid")

# Renfe considera puntual un tren de Cercanías que llega con menos de 3 minutos de retraso.
PUNCTUAL_SECONDS = 180

STATUS_LABELS = {
    "STOPPED_AT": "Parado en",
    "INCOMING_AT": "Llegando a",
    "IN_TRANSIT_TO": "En camino a",
}

LD_GROUPS = {
    "AVE": "Alta Velocidad",
    "AVE INT": "Alta Velocidad",
    "AVLO": "Alta Velocidad",
    "EUROMED": "Alta Velocidad",
    "ALVIA": "Larga Distancia",
    "INTERCITY": "Larga Distancia",
    "TRENCELTA": "Larga Distancia",
}
LD_DEFAULT_GROUP = "Media Distancia"

DELAY_BUCKETS = [
    (60, "< 1 min"),
    (180, "1–2 min"),
    (360, "3–5 min"),
    (660, "6–10 min"),
    (1260, "11–20 min"),
    (None, "> 20 min"),
]

_PLATFORM_RE = re.compile(r"PLATF\.\((\w+)\)")


@dataclass
class Line:
    nucleo: str
    name: str
    color: str
    text_color: str


class LineIndex:
    """Colores y nombres de las líneas de Cercanías a partir del GTFS."""

    def __init__(self, cercanias: gtfs.Gtfs) -> None:
        self.by_key: dict[tuple[str, str], Line] = {}
        self.by_route: dict[str, Line] = {}
        for route in cercanias.routes.values():
            code = route.route_id[:2]
            line = Line(code, route.short_name, route.color, route.text_color)
            self.by_key.setdefault((code, route.short_name.lower()), line)
            self.by_route[route.route_id] = line

    def get(self, nucleo: str, name: str) -> Line:
        return self.by_key.get((nucleo, name.lower())) or Line(nucleo, name, "6B7280", "FFFFFF")

    def for_route(self, route_id: str) -> Line | None:
        route_id = route_id.strip()
        if route_id in self.by_route:
            return self.by_route[route_id]
        m = re.match(r"^(\d{2})T\d+([A-Za-z][A-Za-z0-9]*)$", route_id)
        return self.get(m[1], m[2]) if m else None


def local_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, MADRID).isoformat(timespec="minutes")


def stop_name(stop_id: str | None, *indexes: gtfs.Gtfs) -> str | None:
    if not stop_id:
        return None
    for index in indexes:
        stop = index.stops.get(stop_id.strip())
        if stop:
            return stop.name
    return None


def cercanias_trains(
    vehicles: list[VehiclePosition],
    updates: list[TripUpdate],
    lines: LineIndex,
    cercanias: gtfs.Gtfs,
) -> list[dict[str, Any]]:
    delays = {u.trip_id: u.delay for u in updates if not u.canceled}
    out = []
    for v in vehicles:
        trip = nucleos.parse_trip_id(v.trip_id)
        line_name = trip.line if trip else v.label.split("-")[0]
        nucleo = trip.nucleo if trip else ""
        line = lines.get(nucleo, line_name)
        platform = _PLATFORM_RE.search(v.label)
        out.append(
            {
                "kind": "cercanias",
                "id": v.vehicle_id,
                "lat": v.lat,
                "lon": v.lon,
                "train": trip.train if trip else v.vehicle_id,
                "line": line.name or line_name,
                "color": f"#{line.color}",
                "textColor": f"#{line.text_color}",
                "nucleo": nucleos.nucleo_name(nucleo) if nucleo else "",
                "status": STATUS_LABELS.get(v.status, v.status),
                "stop": stop_name(v.stop_id, cercanias),
                "platform": platform[1] if platform else None,
                "delay": delays.get(v.trip_id),
            }
        )
    return out


def ld_trains(vehicles: list[VehiclePosition], ld: gtfs.Gtfs) -> list[dict[str, Any]]:
    out = []
    for v in vehicles:
        route_id = ld.trip_routes.get(v.trip_id.strip(), "")
        route = ld.routes.get(route_id)
        product = route.short_name if route else ""
        ends = gtfs.ld_endpoints(route_id)
        out.append(
            {
                "kind": "ld",
                "id": v.vehicle_id,
                "lat": v.lat,
                "lon": v.lon,
                "train": v.label or v.trip_id[:5],
                "product": product or "Tren",
                "group": LD_GROUPS.get(product.upper(), LD_DEFAULT_GROUP),
                "origin": stop_name(ends[0], ld) if ends else None,
                "destination": stop_name(ends[1], ld) if ends else None,
                "status": STATUS_LABELS.get(v.status, v.status),
                "stop": stop_name(v.stop_id, ld),
            }
        )
    return out


def _stats(delays: list[int]) -> dict[str, Any]:
    if not delays:
        return {"trips": 0, "punctual_pct": None, "avg_delay_min": None, "max_delay_min": None}
    return {
        "trips": len(delays),
        "punctual_pct": round(100 * sum(d < PUNCTUAL_SECONDS for d in delays) / len(delays), 1),
        "avg_delay_min": round(mean(max(d, 0) for d in delays) / 60, 1),
        "max_delay_min": round(max(delays) / 60),
    }


def delay_report(
    updates: list[TripUpdate], lines: LineIndex, cercanias: gtfs.Gtfs, top: int = 25
) -> dict[str, Any]:
    """Puntualidad de Cercanías según las actualizaciones de viaje en tiempo real."""
    rows = []
    for u in updates:
        trip = nucleos.parse_trip_id(u.trip_id)
        if not trip:
            continue
        line = lines.get(trip.nucleo, trip.line)
        rows.append((u, trip, line))

    tracked = [(u, t, line) for u, t, line in rows if not u.canceled and u.delay is not None]
    canceled = [(u, t, line) for u, t, line in rows if u.canceled]

    by_nucleo: dict[str, list[int]] = defaultdict(list)
    by_line: dict[tuple[str, str], list[int]] = defaultdict(list)
    line_meta: dict[tuple[str, str], Line] = {}
    canceled_by_nucleo: dict[str, int] = defaultdict(int)
    for u, t, line in tracked:
        by_nucleo[t.nucleo_name].append(u.delay)
        by_line[(t.nucleo_name, line.name)].append(u.delay)
        line_meta[(t.nucleo_name, line.name)] = line
    for _, t, _ in canceled:
        canceled_by_nucleo[t.nucleo_name] += 1

    buckets = []
    lower = None
    for upper, label in DELAY_BUCKETS:
        count = sum(
            1
            for u, _, _ in tracked
            if (lower is None or u.delay >= lower) and (upper is None or u.delay < upper)
        )
        buckets.append({"label": label, "trips": count})
        lower = upper

    nucleo_rows = [
        {"nucleo": n, **_stats(d), "canceled": canceled_by_nucleo.get(n, 0)}
        for n, d in by_nucleo.items()
    ]
    for n, c in canceled_by_nucleo.items():
        if n not in by_nucleo:
            nucleo_rows.append({"nucleo": n, **_stats([]), "canceled": c})

    line_rows = [
        {
            "nucleo": n,
            "line": name,
            "color": f"#{line_meta[(n, name)].color}",
            "textColor": f"#{line_meta[(n, name)].text_color}",
            **_stats(d),
        }
        for (n, name), d in by_line.items()
    ]

    worst = sorted(tracked, key=lambda r: -r[0].delay)[:top]
    return {
        "summary": {
            **_stats([u.delay for u, _, _ in tracked]),
            "canceled": len(canceled),
            "threshold_min": PUNCTUAL_SECONDS // 60,
        },
        "buckets": buckets,
        "by_nucleo": sorted(nucleo_rows, key=lambda r: -r["trips"]),
        "by_line": sorted(line_rows, key=lambda r: (r["nucleo"], -(r["avg_delay_min"] or 0))),
        "worst": [
            {
                "train": t.train,
                "line": line.name,
                "color": f"#{line.color}",
                "textColor": f"#{line.text_color}",
                "nucleo": t.nucleo_name,
                "delay_min": round(u.delay / 60),
                "next_stop": stop_name(u.next_stop_id, cercanias),
                "eta": local_iso(u.next_arrival),
            }
            for u, t, line in worst
            if u.delay >= 60
        ],
        "canceled": [
            {
                "train": t.train,
                "line": line.name,
                "color": f"#{line.color}",
                "textColor": f"#{line.text_color}",
                "nucleo": t.nucleo_name,
            }
            for _, t, line in canceled
        ],
    }


def alert_report(alerts: list[Alert], lines: LineIndex) -> list[dict[str, Any]]:
    out = []
    for a in alerts:
        affected: dict[tuple[str, str], Line] = {}
        for route_id in a.route_ids:
            line = lines.for_route(route_id)
            if line:
                affected[(line.nucleo, line.name)] = line
        nucleo_names = sorted({nucleos.nucleo_name(code) for code, _ in affected})
        out.append(
            {
                "id": a.alert_id,
                "text": a.text,
                "start": local_iso(a.start),
                "end": local_iso(a.end),
                "nucleos": nucleo_names,
                "lines": [
                    {
                        "name": line.name,
                        "color": f"#{line.color}",
                        "textColor": f"#{line.text_color}",
                    }
                    for _, line in sorted(affected.items(), key=lambda kv: _line_sort(kv[1].name))
                ],
                "kind": _alert_kind(a.text),
            }
        )
    return sorted(out, key=lambda a: a["start"] or "", reverse=True)


def _alert_kind(text: str) -> str:
    lowered = text.lower()
    if lowered.startswith("ascensor") or "ascensor" in lowered[:60]:
        return "Accesibilidad"
    if "obra" in lowered:
        return "Obras"
    if "autobús" in lowered or "autobus" in lowered:
        return "Transporte alternativo"
    return "Servicio"


def _line_sort(name: str) -> tuple[str, int, str]:
    m = re.match(r"^([A-Za-z]+)(\d*)(.*)$", name)
    if not m:
        return (name, 0, "")
    return (m[1], int(m[2] or 0), m[3])
