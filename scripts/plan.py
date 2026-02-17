#!/usr/bin/env python3
"""
/tv plan <categoria> [--all]

Genera piano nutrizionale completo per categoria usando meal_options strutturati.
Fallback temporaneo: parsing STALE markdown se i JSON non sono presenti.
"""

import sys
import json
import math
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timedelta
from athlete_context import DATA_DIR as SHARED_DATA_DIR, athlete_plans_dir, data_file, ensure_athlete_dirs, get_athlete_id
from integration_config import load_integration_config_strict
from meal_options_repository import CATEGORY_SOURCES, load_plan_for_category

PLANS_DIR = athlete_plans_dir()
COMPOSITION_FILE = data_file("composition.json")
CHANGELOG_FILE = data_file("changelog.json")
NUTRITION_ENGINE_CONFIG_FILE = data_file("NUTRITION_ENGINE_CONFIG.json")
TRAINING_LOAD_FILE = data_file("training_load.json")
RUNNING_PLAN_FILE = data_file("running_plan.json")

VALID_CATEGORIES = list(CATEGORY_SOURCES.keys())
RUNNING_DAY_TYPE_TO_PROFILE = {
    "rest": "rest",
    "easy": "easy",
    "qualita": "qualita",
    "progressivo": "progressivo",
    "lungo": "lungo",
    "forza": "forza",
}


def get_current_bmr():
    """Ottieni BMR attuale da composition.json"""
    with open(COMPOSITION_FILE, 'r') as f:
        data = json.load(f)
    latest = data['measurements'][-1]
    return int(latest['bmr'])


def get_current_body_data():
    """Ottieni dati corporei attuali da composition.json"""
    with open(COMPOSITION_FILE, 'r') as f:
        data = json.load(f)
    latest = data['measurements'][-1]
    return {
        'weight': float(latest['weight']),
        'ffm': float(latest['ffm']),
        'bmr': int(latest['bmr'])
    }


