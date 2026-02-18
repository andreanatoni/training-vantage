#!/usr/bin/env python3
"""Validazione pre-flight del nutrition_base_template atleta."""

import argparse
import json
from pathlib import Path

from scripts.athlete_context import data_file, get_athlete_id, relpath_or_str

REQUIRED_MEAL_IDS = ["breakfast", "snack_am", "lunch", "snack_pm", "dinner"]
REQUIRED_TRACE_KEYS = ["scenario", "reasoning", "source_refs", "rules_doc", "roles_final"]
SHARED_FOOD_DB = Path(__file__).resolve().parents[2] / "data" / "FOOD_DB.json"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Valida nutrition_base_template.json (planner-ready).",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    return parser.parse_args(argv)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _food_id_set() -> set[str]:
    payload = _load_json(SHARED_FOOD_DB)
    return {str(item.get("id")) for item in payload.get("foods", []) if item.get("id")}


def validate_template_payload(template: dict, valid_food_ids: set[str]):
    errors = []
    warnings = []

    meals = template.get("meals")
    if not isinstance(meals, list):
        return ["meals deve essere una lista"], []

    by_id = {m.get("meal_id"): m for m in meals if isinstance(m, dict)}
    for meal_id in REQUIRED_MEAL_IDS:
        meal = by_id.get(meal_id)
        if not meal:
            errors.append(f"meal_id mancante: {meal_id}")
            continue
        options = meal.get("options")
        if not isinstance(options, list) or len(options) == 0:
            errors.append(f"{meal_id}: nessuna opzione configurata")
            continue

        for idx, option in enumerate(options, start=1):
            oid = option.get("option_id", f"opt_{idx}")
            blocks = option.get("blocks")
            if not isinstance(blocks, list) or len(blocks) == 0:
                errors.append(f"{meal_id}/{oid}: blocks vuoti")
                continue

            trace = option.get("rules_trace")
            if not isinstance(trace, dict):
                errors.append(f"{meal_id}/{oid}: rules_trace mancante")
            else:
                for key in REQUIRED_TRACE_KEYS:
                    value = trace.get(key)
                    if value in (None, "", []):
                        errors.append(f"{meal_id}/{oid}: rules_trace.{key} mancante")

            for bidx, block in enumerate(blocks, start=1):
                one_of = block.get("one_of")
                if not isinstance(one_of, list) or len(one_of) == 0:
                    errors.append(f"{meal_id}/{oid}/block_{bidx}: one_of vuoto")
                    continue
                for item in one_of:
                    fid = item.get("food_db_id")
                    if not fid:
                        errors.append(f"{meal_id}/{oid}/block_{bidx}: food_db_id mancante")
                    elif fid not in valid_food_ids:
                        errors.append(f"{meal_id}/{oid}/block_{bidx}: food_db_id sconosciuto '{fid}'")

            tags = option.get("tags")
            if not isinstance(tags, list):
                warnings.append(f"{meal_id}/{oid}: tags non lista")

    return errors, warnings


def main(argv=None):
    args = parse_args(argv)
    athlete = get_athlete_id()
    template_path = data_file("nutrition_base_template.json")

    if not template_path.exists():
        msg = (
            f"Template non trovato per atleta '{athlete}': {relpath_or_str(template_path)}. "
            "Esegui: ./tv nutrition setup-base"
        )
        if args.json:
            print(json.dumps({"ok": False, "errors": [msg], "warnings": []}, ensure_ascii=False, indent=2))
        else:
            print(f"[ERR] {msg}")
        return 1

    try:
        template = _load_json(template_path)
    except Exception as exc:
        msg = f"JSON non leggibile: {exc}"
        if args.json:
            print(json.dumps({"ok": False, "errors": [msg], "warnings": []}, ensure_ascii=False, indent=2))
        else:
            print(f"[ERR] {msg}")
        return 1

    valid_food_ids = _food_id_set()
    errors, warnings = validate_template_payload(template, valid_food_ids)
    ok = len(errors) == 0

    report = {
        "ok": ok,
        "athlete_id": athlete,
        "template": relpath_or_str(template_path),
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "meals": len(template.get("meals", []) if isinstance(template.get("meals"), list) else []),
            "foods_in_db": len(valid_food_ids),
        },
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if ok:
            print(f"[OK] Template planner-ready: {relpath_or_str(template_path)}")
            if warnings:
                print(f"[WARN] warning count: {len(warnings)}")
                for w in warnings[:10]:
                    print(f"- {w}")
        else:
            print(f"[ERR] Template non planner-ready: {relpath_or_str(template_path)}")
            for e in errors[:20]:
                print(f"- {e}")
            if len(errors) > 20:
                print(f"- ... altri {len(errors) - 20} errori")
            print("Correggi con: ./tv nutrition setup-base --edit")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
