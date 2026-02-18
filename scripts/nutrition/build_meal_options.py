#!/usr/bin/env python3
"""Legacy command placeholder. Meal options JSON are the single source-of-truth."""

import argparse

from scripts.nutrition.meal_options_repository import CATEGORY_SOURCES


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Legacy archived command (JSON meal options are source-of-truth)")
    p.add_argument("--category", choices=sorted(CATEGORY_SOURCES.keys()), help="Build only one category")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    target = args.category or "all"
    print(f"[ERR] Comando archiviato: build-options ({target})")
    print("knowledge/meal_options/*.json e' l'unica source-of-truth (runtime/build/migrazioni).")
    print("Per aggiornamenti, modifica direttamente i JSON versionati.")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