def load_nutrition_engine_config():
    """Carica configurazione motore nutrizionale."""
    if not NUTRITION_ENGINE_CONFIG_FILE.exists():
        fallback = SHARED_DATA_DIR / "NUTRITION_ENGINE_CONFIG.json"
        if fallback.exists():
            with open(fallback, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise FileNotFoundError(f"Config non trovato: {NUTRITION_ENGINE_CONFIG_FILE}.")
    with open(NUTRITION_ENGINE_CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_training_profile_costs():
    """Carica costi energetici medi per day-profile da training_load.json."""
    if not TRAINING_LOAD_FILE.exists():
        return {}
    try:
        data = json.loads(TRAINING_LOAD_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    costs = data.get("profile_costs_kcal", {})
    if not isinstance(costs, dict):
        return {}

    cleaned = {}
    for k, v in costs.items():
        try:
            if v is None:
                continue
            val = float(v)
            if val > 0:
                cleaned[k] = val
        except (TypeError, ValueError):
            continue
    return cleaned


def estimate_training_cost_kcal_from_running_session(session, body_data, config):
    """
    Stima costo energetico giornaliero a partire dalla singola seduta del running_plan.
    Regola principale (running): ~1 kcal/kg/km.
    Forza: fallback su valore config day_profile 'forza'.
    """
    if not session:
        return 0

    integration = load_integration_config_strict()
    model = integration["training_cost_model"]
    day_type = session.get("day_type", "rest")
    distance_km = float(session.get("distance_km") or 0.0)
    weight_kg = float(body_data.get("weight", 0.0))
    day_multipliers = model.get("day_type_multipliers", {})
    if day_type not in day_multipliers:
        raise ValueError(f"day_type '{day_type}' missing in training_cost_model.day_type_multipliers")
    multiplier = float(day_multipliers[day_type])

    if day_type in ("easy", "qualita", "progressivo", "lungo"):
        base = float(model["running_kcal_per_kg_per_km"])
        return int(round(max(0.0, distance_km * weight_kg * base * multiplier)))

    if day_type == "forza":
        return int(round(float(model["strength_base_kcal"]) * multiplier))

    return 0


def category_for_day_type(day_type):
    integration = load_integration_config_strict()
    mapping = integration["day_type_to_nutrition_category"]
    if day_type not in mapping:
        raise ValueError(f"day_type '{day_type}' missing in day_type_to_nutrition_category")
    return mapping[day_type]


def round_to_step(value, step):
    """Arrotonda al multiplo di step piu' vicino."""
    if step <= 0:
        return int(round(value))
    return int(round(value / step) * step)


def get_plan_adjustment(category, body_data, config, profile_cost_overrides=None, explicit_override=None):
    """Calcola deficit e guardrail EA per categoria."""
    profile_name = config['category_to_day_profile'].get(category, 'rest')
    profile = config['day_profiles'][profile_name]
    deficit_min, deficit_max = profile['deficit_pct_range']
    deficit_pct = (deficit_min + deficit_max) / 2.0
    training_cost_kcal = int(profile['training_cost_kcal_estimate'])
    training_cost_source = "config"

    if profile_cost_overrides and profile_name in profile_cost_overrides:
        training_cost_kcal = int(round(profile_cost_overrides[profile_name]))
        training_cost_source = "training_load"
    if explicit_override and "training_cost_kcal" in explicit_override:
        training_cost_kcal = int(round(float(explicit_override["training_cost_kcal"])))
        training_cost_source = explicit_override.get("training_cost_source", "running_plan_day")

    ea_cfg = config['energy_availability']
    ea_hard_floor = float(ea_cfg['hard_floor_kcal_per_kg_ffm'])
    ea_target_min = float(ea_cfg['target_min_kcal_per_kg_ffm'])

    min_kcal_hard = math.ceil(body_data['ffm'] * ea_hard_floor + training_cost_kcal)
    min_kcal_target = math.ceil(body_data['ffm'] * ea_target_min + training_cost_kcal)

    return {
        'profile_name': profile_name,
        'deficit_pct': deficit_pct,
        'training_cost_kcal': training_cost_kcal,
        'training_cost_source': training_cost_source,
        'ea_hard_floor': ea_hard_floor,
        'ea_target_min': ea_target_min,
        'min_kcal_hard': min_kcal_hard,
        'min_kcal_target': min_kcal_target
    }


def apply_secondary_scaling(plan_data, ratio):
    """Applica un secondo scaling (post-BMR) su target e ingredienti."""
    if ratio <= 0:
        return plan_data

    scaled = deepcopy(plan_data)
    scaled['target_kcal'] = int(round(scaled['target_kcal'] * ratio))

    for meal_data in scaled['meals'].values():
        meal_data['target']['kcal'] = int(round(meal_data['target']['kcal'] * ratio))
        meal_data['target']['protein'] = int(round(meal_data['target']['protein'] * ratio))
        meal_data['target']['fat'] = int(round(meal_data['target']['fat'] * ratio))
        meal_data['target']['cho'] = int(round(meal_data['target']['cho'] * ratio))

        for option in meal_data['options']:
            for ing in option['ingredients']:
                ing['amount'] = round(ing['amount'] * ratio, 1)
            if option.get('totals'):
                option['totals'] = {
                    'kcal': round(option['totals']['kcal'] * ratio, 0),
                    'protein': round(option['totals']['protein'] * ratio, 1),
                    'fat': round(option['totals']['fat'] * ratio, 1),
                    'cho': round(option['totals']['cho'] * ratio, 1),
                }

    return scaled


def scale_plan_to_bmr(plan_data, new_bmr):
    """Scala piano completo al nuovo BMR (prima del motore deficit/EA)."""
    old_bmr = plan_data.get('bmr')
    if not old_bmr:
        raise ValueError("BMR non presente nel piano base")
    ratio = new_bmr / old_bmr
    print(f"Scaling: BMR {old_bmr} → {new_bmr} (ratio: {ratio:.3f})")
    return apply_secondary_scaling(plan_data, ratio)


def format_ingredient_line(ing_data):
    """Formatta linea ingrediente"""
    if ing_data['type'] == 'single':
        return f"- {ing_data['name']}: {ing_data['amount']:.0f} {ing_data['unit']}"
    elif ing_data['type'] == 'alternatives':
        items_str = ' OR '.join(ing_data['items'])
        return f"- {items_str}: {ing_data['amount']:.0f} {ing_data['unit']}"


def generate_plan_markdown(category, plan_data, current_bmr, engine_meta=None):
    """Genera markdown completo per un piano"""
    lines = []

    # META comment
    lines.append(f"<!-- META")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"FFM: {plan_data.get('ffm', 'N/A')} kg")
    lines.append(f"BMR: {current_bmr} kcal")
    lines.append(f"Status: CURRENT")
    if engine_meta:
        lines.append(f"Engine Config: {engine_meta.get('config_version', 'N/A')}")
        lines.append(f"Day Profile: {engine_meta.get('day_profile', 'N/A')}")
        lines.append(f"Deficit Applied: {engine_meta.get('deficit_pct', 0.0) * 100:.1f}%")
        lines.append(
            "Training Cost: {kcal} kcal ({src})".format(
                kcal=engine_meta.get("training_cost_kcal", 0),
                src=engine_meta.get("training_cost_source", "config"),
            )
        )
        if engine_meta.get("phase"):
            lines.append(f"Running Phase: {engine_meta.get('phase')}")
        if engine_meta.get("workout_label"):
            lines.append(f"Workout Label: {engine_meta.get('workout_label')}")
        if engine_meta.get("session_date"):
            lines.append(f"Session Date: {engine_meta.get('session_date')}")
        lines.append(f"EA: {engine_meta.get('ea_value', 0.0):.1f} kcal/kg FFM")
    lines.append(f"-->")
    lines.append("")

    # Header
    category_titles = {
        'forza': 'FORZA',
        'easy-run': 'EASY RUN',
        'qualita': 'QUALITÀ',
        'tempo': 'TEMPO RUN',
        'lungo': 'LUNGO',
        'rest': 'REST DAY',
        'pizza-day': 'PIZZA DAY',
        'domenica': 'DOMENICA'
    }

    lines.append(f"# Piano {category_titles.get(category, category.upper())}")
    lines.append("")
    lines.append(f"**Target giornaliero**: {plan_data['target_kcal']} kcal")
    lines.append("")

    # Per ogni pasto
    meal_icons = {
        'COLAZIONE': '☕',
        'SPUNTINO MATTINA': '🍎',
        'PRANZO': '🍝',
        'SPUNTINO POMERIGGIO': '🥜',
        'SPUNTINO SERA': '🍌',
        'CENA': '🍖'
    }

    for meal_name, meal_data in plan_data['meals'].items():
        icon = meal_icons.get(meal_name, '🍽️')

        lines.append(f"# {icon} {meal_name}")
        lines.append("")

        # Target pasto
        target = meal_data['target']
        lines.append(f"**Target**: {target['kcal']} kcal | {target['protein']}g P | {target['fat']}g F | {target['cho']}g CHO")
        lines.append("")

        # Opzioni
        for idx, option in enumerate(meal_data['options'], 1):
            lines.append(f"### Opzione {idx} - {option['name']}")
            lines.append("")

            # Ingredienti
            for ing in option['ingredients']:
                lines.append(format_ingredient_line(ing))
            lines.append("")

            # Totali
            if option['totals']:
                tot = option['totals']
                lines.append(f"**Totali**: {tot['kcal']:.0f} kcal | {tot['protein']:.1f}g P | {tot['fat']:.1f}g F | {tot['cho']:.1f}g CHO")
                lines.append("")

            # Swap
            if option['swap']:
                lines.append(f"**Swap**: {option['swap']}")
                lines.append("")

            # Quando
            if option['quando']:
                lines.append(f"**Quando**: {option['quando']}")
                lines.append("")

    return '\n'.join(lines)


def build_plan_json_payload(category, plan_data, body_data, engine_meta):
    """Costruisce payload JSON strutturato del piano giornaliero."""
    return {
        "meta": {
            "generated_at": datetime.now().strftime("%Y-%m-%d"),
            "category": category,
            "status": "CURRENT"
        },
        "inputs": {
            "weight_kg": round(body_data["weight"], 2),
            "ffm_kg": round(body_data["ffm"], 2),
            "bmr_kcal": int(body_data["bmr"])
        },
        "engine": {
            "config_version": engine_meta.get("config_version"),
            "day_profile": engine_meta.get("day_profile"),
            "deficit_pct": round(float(engine_meta.get("deficit_pct", 0.0)), 4),
            "training_cost_kcal": int(engine_meta.get("training_cost_kcal", 0)),
            "training_cost_source": engine_meta.get("training_cost_source", "config"),
            "phase": engine_meta.get("phase"),
            "workout_label": engine_meta.get("workout_label"),
            "session_date": engine_meta.get("session_date"),
            "ea_value_kcal_per_kg_ffm": round(float(engine_meta.get("ea_value", 0.0)), 2),
            "ea_guard_applied": bool(engine_meta.get("ea_guard_applied", False))
        },
        "plan": plan_data
    }


def generate_plan(category, silent=False, engine_overrides=None, output_md_file=None, output_json_file=None):
    """Genera piano completo per categoria"""
    if category not in CATEGORY_SOURCES:
        print(f"❌ Categoria {category} non trovata in mapping")
        return False

    # Parse da JSON strutturato (fallback STALE gestito internamente)
    try:
        plan_data = load_plan_for_category(category, allow_fallback=True)
    except Exception as exc:
        print(f"❌ Errore caricamento meal options per categoria '{category}': {exc}")
        return False

    old_bmr = plan_data['bmr']
    body_data = get_current_body_data()
    current_bmr = body_data['bmr']
    config = load_nutrition_engine_config()

    if not old_bmr:
        print(f"❌ BMR non trovato nel piano STALE")
        return False

    plan_scaled = scale_plan_to_bmr(plan_data, current_bmr)
    training_profile_costs = load_training_profile_costs()
    explicit_adjustment_override = None
    if engine_overrides and "training_cost_kcal" in engine_overrides:
        explicit_adjustment_override = {
            "training_cost_kcal": engine_overrides.get("training_cost_kcal"),
            "training_cost_source": engine_overrides.get("training_cost_source", "running_plan_day"),
        }
    adjustment = get_plan_adjustment(
        category,
        body_data,
        config,
        profile_cost_overrides=training_profile_costs,
        explicit_override=explicit_adjustment_override,
    )

    pre_adjust_kcal = int(plan_scaled['target_kcal'])
    requested_kcal = pre_adjust_kcal * (1.0 - adjustment['deficit_pct'])
    kcal_step = int(config.get('generation', {}).get('rounding', {}).get('kcal_step', 5))
    adjusted_kcal = round_to_step(requested_kcal, kcal_step)

    ea_guard_applied = False
    if adjusted_kcal < adjustment['min_kcal_hard']:
        adjusted_kcal = adjustment['min_kcal_hard']
        ea_guard_applied = True

    secondary_ratio = adjusted_kcal / pre_adjust_kcal if pre_adjust_kcal > 0 else 1.0
    plan_final = apply_secondary_scaling(plan_scaled, secondary_ratio)
    plan_final['ffm'] = round(body_data['ffm'], 2)

    ea_value = (adjusted_kcal - adjustment['training_cost_kcal']) / body_data['ffm']
    engine_meta = {
        'config_version': config.get('meta', {}).get('version', 'N/A'),
        'day_profile': adjustment['profile_name'],
        'deficit_pct': adjustment['deficit_pct'],
        'training_cost_kcal': adjustment['training_cost_kcal'],
        'training_cost_source': adjustment['training_cost_source'],
        'phase': engine_overrides.get('phase') if engine_overrides else None,
        'workout_label': engine_overrides.get('workout_label') if engine_overrides else None,
        'session_date': engine_overrides.get('session_date') if engine_overrides else None,
        'ea_value': ea_value,
        'ea_guard_applied': ea_guard_applied
    }

    # Genera markdown
    markdown = generate_plan_markdown(category, plan_final, current_bmr, engine_meta=engine_meta)
    plan_json_payload = build_plan_json_payload(category, plan_final, body_data, engine_meta)

    # Salva markdown + json
    ensure_athlete_dirs()
    if output_md_file is None:
        output_md_file = PLANS_DIR / f"{category}.md"
    if output_json_file is None:
        output_json_file = PLANS_DIR / f"{category}.json"
    with open(output_md_file, 'w', encoding='utf-8') as f:
        f.write(markdown)
    with open(output_json_file, 'w', encoding='utf-8') as f:
        json.dump(plan_json_payload, f, ensure_ascii=False, indent=2)

    # Report
    num_options = sum(len(meal['options']) for meal in plan_final['meals'].values())

    if not silent:
        guard_msg = " | EA-GUARD" if ea_guard_applied else ""
        print(
            f"✓ Piano {category}: {plan_final['target_kcal']} kcal | "
            f"EA {ea_value:.1f} | {num_options} opzioni → "
            f"{output_md_file} + {output_json_file}{guard_msg}"
        )

    return True


def generate_all():
    """Rigenera tutti gli 8 piani"""
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║           RIGENERAZIONE PIANI NUTRIZIONALI COMPLETI               ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Atleta: {get_athlete_id()}")
    print()

    current_bmr = get_current_bmr()
    print(f"BMR attuale: {current_bmr} kcal (da composition.json)")
    print()

    success_count = 0
    for category in VALID_CATEGORIES:
        if generate_plan(category, silent=False):
            success_count += 1

    print()
    print("─" * 70)
    print(f"Completato: {success_count}/{len(VALID_CATEGORIES)} piani generati con successo")
    print()


def load_running_week(iso_week):
    """Carica settimana da running_plan.json tramite chiave ISO (es. 2026-W11)."""
    if not RUNNING_PLAN_FILE.exists():
        print(
            f"❌ File non trovato: {RUNNING_PLAN_FILE}. "
            "Genera prima il piano running con: ./tv running generate ..."
        )
        return None
    try:
        data = json.loads(RUNNING_PLAN_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"❌ Errore lettura {RUNNING_PLAN_FILE}: {exc}")
        return None

    for week in data.get("weeks", []):
        if week.get("iso_week") == iso_week:
            return week
    return None


def load_running_plan_data():
    """Carica intero running_plan.json."""
    if not RUNNING_PLAN_FILE.exists():
        print(
            f"❌ File non trovato: {RUNNING_PLAN_FILE}. "
            "Genera prima il piano running con: ./tv running generate ..."
        )
        return None
    try:
        return json.loads(RUNNING_PLAN_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"❌ Errore lettura {RUNNING_PLAN_FILE}: {exc}")
        return None


def date_range(start_date, end_date):
    """Itera date incluse nel range YYYY-MM-DD."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def generate_week_plan(iso_week):
    """
    Genera pacchetto nutrizionale settimanale a partire da running_plan.json.
    Output:
      plans/nutrition/athletes/<id>/weeks/<iso_week>/*.md
      plans/nutrition/athletes/<id>/weeks/<iso_week>/*.json
      plans/nutrition/athletes/<id>/weeks/<iso_week>/week-summary.md
      plans/nutrition/athletes/<id>/weeks/<iso_week>/week-summary.json
    """
    week = load_running_week(iso_week)
    if not week:
        print(f"❌ Settimana {iso_week} non trovata in {RUNNING_PLAN_FILE}")
        return False

    sessions = week.get("sessions", [])
    session_by_date = {}
    for s in sessions:
        d = s.get("date")
        if d:
            session_by_date[d] = s

    start_date = week.get("start_date")
    end_date = week.get("end_date")
    if not start_date or not end_date:
        print("❌ start_date/end_date mancanti nella settimana running.")
        return False

    week_dir = PLANS_DIR / "weeks" / iso_week
    week_dir.mkdir(parents=True, exist_ok=True)

    day_rows = []
    body_data = get_current_body_data()
    config = load_nutrition_engine_config()
    for day in date_range(start_date, end_date):
        day_str = day.isoformat()
        session = session_by_date.get(day_str)
        day_type = session.get("day_type", "rest") if session else "rest"
        category = category_for_day_type(day_type)
        training_cost_kcal = estimate_training_cost_kcal_from_running_session(session, body_data, config)
        day_rows.append(
            {
                "date": day_str,
                "weekday": day.strftime("%A"),
                "category": category,
                "day_type": day_type,
                "phase": week.get("phase"),
                "workout_label": session.get("workout_label") if session else None,
                "training_cost_kcal": training_cost_kcal,
            }
        )

    # Genera piani giornalieri specifici
    day_outputs = []
    for row in day_rows:
        d = row["date"]
        category = row["category"]
        dst_md = week_dir / f"{d}-{category}.md"
        dst_json = week_dir / f"{d}-{category}.json"
        ok = generate_plan(
            category,
            silent=True,
            engine_overrides={
                "training_cost_kcal": row["training_cost_kcal"],
                "training_cost_source": "running_plan_day",
                "phase": row.get("phase"),
                "workout_label": row.get("workout_label"),
                "session_date": d,
            },
            output_md_file=dst_md,
            output_json_file=dst_json,
        )
        if not ok:
            print(f"❌ Impossibile generare piano giornaliero per {d} ({category})")
            return False
        day_outputs.append(
            {
                "date": d,
                "weekday": row["weekday"],
                "category": category,
                "day_type": row["day_type"],
                "training_cost_kcal": row["training_cost_kcal"],
                "phase": row.get("phase"),
                "workout_label": row.get("workout_label"),
                "md_file": str(dst_md.relative_to(Path(__file__).parent.parent)),
                "json_file": str(dst_json.relative_to(Path(__file__).parent.parent)),
            }
        )

    summary_json = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "athlete_id": get_athlete_id(),
            "iso_week": iso_week,
            "source_running_plan": str(RUNNING_PLAN_FILE.relative_to(Path(__file__).parent.parent)),
        },
        "week": {
            "iso_week": iso_week,
            "start_date": start_date,
            "end_date": end_date,
            "phase": week.get("phase"),
            "target_km": week.get("target_km"),
        },
        "days": day_outputs,
    }
    summary_json_path = week_dir / "week-summary.json"
    summary_json_path.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Piano Nutrizione Settimanale {iso_week}",
        "",
        f"- Periodo: {start_date} -> {end_date}",
        f"- Fase running: {week.get('phase', 'N/A')}",
        f"- Target running: {week.get('target_km', 'N/A')} km",
        "",
        "| Data | Giorno | Categoria | DayType | Cost kcal | File |",
        "|------|--------|-----------|---------|-----------|------|",
    ]
    for row in day_outputs:
        lines.append(
            f"| {row['date']} | {row['weekday']} | {row['category']} | {row['day_type']} | {row['training_cost_kcal']} | "
            f"`{Path(row['md_file']).name}` / `{Path(row['json_file']).name}` |"
        )
    summary_md_path = week_dir / "week-summary.md"
    summary_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"✓ Piano week {iso_week} generato in {week_dir}")
    used_categories = sorted({d["category"] for d in day_outputs})
    print(f"  Giorni: {len(day_outputs)} | Categorie usate: {', '.join(used_categories)}")
    print(f"  Summary: {summary_md_path} + {summary_json_path}")
    return True


def generate_month_plan(month_yyyy_mm):
    """
    Genera pacchetto nutrizionale mensile a partire da running_plan.json.
    Output:
      plans/nutrition/athletes/<id>/months/<YYYY-MM>/*.md
      plans/nutrition/athletes/<id>/months/<YYYY-MM>/*.json
      plans/nutrition/athletes/<id>/months/<YYYY-MM>/month-summary.md
      plans/nutrition/athletes/<id>/months/<YYYY-MM>/month-summary.json
    """
    plan = load_running_plan_data()
    if not plan:
        return False

    weeks = plan.get("weeks", [])
    if not weeks:
        print("❌ running_plan.json non contiene settimane.")
        return False

    # Map date -> sessione pianificata
    session_by_date = {}
    covered_dates = set()
    for week in weeks:
        for d in date_range(week["start_date"], week["end_date"]):
            covered_dates.add(d.isoformat())
        for s in week.get("sessions", []):
            if s.get("date"):
                # Include phase della settimana per contesto nutrizionale
                enriched = dict(s)
                enriched["phase"] = week.get("phase")
                session_by_date[s.get("date")] = enriched

    month_dates = sorted([d for d in covered_dates if d.startswith(month_yyyy_mm + "-")])
    if not month_dates:
        print(f"❌ Nessun giorno del mese {month_yyyy_mm} trovato in {RUNNING_PLAN_FILE}")
        return False

    day_rows = []
    body_data = get_current_body_data()
    config = load_nutrition_engine_config()
    for d in month_dates:
        session = session_by_date.get(d)
        day_type = session.get("day_type", "rest") if session else "rest"
        category = category_for_day_type(day_type)
        training_cost_kcal = estimate_training_cost_kcal_from_running_session(session, body_data, config)
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        day_rows.append(
            {
                "date": d,
                "weekday": dt.strftime("%A"),
                "category": category,
                "day_type": day_type,
                "phase": session.get("phase") if session else None,
                "workout_label": session.get("workout_label") if session else None,
                "training_cost_kcal": training_cost_kcal,
            }
        )

    month_dir = PLANS_DIR / "months" / month_yyyy_mm
    month_dir.mkdir(parents=True, exist_ok=True)

    day_outputs = []
    for row in day_rows:
        d = row["date"]
        category = row["category"]
        dst_md = month_dir / f"{d}-{category}.md"
        dst_json = month_dir / f"{d}-{category}.json"
        ok = generate_plan(
            category,
            silent=True,
            engine_overrides={
                "training_cost_kcal": row["training_cost_kcal"],
                "training_cost_source": "running_plan_day",
                "phase": row.get("phase"),
                "workout_label": row.get("workout_label"),
                "session_date": d,
            },
            output_md_file=dst_md,
            output_json_file=dst_json,
        )
        if not ok:
            print(f"❌ Impossibile generare piano giornaliero per {d} ({category})")
            return False
        day_outputs.append(
            {
                "date": d,
                "weekday": row["weekday"],
                "category": category,
                "day_type": row["day_type"],
                "training_cost_kcal": row["training_cost_kcal"],
                "phase": row.get("phase"),
                "workout_label": row.get("workout_label"),
                "md_file": str(dst_md.relative_to(Path(__file__).parent.parent)),
                "json_file": str(dst_json.relative_to(Path(__file__).parent.parent)),
            }
        )

    summary_json = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "athlete_id": get_athlete_id(),
            "month": month_yyyy_mm,
            "source_running_plan": str(RUNNING_PLAN_FILE.relative_to(Path(__file__).parent.parent)),
        },
        "month": month_yyyy_mm,
        "days_count": len(day_outputs),
        "days": day_outputs,
    }
    summary_json_path = month_dir / "month-summary.json"
    summary_json_path.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Piano Nutrizione Mensile {month_yyyy_mm}",
        "",
        f"- Giorni coperti: {len(day_outputs)}",
        "",
        "| Data | Giorno | Categoria | DayType | Cost kcal | File |",
        "|------|--------|-----------|---------|-----------|------|",
    ]
    for row in day_outputs:
        lines.append(
            f"| {row['date']} | {row['weekday']} | {row['category']} | {row['day_type']} | {row['training_cost_kcal']} | "
            f"`{Path(row['md_file']).name}` / `{Path(row['json_file']).name}` |"
        )
    summary_md_path = month_dir / "month-summary.md"
    summary_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"✓ Piano month {month_yyyy_mm} generato in {month_dir}")
    used_categories = sorted({d["category"] for d in day_outputs})
    print(f"  Giorni: {len(day_outputs)} | Categorie usate: {', '.join(used_categories)}")
    print(f"  Summary: {summary_md_path} + {summary_json_path}")
    return True


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == "week":
        generate_week_plan(sys.argv[2])
        sys.exit(0)

    if len(sys.argv) >= 3 and sys.argv[1] == "month":
        generate_month_plan(sys.argv[2])
        sys.exit(0)

    if len(sys.argv) < 2 or sys.argv[1] not in VALID_CATEGORIES + ['--all']:
        print(f"Usage: plan.py <categoria> | --all | week <YYYY-Www> | month <YYYY-MM>")
        print(f"Categorie: {', '.join(VALID_CATEGORIES)}")
        sys.exit(1)

    if sys.argv[1] == '--all':
        generate_all()
    else:
        generate_plan(sys.argv[1])
