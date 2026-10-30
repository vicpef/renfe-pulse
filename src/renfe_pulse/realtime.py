"""Lectura de los feeds GTFS-Realtime de Renfe en su variante JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any

import requests


@dataclass
class Feed:
    timestamp: int
    entities: list[dict[str, Any]]
    last_modified: int | None = None

    @property
    def updated(self) -> int:
        """Hora de la última actualización del feed.

        Preferimos la cabecera HTTP `Last-Modified`: el `timestamp` de la cabecera GTFS-RT
        del feed de AV/LD llega desplazado una hora.
        """
        return self.last_modified or self.timestamp


@dataclass
class VehiclePosition:
    vehicle_id: str
    label: str
    trip_id: str
    lat: float
    lon: float
    status: str
    stop_id: str | None
    timestamp: int | None


@dataclass
class TripUpdate:
    trip_id: str
    delay: int | None
    canceled: bool
    next_stop_id: str | None
    next_arrival: int | None


@dataclass
class Alert:
    alert_id: str
    text: str
    start: int | None
    end: int | None
    route_ids: list[str] = field(default_factory=list)
    stop_ids: list[str] = field(default_factory=list)


def fetch_feed(session: requests.Session, url: str) -> Feed:
    resp = session.get(url)
    resp.raise_for_status()
    feed = parse_feed(resp.json())
    feed.last_modified = _http_date(resp.headers.get("Last-Modified"))
    return feed


def parse_feed(payload: dict[str, Any]) -> Feed:
    header = payload.get("header") or {}
    return Feed(timestamp=_int(header.get("timestamp")) or 0, entities=payload.get("entity") or [])


def vehicle_positions(feed: Feed) -> list[VehiclePosition]:
    """Posiciones de los trenes, una por vehículo.

    El feed de AV/LD repite a veces el mismo vehículo con dos `trip_id` (p. ej. el viaje de
    ida y el siguiente); nos quedamos con la entrada que indica la parada actual.
    """
    by_vehicle: dict[str, VehiclePosition] = {}
    for entity in feed.entities:
        v = entity.get("vehicle") or {}
        pos = v.get("position") or {}
        if "latitude" not in pos or "longitude" not in pos:
            continue
        info = v.get("vehicle") or {}
        vp = VehiclePosition(
            vehicle_id=str(info.get("id") or entity.get("id", "")),
            label=str(info.get("label") or ""),
            trip_id=str((v.get("trip") or {}).get("tripId") or ""),
            lat=round(float(pos["latitude"]), 5),
            lon=round(float(pos["longitude"]), 5),
            status=str(v.get("currentStatus") or ""),
            stop_id=v.get("stopId"),
            timestamp=_int(v.get("timestamp")),
        )
        prev = by_vehicle.get(vp.vehicle_id)
        if prev is None or (prev.stop_id is None and vp.stop_id is not None):
            by_vehicle[vp.vehicle_id] = vp
    return list(by_vehicle.values())


def trip_updates(feed: Feed) -> list[TripUpdate]:
    out = []
    for entity in feed.entities:
        tu = entity.get("tripUpdate")
        if not tu:
            continue
        trip = tu.get("trip") or {}
        stops = tu.get("stopTimeUpdate") or []
        first = stops[0] if stops else {}
        event = first.get("arrival") or first.get("departure") or {}
        delay = tu.get("delay", event.get("delay"))
        out.append(
            TripUpdate(
                trip_id=str(trip.get("tripId") or ""),
                delay=_int(delay),
                canceled=trip.get("scheduleRelationship") == "CANCELED",
                next_stop_id=first.get("stopId"),
                next_arrival=_int(event.get("time")),
            )
        )
    return out


def alerts(feed: Feed) -> list[Alert]:
    out = []
    for entity in feed.entities:
        a = entity.get("alert")
        if not a:
            continue
        periods = a.get("activePeriod") or [{}]
        informed = a.get("informedEntity") or []
        out.append(
            Alert(
                alert_id=str(entity.get("id", "")),
                text=_translation(a.get("descriptionText")) or _translation(a.get("headerText")),
                start=_int(periods[0].get("start")),
                end=_int(periods[0].get("end")),
                route_ids=sorted({e["routeId"] for e in informed if e.get("routeId")}),
                stop_ids=sorted({e["stopId"] for e in informed if e.get("stopId")}),
            )
        )
    return out


def _translation(text: dict[str, Any] | None, lang: str = "es") -> str:
    translations = (text or {}).get("translation") or []
    for t in translations:
        if t.get("language") == lang:
            return t.get("text", "").strip()
    return translations[0].get("text", "").strip() if translations else ""


def _http_date(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(parsedate_to_datetime(value).timestamp())
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
