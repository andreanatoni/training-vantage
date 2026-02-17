#!/usr/bin/env python3
"""Manual one-by-one FOOD_DB -> LARN mapping utilities."""

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
FOOD_DB_JSON = DATA_DIR / "FOOD_DB.json"
MAPPING_JSON = DATA_DIR / "FOOD_DB_TO_LARN_MAPPING.json"
LARN_JSON = DATA_DIR / "LARN_PORTIONS.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_indexes():
    food_db = load_json(FOOD_DB_JSON)
    mapping_db = load_json(MAPPING_JSON)
    larn_db = load_json(LARN_JSON)

    foods = food_db.get("foods", [])
    food_by_id = {f.get("id"): f for f in foods if f.get("id")}

    mapping_entries = mapping_db.get("mapping", [])
    mapping_by_food_id = {m.get("food_db_id"): m for m in mapping_entries if m.get("food_db_id")}

    larn_ids = {p.get("id") for p in larn_db.get("portions", []) if p.get("id")}

    return mapping_db, food_by_id, mapping_by_food_id, larn_ids


def ensure_mapping_entry(mapping_db, mapping_by_food_id, food_id, food_name):
    entry = mapping_by_food_id.get(food_id)
    if entry:
        return entry

    entry = {
        "food_db_id": food_id,
        "food_db_name": food_name,
        "larn_portion_id": None,
        "operational_portion_id": None,
        "note": "Created for manual review.",
        "review_status": "pending_review",
        "mapping_confidence": 0.0,
        "mapping_source": "none",
        "last_reviewed_at": None,
    }
    mapping_db.setdefault("mapping", []).append(entry)
    mapping_by_food_id[food_id] = entry
    return entry


def cmd_next(args):
    _, food_by_id, mapping_by_food_id, _ = load_indexes()

    pending = []
    for fid, food in food_by_id.items():
        m = mapping_by_food_id.get(fid)
        is_mapped = bool(m and (m.get("larn_portion_id") or m.get("operational_portion_id")))
        if is_mapped:
            continue
        if args.contains:
            q = args.contains.lower()
            hay = f"{fid} {food.get('name', '')}".lower()
            if q not in hay:
                continue
        pending.append((fid, food.get("name", "")))

    pending.sort(key=lambda x: x[0])
    total = len(pending)

    start = max(args.offset, 0)
    end = min(start + args.limit, total)
    slice_items = pending[start:end]

    print(f"Pending review: {total}")
    print(f"Showing: {start + 1}-{end}" if slice_items else "Showing: none")
    for i, (fid, name) in enumerate(slice_items, start=1):
        print(f"{i}. {fid} | {name}")


def cmd_set(args):
    mapping_db, food_by_id, mapping_by_food_id, larn_ids = load_indexes()

    if args.food_db_id not in food_by_id:
        raise SystemExit(f"[ERR] food_db_id non trovato: {args.food_db_id}")
    if args.larn_portion_id not in larn_ids:
        raise SystemExit(f"[ERR] larn_portion_id non valido: {args.larn_portion_id}")

    food_name = food_by_id[args.food_db_id].get("name", args.food_db_id)
    entry = ensure_mapping_entry(mapping_db, mapping_by_food_id, args.food_db_id, food_name)

    entry["food_db_name"] = food_name
    entry["larn_portion_id"] = args.larn_portion_id
    entry["operational_portion_id"] = None
    entry["review_status"] = "reviewed"
    entry["mapping_confidence"] = round(args.confidence, 3)
    entry["mapping_source"] = "manual_user"
    entry["last_reviewed_at"] = datetime.now().strftime("%Y-%m-%d")
    entry["note"] = args.note or "Manual mapping set via tv food map-larn set."

    mapping_db.setdefault("meta", {})["generated_at"] = datetime.now().isoformat()
    save_json(MAPPING_JSON, mapping_db)

    print("[OK] Mapping aggiornato.")
    print(f"- food_db_id: {args.food_db_id}")
    print(f"- food_db_name: {food_name}")
    print(f"- larn_portion_id: {args.larn_portion_id}")


def cmd_unset(args):
    mapping_db, food_by_id, mapping_by_food_id, _ = load_indexes()

    if args.food_db_id not in food_by_id:
        raise SystemExit(f"[ERR] food_db_id non trovato: {args.food_db_id}")

    food_name = food_by_id[args.food_db_id].get("name", args.food_db_id)
    entry = ensure_mapping_entry(mapping_db, mapping_by_food_id, args.food_db_id, food_name)

    entry["food_db_name"] = food_name
    entry["larn_portion_id"] = None
    entry["operational_portion_id"] = None
    entry["review_status"] = "pending_review"
    entry["mapping_confidence"] = 0.0
    entry["mapping_source"] = "none"
    entry["last_reviewed_at"] = None
    entry["note"] = args.note or "Manual unmap via tv food map-larn unset."

    mapping_db.setdefault("meta", {})["generated_at"] = datetime.now().isoformat()
    save_json(MAPPING_JSON, mapping_db)

    print("[OK] Mapping rimosso.")
    print(f"- food_db_id: {args.food_db_id}")
    print(f"- food_db_name: {food_name}")


def cmd_larn(args):
    _, _, _, larn_ids = load_indexes()
    items = sorted(larn_ids)
    if args.contains:
        q = args.contains.lower()
        items = [x for x in items if q in x.lower()]

    total = len(items)
    end = min(args.limit, total)
    print(f"LARN IDs: {total}")
    for i, item in enumerate(items[:end], start=1):
        print(f"{i}. {item}")


def build_parser():
    p = argparse.ArgumentParser(
        description="Manual FOOD_DB -> LARN mapping",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    p_next = sub.add_parser("next", help="Mostra alimenti pending review")
    p_next.add_argument("--limit", type=int, default=20)
    p_next.add_argument("--offset", type=int, default=0)
    p_next.add_argument("--contains", default=None)
    p_next.set_defaults(func=cmd_next)

    p_set = sub.add_parser("set", help="Imposta mapping singolo")
    p_set.add_argument("food_db_id")
    p_set.add_argument("larn_portion_id")
    p_set.add_argument("--confidence", type=float, default=1.0)
    p_set.add_argument("--note", default=None)
    p_set.set_defaults(func=cmd_set)

    p_unset = sub.add_parser("unset", help="Rimuove mapping singolo")
    p_unset.add_argument("food_db_id")
    p_unset.add_argument("--note", default=None)
    p_unset.set_defaults(func=cmd_unset)

    p_larn = sub.add_parser("larn", help="Lista IDs LARN disponibili")
    p_larn.add_argument("--limit", type=int, default=50)
    p_larn.add_argument("--contains", default=None)
    p_larn.set_defaults(func=cmd_larn)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
