"""Cliente mínimo de la API CKAN de https://data.renfe.com."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import requests

BASE_URL = "https://data.renfe.com/api/3/action"
PORTAL_URL = "https://data.renfe.com/dataset"

# Formatos que publican datos en tiempo real (se actualizan cada pocos segundos).
REALTIME_FORMATS = {"GTFS-RT", "PB"}


class CkanError(RuntimeError):
    pass


class CkanClient:
    def __init__(self, session: requests.Session, base_url: str = BASE_URL) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")

    def call(self, action: str, **params: Any) -> Any:
        resp = self.session.get(f"{self.base_url}/{action}", params=params)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise CkanError(f"{action} falló: {payload.get('error')}")
        return payload["result"]

    def package_list(self) -> list[str]:
        return self.call("package_list")

    def package_show(self, name: str) -> dict[str, Any]:
        return self.call("package_show", id=name)

    def packages(self, page_size: int = 100) -> list[dict[str, Any]]:
        """Todos los datasets con sus recursos, paginando `package_search`."""
        out: list[dict[str, Any]] = []
        start = 0
        while True:
            result = self.call("package_search", rows=page_size, start=start)
            out.extend(result["results"])
            start += page_size
            if start >= result["count"] or not result["results"]:
                return out

    def datastore_records(self, resource_id: str, page_size: int = 1000) -> Iterator[dict]:
        """Recorre todos los registros de un recurso cargado en el DataStore."""
        offset = 0
        while True:
            result = self.call(
                "datastore_search", resource_id=resource_id, limit=page_size, offset=offset
            )
            records = result["records"]
            yield from records
            offset += len(records)
            if not records or offset >= result.get("total", 0):
                return


@dataclass
class Resource:
    name: str
    format: str
    url: str
    datastore: bool


@dataclass
class Dataset:
    name: str
    title: str
    description: str
    modified: str
    url: str
    realtime: bool
    tags: list[str] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)

    @property
    def formats(self) -> list[str]:
        return sorted({r.format for r in self.resources if r.format})


def summarize(pkg: dict[str, Any]) -> Dataset:
    resources = [
        Resource(
            name=(r.get("name") or "").strip(),
            format=(r.get("format") or "").strip().upper(),
            url=r.get("url") or "",
            datastore=bool(r.get("datastore_active")),
        )
        for r in pkg.get("resources", [])
    ]
    notes = (pkg.get("notes") or "").strip()
    # Las descripciones vienen en Markdown; nos quedamos con el primer párrafo, sin énfasis.
    description = notes.split("\n\n")[0].replace("__", "").replace("**", "").strip()
    return Dataset(
        name=pkg["name"],
        title=(pkg.get("title") or pkg["name"]).strip(),
        description=description,
        modified=pkg.get("metadata_modified") or "",
        url=f"{PORTAL_URL}/{pkg['name']}",
        realtime=any(r.format in REALTIME_FORMATS for r in resources),
        tags=sorted(t["display_name"] for t in pkg.get("tags", []) if t.get("display_name")),
        resources=resources,
    )
