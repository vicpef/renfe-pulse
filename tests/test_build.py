import json
import re
from datetime import UTC, datetime

import pytest
from conftest import FakeResponse, FakeSession, default_routes

from renfe_pulse import sources
from renfe_pulse.build import PAGES, BuildError, build

NOW = datetime(2026, 10, 30, 15, 45, tzinfo=UTC)


def test_build_writes_pages_and_data(tmp_path, fake_session):
    meta = build(tmp_path, session=fake_session, now=NOW)

    for filename, _ in PAGES:
        html = (tmp_path / filename).read_text("utf-8")
        assert "<title>" in html and "Renfe Pulse" in html
        # El JSON incrustado debe poder leerse tal cual desde el navegador
        for blob in re.findall(r'<script type="application/json" id="[^"]+">(.*?)</script>', html):
            json.loads(blob)
    assert (tmp_path / "static" / "app.js").exists()
    assert (tmp_path / "static" / "style.css").exists()

    live = json.loads((tmp_path / "data" / "live.json").read_text())
    assert live["counts"]["cercanias"] == 2
    assert live["counts"]["ld"] == 2
    assert {t["kind"] for t in live["trains"]} == {"cercanias", "ld"}

    hist = json.loads((tmp_path / "data" / "history.json").read_text())
    assert hist["points"][-1]["t"] == int(NOW.timestamp())

    assert all(s["ok"] for s in meta["sources"])
    assert meta["stale_feeds"] == ["alerts"]
    assert "no actualiza este feed" in (tmp_path / "avisos.html").read_text("utf-8")


def test_build_appends_to_published_history(tmp_path):
    routes = default_routes()
    routes["https://example.github.io/renfe-pulse/data/history.json"] = FakeResponse(
        {"points": [{"t": int(NOW.timestamp()) - 3600, "cercanias": 10}]}
    )
    build(
        tmp_path,
        session=FakeSession(routes),
        site_url="https://example.github.io/renfe-pulse/",
        now=NOW,
    )
    points = json.loads((tmp_path / "data" / "history.json").read_text())["points"]
    assert [p["cercanias"] for p in points] == [10, 2]


def test_build_survives_a_failing_source(tmp_path):
    routes = default_routes()
    del routes[sources.RIDERSHIP_CSV]
    meta = build(tmp_path, session=FakeSession(routes), now=NOW)
    failed = [s["name"] for s in meta["sources"] if not s["ok"]]
    assert failed == ["Volumen de viajeros por franja horaria"]
    assert "no estaba disponible" in (tmp_path / "viajeros.html").read_text("utf-8")


def test_build_fails_without_realtime_feeds(tmp_path):
    routes = default_routes()
    for url in (sources.VEHICLES_CERCANIAS, sources.VEHICLES_LD, sources.TRIP_UPDATES):
        del routes[url]
    with pytest.raises(BuildError):
        build(tmp_path, session=FakeSession(routes), now=NOW)


def test_embedded_json_cannot_close_script_tag(tmp_path):
    routes = default_routes()
    routes[sources.ALERTS] = FakeResponse(
        {
            "header": {"timestamp": "1"},
            "entity": [
                {
                    "id": "x",
                    "alert": {
                        "descriptionText": {
                            "translation": [{"text": "</script><b>hola</b>", "language": "es"}]
                        }
                    },
                }
            ],
        }
    )
    build(tmp_path, session=FakeSession(routes), now=NOW)
    html = (tmp_path / "avisos.html").read_text("utf-8")
    assert "</script><b>" not in html
    assert "&lt;/script&gt;&lt;b&gt;hola" in html
