#!/usr/bin/env python3
"""
Rebuild completo FOOD_DB da CREA_INDEX.

Workflow:
1) Backup dei file target
2) Rebuild data/FOOD_DB.json da data/CREA_INDEX.json (fetch schede CREA)
3) Rebuild data/FOOD_DB_TO_LARN_MAPPING.json con 1 entry per alimento
4) Rigenera knowledge/food-db.md da FOOD_DB (sync)
5) Traccia summary in data/changelog.json
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from food_add import make_food_id, parse_crea_url
from sync_food_db import sync_food_db_files

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"

FOOD_DB_JSON_FILE = DATA_DIR / "FOOD_DB.json"
FOOD_DB_MAPPING_FILE = DATA_DIR / "FOOD_DB_TO_LARN_MAPPING.json"
CREA_INDEX_JSON_FILE = DATA_DIR / "CREA_INDEX.json"
FOOD_DB_MD_FILE = KNOWLEDGE_DIR / "food-db.md"
CHANGELOG_FILE = DATA_DIR / "changelog.json"

BACKUP_ROOT = DATA_DIR / "backups"


def backup_files():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = BACKUP_ROOT / f"food-db-rebuild-{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    targets = [FOOD_DB_JSON_FILE, FOOD_DB_MAPPING_FILE, FOOD_DB_MD_FILE]
    copied = []
    for src in targets:
        if src.exists():
            dst = backup_dir / src.name
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(str(dst.relative_to(ROOT)))

    return backup_dir, copied


def load_crea_index():
    if not CREA_INDEX_JSON_FILE.exists():
        raise ValueError("data/CREA_INDEX.json non trovato. Esegui prima: ./tv food crawl-index")
    payload = json.loads(CREA_INDEX_JSON_FILE.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    if not items:
        raise ValueError("data/CREA_INDEX.json presente ma vuoto")
    return items


def extract_crea_id(url):
    match = re.search(r"/tabelle-nutrizionali/(\d+)$", url)
    return match.group(1) if match else None


def build_food_entry(parsed, crea_id, assigned_id):
    return {
        "id": assigned_id,
        "name": parsed["food_name"],
        "crea_id": crea_id,
        "reference": {
            "amount": 100.0,
            "unit": "g",
            "label": parsed["reference"],
        },
        "nutrients_per_reference": {
            "kcal": float(parsed["kcal"]),
            "P": float(parsed["protein"]),
            "CHO": float(parsed["cho"]),
            "F": float(parsed["fat"]),
            "Fibre": float(parsed["fiber"]),
        },
        "data_source": "CREA",
        "source_type": "CREA",
        "source_url": parsed.get("source_url"),
        "last_verified_at": datetime.now().strftime("%Y-%m-%d"),
    }


def build_mapping_entry(food_id, food_name):
    return {
        "food_db_id": food_id,
        "food_db_name": food_name,
        "larn_portion_id": None,
        "operational_portion_id": None,
        "note": "Auto-generated from CREA full rebuild. Assegna larn_portion_id o operational_portion_id.",
    }


def rebuild():
    items = load_crea_index()

    foods = []
    mapping = []
    failures = []
    used_ids = set()
    used_names = set()

    total = len(items)
    for idx, item in enumerate(items, 1):
        url = item["url"]
        crea_id = item.get("crea_id") or extract_crea_id(url)
        try:
            parsed = parse_crea_url(url)
            name = parsed["food_name"]

            base_id = make_food_id(name) or f"crea_{crea_id or idx}"
            assigned_id = base_id
            if assigned_id in used_ids:
                assigned_id = f"{base_id}_{crea_id}" if crea_id else f"{base_id}_{idx}"
            if assigned_id in used_ids:
                raise ValueError(f"ID collision non risolta per '{name}'")

            if name in used_names:
                raise ValueError(f"Nome duplicato in import CREA: {name}")

            food_entry = build_food_entry(parsed, crea_id, assigned_id)
            foods.append(food_entry)
            mapping.append(build_mapping_entry(assigned_id, name))
            used_ids.add(assigned_id)
            used_names.add(name)

            if idx % 50 == 0 or idx == total:
                print(f"[{idx}/{total}] OK")

            time.sleep(0.05)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                {
                    "url": url,
                    "crea_id": crea_id,
                    "name_from_index": item.get("name"),
                    "error": str(exc),
                }
            )
            print(f"[{idx}/{total}] FAIL {url} -> {exc}")

    food_db = {
        "meta": {
            "name": "FOOD_DB",
            "source_of_truth": "CREA full rebuild from CREA_INDEX.json",
            "units": ["g", "mL"],
            "nutrition_fields": ["kcal", "P", "CHO", "F", "Fibre"],
            "rules": {
                "use_only_food_db_for_nutrition": True,
                "if_food_missing_fail": True,
            },
            "generated_at": datetime.now().isoformat(),
            "generated_from": str(CREA_INDEX_JSON_FILE.relative_to(ROOT)),
            "imported_count": len(foods),
            "failed_count": len(failures),
        },
        "foods": foods,
    }

    mapping_db = {
        "meta": {
            "name": "FOOD_DB_TO_LARN_MAPPING",
            "food_db": "FOOD_DB.json",
            "larn_portions": "LARN_PORTIONS.json",
            "operational_portions": "OPERATIVE_PORTIONS.json",
            "version": "v2",
            "generated_at": datetime.now().isoformat(),
            "generated_from_food_db_count": len(foods),
        },
        "mapping": mapping,
    }

    FOOD_DB_JSON_FILE.write_text(json.dumps(food_db, indent=2, ensure_ascii=False), encoding="utf-8")
    FOOD_DB_MAPPING_FILE.write_text(json.dumps(mapping_db, indent=2, ensure_ascii=False), encoding="utf-8")
    sync_food_db_files(write=True)

    failures_file = None
    if failures:
        failures_file = DATA_DIR / "CREA_IMPORT_FAILURES.json"
        failures_file.write_text(json.dumps({"failures": failures}, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "total_index": total,
        "imported": len(foods),
        "failed": len(failures),
        "failures_file": str(failures_file.relative_to(ROOT)) if failures_file else None,
    }


def append_changelog(details):
    payload = json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))
    payload.setdefault("entries", []).append(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "food rebuild-from-crea",
            "details": details,
        }
    )
    CHANGELOG_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    backup_dir, copied = backup_files()
    print(f"[BACKUP] cartella: {backup_dir}")
    for path in copied:
        print(f"  - {path}")

    summary = rebuild()
    summary["backup_dir"] = str(backup_dir.relative_to(ROOT))
    summary["updated_files"] = [
        "data/FOOD_DB.json",
        "data/FOOD_DB_TO_LARN_MAPPING.json",
        "knowledge/food-db.md",
    ]
    append_changelog(summary)

    print()
    print("[SUMMARY]")
    print(
        f"index={summary['total_index']} imported={summary['imported']} failed={summary['failed']}"
    )
    if summary["failures_file"]:
        print(f"failures_file={summary['failures_file']}")
    print(f"backup_dir={summary['backup_dir']}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Errore: {exc}")
        sys.exit(1)
