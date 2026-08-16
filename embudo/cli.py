"""CLI de Embudo — `embudo stats <db>` (Fase A3; G1 la extiende).

Salida legible por humanos; `main()` devuelve el código de salida para que
scripts y CI lo consuman: 0 ok, 1 store ocupado ([D-06]), 2 uso incorrecto.
"""
from __future__ import annotations

import argparse
import sys

from embudo import __version__
from embudo.api import Embudo
from memory.sqlite_store import StoreLockedError


def _imprimir_stats(stats: dict, db: str) -> None:
    print(f"Embudo v{__version__} — {db}")
    if stats["esquema"] is not None:
        print(f"esquema: v{stats['esquema']}")
    tiers = ", ".join(f"{t} {n}" for t, n in sorted(stats["por_tier"].items()))
    print(f"claims activos: {stats['claims_activos']} ({tiers})")
    estados = ", ".join(f"{e} {n}" for e, n in sorted(stats["por_estado"].items()))
    print(f"estados: {estados}")
    if stats["eventos"] is not None:
        eventos = ", ".join(f"{t} {n}" for t, n in sorted(stats["eventos"].items()))
        print(f"eventos de custodia: {eventos}")
    if stats["conversaciones_t0"] is not None:
        print(f"conversaciones T0: {stats['conversaciones_t0']}")
    print(f"construcciones de índice: {stats['construcciones_indice']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="embudo", description="Memoria nivelada para agentes.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_stats = sub.add_parser("stats", help="resumen de salud de una memoria")
    p_stats.add_argument("db", help="ruta de la DB de claims (SQLite)")

    args = parser.parse_args(argv)
    try:
        if args.comando == "stats":
            with Embudo.open(args.db) as embudo:
                _imprimir_stats(embudo.stats(), args.db)
            return 0
    except StoreLockedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
