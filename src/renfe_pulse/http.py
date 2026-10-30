"""Sesión HTTP compartida con reintentos y timeouts razonables."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import __version__

USER_AGENT = f"renfe-pulse/{__version__} (+https://github.com/; datos abiertos de Renfe)"
DEFAULT_TIMEOUT = 60


class TimeoutSession(requests.Session):
    """`requests.Session` que aplica un timeout por defecto a cada petición."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        super().__init__()
        self.timeout = timeout

    def request(self, method, url, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", self.timeout)
        return super().request(method, url, **kwargs)


def make_session(retries: int = 3, timeout: float = DEFAULT_TIMEOUT) -> requests.Session:
    session = TimeoutSession(timeout)
    retry = Retry(
        total=retries,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = USER_AGENT
    return session
