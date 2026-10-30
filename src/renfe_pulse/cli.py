"""Línea de comandos: `python -m renfe_pulse build --out _site`."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .build import BuildError, build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="renfe-pulse", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="descarga los datos y genera el sitio estático")
    b.add_argument("--out", type=Path, default=Path("_site"), help="carpeta de salida")
    b.add_argument(
        "--site-url",
        default=os.environ.get("SITE_URL"),
        help="URL pública del sitio, para recuperar el histórico ya publicado",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.command == "build":
        try:
            build(args.out, site_url=args.site_url or None)
        except BuildError as exc:
            logging.error("%s", exc)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
