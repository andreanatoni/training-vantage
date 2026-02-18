#!/usr/bin/env python3
"""Rules engine nutrizione: suggerimento blocchi pasto + trigger safety."""

import json
from pathlib import Path

from scripts.athlete_context import DATA_DIR, ROOT_DIR


TRIGGERS_FILE = DATA_DIR / "NUTRITION_SAFETY_TRIGGERS.json"
RULES_DOC_PATH = ROOT_DIR / "knowledge" / "nutrition-rules.md"


def load_safety_triggers():
    return json.loads(TRIGGERS_FILE.read_text(encoding="utf-8"))


def evaluate_safety(profile):
    advanced = profile.get("advanced_bia") or {}
    triggers = load_safety_triggers()
    hard = []
    warnings = []

    body_fat = advanced.get("body_fat_pct")
    ffm = advanced.get("ffm_kg")

    bf_threshold = triggers.get("hard_stop", {}).get("body_fat_pct_min")
    ffm_threshold = triggers.get("hard_stop", {}).get("ffm_kg_min")
    if body_fat is not None and bf_threshold is not None and float(body_fat) < float(bf_threshold):
        hard.append(
            f"Body fat {body_fat}% sotto soglia hard ({bf_threshold}%)."
        )
    if ffm is not None and ffm_threshold is not None and float(ffm) < float(ffm_threshold):
        hard.append(
            f"FFM {ffm} kg sotto soglia hard ({ffm_threshold} kg)."
        )

    for rule in triggers.get("warnings", []):
        field = rule.get("field")
        min_value = rule.get("min")
        max_value = rule.get("max")
        value = advanced.get(field)
        if value is None:
            continue
        if min_value is not None and float(value) < float(min_value):
            warnings.append(f"{field}={value} sotto range prudente ({min_value}+).")
        if max_value is not None and float(value) > float(max_value):
            warnings.append(f"{field}={value} sopra range prudente (<= {max_value}).")

    return {
        "hard_stop": hard,
        "warnings": warnings,
        "consult_professional": bool(hard),
    }


def _base_blocks_by_scenario(scenario):
    if scenario == "pre_workout":
        return ["carb", "protein", "beverage"]
    if scenario == "post_workout":
        return ["carb", "protein", "beverage", "fruit"]
    return ["carb", "protein", "fat"]


def suggest_blocks(profile, meal_id, scenario):
    goal = (profile.get("profile") or {}).get("goal", "maintenance")
    training = profile.get("training_context") or {}
    run_days = int(training.get("running_days_per_week", 0) or 0)
    strength_days = int(training.get("strength_days_per_week", 0) or 0)
    train_time = training.get("typical_training_time", "mixed")

    roles = _base_blocks_by_scenario(scenario)
    reasons = [f"Scenario {scenario}: base blocchi evidence-based conservativa."]
    sources = [
        "LARN V revisione (SINU)",
        "ACSM/AND/DC Nutrition and Athletic Performance (2016)",
    ]

    # Meal-specific tuning
    if meal_id in {"lunch", "dinner"}:
        if "veg" not in roles:
            roles.append("veg")
            reasons.append("Pranzo/cena: aggiunta verdure per qualita' dieta e sazieta'.")
    if meal_id in {"snack_am", "snack_pm"}:
        roles = [r for r in roles if r not in {"veg"}]
        if "fruit" not in roles:
            roles.append("fruit")
            reasons.append("Snack: frutta come scelta semplice e aderente.")

    # Goal tuning
    if goal == "fat_loss":
        if meal_id in {"lunch", "dinner"} and "veg" not in roles:
            roles.append("veg")
        if "fat" in roles and meal_id in {"snack_am", "snack_pm"}:
            roles.remove("fat")
            reasons.append("Goal fat_loss: riduzione densita' energetica negli snack.")
    elif goal == "performance":
        if meal_id in {"breakfast", "lunch"} and "carb" not in roles:
            roles.append("carb")
            reasons.append("Goal performance: priorita' disponibilita' carboidrati.")

    # Training load tuning
    if run_days >= 5 and meal_id in {"breakfast", "lunch", "dinner"} and "carb" not in roles:
        roles.append("carb")
        reasons.append("Alto carico running: mantenuto blocco carb nei pasti principali.")
    if strength_days >= 2 and "protein" not in roles:
        roles.append("protein")
        reasons.append("Frequenza forza >=2: proteine presenti in tutti i pasti chiave.")

    # Timing hint
    if train_time == "morning" and meal_id == "breakfast" and scenario == "pre_workout":
        if "fat" in roles:
            roles.remove("fat")
        reasons.append("Allenamento mattutino: pre-workout a digestione piu rapida.")
    if train_time == "evening" and meal_id == "dinner" and scenario == "post_workout":
        if "protein" not in roles:
            roles.append("protein")
        reasons.append("Allenamento serale: cena con enfasi recupero proteico.")

    # Deterministic de-dup / stable order
    order = ["carb", "protein", "fat", "veg", "fruit", "beverage", "extra"]
    unique = []
    seen = set()
    for role in roles:
        if role not in seen:
            seen.add(role)
            unique.append(role)
    unique.sort(key=lambda r: order.index(r) if r in order else 999)

    return {
        "roles": unique,
        "reasons": reasons,
        "source_refs": sources,
        "rules_doc": str(RULES_DOC_PATH),
    }


def suggest_scenario_for_meal(profile, meal_id):
    training = profile.get("training_context") or {}
    train_time = training.get("typical_training_time", "mixed")
    run_days = int(training.get("running_days_per_week", 0) or 0)

    # Conservative default
    scenario = "default_day"
    reason = "Fallback conservativo: contesto non specifico."

    if meal_id == "breakfast":
        if train_time == "morning" and run_days >= 1:
            scenario = "pre_workout"
            reason = "Allenamento tipico mattutino: colazione orientata al pre-workout."
        elif train_time in {"evening", "lunch"} and run_days >= 1:
            scenario = "default_day"
            reason = "Allenamento non mattutino: colazione standard."
    elif meal_id == "snack_am":
        if train_time == "lunch" and run_days >= 1:
            scenario = "pre_workout"
            reason = "Allenamento in pausa pranzo: snack AM come pre-workout."
        else:
            scenario = "default_day"
            reason = "Snack AM standard."
    elif meal_id == "lunch":
        if train_time == "lunch" and run_days >= 1:
            scenario = "post_workout"
            reason = "Allenamento a pranzo: lunch come post-workout."
        elif train_time == "evening" and run_days >= 1:
            scenario = "pre_workout"
            reason = "Allenamento serale: lunch come pre-workout."
        else:
            scenario = "default_day"
            reason = "Lunch standard."
    elif meal_id == "snack_pm":
        if train_time == "evening" and run_days >= 1:
            scenario = "pre_workout"
            reason = "Allenamento serale: snack PM come pre-workout."
        else:
            scenario = "default_day"
            reason = "Snack PM standard."
    elif meal_id == "dinner":
        if train_time == "evening" and run_days >= 1:
            scenario = "post_workout"
            reason = "Allenamento serale: dinner come post-workout."
        else:
            scenario = "default_day"
            reason = "Cena standard."

    return {"scenario": scenario, "reason": reason}
