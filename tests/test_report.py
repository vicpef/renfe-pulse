from conftest import ALERTS, CERCANIAS_GTFS, LD_GTFS, TRIP_UPDATES, VEHICLES, VEHICLES_LD

from renfe_pulse import gtfs, realtime, report

CER = gtfs.load(CERCANIAS_GTFS, ("routes", "stops"))
LD = gtfs.load(LD_GTFS)
LINES = report.LineIndex(CER)
UPDATES = realtime.trip_updates(realtime.parse_feed(TRIP_UPDATES))


def test_line_index():
    assert LINES.get("10", "c1").color == "75B6E0"
    assert LINES.get("99", "X9").color == "6B7280"  # línea desconocida: gris
    assert LINES.for_route("10T0011C4  ").name == "C4"
    assert LINES.for_route("62T0001C1").nucleo == "62"
    assert LINES.for_route("basura") is None


def test_cercanias_trains_join_delay_and_platform():
    vehicles = realtime.vehicle_positions(realtime.parse_feed(VEHICLES))
    trains = report.cercanias_trains(vehicles, UPDATES, LINES, CER)
    c1 = trains[0]
    assert c1["line"] == "C1" and c1["color"] == "#75B6E0"
    assert c1["nucleo"] == "Madrid"
    assert c1["stop"] == "Madrid-Atocha Cercanías"
    assert c1["status"] == "Parado en"
    assert c1["platform"] == "2"
    assert c1["delay"] == 420
    assert trains[1]["nucleo"] == "Rodalies de Catalunya"


def test_ld_trains_route_and_product():
    vehicles = realtime.vehicle_positions(realtime.parse_feed(VEHICLES_LD))
    ave, md = report.ld_trains(vehicles, LD)
    assert ave["product"] == "AVE" and ave["group"] == "Alta Velocidad"
    assert ave["origin"] == "Madrid-Chamartín-Clara Campoamor"
    assert ave["destination"] == "Barcelona-Sants"
    assert md["group"] == "Media Distancia"
    assert md["stop"] == "Badajoz"


def test_delay_report():
    rep = report.delay_report(UPDATES, LINES, CER)
    s = rep["summary"]
    assert s["trips"] == 3
    assert s["canceled"] == 1
    assert s["punctual_pct"] == 66.7  # 0 s y 120 s son puntuales; 420 s no
    assert s["avg_delay_min"] == 3.0
    assert s["max_delay_min"] == 7
    # 0 s -> "< 1 min", 120 s -> "1–2 min", 420 s -> "6–10 min"
    assert [b["trips"] for b in rep["buckets"]] == [1, 1, 0, 1, 0, 0]
    madrid = next(r for r in rep["by_nucleo"] if r["nucleo"] == "Madrid")
    assert madrid["trips"] == 2 and madrid["canceled"] == 0
    rodalies = next(r for r in rep["by_nucleo"] if r["nucleo"] == "Rodalies de Catalunya")
    assert rodalies["canceled"] == 1
    assert rep["worst"][0]["train"] == "19799"
    assert rep["worst"][0]["next_stop"] == "Madrid-Chamartín"
    assert len(rep["worst"]) == 2  # el viaje sin retraso no aparece
    assert rep["canceled"][0]["line"] == "R1"


def test_delay_report_empty():
    rep = report.delay_report([], LINES, CER)
    assert rep["summary"]["trips"] == 0
    assert rep["summary"]["punctual_pct"] is None
    assert rep["worst"] == []


def test_alert_report():
    alerts = report.alert_report(realtime.alerts(realtime.parse_feed(ALERTS)), LINES)
    first = alerts[0]
    assert first["nucleos"] == ["Madrid"]
    assert [line["name"] for line in first["lines"]] == ["C1", "C4"]
    assert first["kind"] == "Obras"
    assert first["start"].startswith("2026-10-07T")
    assert alerts[1]["kind"] == "Accesibilidad"
    assert alerts[1]["lines"] == []
