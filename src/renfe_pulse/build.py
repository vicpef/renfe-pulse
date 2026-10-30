"""Descarga los datos de Renfe, los procesa y escribe el sitio estático."""

from __future__ import annotations

import json
import logging
import shutil
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar

import requests
from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from . import __version__, ckan, gtfs, history, realtime, report, ridership, sources, stations
from .http import make_session

log = logging.getLogger(__name__)

T = TypeVar("T")

STALE_SECONDS = 24 * 3600

PAGES = [
    ("index.html", "Resumen"),
    ("mapa.html", "Mapa"),
    ("retrasos.html", "Retrasos"),
    ("avisos.html", "Avisos"),
    ("estaciones.html", "Estaciones"),
    ("viajeros.html", "Viajeros"),
    ("catalogo.html", "Catálogo"),
]


class BuildError(RuntimeError):
    pass


class SourceLog:
    """Registra qué fuentes se pudieron leer, para mostrarlo en el sitio."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def attempt(self, name: str, url: str, fn: Callable[[], T], default: T) -> T:
        try:
            result = fn()
        except Exception as exc:  # una fuente caída no debe tumbar todo el sitio
            log.warning("Fuente no disponible: %s (%s): %s", name, url, exc)
            self.entries.append({"name": name, "url": url, "ok": False, "error": str(exc)[:300]})
            return default
        self.entries.append({"name": name, "url": url, "ok": True})
        return result


def build(
    out_dir: Path,
    *,
    session: requests.Session | None = None,
    site_url: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    session = session or make_session()
    now = now or datetime.now(UTC)
    src = SourceLog()

    datasets = src.attempt(
        "Catálogo de datasets (API CKAN)",
        f"{ckan.BASE_URL}/package_search",
        lambda: [ckan.summarize(p) for p in ckan.CkanClient(session).packages()],
        [],
    )
    gtfs_cer = src.attempt(
        "Horarios Cercanías (GTFS)",
        sources.GTFS_CERCANIAS,
        lambda: gtfs.load(gtfs.download(session, sources.GTFS_CERCANIAS), ("routes", "stops")),
        gtfs.Gtfs(),
    )
    gtfs_ld = src.attempt(
        "Horarios AV, LD y MD (GTFS)",
        sources.GTFS_LD,
        lambda: gtfs.load(gtfs.download(session, sources.GTFS_LD)),
        gtfs.Gtfs(),
    )
    feeds = {
        key: src.attempt(name, url, lambda url=url: realtime.fetch_feed(session, url), None)
        for key, name, url in [
            ("cercanias", "Ubicación de vehículos de Cercanías", sources.VEHICLES_CERCANIAS),
            ("ld", "Posición de vehículos AV, LD y MD", sources.VEHICLES_LD),
            ("updates", "Horarios de viaje de Cercanías", sources.TRIP_UPDATES),
            ("alerts", "Incidencias y avisos", sources.ALERTS),
        ]
    }
    station_list = src.attempt(
        "Estaciones. Listado completo",
        sources.STATIONS_CSV,
        lambda: stations.fetch(session, sources.STATIONS_CSV),
        [],
    )
    rider_rows = src.attempt(
        "Volumen de viajeros por franja horaria",
        sources.RIDERSHIP_CSV,
        lambda: ridership.fetch(session, sources.RIDERSHIP_CSV),
        [],
    )

    if not any(feeds[k] for k in ("cercanias", "ld", "updates")):
        raise BuildError("No se pudo leer ningún feed en tiempo real; no se publica el sitio.")

    lines = report.LineIndex(gtfs_cer)
    updates = realtime.trip_updates(feeds["updates"]) if feeds["updates"] else []
    trains = []
    if feeds["cercanias"]:
        vehicles = realtime.vehicle_positions(feeds["cercanias"])
        trains += report.cercanias_trains(vehicles, updates, lines, gtfs_cer)
    if feeds["ld"]:
        trains += report.ld_trains(realtime.vehicle_positions(feeds["ld"]), gtfs_ld)
    delays = report.delay_report(updates, lines, gtfs_cer)
    alerts = report.alert_report(realtime.alerts(feeds["alerts"]) if feeds["alerts"] else [], lines)
    rider = ridership.summarize(rider_rows)

    counts = Counter(t["kind"] for t in trains)
    ld_groups = Counter(t["group"] for t in trains if t["kind"] == "ld")
    point = {
        "t": int(now.timestamp()),
        "cercanias": counts["cercanias"],
        "ld": counts["ld"],
        "punctual_pct": delays["summary"]["punctual_pct"],
        "avg_delay_min": delays["summary"]["avg_delay_min"],
        "canceled": delays["summary"]["canceled"],
        "alerts": len(alerts),
    }
    points = history.append(history.load_previous(session, site_url), point)

    meta = {
        "generated_at": now.astimezone(report.MADRID).isoformat(timespec="minutes"),
        "version": __version__,
        "site_url": site_url,
        "feeds": {k: report.local_iso(f.updated) if f else None for k, f in feeds.items()},
        # Feeds que llevan más de un día sin actualizarse (el de avisos se queda parado a veces)
        "stale_feeds": [
            k for k, f in feeds.items() if f and now.timestamp() - f.updated > STALE_SECONDS
        ],
        "sources": src.entries,
    }
    live = {
        "generated_at": meta["generated_at"],
        "feeds": meta["feeds"],
        "counts": {"cercanias": counts["cercanias"], "ld": counts["ld"], **ld_groups},
        "trains": trains,
    }
    station_rows = [asdict(s) for s in station_list]
    # Versión compacta para los mapas: [código, nombre, lat, lon, cercanías]
    station_points = [
        [s.code, s.name, s.lat, s.lon, int(s.cercanias)]
        for s in station_list
        if s.lat is not None and s.lon is not None
    ]
    catalog = [{**asdict(d), "formats": d.formats} for d in datasets]

    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)
    _write_json(data_dir / "live.json", live)
    _write_json(data_dir / "delays.json", delays)
    _write_json(data_dir / "alerts.json", alerts)
    _write_json(data_dir / "stations.json", station_rows)
    _write_json(data_dir / "ridership.json", rider)
    _write_json(data_dir / "catalog.json", catalog)
    _write_json(data_dir / "history.json", {"points": points})
    _write_json(data_dir / "build.json", meta)

    context = {
        "meta": meta,
        "live": live,
        "delays": delays,
        "alerts": alerts,
        "stations": station_rows,
        "station_points": station_points,
        "ridership": rider,
        "catalog": catalog,
        "history": points,
        "pages": PAGES,
    }
    _render(out_dir, context)
    _copy_static(out_dir / "static")
    (out_dir / ".nojekyll").touch()
    log.info(
        "Sitio generado en %s: %d trenes, %d avisos, %d estaciones, %d datasets",
        out_dir,
        len(trains),
        len(alerts),
        len(station_rows),
        len(catalog),
    )
    return meta


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("renfe_pulse", "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["num"] = _num
    env.filters["fecha"] = _fecha
    env.filters["tojson_safe"] = _json_script
    return env


def _json_script(value: Any) -> Markup:
    """JSON para incrustar en `<script type="application/json">` sin romper el HTML."""
    text = json.dumps(value, ensure_ascii=False)
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e")):
        text = text.replace(char, escaped)
    return Markup(text)


def _render(out_dir: Path, context: dict[str, Any]) -> None:
    env = _env()
    for filename, title in PAGES:
        html = env.get_template(filename).render(page=filename, title=title, **context)
        (out_dir / filename).write_text(html, "utf-8")


def _copy_static(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for item in resources.files("renfe_pulse").joinpath("static").iterdir():
        if item.is_file():
            (dest / item.name).write_bytes(item.read_bytes())


def _num(value: Any, decimals: int = 0) -> str:
    """Número con formato español: 1.234,5."""
    if value is None:
        return "—"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


_MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()


def _fecha(value: str | None, with_time: bool = True) -> str:
    if not value:
        return "—"
    dt = datetime.fromisoformat(value)
    text = f"{dt.day} {_MESES[dt.month - 1]} {dt.year}"
    return f"{text}, {dt:%H:%M}" if with_time else text
