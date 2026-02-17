#!/usr/bin/env python3
"""Build structured meal options JSON from legacy STALE markdown sources."""

import argparse
from meal_options_repository import CATEGORY_SOURCES, build_all_from_stale, build_category_from_stale


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Build knowledge/meal_options/*.json from sources/piano_*.md")
    p.add_argument("--category", choices=sorted(CATEGORY_SOURCES.keys()), help="Build only one category")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.category:
        path = build_category_from_stale(args.category)
        print(f"[OK] Built meal options: {path}")
        return

    generated = build_all_from_stale()
    print("[OK] Built meal options files:")
    for path in generated:
        print(f"- {path}")


if __name__ == "__main__":
    main()
