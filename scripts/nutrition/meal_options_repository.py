#!/usr/bin/env python3
"""Repository helpers for structured meal options (strict mode)."""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEAL_OPTIONS_DIR = ROOT / "knowledge" / "meal_options"

CATEGORY_SOURCES = {
    "forza": "forza",
    "easy-run": "easy-run",
    "qualita": "qualita",
    "tempo": "tempo",
    "lungo": "lungo",
    "rest": "rest",
    "pizza-day": "pizza-day",
    "domenica": "domenica",
}


def _meal_options_path(category: str) -> Path:
    return MEAL_OPTIONS_DIR / f"{category}.json"


def _validate_payload(payload: dict) -> None:
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("Invalid meal_options payload: missing 'plan'")
    if "bmr" not in plan or "target_kcal" not in plan or "meals" not in plan:
        raise ValueError("Invalid meal_options payload: expected keys bmr/target_kcal/meals")


def load_plan_for_category(category: str) -> dict:
    """
    Load structured plan for category from knowledge/meal_options/<category>.json.
    No fallback to STALE markdown.
    """
    path = _meal_options_path(category)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_payload(payload)
        return deepcopy(payload["plan"])

    raise FileNotFoundError(
        f"File meal options non trovato: {path}. "
        "I file JSON in knowledge/meal_options sono l'unica source-of-truth "
        "(runtime/build/migrazioni)."
    )
