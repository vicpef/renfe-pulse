"""Datos de ejemplo con la forma real de las fuentes de Renfe, para probar sin red."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import pytest
import requests

from renfe_pulse import ckan, sources


def gtfs_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


# Los GTFS de Renfe rellenan los campos con espacios: lo reproducimos a propósito.
CERCANIAS_GTFS = gtfs_zip(
    {
        "routes.txt": (
            "route_id,route_short_name,route_long_name,route_type,route_color,route_text_color\n"
            "10T0001C1  ,C1  ,Principe Pio   -Aeropuerto-T4   ,2,75B6E0,FFFFFF\n"
            "10T0011C4  ,C4  ,Parla   -Colmenar Viejo  ,2,2C2A86,FFFFFF\n"
            "51T0001R1  ,R1  ,Molins de Rei -Maçanet-Massanes ,2,7DBCEC,FFFFFF\n"
        ),
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon,wheelchair_boarding\n"
            "18000,Madrid-Atocha Cercanías,40.4065,-3.6895,1\n"
            "17000,Madrid-Chamartín,40.4722,-3.6825,1\n"
            "79400,Barcelona-Sants,41.3792,2.1402,1\n"
        ),
        "trips.txt": "route_id,service_id,trip_id\n",
    }
)

LD_GTFS = gtfs_zip(
    {
        "routes.txt": (
            "route_id,agency_id,route_short_name,route_long_name,route_desc,route_type\n"
            "1700071801GL001,1071,AVE,,,2\n"
            "1800037606GL023,1071,MD,,,2\n"
        ),
        "stops.txt": (
            "stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon\n"
            "17000,,Madrid-Chamartín-Clara Campoamor,,40.47,-3.68\n"
            "71801,,Barcelona-Sants,,41.38,2.14\n"
            "18000,,Madrid-Puerta de Atocha,,40.40,-3.69\n"
            "37606,,Badajoz,,38.89,-6.98\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign,trip_short_name\n"
            "1700071801GL001,s1,0310012026-10-30,,03100\n"
            "1800037606GL023,s2,1770012026-10-30,,17700\n"
        ),
    }
)

VEHICLES = {
    "header": {"gtfsRealtimeVersion": "2.0", "timestamp": "1793374052"},
    "entity": [
        {
            "id": "VP_C1-19799",
            "vehicle": {
                "trip": {"tripId": "1002V19799C1"},
                "position": {"latitude": 40.40651, "longitude": -3.68951},
                "currentStatus": "STOPPED_AT",
                "timestamp": "1793374050",
                "stopId": "18000",
                "vehicle": {"id": "19799", "label": "C1-19799-PLATF.(2)"},
            },
        },
        {
            "id": "VP_R1-25001",
            "vehicle": {
                "trip": {"tripId": "5102V25001R1"},
                "position": {"latitude": 41.38, "longitude": 2.14},
                "currentStatus": "IN_TRANSIT_TO",
                "stopId": "79400",
                "vehicle": {"id": "25001", "label": "R1-25001"},
            },
        },
        {"id": "SIN_POSICION", "vehicle": {"trip": {"tripId": "1002V1C1"}}},
    ],
}

VEHICLES_LD = {
    "header": {"gtfsRealtimeVersion": "2.0", "timestamp": "1793370508"},
    "entity": [
        {
            "id": "VP_03100",
            "vehicle": {
                "trip": {"tripId": "0310012026-10-30"},
                "position": {"latitude": 41.0, "longitude": -1.0},
                "currentStatus": "IN_TRANSIT_TO",
                "vehicle": {"id": "03100", "label": "03100"},
            },
        },
        {
            "id": "VP_03100",
            "vehicle": {
                "trip": {"tripId": "0310012026-10-30"},
                "position": {"latitude": 41.0, "longitude": -1.0},
                "currentStatus": "IN_TRANSIT_TO",
                "stopId": "71801",
                "vehicle": {"id": "03100", "label": "03100"},
            },
        },
        {
            "id": "VP_17700",
            "vehicle": {
                "trip": {"tripId": "1770012026-10-30"},
                "position": {"latitude": 39.0, "longitude": -5.0},
                "currentStatus": "STOPPED_AT",
                "stopId": "37606",
                "vehicle": {"id": "17700", "label": "17700"},
            },
        },
    ],
}

TRIP_UPDATES = {
    "header": {"gtfsRealtimeVersion": "2.0", "timestamp": "1793374093"},
    "entity": [
        {
            "id": "TU_1",
            "tripUpdate": {
                "trip": {"tripId": "1002V19799C1", "scheduleRelationship": "SCHEDULED"},
                "stopTimeUpdate": [
                    {"arrival": {"delay": 420, "time": "1793375000"}, "stopId": "17000"}
                ],
                "delay": 420,
            },
        },
        {
            "id": "TU_2",
            "tripUpdate": {
                "trip": {"tripId": "1002V19800C4", "scheduleRelationship": "SCHEDULED"},
                "stopTimeUpdate": [{"arrival": {"delay": 0, "time": "1793375100"}}],
                "delay": 0,
            },
        },
        {
            "id": "TU_3",
            "tripUpdate": {
                "trip": {"tripId": "5102V25001R1", "scheduleRelationship": "SCHEDULED"},
                "stopTimeUpdate": [{"arrival": {"delay": 120}, "stopId": "79400"}],
            },
        },
        {
            "id": "TU_4",
            "tripUpdate": {
                "trip": {"tripId": "5102V25003R1", "scheduleRelationship": "CANCELED"},
            },
        },
    ],
}

ALERTS = {
    "header": {"gtfsRealtimeVersion": "2.0", "timestamp": "1791358372"},
    "entity": [
        {
            "id": "AVISO_1",
            "alert": {
                "activePeriod": [{"start": "1791356520"}],
                "informedEntity": [{"routeId": "10T0011C4"}, {"routeId": "10T0001C1"}],
                "descriptionText": {
                    "translation": [
                        {"text": "#MadC4 Por obras, los trenes no paran.", "language": "es"}
                    ]
                },
            },
        },
        {
            "id": "AVISO_2",
            "alert": {
                "activePeriod": [{"start": "1791356000"}],
                "informedEntity": [{"stopId": "18000"}],
                "descriptionText": {
                    "translation": [{"text": "Ascensor fuera de servicio.", "language": "es"}]
                },
            },
        },
    ],
}

STATIONS_CSV = (
    '"CODIGO";"DESCRIPCION";"LATITUD";"LONGITUD";"DIRECION";"CP";"POBLACION";"PROVINCIA";'
    '"PAIS";"CERCANIAS";"ANCHO MÉTRICO";"COMUN"\n'
    '"18000";"MADRID-PUERTA DE ATOCHA";"40.4065";"-3.6895";"Glorieta del Emperador";'
    '"28045";"MADRID";"MADRID";"ESPAÑA";"SI";"NO";""\n'
    '"05409";"LA FELGUERA";"43.30";"-5.69";"C/ Estación";"33930";"LANGREO";"ASTURIAS";'
    '"ESPAÑA";"NO";"SI";""\n'
).encode("latin-1")

RIDERSHIP_CSV = (
    b"CODIGO_ESTACION;NOMBRE_ESTACION;NUCLEO_CERCANIAS;TRAMO_HORARIO;"
    b"VIAJEROS_SUBIDOS;VIAJEROS_BAJADOS\n"
    b"18000;MADRID ATOCHA;MADRID;07:00 - 07:30;100;50\n"
    b"18000;MADRID ATOCHA;MADRID;07:30 - 08:00;80;70\n"
    b"17000;CHAMARTIN;MADRID;07:00 - 07:30;20;10\n"
    b"4040;ZARAGOZA DELICIAS;ZARAGOZA;06:00 - 06:30;3;0\n"
    b"5409;LA FELGUERA;ASTURIAS AM;06:00 - 06:30;1;2\n"
)

PACKAGE = {
    "name": "ubicacion-vehiculos",
    "title": "Ubicación de los vehículos",
    "notes": "Proporciona la ubicación en tiempo real.\n\n__Se actualiza cada 20 segundos.__",
    "metadata_modified": "2026-10-29T23:01:29.288978",
    "tags": [{"display_name": "Tiempo Real"}, {"display_name": "Cercanias"}],
    "resources": [
        {"name": "vehicle_positions.pb", "format": "GTFS-RT", "url": "https://x/vp.pb"},
        {"name": "vehicle_positions.json", "format": "json", "url": "https://x/vp.json"},
    ],
}
STATIC_PACKAGE = {
    "name": "estaciones-listado-completo",
    "title": "Estaciones. Listado completo",
    "notes": "Relación de todas las estaciones donde opera Renfe.",
    "metadata_modified": "2026-10-30T04:30:27",
    "tags": [],
    "resources": [
        {"name": "csv", "format": "CSV", "url": "https://x/e.csv", "datastore_active": True}
    ],
}


class FakeResponse:
    def __init__(self, body: Any = None, status: int = 200, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}
        if isinstance(body, bytes):
            self.content = body
        else:
            self.content = json.dumps(body).encode()

    def json(self) -> Any:
        return json.loads(self.content)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Sesión que responde con los datos de ejemplo según la URL pedida."""

    def __init__(self, routes: dict[str, FakeResponse]):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url: str, params: dict | None = None, timeout: float | None = None):
        self.calls.append(url)
        if url in self.routes:
            return self.routes[url]
        return FakeResponse({"error": "not found"}, status=404)


def default_routes() -> dict[str, FakeResponse]:
    lm = {"Last-Modified": "Fri, 30 Oct 2026 15:41:43 GMT"}
    return {
        f"{ckan.BASE_URL}/package_search": FakeResponse(
            {"success": True, "result": {"count": 2, "results": [PACKAGE, STATIC_PACKAGE]}}
        ),
        sources.GTFS_CERCANIAS: FakeResponse(CERCANIAS_GTFS),
        sources.GTFS_LD: FakeResponse(LD_GTFS),
        sources.VEHICLES_CERCANIAS: FakeResponse(VEHICLES, headers=lm),
        sources.VEHICLES_LD: FakeResponse(VEHICLES_LD, headers=lm),
        sources.TRIP_UPDATES: FakeResponse(TRIP_UPDATES, headers=lm),
        sources.ALERTS: FakeResponse(
            ALERTS, headers={"Last-Modified": "Wed, 07 Oct 2026 07:32:52 GMT"}
        ),
        sources.STATIONS_CSV: FakeResponse(STATIONS_CSV),
        sources.RIDERSHIP_CSV: FakeResponse(RIDERSHIP_CSV),
    }


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession(default_routes())
