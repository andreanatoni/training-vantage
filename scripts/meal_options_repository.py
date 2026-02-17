#!/usr/bin/env python3
"""Repository helpers for structured meal options."""

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

try:
    from scripts.extract_from_stale import StalePlanParser
except ModuleNotFoundError:
    from extract_from_stale import StalePlanParser

ROOT = Path(__file__).parent.parent
SOURCES_DIR = ROOT / "sources"
MEAL_OPTIONS_DIR = ROOT / "knowledge" / "meal_options"

CATEGORY_SOURCES = {
    "forza": "piano_forza.md",
    "easy-run": "piano_easy_run.md",
    "qualita": "piano_qualita.md",
    "tempo": "piano_tempo.md",
    "lungo": "piano_lungo.md",
    "rest": "piano_rest.md",
    "pizza-day": "piano_pizza_day.md",
    "domenica": "piano_domenica.md",
}


def _meal_options_path(category: str) -> Path:
    return MEAL_OPTIONS_DIR / f"{category}.json"


def _source_path(category: str) -> Path:
    source_file = CATEGORY_SOURCES.get(category)
    if not source_file:
        raise ValueError(f"Categoria sconosciuta: {category}")
    return SOURCES_DIR / source_file


def _build_payload(category: str, source_file: str, plan_data: dict) -> dict:
    return {
        "meta": {
            "category": category,
            "source_type": "stale_markdown_migration",
            "source_file": source_file,
            "generated_at": datetime.now().isoformat(),
            "schema_version": "v1",
        },
        "plan": plan_data,
    }


def _validate_payload(payload: dict) -> None:
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("Invalid meal_options payload: missing 'plan'")
    if "bmr" not in plan or "target_kcal" not in plan or "meals" not in plan:
        raise ValueError("Invalid meal_options payload: expected keys bmr/target_kcal/meals")


def build_category_from_stale(category: str, parser: StalePlanParser = None) -> Path:
    parser = parser or StalePlanParser()
    source_path = _source_path(category)
    if not source_path.exists():
        raise FileNotFoundError(f"File sorgente non trovato: {source_path}")

    plan_data = parser.parse_plan_file(source_path)
    payload = _build_payload(category, source_path.name, plan_data)
    _validate_payload(payload)

    MEAL_OPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    dst = _meal_options_path(category)
    dst.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dst


def build_all_from_stale(parser: StalePlanParser = None) -> list[Path]:
    parser = parser or StalePlanParser()
    out = []
    for category in CATEGORY_SOURCES:
        out.append(build_category_from_stale(category, parser=parser))
    return out


def load_plan_for_category(category: str, parser: StalePlanParser = None, allow_fallback: bool = True) -> dict:
    """
    Load structured plan for category.

    Preferred path: knowledge/meal_options/<category>.json
    Fallback path: parse sources/piano_<category>.md when allowed.
    """
    path = _meal_options_path(category)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_payload(payload)
        return deepcopy(payload["plan"])

    if not allow_fallback:
        raise FileNotFoundError(f"File meal options non trovato: {path}")

    parser = parser or StalePlanParser()
    source_path = _source_path(category)
    if not source_path.exists():
        raise FileNotFoundError(f"File sorgente fallback non trovato: {source_path}")
    print(
        f"[WARN] meal_options/{category}.json mancante. "
        f"Uso fallback STALE da {source_path.name} (deprecato). "
        "Esegui: ./tv plan build-options"
    )
    return parser.parse_plan_file(source_path)
