#!/usr/bin/env python3
"""Strict loader/validator for per-athlete integration config."""

import json
from datetime import datetime
from pathlib import Path

try:
    from scripts.athlete_context import data_file, get_athlete_id
except ModuleNotFoundError:
    from athlete_context import data_file, get_athlete_id


INTEGRATION_CONFIG_FILE = data_file("INTEGRATION_CONFIG.json")
REQUIRED_DAY_TYPES = {"rest", "easy", "qualita", "progressivo", "lungo", "forza"}


class IntegrationConfigError(RuntimeError):
    """Raised when integration config is missing or invalid."""


def _err(msg):
    athlete_id = get_athlete_id()
    raise IntegrationConfigError(
        f"[ERR] INTEGRATION_CONFIG invalid for athlete '{athlete_id}': {msg}. "
        f"Expected file: {INTEGRATION_CONFIG_FILE}"
    )


def _require_number(obj, key, min_value=None):
    val = obj.get(key)
    if not isinstance(val, (int, float)):
        _err(f"'{key}' must be numeric")
    val = float(val)
    if min_value is not None and val < min_value:
        _err(f"'{key}' must be >= {min_value}")
    return val


def _validate(config):
    if not isinstance(config, dict):
        _err("root must be an object")

    day_map = config.get("day_type_to_nutrition_category")
    if not isinstance(day_map, dict):
        _err("'day_type_to_nutrition_category' must be an object")
    missing_day_types = sorted(REQUIRED_DAY_TYPES - set(day_map.keys()))
    if missing_day_types:
        _err(f"missing day_type mappings: {', '.join(missing_day_types)}")

    training = config.get("training_cost_model")
    if not isinstance(training, dict):
        _err("'training_cost_model' must be an object")
    _require_number(training, "running_kcal_per_kg_per_km", min_value=0.0)
    _require_number(training, "strength_base_kcal", min_value=0.0)
    multipliers = training.get("day_type_multipliers")
    if not isinstance(multipliers, dict):
        _err("'training_cost_model.day_type_multipliers' must be an object")
    missing_mult = sorted(REQUIRED_DAY_TYPES - set(multipliers.keys()))
    if missing_mult:
        _err(f"missing day_type multipliers: {', '.join(missing_mult)}")
    for key in REQUIRED_DAY_TYPES:
        _require_number(multipliers, key, min_value=0.0)

    races = config.get("race_calendar")
    if not isinstance(races, list) or not races:
        _err("'race_calendar' must be a non-empty array")
    for idx, race in enumerate(races, start=1):
        if not isinstance(race, dict):
            _err(f"race_calendar[{idx}] must be an object")
        if not race.get("name"):
            _err(f"race_calendar[{idx}].name is required")
        d = race.get("date")
        if not d:
            _err(f"race_calendar[{idx}].date is required")
        try:
            datetime.strptime(str(d), "%Y-%m-%d")
        except ValueError:
            _err(f"race_calendar[{idx}].date must be YYYY-MM-DD")

    alerts = config.get("alerts")
    if not isinstance(alerts, dict):
        _err("'alerts' must be an object")
    _require_number(alerts, "ffm_red_flag_kg", min_value=0.0)
    _require_number(alerts, "weight_drop_warning_pct_per_week", min_value=0.0)

    status_cfg = config.get("status")
    if not isinstance(status_cfg, dict):
        _err("'status' must be an object")
    plan_start = status_cfg.get("plan_start_date")
    if not plan_start:
        _err("'status.plan_start_date' is required")
    try:
        datetime.strptime(str(plan_start), "%Y-%m-%d")
    except ValueError:
        _err("'status.plan_start_date' must be YYYY-MM-DD")
    plan_total_weeks = status_cfg.get("plan_total_weeks")
    if not isinstance(plan_total_weeks, int) or plan_total_weeks <= 0:
        _err("'status.plan_total_weeks' must be positive integer")

    return config


def load_integration_config_strict(path: Path = None):
    path = path or INTEGRATION_CONFIG_FILE
    if not path.exists():
        _err("file not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _err(f"json parse failed: {exc}")
    return _validate(payload)


def get_next_race(config, today=None):
    today = today or datetime.now().date()
    races = sorted(config["race_calendar"], key=lambda x: x["date"])
    for race in races:
        race_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
        if race_date >= today:
            days_to = (race_date - today).days
            return {
                "name": race["name"],
                "date": race["date"],
                "target": race.get("target_pace") or race.get("target") or "N/A",
                "days_to_race": days_to,
            }
    return None
