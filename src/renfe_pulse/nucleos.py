"""Núcleos de Cercanías y cómo leerlos de los identificadores de Renfe.

Los `trip_id` de Cercanías tienen la forma `NNSSV<tren><línea>`, p. ej. `1002V19799C1`:
núcleo 10 (Madrid), tren 19799, línea C1. Los `route_id` empiezan por el mismo código.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NUCLEOS: dict[str, str] = {
    "10": "Madrid",
    "20": "Asturias",
    "30": "Sevilla",
    "31": "Cádiz",
    "32": "Málaga",
    "40": "Valencia",
    "41": "Murcia/Alicante",
    "45": "Cartagena (ancho métrico)",
    "46": "Ferrol (ancho métrico)",
    "47": "León (ancho métrico)",
    "50": "Rodalies de Catalunya",
    "51": "Rodalies de Catalunya",
    "60": "Bilbao",
    "61": "San Sebastián",
    "62": "Santander",
    "70": "Zaragoza",
}

_TRIP_RE = re.compile(r"^(?P<nucleo>\d{2})\d{2}V(?P<train>\d+?)(?P<line>[A-Za-z][A-Za-z0-9]*)$")


@dataclass(frozen=True)
class CercaniasTrip:
    nucleo: str
    train: str
    line: str

    @property
    def nucleo_name(self) -> str:
        return nucleo_name(self.nucleo)


def nucleo_name(code: str) -> str:
    return NUCLEOS.get(code, f"Núcleo {code}")


def parse_trip_id(trip_id: str) -> CercaniasTrip | None:
    m = _TRIP_RE.match(trip_id.strip())
    if not m:
        return None
    return CercaniasTrip(m["nucleo"], m["train"], m["line"])
