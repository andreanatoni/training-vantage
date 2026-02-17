#!/usr/bin/env python3
"""Legacy CLI entrypoint (archived)."""

import sys


def main() -> int:
    print("[ERR] scripts/cli.py e' archiviato e non supportato.")
    print("Usa il dispatcher ufficiale: ./tv")
    print("Esempi:")
    print("  ./tv help")
    print("  ./tv plan rest")
    print("  ./tv status")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

