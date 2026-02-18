#!/usr/bin/env python3
"""Generate display_name (3rd column) for food_mapped.md from FOOD_DB.json names.

Reads existing food_mapped.md (2 or 3 columns), reads FOOD_DB.json for CREA names,
cleans them into user-friendly display names, and writes back food_mapped.md with
3 columns: food_db_id|larn_portion_id|display_name.

If a row already has a 3rd column it is preserved (manual override) unless --force
is passed.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
FOOD_DB_JSON = DATA_DIR / "FOOD_DB.json"
MAPPED_FILE = DATA_DIR / "food_mapped.md"


def clean_crea_name(raw: str) -> str:
    """Turn a raw CREA name into a clean display name.

    Examples:
        'Agnello, coscio, cotto, al forno' → 'Agnello coscio cotto al forno'
        'Aceto (di vino rosso)'            → 'Aceto di vino rosso'
        '"|Caramelle tipo ""mou""|"'       → 'Caramelle tipo mou'
    """
    name = raw.strip().strip('"').strip("|").strip()
    # Remove doubled quotes (CREA CSV artefact)
    name = name.replace('""', '')
    # Integrate parentheticals: "(di vino rosso)" → "di vino rosso"
    name = re.sub(r'\(([^)]+)\)', r'\1', name)
    # Replace CREA comma separators with spaces
    name = name.replace(', ', ' ')
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    # Capitalize first letter only
    if name:
        name = name[0].upper() + name[1:]
    return name


def load_crea_names() -> dict[str, str]:
    """Return {food_db_id: cleaned_display_name} from FOOD_DB.json."""
    db = json.loads(FOOD_DB_JSON.read_text(encoding="utf-8"))
    names = {}
    for food in db.get("foods", []):
        fid = food.get("id")
        raw_name = food.get("name", "")
        if fid:
            names[fid] = clean_crea_name(raw_name)
    return names


def run(force: bool = False):
    crea_names = load_crea_names()
    lines_in = MAPPED_FILE.read_text(encoding="utf-8").splitlines()
    lines_out = []
    added = 0
    preserved = 0
    overwritten = 0

    for raw in lines_in:
        txt = raw.strip()
        if not txt or txt.startswith("#"):
            lines_out.append(raw)
            continue
        parts = [p.strip() for p in txt.split("|")]
        if len(parts) == 3 and parts[2] and not force:
            # Already has display_name — preserve
            lines_out.append(f"{parts[0]}|{parts[1]}|{parts[2]}")
            preserved += 1
        elif len(parts) >= 2:
            fid = parts[0]
            lid = parts[1]
            dname = crea_names.get(fid, fid.replace("_", " ").title())
            lines_out.append(f"{fid}|{lid}|{dname}")
            if len(parts) == 3 and parts[2]:
                overwritten += 1
            else:
                added += 1
        else:
            lines_out.append(raw)

    MAPPED_FILE.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(f"[OK] food_mapped.md updated: {added} generated, {preserved} preserved, {overwritten} overwritten")
    print(f"     Total lines: {len(lines_out)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate display names for food_mapped.md")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing display names with cleaned CREA names")
    args = parser.parse_args()
    run(force=args.force)
