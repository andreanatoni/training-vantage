#!/usr/bin/env python3
"""Wizard interattivo per compilare il nutrition base template per atleta."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import os

try:
    from scripts.athlete_context import (
        DEFAULT_ATHLETE_ID,
        DATA_DIR as SHARED_DATA_DIR,
        athlete_knowledge_dir,
        data_file,
        ensure_athlete_dirs,
        normalize_athlete_id,
        relpath_or_str,
    )
    from scripts.nutrition.rules_engine import (
        evaluate_safety,
        suggest_blocks,
        suggest_scenario_for_meal,
    )
except ModuleNotFoundError:
    from athlete_context import (
        DEFAULT_ATHLETE_ID,
        DATA_DIR as SHARED_DATA_DIR,
        athlete_knowledge_dir,
        data_file,
        ensure_athlete_dirs,
        normalize_athlete_id,
        relpath_or_str,
    )
    from rules_engine import evaluate_safety, suggest_blocks, suggest_scenario_for_meal


SHARED_TEMPLATE_FILE = SHARED_DATA_DIR / "templates" / "nutrition_base_template.shared.json"
FOOD_DB_FILE = SHARED_DATA_DIR / "FOOD_DB.json"
NUTRITION_PROFILE_FILE = "NUTRITION_PROFILE.json"

MEAL_ORDER = ["breakfast", "snack_am", "lunch", "snack_pm", "dinner"]
MEAL_LABELS = {
    "breakfast": "Colazione",
    "snack_am": "Spuntino AM",
    "lunch": "Pranzo",
    "snack_pm": "Spuntino PM",
    "dinner": "Cena",
}
ROLE_OPTIONS = ["carb", "protein", "fat", "veg", "fruit", "extra", "beverage"]
SCENARIO_CHOICES = [
    ("pre_workout", "Allenamento vicino"),
    ("post_workout", "Recupero post allenamento"),
    ("default_day", "Giornata standard (workout non definito)"),
]
SWEET_KEYWORDS = [
    "marmellata",
    "miele",
    "biscott",
    "ciambell",
    "plum",
    "cake",
    "yogurt",
    "banana",
    "mela",
    "pera",
    "frutta",
    "burro d'arachidi",
]
SAVORY_KEYWORDS = [
    "prosciutto",
    "bresaola",
    "tacchino",
    "pollo",
    "uova",
    "tonno",
    "salmone",
    "merluzzo",
    "manzo",
    "vitello",
    "mozzarella",
    "hummus",
]


def runtime_paths_for_athlete(athlete_id):
    os.environ["TV_ATHLETE_ID"] = athlete_id
    return {
        "template_json": data_file("nutrition_base_template.json"),
        "template_md": athlete_knowledge_dir() / "nutrition-base-template.md",
    }


def resolve_target_athlete_id(athlete_name):
    current_id = normalize_athlete_id(os.environ.get("TV_ATHLETE_ID", DEFAULT_ATHLETE_ID))
    if current_id != DEFAULT_ATHLETE_ID:
        return current_id
    return normalize_athlete_id(athlete_name)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Wizard setup template base nutrizione (multi-atleta).",
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Modifica template esistente senza ricreare struttura opzioni.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sovrascrivi senza chiedere conferma.",
    )
    parser.add_argument(
        "--strict-no-defaults",
        action="store_true",
        help=(
            "Azzera campi non strutturali prima del wizard "
            "(excluded_meals, user_constraints, timing/tag/when_to_use)."
        ),
    )
    parser.add_argument(
        "--allow-manual-block-overrides",
        action="store_true",
        help="Abilita modifica manuale completa dei blocchi (modalita avanzata).",
    )
    return parser.parse_args(argv)


def iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ask_text(prompt, required=False, allow_empty=False):
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        if allow_empty:
            return ""
        if not required:
            return ""
        print("Valore richiesto.")


def ask_yes_no(prompt, default=None):
    suffix = "(y/n)"
    if default is True:
        suffix = "(Y/n)"
    elif default is False:
        suffix = "(y/N)"
    while True:
        raw = input(f"{prompt} {suffix}: ").strip().lower()
        if not raw and default is not None:
            return default
        if raw in {"y", "yes", "s", "si"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Risposta non valida. Usa y oppure n.")


def ask_int(prompt, min_value=0, max_value=None):
    while True:
        raw = input(f"{prompt}: ").strip()
        try:
            value = int(raw)
        except ValueError:
            print("Inserisci un numero intero.")
            continue
        if value < min_value:
            print(f"Valore minimo: {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"Valore massimo: {max_value}.")
            continue
        return value


def ask_choice(prompt, choices):
    for idx, choice in enumerate(choices, start=1):
        if isinstance(choice, tuple):
            print(f"{idx}. {choice[0]} - {choice[1]}")
        else:
            print(f"{idx}. {choice}")
    while True:
        raw = input(f"{prompt}: ").strip()
        try:
            pick = int(raw)
        except ValueError:
            print("Inserisci il numero della scelta.")
            continue
        if 1 <= pick <= len(choices):
            selected = choices[pick - 1]
            return selected[0] if isinstance(selected, tuple) else selected
        print("Scelta fuori range.")


def ask_list_until_blank(prompt):
    print(prompt)
    print("Inserisci una voce per riga; invio su riga vuota per terminare.")
    values = []
    while True:
        item = input("- ").strip()
        if not item:
            break
        values.append(item)
    return values


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_required_nutrition_profile(path):
    if not path.exists():
        raise ValueError(
            "Profilo nutrizione mancante. Esegui prima: ./tv nutrition setup-profile"
        )

    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("NUTRITION_PROFILE.json non valido (root deve essere object).")

    profile = payload.get("profile")
    body_core = payload.get("body_core")
    training = payload.get("training_context")

    if not isinstance(profile, dict):
        raise ValueError("NUTRITION_PROFILE.json non valido: manca 'profile'.")
    if not isinstance(body_core, dict):
        raise ValueError("NUTRITION_PROFILE.json non valido: manca 'body_core'.")
    if not isinstance(training, dict):
        raise ValueError("NUTRITION_PROFILE.json non valido: manca 'training_context'.")

    required_profile = ["goal"]
    required_body = ["sex", "age_years", "height_cm", "weight_kg"]
    required_training = [
        "running_days_per_week",
        "strength_days_per_week",
        "typical_training_time",
    ]

    missing = []
    for key in required_profile:
        if profile.get(key) in (None, ""):
            missing.append(f"profile.{key}")
    for key in required_body:
        if body_core.get(key) in (None, ""):
            missing.append(f"body_core.{key}")
    for key in required_training:
        if training.get(key) in (None, ""):
            missing.append(f"training_context.{key}")

    if missing:
        raise ValueError(
            "NUTRITION_PROFILE.json incompleto. Campi mancanti: "
            + ", ".join(missing)
        )

    return payload


def load_foods():
    data = load_json(FOOD_DB_FILE)
    foods = data.get("foods", [])
    valid = []
    for item in foods:
        food_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        if food_id and name:
            valid.append({"id": food_id, "name": name})
    return valid


def search_foods(foods, query, limit=25):
    q = query.strip().lower()
    if not q:
        return []
    tokens = [t for t in q.split() if t]
    ranked = []
    for food in foods:
        name = food["name"].lower()
        food_id = food["id"].lower()
        if not all((tok in name) or (tok in food_id) for tok in tokens):
            continue
        score = 0
        if name.startswith(q):
            score += 5
        if food_id.startswith(q):
            score += 4
        if q in name:
            score += 2
        if q in food_id:
            score += 1
        score -= len(name) / 1000.0
        ranked.append((score, food))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in ranked[:limit]]


def infer_option_tags(blocks, food_name_by_id):
    roles = {b.get("role") for b in blocks if b.get("role")}
    all_names = []
    for block in blocks:
        for choice in block.get("one_of", []):
            food_id = choice.get("food_db_id", "")
            all_names.append(food_name_by_id.get(food_id, "").lower())

    tags = []
    if "carb" in roles:
        tags.append("carb_based")
    if "protein" in roles:
        tags.append("protein_based")
    if {"carb", "protein"}.issubset(roles):
        tags.append("post_workout")
    if "carb" in roles and "fat" not in roles and "veg" not in roles:
        tags.append("pre_workout")
    if "fat" not in roles and "veg" not in roles:
        tags.append("quick_digest")

    has_sweet = any(any(k in name for k in SWEET_KEYWORDS) for name in all_names if name)
    has_savory = any(any(k in name for k in SAVORY_KEYWORDS) for name in all_names if name)
    if has_sweet and not has_savory:
        tags.append("sweet")
    if has_savory and not has_sweet:
        tags.append("savory")
    if {"carb", "protein"}.issubset(roles) and (("fat" in roles) or ("veg" in roles) or ("fruit" in roles)):
        tags.append("balanced")

    return sorted(set(tags))


def infer_when_to_use(meal_id, blocks, tags, scenario):
    roles = {b.get("role") for b in blocks if b.get("role")}
    if scenario == "default_day":
        return "Opzione standard quando il tipo di allenamento non e ancora definito."
    if meal_id == "breakfast":
        if "pre_workout" in tags:
            return "Colazione pre-allenamento o mattine con digestione da facilitare."
        if "savory" in tags:
            return "Colazione salata quando cerchi maggiore sazieta."
        return "Colazione standard per mattine senza esigenze specifiche."
    if meal_id == "snack_am":
        if "protein_based" in tags:
            return "Spuntino meta mattina quando vuoi sostenere sazieta e quota proteica."
        return "Spuntino rapido meta mattina."
    if meal_id == "lunch":
        if {"carb", "protein"}.issubset(roles):
            return "Pranzo completo nei giorni con allenamento nel pomeriggio/sera."
        return "Pranzo leggero e gestibile nei giorni a carico ridotto."
    if meal_id == "snack_pm":
        if "pre_workout" in tags:
            return "Spuntino pre-allenamento (60-120 minuti prima)."
        return "Spuntino pomeridiano nei giorni senza allenamento intenso."
    if meal_id == "dinner":
        if "protein_based" in tags:
            return "Cena orientata al recupero serale."
        return "Cena standard di chiusura giornata."
    return "Uso generale."


def suggest_roles_for_option(meal_id, scenario):
    defaults = {
        "breakfast": {
            "pre_workout": ["carb", "protein", "beverage"],
            "post_workout": ["carb", "protein", "beverage", "fruit"],
            "default_day": ["carb", "protein", "beverage", "fat"],
        },
        "snack_am": {
            "pre_workout": ["carb", "fruit"],
            "post_workout": ["carb", "protein"],
            "default_day": ["protein", "fruit"],
        },
        "lunch": {
            "pre_workout": ["carb", "protein", "veg"],
            "post_workout": ["carb", "protein", "veg", "fruit"],
            "default_day": ["carb", "protein", "veg", "fat"],
        },
        "snack_pm": {
            "pre_workout": ["carb", "fruit"],
            "post_workout": ["carb", "protein"],
            "default_day": ["protein", "fruit"],
        },
        "dinner": {
            "pre_workout": ["carb", "protein", "veg"],
            "post_workout": ["protein", "veg", "carb"],
            "default_day": ["protein", "veg", "fat", "carb"],
        },
    }
    meal_defaults = defaults.get(meal_id, {})
    return meal_defaults.get(scenario, meal_defaults.get("default_day", ["carb", "protein"]))


def choose_roles(meal_id, nutrition_profile, allow_manual_block_overrides=False):
    scenario_suggestion = suggest_scenario_for_meal(nutrition_profile, meal_id)
    scenario = scenario_suggestion["scenario"]
    print(
        "Scenario suggerito dal sistema: "
        f"{scenario} ({scenario_suggestion['reason']})"
    )
    if ask_yes_no("Vuoi cambiare scenario?", default=False):
        scenario = ask_choice("Scenario opzione", SCENARIO_CHOICES)

    suggestion = suggest_blocks(nutrition_profile, meal_id, scenario)
    suggested_roles = suggestion["roles"]
    print(f"Blocchi suggeriti: {', '.join(suggested_roles)}")
    if suggestion.get("reasons"):
        for reason in suggestion["reasons"]:
            print(f"- Motivo: {reason}")
    if suggestion.get("source_refs"):
        print(f"- Fonti: {', '.join(suggestion['source_refs'])}")
    if not ask_yes_no("Confermi i blocchi proposti dal sistema?", default=True):
        scenario = ask_choice("Scenario opzione", SCENARIO_CHOICES)
        suggestion = suggest_blocks(nutrition_profile, meal_id, scenario)
        suggested_roles = suggestion["roles"]
        print(f"Nuovi blocchi suggeriti: {', '.join(suggested_roles)}")

    if not allow_manual_block_overrides:
        return scenario, suggested_roles, suggestion

    if not ask_yes_no("Vuoi modificare manualmente i blocchi suggeriti?", default=False):
        return scenario, suggested_roles, suggestion

    blocks_count = ask_int("Quanti blocchi per questa opzione", min_value=1, max_value=8)
    roles = []
    for block_idx in range(1, blocks_count + 1):
        print(f"\nBlocco {block_idx}/{blocks_count}")
        role = ask_choice("Ruolo blocco", ROLE_OPTIONS)
        roles.append(role)
    return scenario, roles, suggestion


def ask_food_choices(foods, role):
    print(f"\nBlocco ruolo: {role}")
    print("Seleziona una o piu alternative OR.")
    while True:
        query = ask_text("Ricerca alimento (nome o id)", required=True)
        matches = search_foods(foods, query)
        if not matches:
            print("Nessun alimento trovato. Riprova con un termine diverso.")
            continue
        for idx, food in enumerate(matches, start=1):
            print(f"{idx}. {food['name']} [{food['id']}]")
        raw = ask_text("Indici da includere (es. 1 oppure 1,3,5)", required=True)
        try:
            picks = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            print("Formato indici non valido.")
            continue
        if not picks:
            print("Seleziona almeno un indice.")
            continue
        if any(p < 1 or p > len(matches) for p in picks):
            print("Uno o piu indici fuori range.")
            continue
        unique = []
        seen_ids = set()
        for p in picks:
            selected = matches[p - 1]
            if selected["id"] in seen_ids:
                continue
            seen_ids.add(selected["id"])
            unique.append({"food_db_id": selected["id"], "label": selected["name"]})
        if unique:
            return unique
        print("Selezione vuota, riprova.")


def build_option(foods, meal_id, idx, food_name_by_id, nutrition_profile, allow_manual_block_overrides=False):
    print(f"\nCompilazione {MEAL_LABELS[meal_id]} - Opzione {idx}")
    scenario, roles, suggestion = choose_roles(
        meal_id,
        nutrition_profile,
        allow_manual_block_overrides=allow_manual_block_overrides,
    )
    blocks = []
    for block_idx, role in enumerate(roles, start=1):
        print(f"\nBlocco {block_idx}/{len(roles)}")
        print(f"Ruolo blocco: {role}")
        one_of = ask_food_choices(foods, role)
        blocks.append({"role": role, "one_of": one_of})
    tags = infer_option_tags(blocks, food_name_by_id)
    when_to_use = infer_when_to_use(meal_id, blocks, tags, scenario)
    print("Tag auto-calcolati:", ", ".join(tags) if tags else "(nessuno)")
    print("Quando usarla (auto):", when_to_use)
    return {
        "option_id": f"{meal_id}_opt_{idx}",
        "title": f"Opzione {idx}",
        "immutable": True,
        "tags": tags,
        "when_to_use": when_to_use,
        "rules": {
            "allow_merge_with_other_options": False,
        },
        "rules_trace": {
            "scenario": scenario,
            "roles_final": roles,
            "reasoning": suggestion.get("reasons", []),
            "source_refs": suggestion.get("source_refs", []),
            "rules_doc": suggestion.get("rules_doc"),
        },
        "blocks": blocks,
    }


def render_markdown(template, athlete_id):
    lines = []
    lines.append("# Nutrition Base Template")
    lines.append("")
    lines.append(f"- Athlete: `{athlete_id}`")
    lines.append(f"- Template version: `{template['meta'].get('template_version', '')}`")
    lines.append(f"- Updated at: `{template['meta'].get('updated_at', '')}`")
    lines.append("")
    lines.append("## Meals")
    lines.append("")
    for meal in template.get("meals", []):
        lines.append(f"### {meal.get('name', meal.get('meal_id', 'Meal'))}")
        lines.append("")
        options = meal.get("options", [])
        if not options:
            lines.append("_Nessuna opzione configurata._")
            lines.append("")
            continue
        for option in options:
            lines.append(f"- {option.get('title', '')} (`{option.get('option_id', '')}`)")
            if option.get("tags"):
                lines.append(f"  Tags: {', '.join(option['tags'])}")
            if option.get("when_to_use"):
                lines.append(f"  Quando usarla: {option['when_to_use']}")
            trace = option.get("rules_trace") or {}
            if trace.get("scenario"):
                lines.append(f"  Scenario: `{trace.get('scenario')}`")
            if trace.get("roles_final"):
                lines.append(f"  Blocchi finali: {', '.join(trace.get('roles_final', []))}")
            if trace.get("source_refs"):
                lines.append(f"  Fonti: {', '.join(trace.get('source_refs'))}")
            if trace.get("reasoning"):
                lines.append("  Rationale:")
                for reason in trace.get("reasoning", []):
                    lines.append(f"  - {reason}")
            for block in option.get("blocks", []):
                items = [f"`{i.get('food_db_id', '')}`" for i in block.get("one_of", [])]
                joined = " OR ".join(items) if items else "_vuoto_"
                lines.append(f"  - {block.get('role', 'extra')}: {joined}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_structure_from_scratch(
    template,
    foods,
    food_name_by_id,
    nutrition_profile,
    allow_manual_block_overrides=False,
):
    print("\nStruttura base pasti (numero opzioni per pasto)")
    meals = []
    for meal_id in MEAL_ORDER:
        meal_name = MEAL_LABELS[meal_id]
        count = ask_int(f"Quante opzioni vuoi per {meal_name}", min_value=1, max_value=20)
        meal = {
            "meal_id": meal_id,
            "name": meal_name,
            "timing_hint": "",
            "options": [],
        }
        for idx in range(1, count + 1):
            meal["options"].append(
                build_option(
                    foods,
                    meal_id,
                    idx,
                    food_name_by_id,
                    nutrition_profile,
                    allow_manual_block_overrides=allow_manual_block_overrides,
                )
            )
        meals.append(meal)
    template["meals"] = meals


def edit_existing_options(
    template,
    foods,
    food_name_by_id,
    nutrition_profile,
    allow_manual_block_overrides=False,
):
    for meal in template.get("meals", []):
        meal_id = meal.get("meal_id")
        if meal_id not in MEAL_ORDER:
            continue
        name = meal.get("name", meal_id)
        options = meal.get("options", [])
        print(f"\n{name}: {len(options)} opzioni esistenti")
        if not options:
            if ask_yes_no("Nessuna opzione presente. Vuoi aggiungerne ora?", default=True):
                count = ask_int(f"Quante opzioni vuoi per {name}", min_value=1, max_value=20)
                for idx in range(1, count + 1):
                    options.append(
                        build_option(
                            foods,
                            meal_id,
                            idx,
                            food_name_by_id,
                            nutrition_profile,
                            allow_manual_block_overrides=allow_manual_block_overrides,
                        )
                    )
            meal["options"] = options
            continue
        if not ask_yes_no(f"Vuoi ricompilare le opzioni di {name}?", default=False):
            continue
        count = ask_int(f"Nuovo numero opzioni per {name}", min_value=1, max_value=20)
        new_options = []
        for idx in range(1, count + 1):
            new_options.append(
                build_option(
                    foods,
                    meal_id,
                    idx,
                    food_name_by_id,
                    nutrition_profile,
                    allow_manual_block_overrides=allow_manual_block_overrides,
                )
            )
        meal["options"] = new_options


def apply_strict_no_defaults(template):
    settings = template.setdefault("settings", {})
    settings["excluded_meals"] = []
    constraints = template.setdefault("user_constraints", {})
    constraints["hard_rules"] = []
    constraints["soft_preferences"] = []
    constraints["notes"] = ""

    for meal in template.get("meals", []):
        meal["timing_hint"] = ""
        for option in meal.get("options", []):
            option["tags"] = []
            option["when_to_use"] = ""


def collect_user_constraints(template):
    constraints = template.setdefault("user_constraints", {})
    existing_hard = constraints.get("hard_rules", [])
    existing_soft = constraints.get("soft_preferences", [])
    existing_notes = constraints.get("notes", "")

    if existing_hard:
        print(f"\nHard rules attuali: {len(existing_hard)}")
    if existing_soft:
        print(f"Soft preferences attuali: {len(existing_soft)}")

    if ask_yes_no("Vuoi configurare/aggiornare i vincoli personali atleta?", default=False):
        hard_rules = ask_list_until_blank("Vincoli hard (personali atleta)")
        soft_preferences = ask_list_until_blank("Preferenze soft (personali atleta)")
        notes = ask_text("Note vincoli (opzionale)", allow_empty=True)
        constraints["hard_rules"] = hard_rules
        constraints["soft_preferences"] = soft_preferences
        constraints["notes"] = notes
    else:
        constraints["hard_rules"] = existing_hard
        constraints["soft_preferences"] = existing_soft
        constraints["notes"] = existing_notes


def main(argv=None):
    args = parse_args(argv)
    foods = load_foods()
    if not foods:
        print("Errore: FOOD_DB vuoto o non valido.")
        return 1

    print("=== Nutrition Setup Base - Wizard Interattivo ===")
    food_name_by_id = {f["id"]: f["name"] for f in foods}
    athlete_name = ask_text("Nome atleta", required=True)
    target_athlete_id = resolve_target_athlete_id(athlete_name)
    paths = runtime_paths_for_athlete(target_athlete_id)
    ensure_athlete_dirs()
    print(f"Destinazione dati atleta: {target_athlete_id}")
    if target_athlete_id != normalize_athlete_id(athlete_name):
        print(
            "Nota: target atleta forzato da --athlete/TV_ATHLETE_ID "
            f"({target_athlete_id}), nome atleta inserito: {athlete_name}."
        )

    template_json_file = paths["template_json"]
    template_md_file = paths["template_md"]
    nutrition_profile_file = data_file(NUTRITION_PROFILE_FILE)

    try:
        nutrition_profile = load_required_nutrition_profile(nutrition_profile_file)
    except ValueError as exc:
        print(f"Errore: {exc}")
        return 1
    safety = evaluate_safety(nutrition_profile)
    if safety.get("warnings"):
        print("\n[WARN] Safety checks profilo:")
        for warn in safety["warnings"]:
            print(f"- {warn}")
    if safety.get("consult_professional"):
        print("\n[STOP] Trigger safety hard rilevato.")
        for err in safety.get("hard_stop", []):
            print(f"- {err}")
        print("Consulta un professionista prima di proseguire con il setup nutrizione.")
        return 1

    if template_json_file.exists():
        template = load_json(template_json_file)
        if not args.force and not ask_yes_no(
            "Template base gia presente. Vuoi modificarlo?",
            default=True,
        ):
            print("Operazione annullata.")
            return 1
    else:
        template = load_json(SHARED_TEMPLATE_FILE)

    if args.strict_no_defaults:
        apply_strict_no_defaults(template)

    template.setdefault("meta", {})
    template["meta"]["owner_athlete_id"] = target_athlete_id
    template["meta"]["source"] = "setup_wizard"
    template["meta"]["profile_ref"] = {
        "path": relpath_or_str(nutrition_profile_file),
        "goal": nutrition_profile.get("profile", {}).get("goal"),
        "profile_generated_at": nutrition_profile.get("meta", {}).get("generated_at"),
    }
    if not template["meta"].get("created_at"):
        template["meta"]["created_at"] = iso_now()
    template["meta"]["updated_at"] = iso_now()

    if args.edit and template.get("meals"):
        edit_existing_options(
            template,
            foods,
            food_name_by_id,
            nutrition_profile,
            allow_manual_block_overrides=args.allow_manual_block_overrides,
        )
    else:
        build_structure_from_scratch(
            template,
            foods,
            food_name_by_id,
            nutrition_profile,
            allow_manual_block_overrides=args.allow_manual_block_overrides,
        )
    collect_user_constraints(template)

    template_json_file.parent.mkdir(parents=True, exist_ok=True)
    template_json_file.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    template_md_file.parent.mkdir(parents=True, exist_ok=True)
    template_md_file.write_text(
        render_markdown(template, target_athlete_id),
        encoding="utf-8",
    )

    print("\n[OK] Nutrition base template aggiornato.")
    print(f"- JSON: {relpath_or_str(template_json_file)}")
    print(f"- MD:   {relpath_or_str(template_md_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
