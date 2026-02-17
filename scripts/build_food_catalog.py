#!/usr/bin/env python3
"""Build derived FOOD_CATALOG.json from existing nutrition datasets."""

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

FOOD_DB_JSON = DATA_DIR / "FOOD_DB.json"
MAPPING_JSON = DATA_DIR / "FOOD_DB_TO_LARN_MAPPING.json"
LARN_JSON = DATA_DIR / "LARN_PORTIONS.json"
LIMITS_JSON = DATA_DIR / "PERSONAL_LIMITS.json"
OUTPUT_JSON = DATA_DIR / "FOOD_CATALOG.json"


def now_iso():
    return datetime.now().isoformat()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(output_path: Path, strict: bool = True, dry_run: bool = False):
    food_db = load_json(FOOD_DB_JSON)
    mapping_db = load_json(MAPPING_JSON)
    larn_db = load_json(LARN_JSON)
    limits_db = load_json(LIMITS_JSON)

    foods = food_db.get("foods", [])
    food_by_id = {f.get("id"): f for f in foods if f.get("id")}

    mapping_entries = mapping_db.get("mapping", [])
    mapping_by_food = {m.get("food_db_id"): m for m in mapping_entries if m.get("food_db_id")}

    larn_portions = larn_db.get("portions", [])
    larn_by_id = {p.get("id"): p for p in larn_portions if p.get("id")}

    limits_entries = limits_db.get("limits", [])
    limits_by_food = {e.get("food_db_id"): e for e in limits_entries if e.get("food_db_id")}

    missing_mapping = []
    invalid_larn_mapping = []

    catalog_foods = []

    for fid in sorted(food_by_id.keys()):
        food = food_by_id[fid]
        mapping = mapping_by_food.get(fid)
        larn_id = None
        larn_portion = None

        if not mapping:
            missing_mapping.append(fid)
        else:
            larn_id = mapping.get("larn_portion_id")
            if not larn_id or larn_id not in larn_by_id:
                invalid_larn_mapping.append(fid)
            else:
                larn_portion = larn_by_id[larn_id]

        personal_limit = limits_by_food.get(fid)

        catalog_food = {
            "id": fid,
            "name": food.get("name"),
            "reference": food.get("reference"),
            "nutrients_per_reference": food.get("nutrients_per_reference"),
            "data_source": food.get("data_source"),
            "source_type": food.get("source_type"),
            "source_url": food.get("source_url"),
            "last_verified_at": food.get("last_verified_at"),
            "portion": {
                "larn_portion_id": larn_id,
                "group": larn_portion.get("group") if larn_portion else None,
                "item_label": larn_portion.get("item_label") if larn_portion else None,
                "standard": larn_portion.get("standard") if larn_portion else None,
                "practical": larn_portion.get("practical") if larn_portion else [],
                "source": larn_portion.get("source") if larn_portion else None,
            },
            "mapping": {
                "review_status": mapping.get("review_status") if mapping else None,
                "mapping_confidence": mapping.get("mapping_confidence") if mapping else None,
                "mapping_source": mapping.get("mapping_source") if mapping else None,
                "last_reviewed_at": mapping.get("last_reviewed_at") if mapping else None,
                "note": mapping.get("note") if mapping else None,
            },
            "personal_limits": personal_limit,
        }
        catalog_foods.append(catalog_food)

    stats = {
        "foods_total": len(foods),
        "mappings_total": len(mapping_entries),
        "larn_portions_total": len(larn_by_id),
        "limits_total": len(limits_entries),
        "catalog_foods_total": len(catalog_foods),
        "missing_mapping_count": len(missing_mapping),
        "invalid_larn_mapping_count": len(invalid_larn_mapping),
    }

    report = {
        "meta": {
            "version": "v0-shadow",
            "generated_at": now_iso(),
            "strict": strict,
            "derived": True,
            "sources": {
                "food_db": str(FOOD_DB_JSON.relative_to(ROOT)),
                "mapping": str(MAPPING_JSON.relative_to(ROOT)),
                "larn": str(LARN_JSON.relative_to(ROOT)),
                "personal_limits": str(LIMITS_JSON.relative_to(ROOT)),
            },
        },
        "stats": stats,
        "issues": {
            "missing_mapping_preview": missing_mapping[:100],
            "invalid_larn_mapping_preview": invalid_larn_mapping[:100],
        },
        "foods": catalog_foods,
    }

    failed = bool(missing_mapping or invalid_larn_mapping)
    if strict and failed:
        # Write report anyway if not dry-run? we keep behavior consistent and don't write catalog on strict fail.
        if not dry_run:
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(
            "[ERR] FOOD_CATALOG build failed in strict mode: "
            f"missing_mapping={len(missing_mapping)} invalid_larn_mapping={len(invalid_larn_mapping)}"
        )

    if not dry_run:
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return report


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Build derived FOOD_CATALOG.json")
    p.add_argument("--output", default=str(OUTPUT_JSON), help="Output JSON path (default: data/FOOD_CATALOG.json)")
    p.add_argument("--dry-run", action="store_true", help="Validate/build in memory without writing file")
    p.add_argument(
        "--no-strict",
        action="store_true",
        help="Allow missing/invalid mappings (still reported in issues)",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    report = run(Path(args.output), strict=not args.no_strict, dry_run=bool(args.dry_run))
    s = report["stats"]
    print("[OK] FOOD_CATALOG build completed.")
    print(f"- output: {Path(args.output)}")
    print(f"- foods_total: {s['foods_total']}")
    print(f"- missing_mapping_count: {s['missing_mapping_count']}")
    print(f"- invalid_larn_mapping_count: {s['invalid_larn_mapping_count']}")


if __name__ == "__main__":
    main()
