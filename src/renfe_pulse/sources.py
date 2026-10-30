"""URLs de los recursos de data.renfe.com que usa el sitio.

Los feeds GTFS-Realtime y los GTFS estáticos no están en el DataStore de CKAN:
se descargan directamente desde los servidores de Renfe que enlaza cada dataset.
"""

GTFSRT = "https://gtfsrt.renfe.com"

# Tiempo real (dataset: ubicacion-vehiculos, posicion-vehiculos-av-ld-md,
# horarios-viaje-cercanias, incidencias-avisos)
VEHICLES_CERCANIAS = f"{GTFSRT}/vehicle_positions.json"
VEHICLES_LD = f"{GTFSRT}/vehicle_positions_LD.json"
TRIP_UPDATES = f"{GTFSRT}/trip_updates.json"
ALERTS = f"{GTFSRT}/alerts.json"

# Horarios GTFS (datasets: horarios-cercanias, horarios-de-alta-velocidad-...)
GTFS_CERCANIAS = "https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip"
GTFS_LD = "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip"

# Estaciones (dataset: estaciones-listado-completo)
STATIONS_CSV = "https://ssl.renfe.com/ftransit/Fichero_estaciones/estaciones.csv"

# Volumen de viajeros por franja horaria en estaciones de Cercanías, año 2018
# (dataset: volumen-de-viajeros-por-franja-horaria-estaciones-de-cercanias)
RIDERSHIP_CSV = (
    "https://data.renfe.com/dataset/bad45d4d-b809-40bd-8abb-d7f2c8bc9214/resource/"
    "566dcfa2-4c02-48bf-99c9-a7606a097073/download/viajeros_por_franja_csv.csv"
)
