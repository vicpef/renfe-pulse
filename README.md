# Renfe Pulse

Panel estático con los [datos abiertos de Renfe](https://data.renfe.com/dataset), generado
en Python y publicado en GitHub Pages. Un workflow de GitHub Actions lo regenera **cada hora**
con los datos en tiempo real.

| Página | Qué muestra | Datasets de Renfe |
|---|---|---|
| **Resumen** | Trenes en circulación, puntualidad de Cercanías, histórico de 30 días | todos los de tiempo real |
| **Mapa** | Posición de cada tren con su línea, estado, próxima parada y retraso | `ubicacion-vehiculos`, `posicion-vehiculos-av-ld-md`, `horarios-cercanias`, `horarios-de-alta-velocidad-larga-distancia-y-media-distancia` |
| **Retrasos** | Puntualidad por núcleo y línea, distribución, trenes más retrasados, cancelaciones | `horarios-viaje-cercanias` |
| **Avisos** | Incidencias con las líneas afectadas, filtrables | `incidencias-avisos` |
| **Estaciones** | Buscador y mapa de todas las estaciones | `estaciones-listado-completo` |
| **Viajeros** | Perfil horario de subidas/bajadas por núcleo (2018) | `volumen-de-viajeros-por-franja-horaria-estaciones-de-cercanias` |
| **Catálogo** | Todos los datasets del portal, vía la API CKAN | API `package_search` |

Además publica los datos ya procesados en `data/*.json` (trenes, retrasos, avisos, histórico…)
para quien quiera reutilizarlos.

## Cómo funciona

```
GitHub Actions (cada hora)
  └─ python -m renfe_pulse build
       ├─ API CKAN de data.renfe.com ........ catálogo de datasets
       ├─ GTFS estáticos (zip) .............. líneas, colores, paradas, recorridos AV/LD
       ├─ GTFS-Realtime (JSON) .............. posiciones, retrasos, avisos
       ├─ CSV de estaciones y de viajeros
       ├─ data/history.json ya publicado .... + el punto de esta hora = histórico
       └─ Jinja2 → _site/ (HTML + JSON) → actions/deploy-pages
```

El código está en [`src/renfe_pulse`](src/renfe_pulse):

- `ckan.py`: cliente de la API CKAN (`package_search`, `datastore_search`).
- `realtime.py`, `gtfs.py`: lectura de los feeds GTFS-Realtime y de los GTFS estáticos
  (solo las tablas pequeñas; el `stop_times.txt` de Cercanías ocupa ~300 MB).
- `nucleos.py`: núcleo, tren y línea a partir de los `trip_id` de Cercanías.
- `report.py`: cruces y cálculos (puntualidad, líneas afectadas por avisos…), sin red.
- `build.py`: orquesta todo y genera el sitio. Si una fuente falla, el resto se publica
  igualmente y queda reflejado en *Catálogo → Fuentes*; si fallan todos los feeds en tiempo
  real, el build falla y se mantiene la versión anterior publicada.
- `templates/` y `static/`: páginas, estilos (modo claro/oscuro) y JS (Leaflet, Chart.js).

### Particularidades de los datos de Renfe

- El `timestamp` de cabecera del feed de AV/LD/MD llega desplazado una hora; se usa la
  cabecera HTTP `Last-Modified` como hora real de actualización.
- El feed de avisos a veces deja de actualizarse durante semanas; el sitio lo indica cuando
  lleva más de 24 h parado.
- Los GTFS rellenan los campos con espacios y el CSV de estaciones está en latin-1.
- En el GTFS de AV/LD el `route_id` empieza por los códigos de estación de origen y destino.
- Los feeds no permiten CORS, por eso los datos se descargan en el build (Python) y no desde
  el navegador.

## Desarrollo local

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/python -m renfe_pulse build --out _site
python -m http.server 8000 --directory _site
```

Con `--site-url https://<usuario>.github.io/renfe-pulse/` el build parte del histórico ya
publicado.

## Publicación

1. *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
2. El workflow [`pages.yml`](.github/workflows/pages.yml) se ejecuta en cada push a `main`,
   cada hora y a mano (*Actions → Publicar sitio → Run workflow*).

Notas:

- GitHub Pages en un repositorio **privado** requiere un plan de pago (Pro, Team o
  Enterprise). Aun así, el sitio publicado es público salvo en Enterprise Cloud.
- Las ejecuciones programadas consumen minutos de Actions (≈1 min por ejecución, unos
  720 min/mes). Para reducirlo, cambia el `cron` del workflow.
- GitHub desactiva los workflows programados tras 60 días sin actividad en el repositorio.

## Licencias

Datos: © Renfe, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.es). Mapas:
© colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright). Proyecto no
oficial, sin relación con Renfe.
