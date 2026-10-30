from conftest import (
    ALERTS,
    CERCANIAS_GTFS,
    LD_GTFS,
    PACKAGE,
    RIDERSHIP_CSV,
    STATIC_PACKAGE,
    STATIONS_CSV,
    TRIP_UPDATES,
    VEHICLES,
    VEHICLES_LD,
    FakeResponse,
    FakeSession,
)

from renfe_pulse import ckan, gtfs, history, nucleos, realtime, ridership, stations


def test_parse_trip_id():
    trip = nucleos.parse_trip_id("1002V19799C1")
    assert (trip.nucleo, trip.train, trip.line) == ("10", "19799", "C1")
    assert trip.nucleo_name == "Madrid"
    assert nucleos.parse_trip_id("5102V25001R2S").line == "R2S"
    assert nucleos.parse_trip_id("1002V20483C4b").line == "C4b"
    assert nucleos.parse_trip_id("0310012026-10-30") is None
    assert nucleos.nucleo_name("99") == "Núcleo 99"


def test_vehicle_positions_skip_missing_position_and_dedupe():
    cer = realtime.vehicle_positions(realtime.parse_feed(VEHICLES))
    assert [v.vehicle_id for v in cer] == ["19799", "25001"]
    assert cer[0].stop_id == "18000" and cer[0].status == "STOPPED_AT"

    ld = realtime.vehicle_positions(realtime.parse_feed(VEHICLES_LD))
    # El vehículo repetido se queda con la entrada que trae parada
    assert len(ld) == 2
    assert ld[0].stop_id == "71801"


def test_trip_updates():
    updates = {u.trip_id: u for u in realtime.trip_updates(realtime.parse_feed(TRIP_UPDATES))}
    assert updates["1002V19799C1"].delay == 420
    assert updates["1002V19799C1"].next_stop_id == "17000"
    # Sin `delay` a nivel de viaje se usa el de la primera parada
    assert updates["5102V25001R1"].delay == 120
    assert updates["5102V25003R1"].canceled


def test_alerts():
    alerts = realtime.alerts(realtime.parse_feed(ALERTS))
    assert alerts[0].text.startswith("#MadC4")
    assert alerts[0].route_ids == ["10T0001C1", "10T0011C4"]
    assert alerts[1].stop_ids == ["18000"]
    assert alerts[0].end is None


def test_feed_prefers_last_modified_header():
    session = FakeSession(
        {"u": FakeResponse(VEHICLES_LD, headers={"Last-Modified": "Fri, 30 Oct 2026 15:41:43 GMT"})}
    )
    feed = realtime.fetch_feed(session, "u")
    assert feed.timestamp == 1793370508
    assert feed.updated == 1793374903


def test_gtfs_strips_padding():
    cer = gtfs.load(CERCANIAS_GTFS, ("routes", "stops"))
    assert cer.routes["10T0001C1"].short_name == "C1"
    assert cer.routes["10T0001C1"].long_name == "Principe Pio -Aeropuerto-T4"
    assert cer.stops["18000"].name == "Madrid-Atocha Cercanías"
    assert cer.trip_routes == {}

    ld = gtfs.load(LD_GTFS)
    assert ld.trip_routes["0310012026-10-30"] == "1700071801GL001"
    assert gtfs.ld_endpoints("1700071801GL001") == ("17000", "71801")
    assert gtfs.ld_endpoints("raro") is None


def test_stations_latin1():
    rows = stations.parse(STATIONS_CSV)
    atocha, felguera = rows
    assert atocha.name == "Madrid-Puerta de Atocha"
    assert atocha.cercanias and not atocha.ancho_metrico
    assert atocha.lat == 40.4065
    assert felguera.ancho_metrico and felguera.town == "Langreo"


def test_ridership_summary():
    summary = ridership.summarize(ridership.parse(RIDERSHIP_CSV))
    madrid = summary[0]
    assert madrid["nucleo"] == "Madrid"
    assert madrid["total"] == 330
    assert madrid["profile"][0] == {"slot": "07:00 - 07:30", "up": 120, "down": 60}
    assert madrid["stations"][0] == {"name": "Madrid Atocha", "total": 300}
    assert {n["nucleo"] for n in summary} == {"Madrid", "Zaragoza", "Asturias (ancho métrico)"}


def test_history_append_dedupes_and_trims():
    day = 24 * 3600
    points = [{"t": 0, "v": 1}, {"t": 10 * day, "v": 2}, {"t": 40 * day, "v": 3}]
    out = history.append(points, {"t": 40 * day, "v": 4})
    assert out == [{"t": 10 * day, "v": 2}, {"t": 40 * day, "v": 4}]


def test_history_load_previous_tolerates_errors():
    assert history.load_previous(FakeSession({}), None) == []
    assert history.load_previous(FakeSession({}), "https://x.github.io/repo") == []
    good = FakeSession({"https://x/data/history.json": FakeResponse({"points": [{"t": 1}, {}]})})
    assert history.load_previous(good, "https://x/") == [{"t": 1}]
    broken = FakeSession({"https://x/data/history.json": FakeResponse(b"<html>")})
    assert history.load_previous(broken, "https://x") == []


def test_ckan_packages_and_summary():
    session = FakeSession(
        {
            f"{ckan.BASE_URL}/package_search": FakeResponse(
                {"success": True, "result": {"count": 2, "results": [PACKAGE, STATIC_PACKAGE]}}
            )
        }
    )
    packages = ckan.CkanClient(session).packages()
    assert len(packages) == 2
    live, static = (ckan.summarize(p) for p in packages)
    assert live.realtime and not static.realtime
    assert live.formats == ["GTFS-RT", "JSON"]
    assert live.description == "Proporciona la ubicación en tiempo real."
    assert live.url == "https://data.renfe.com/dataset/ubicacion-vehiculos"
    assert static.resources[0].datastore
