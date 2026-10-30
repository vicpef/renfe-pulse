/* Renfe Pulse: interacción de las páginas generadas (mapas, gráficos y filtros). */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const nf = new Intl.NumberFormat("es-ES");
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const readJson = (id) => {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  };
  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const norm = (value) => String(value ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const debounce = (fn, ms = 120) => {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  };
  const linePill = (name, bg, fg) => `<span class="line" style="background:${esc(bg)};color:${esc(fg)}">${esc(name)}</span>`;
  const delayText = (seconds) => (seconds == null ? "—" : `+${Math.round(seconds / 60)} min`);

  const GROUP_VARS = { "Alta Velocidad": "--series-1", "Larga Distancia": "--series-2", "Media Distancia": "--series-3" };

  /* ---------- Gráficos (Chart.js) ---------- */

  // Línea vertical que sigue al tooltip, para leer todas las series de un mismo instante.
  const crosshair = {
    id: "crosshair",
    afterDatasetsDraw(chart) {
      const active = chart.tooltip && chart.tooltip.getActiveElements();
      if (!active || !active.length) return;
      const { ctx, chartArea } = chart;
      const x = active[0].element.x;
      ctx.save();
      ctx.strokeStyle = css("--text-3");
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  function lineChart(container, labels, datasets, { yMax, ySuffix = "" } = {}) {
    const canvas = document.createElement("canvas");
    container.appendChild(canvas);
    const grid = css("--border");
    const muted = css("--text-3");
    return new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: datasets.map((d) => ({
          borderColor: d.color,
          backgroundColor: d.color,
          pointBackgroundColor: d.color,
          pointBorderColor: css("--surface"),
          pointBorderWidth: 2,
          ...d,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        elements: {
          line: { borderWidth: 2, tension: 0.25 },
          point: { radius: labels.length > 60 ? 0 : 2.5, hoverRadius: 5, hitRadius: 10 },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: css("--surface"),
            titleColor: css("--text"),
            bodyColor: css("--text-2"),
            borderColor: grid,
            borderWidth: 1,
            padding: 10,
            boxPadding: 4,
            usePointStyle: true,
            callbacks: {
              label: (item) => ` ${item.dataset.label}: ${item.raw == null ? "—" : nf.format(item.raw)}${ySuffix}`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { color: grid },
            ticks: { color: muted, maxRotation: 0, autoSkip: true, maxTicksLimit: 6 },
          },
          y: {
            beginAtZero: true,
            max: yMax,
            grid: { color: grid },
            border: { display: false },
            ticks: { color: muted, maxTicksLimit: 5, callback: (v) => nf.format(v) + ySuffix },
          },
        },
      },
      plugins: [crosshair],
    });
  }

  function emptyState(container, text) {
    container.innerHTML = `<p class="empty">${esc(text)}</p>`;
  }

  function initHistory() {
    const points = readJson("history-data");
    const trains = $("#chart-trains");
    const punctuality = $("#chart-punctuality");
    if (!points || !trains) return;
    if (points.length < 2 || typeof Chart === "undefined") {
      const msg = "El histórico se irá llenando con cada actualización horaria.";
      emptyState(trains, msg);
      emptyState(punctuality, msg);
      return;
    }
    const labels = points.map((p) =>
      new Date(p.t * 1000).toLocaleString("es-ES", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid",
      })
    );
    lineChart(trains, labels, [
      { label: "Cercanías", data: points.map((p) => p.cercanias), color: css("--series-1") },
      { label: "AV, LD y MD", data: points.map((p) => p.ld), color: css("--series-2") },
    ]);
    lineChart(
      punctuality,
      labels,
      [{ label: "Puntualidad", data: points.map((p) => p.punctual_pct), color: css("--series-1") }],
      { yMax: 100, ySuffix: " %" }
    );
  }

  function initRidership() {
    const nucleos = readJson("ridership-data");
    const select = $("#rider-nucleo");
    const box = $("#chart-rider");
    if (!nucleos || !select || !box || typeof Chart === "undefined") return;
    let chart;
    const render = () => {
      const n = nucleos[Number(select.value)];
      $("#rider-total").textContent = `${nf.format(n.total)} viajeros al día`;
      const labels = n.profile.map((p) => p.slot.split(" - ")[0]);
      if (chart) chart.destroy();
      box.innerHTML = "";
      chart = lineChart(box, labels, [
        { label: "Suben", data: n.profile.map((p) => p.up), color: css("--series-1") },
        { label: "Bajan", data: n.profile.map((p) => p.down), color: css("--series-2") },
      ]);
      const top = n.stations.length ? n.stations[0].total : 1;
      $("#rider-stations").innerHTML = n.stations
        .map(
          (s) => `<li class="bar-row" title="${esc(s.name)}: ${nf.format(s.total)} viajeros">
            <span class="name">${esc(s.name)}</span>
            <span class="bar-track"><span class="bar-fill" style="width:${(100 * s.total) / top}%"></span></span>
            <span class="val">${nf.format(s.total)}</span></li>`
        )
        .join("");
    };
    select.addEventListener("change", render);
    render();
  }

  /* ---------- Mapas (Leaflet) ---------- */

  function baseMap(id) {
    const map = L.map(id, { preferCanvas: true, worldCopyJump: false }).setView([40.2, -3.7], 6);
    // Teselas estándar de OpenStreetMap; style.css las desatura (y las invierte en modo oscuro)
    // para que destaquen los colores de las líneas.
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    return map;
  }

  function trainPopup(t) {
    if (t.kind === "cercanias") {
      const where = t.stop ? `${esc(t.status)} ${esc(t.stop)}` : esc(t.status);
      const platform = t.platform ? ` · vía ${esc(t.platform)}` : "";
      const delay = t.delay == null ? "" : `<div class="pop-row">Retraso: <strong>${delayText(t.delay)}</strong></div>`;
      return `<div class="pop-title">${linePill(t.line, t.color, t.textColor)} Tren ${esc(t.train)}</div>
        <div class="pop-row">Cercanías ${esc(t.nucleo)}</div>
        <div class="pop-row">${where}${platform}</div>${delay}`;
    }
    const route = t.origin && t.destination ? `<div class="pop-row">${esc(t.origin)} → ${esc(t.destination)}</div>` : "";
    const where = t.stop ? `${esc(t.status)} ${esc(t.stop)}` : esc(t.status);
    return `<div class="pop-title"><span class="swatch diamond" style="background:${css(GROUP_VARS[t.group])}"></span>${esc(t.product)} ${esc(t.train)}</div>
      ${route}<div class="pop-row">${where}</div>`;
  }

  function stationLayer(points) {
    const group = L.layerGroup();
    const color = css("--station");
    for (const [code, name, lat, lon] of points) {
      L.circleMarker([lat, lon], { radius: 3, stroke: false, fillColor: color, fillOpacity: 0.7 })
        .bindTooltip(`${esc(name)} (${esc(code)})`)
        .addTo(group);
    }
    return group;
  }

  function initTrainMap() {
    const trains = readJson("trains-data");
    if (!trains || !$("#map") || typeof L === "undefined") return;
    const map = baseMap("map");
    const surface = css("--surface");
    const layers = {
      cercanias: L.layerGroup(),
      "Alta Velocidad": L.layerGroup(),
      "Larga Distancia": L.layerGroup(),
      "Media Distancia": L.layerGroup(),
    };
    const markers = new Map();

    for (const t of trains) {
      let marker;
      if (t.kind === "cercanias") {
        marker = L.circleMarker([t.lat, t.lon], {
          radius: 5.5, fillColor: t.color, fillOpacity: 1, color: surface, weight: 1.5,
        });
        marker.addTo(layers.cercanias);
      } else {
        const icon = L.divIcon({
          className: "",
          html: `<div class="ld-marker" style="background:${css(GROUP_VARS[t.group])}"></div>`,
          iconSize: [12, 12],
          iconAnchor: [6, 6],
        });
        marker = L.marker([t.lat, t.lon], { icon, keyboard: false, title: `${t.product} ${t.train}` });
        marker.addTo(layers[t.group] || layers["Media Distancia"]);
      }
      marker.bindPopup(trainPopup(t));
      markers.set(`${t.kind}-${t.id}`, marker);
    }
    Object.values(layers).forEach((l) => l.addTo(map));
    if (trains.length) map.fitBounds(L.latLngBounds(trains.map((t) => [t.lat, t.lon])), { padding: [20, 20] });

    let stations;
    $$("input[data-layer]").forEach((input) => {
      input.addEventListener("change", () => {
        const key = input.dataset.layer;
        if (key === "stations") {
          stations = stations || stationLayer(readJson("stations-data") || []);
          input.checked ? stations.addTo(map) : stations.remove();
          return;
        }
        input.checked ? layers[key].addTo(map) : layers[key].remove();
      });
    });

    const select = $("#nucleo-filter");
    const byNucleo = {};
    trains.filter((t) => t.nucleo).forEach((t) => (byNucleo[t.nucleo] = byNucleo[t.nucleo] || []).push([t.lat, t.lon]));
    Object.keys(byNucleo).sort((a, b) => a.localeCompare(b, "es")).forEach((n) => select.add(new Option(`${n} (${byNucleo[n].length})`, n)));
    select.addEventListener("change", () => {
      const pts = select.value ? byNucleo[select.value] : trains.map((t) => [t.lat, t.lon]);
      if (pts && pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [30, 30], maxZoom: 12 });
    });

    initTrainTable(trains, (key) => {
      const marker = markers.get(key);
      if (!marker) return;
      document.getElementById("map").scrollIntoView({ behavior: "smooth", block: "center" });
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 11));
      marker.openPopup();
    });
  }

  function initTrainTable(trains, onSelect) {
    const tbody = $("#train-table tbody");
    const search = $("#train-search");
    const count = $("#train-count");
    if (!tbody) return;
    const sorted = [...trains].sort((a, b) =>
      (a.kind + (a.nucleo || a.group) + (a.line || a.product)).localeCompare(b.kind + (b.nucleo || b.group) + (b.line || b.product), "es")
    );
    tbody.innerHTML = sorted
      .map((t) => {
        const service = t.kind === "cercanias"
          ? linePill(t.line, t.color, t.textColor)
          : `<span class="tag">${esc(t.product)}</span>`;
        const zone = t.kind === "cercanias" ? esc(t.nucleo) : t.origin ? `${esc(t.origin)} → ${esc(t.destination)}` : "—";
        const where = t.stop ? `${esc(t.status)} ${esc(t.stop)}` : esc(t.status);
        const text = norm([t.line, t.product, t.train, t.nucleo, t.origin, t.destination, t.stop, t.group].join(" "));
        return `<tr data-key="${esc(t.kind)}-${esc(t.id)}" data-text="${esc(text)}" style="cursor:pointer">
          <td>${service}</td><td>${esc(t.train)}</td><td>${zone}</td><td>${where}</td>
          <td class="num">${t.kind === "cercanias" ? delayText(t.delay) : "—"}</td></tr>`;
      })
      .join("");
    const rows = $$("tr", tbody);
    const apply = () => {
      const q = norm(search.value.trim());
      let shown = 0;
      rows.forEach((r) => {
        const ok = !q || r.dataset.text.includes(q);
        r.hidden = !ok;
        shown += ok;
      });
      count.textContent = `${nf.format(shown)} de ${nf.format(rows.length)} trenes`;
    };
    search.addEventListener("input", debounce(apply));
    tbody.addEventListener("click", (e) => {
      const row = e.target.closest("tr[data-key]");
      if (row) onSelect(row.dataset.key);
    });
    apply();
  }

  function initStations() {
    const table = $("#station-table");
    if (!table) return;
    const points = readJson("stations-data") || [];
    const search = $("#station-search");
    const province = $("#station-province");
    const onlyCercanias = $("#station-cercanias");
    const count = $("#station-count");
    const rows = $$("tbody tr", table).map((r) => ({ el: r, text: norm(r.textContent), code: r.dataset.code }));

    let map, layer;
    const markers = new Map();
    if ($("#station-map") && typeof L !== "undefined") {
      map = baseMap("station-map");
      layer = L.layerGroup().addTo(map);
      const color = css("--accent");
      for (const [code, name, lat, lon] of points) {
        markers.set(code, L.circleMarker([lat, lon], { radius: 3.5, stroke: false, fillColor: color, fillOpacity: 0.75 }).bindTooltip(esc(name)));
      }
    }

    const apply = () => {
      const q = norm(search.value.trim());
      const prov = province.value;
      const cer = onlyCercanias.checked;
      let shown = 0;
      const visible = [];
      rows.forEach((r) => {
        const ok = (!q || r.text.includes(q)) && (!prov || r.el.dataset.province === prov) && (!cer || r.el.dataset.cercanias === "1");
        r.el.hidden = !ok;
        if (ok) {
          shown++;
          const m = markers.get(r.code);
          if (m) visible.push(m);
        }
      });
      count.textContent = `${nf.format(shown)} de ${nf.format(rows.length)} estaciones`;
      if (map) {
        layer.clearLayers();
        visible.forEach((m) => layer.addLayer(m));
        if (visible.length && (q || prov || cer)) {
          map.fitBounds(L.latLngBounds(visible.map((m) => m.getLatLng())), { padding: [20, 20], maxZoom: 13 });
        }
      }
    };
    search.addEventListener("input", debounce(apply, 200));
    province.addEventListener("change", apply);
    onlyCercanias.addEventListener("change", apply);
    apply();
    if (map && markers.size) map.fitBounds(L.latLngBounds([...markers.values()].map((m) => m.getLatLng())), { padding: [10, 10] });
  }

  /* ---------- Filtros de listas y tablas ---------- */

  function initAlerts() {
    const list = $("#alert-list");
    if (!list) return;
    const items = $$(".alert", list).map((el) => ({ el, text: norm(el.textContent) }));
    const search = $("#alert-search");
    const nucleo = $("#alert-nucleo");
    const kind = $("#alert-kind");
    const apply = () => {
      const q = norm(search.value.trim());
      let shown = 0;
      items.forEach(({ el, text }) => {
        const ok = (!q || text.includes(q))
          && (!nucleo.value || el.dataset.nucleos.split("|").includes(nucleo.value))
          && (!kind.value || el.dataset.kind === kind.value);
        el.hidden = !ok;
        shown += ok;
      });
      $("#alert-count").textContent = `${nf.format(shown)} de ${nf.format(items.length)} avisos`;
    };
    search.addEventListener("input", debounce(apply));
    nucleo.addEventListener("change", apply);
    kind.addEventListener("change", apply);
  }

  function initTableFilters() {
    $$("select[data-filter-table]").forEach((select) => {
      const table = document.getElementById(select.dataset.filterTable);
      const key = select.dataset.filterKey;
      select.addEventListener("change", () => {
        $$("tbody tr", table).forEach((r) => (r.hidden = !!select.value && r.dataset[key] !== select.value));
      });
    });
  }

  initHistory();
  initRidership();
  initTrainMap();
  initStations();
  initAlerts();
  initTableFilters();
})();
