#!/usr/bin/env python3
"""Build per-athlete active FOOD_DB subset."""

import json
import re
from datetime import datetime
from pathlib import Path

from scripts.common.paths import athlete_plans_dir, data_file, ensure_athlete_dirs, get_athlete_id, relpath_or_str

ROOT = Path(__file__).resolve().parents[2]
GLOBAL_FOOD_DB = ROOT / "data" / "FOOD_DB.json"


def load_json(path, default=None):
    if default is None:
        default = {}
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize_name(text):
    txt = (text or "").strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    txt = re.sub(r"[^a-z0-9 ]+", "", txt)
    return txt.strip()


def collect_from_nutrition_template(template_path):
    payload = load_json(template_path, {})
    found = set()

    meals = payload.get("meals", [])
    if isinstance(meals, dict):
        meals = list(meals.values())

    for meal in meals:
        options = meal.get("options", []) if isinstance(meal, dict) else []
        for opt in options:
            # New structure: blocks -> one_of -> food_db_id
            for block in opt.get("blocks", []) or []:
                for item in block.get("one_of", []) or []:
                    fid = item.get("food_db_id")
                    if fid:
                        found.add(fid)
            # Legacy structure fallback: ingredients with explicit food_db_id
            for ing in opt.get("ingredients", []) or []:
                fid = ing.get("food_db_id") if isinstance(ing, dict) else None
                if fid:
                    found.add(fid)

    return found


def build_food_name_index(food_db):
    idx = {}
    for food in food_db.get("foods", []):
        fid = food.get("id")
        name = food.get("name")
        if not fid or not name:
            continue
        key = normalize_name(name)
        idx.setdefault(key, set()).add(fid)
    return idx


def collect_from_plan_jsons(plans_dir, food_name_index):
    found_ids = set()
    matched_from_name_occurrences = 0
    matched_from_name_unique = set()
    unresolved_missing = set()
    unresolved_ambiguous = {}

    if not plans_dir.exists():
        return (
            found_ids,
            matched_from_name_occurrences,
            matched_from_name_unique,
            unresolved_missing,
            unresolved_ambiguous,
        )

    for p in plans_dir.rglob("*.json"):
        if p.name in ("week-summary.json", "month-summary.json"):
            continue
        doc = load_json(p, {})
        meals = ((doc.get("plan") or {}).get("meals") or {})
        if not isinstance(meals, dict):
            continue

        for meal_data in meals.values():
            options = meal_data.get("options", []) if isinstance(meal_data, dict) else []
            for opt in options:
                for ing in opt.get("ingredients", []) or []:
                    if not isinstance(ing, dict):
                        continue
                    fid = ing.get("food_db_id")
                    if fid:
                        found_ids.add(fid)
                        continue

                    name = ing.get("name")
                    if not name:
                        continue
                    key = normalize_name(name)
                    cands = sorted(food_name_index.get(key, []))
                    if len(cands) == 1:
                        found_ids.add(cands[0])
                        matched_from_name_occurrences += 1
                        matched_from_name_unique.add(name)
                    elif len(cands) == 0:
                        unresolved_missing.add(name)
                    else:
                        unresolved_ambiguous[name] = cands

                    if ing.get("type") == "alternatives":
                        for alt in ing.get("items", []) or []:
                            if not isinstance(alt, str):
                                continue
                            akey = normalize_name(alt)
                            acands = sorted(food_name_index.get(akey, []))
                            if len(acands) == 1:
                                found_ids.add(acands[0])
                                matched_from_name_occurrences += 1
                                matched_from_name_unique.add(alt)
                            elif len(acands) == 0:
                                unresolved_missing.add(alt)
                            else:
                                unresolved_ambiguous[alt] = acands

    return (
        found_ids,
        matched_from_name_occurrences,
        matched_from_name_unique,
        unresolved_missing,
        unresolved_ambiguous,
    )


def main():
    ensure_athlete_dirs()
    athlete_id = get_athlete_id()

    food_db = load_json(GLOBAL_FOOD_DB, {})
    foods = food_db.get("foods", [])
    by_id = {f.get("id"): f for f in foods if f.get("id")}

    template_path = data_file("nutrition_base_template.json")
    plans_dir = athlete_plans_dir()

    ids_from_template = collect_from_nutrition_template(template_path)
    name_index = build_food_name_index(food_db)
    (
        ids_from_plans,
        matched_from_name_occurrences,
        matched_from_name_unique,
        unresolved_missing,
        unresolved_ambiguous,
    ) = collect_from_plan_jsons(plans_dir, name_index)

    active_ids = sorted(ids_from_template | ids_from_plans)
    missing_ids = sorted([fid for fid in active_ids if fid not in by_id])

    active_foods = [by_id[fid] for fid in active_ids if fid in by_id]

    out = {
        "meta": {
            "version": "v1.0",
            "generated_at": datetime.now().isoformat(),
            "athlete_id": athlete_id,
            "source_files": {
                "food_db": relpath_or_str(GLOBAL_FOOD_DB),
                "nutrition_base_template": relpath_or_str(template_path),
                "nutrition_plans_dir": relpath_or_str(plans_dir),
            },
        },
        "stats": {
            "global_food_count": len(foods),
            "active_food_count": len(active_foods),
            "active_ids_from_template": len(ids_from_template),
            "active_ids_from_plans": len(ids_from_plans),
            "matched_from_plan_name_occurrences": matched_from_name_occurrences,
            "matched_from_plan_name_unique": len(matched_from_name_unique),
            "missing_ids_in_global_db": len(missing_ids),
            "unresolved_plan_names_missing": len(unresolved_missing),
            "unresolved_plan_names_ambiguous": len(unresolved_ambiguous),
        },
        "active_food_ids": active_ids,
        "foods": active_foods,
        "issues": {
            "missing_ids_in_global_db": missing_ids,
            "unresolved_plan_names_missing": sorted(unresolved_missing),
            "unresolved_plan_names_ambiguous": unresolved_ambiguous,
            "matched_plan_names_unique": sorted(matched_from_name_unique),
        },
    }

    out_path = data_file("FOOD_DB_ACTIVE.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("[OK] FOOD_DB_ACTIVE generated.")
    print(f"- Athlete: {athlete_id}")
    print(f"- File: {out_path}")
    print(f"- Active foods: {len(active_foods)} / {len(foods)}")
    print(
        "- Sources: template_ids={t}, plan_ids={p}, matched_by_name={m}".format(
            t=len(ids_from_template), p=len(ids_from_plans), m=len(matched_from_name_unique)
        )
    )
    if missing_ids:
        print(f"- Warning: {len(missing_ids)} active IDs not found in global FOOD_DB")
    if unresolved_missing or unresolved_ambiguous:
        print(
            "- Unresolved plan ingredient names: missing={m} ambiguous={a}".format(
                m=len(unresolved_missing), a=len(unresolved_ambiguous)
            )
        )


if __name__ == "__main__":
    main()
