#!/usr/bin/env python3
"""
Sincronizza knowledge/food-db.md a partire da data/FOOD_DB.json
e valida referenze con data/FOOD_DB_TO_LARN_MAPPING.json.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FOOD_DB_JSON_FILE = ROOT / "data" / "FOOD_DB.json"
FOOD_DB_MAPPING_FILE = ROOT / "data" / "FOOD_DB_TO_LARN_MAPPING.json"
FOOD_DB_MD_FILE = ROOT / "knowledge" / "food-db.md"


def normalize_unit(unit):
    if unit == "mL":
        return "ml"
    return unit


def build_reference_label(reference):
    amount = reference["amount"]
    unit = normalize_unit(reference["unit"])
    amount_str = f"{amount:.0f}" if float(amount).is_integer() else f"{amount:.1f}"
    label = f"{amount_str} {unit}"
    if reference.get("note"):
        label = f"{label} {reference['note']}"
    return label


def validate_food_db(food_db):
    foods = food_db.get("foods", [])
    ids = set()
    names = set()

    for food in foods:
        food_id = food.get("id")
        name = food.get("name")
        if not food_id or not name:
            raise ValueError("Ogni alimento deve avere id e name")
        if food_id in ids:
            raise ValueError(f"ID duplicato in FOOD_DB.json: {food_id}")
        if name in names:
            raise ValueError(f"Nome duplicato in FOOD_DB.json: {name}")
        ids.add(food_id)
        names.add(name)

        ref = food.get("reference", {})
        if "amount" not in ref or "unit" not in ref:
            raise ValueError(f"Reference incompleta per {food_id}")

        nutrients = food.get("nutrients_per_reference", {})
        for key in ["kcal", "P", "CHO", "F", "Fibre"]:
            if key not in nutrients:
                raise ValueError(f"Nutriente mancante '{key}' per {food_id}")


def validate_mapping(mapping_db, food_db):
    foods = food_db.get("foods", [])
    valid_food_ids = {f["id"] for f in foods}

    mapping = mapping_db.get("mapping", [])
    seen_mapping_ids = set()
    for item in mapping:
        food_db_id = item.get("food_db_id")
        if not food_db_id:
            raise ValueError("Mapping con food_db_id mancante")
        if food_db_id in seen_mapping_ids:
            raise ValueError(f"Mapping duplicato per food_db_id: {food_db_id}")
        seen_mapping_ids.add(food_db_id)
        if food_db_id not in valid_food_ids:
            raise ValueError(f"Mapping orfano: food_db_id '{food_db_id}' non presente in FOOD_DB.json")


def render_markdown(food_db):
    lines = []
    lines.append("# 📊 FOOD_DB – versione aggiornata")
    lines.append("")
    lines.append("| Alimento | Riferimento | kcal | P (g) | CHO (g) | F (g) | Fibre (g) | Fonte |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")

    foods = sorted(food_db.get("foods", []), key=lambda item: item["name"].lower())
    for food in foods:
        reference = build_reference_label(food["reference"])
        nutrients = food["nutrients_per_reference"]
        source = food.get("data_source", "N/A")
        lines.append(
            "| {name} | {reference} | {kcal:.1f} | {P:.1f} | {CHO:.1f} | {F:.1f} | {Fibre:.1f} | {source} |".format(
                name=food["name"],
                reference=reference,
                kcal=float(nutrients["kcal"]),
                P=float(nutrients["P"]),
                CHO=float(nutrients["CHO"]),
                F=float(nutrients["F"]),
                Fibre=float(nutrients["Fibre"]),
                source=source,
            )
        )

    lines.append("")
    return "\n".join(lines)


def sync_food_db_files(write=True):
    food_db = json.loads(FOOD_DB_JSON_FILE.read_text(encoding="utf-8"))
    mapping_db = json.loads(FOOD_DB_MAPPING_FILE.read_text(encoding="utf-8"))

    validate_food_db(food_db)
    validate_mapping(mapping_db, food_db)

    markdown = render_markdown(food_db)
    if write:
        FOOD_DB_MD_FILE.write_text(markdown, encoding="utf-8")

    return {"foods": len(food_db.get("foods", [])), "mapping": len(mapping_db.get("mapping", []))}


def is_markdown_in_sync():
    food_db = json.loads(FOOD_DB_JSON_FILE.read_text(encoding="utf-8"))
    expected = render_markdown(food_db)
    if not FOOD_DB_MD_FILE.exists():
        return False
    current = FOOD_DB_MD_FILE.read_text(encoding="utf-8")
    return current == expected


def main():
    check_only = len(sys.argv) > 1 and sys.argv[1] == "--check"
    result = sync_food_db_files(write=not check_only)

    if check_only:
        if not is_markdown_in_sync():
            print("[CHECK] FOOD_DB FAIL - knowledge/food-db.md non allineato a data/FOOD_DB.json")
            print("Esegui: ./tv food sync")
            sys.exit(1)
        print(f"[CHECK] FOOD_DB OK - foods: {result['foods']}, mapping: {result['mapping']}")
    else:
        print(f"[SYNC] FOOD_DB OK - foods: {result['foods']}, mapping: {result['mapping']}")
        print(f"[SYNC] Markdown rigenerato: {FOOD_DB_MD_FILE}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Errore: {exc}")
        sys.exit(1)
