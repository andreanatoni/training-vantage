#!/usr/bin/env python3
"""
Genera piani nutrizionali completi da piani STALE esistenti.

Estrae tutte le opzioni validate dai piani esistenti, scala per nuovo BMR,
ricalcola totali, genera markdown completo.
"""

from pathlib import Path
from datetime import datetime
import json

try:
    from scripts.legacy.extract_from_stale import StalePlanParser
    from scripts.food_db import FoodDB
except ModuleNotFoundError:
    from legacy.extract_from_stale import StalePlanParser
    from food_db import FoodDB

ROOT = Path(__file__).parent.parent.parent
SOURCES_DIR = ROOT / "sources"
PLANS_DIR = ROOT / "plans" / "nutrition"
DATA_DIR = ROOT / "data"
COMPOSITION_FILE = DATA_DIR / "composition.json"


# Mapping categoria → file sorgente STALE
CATEGORY_SOURCES = {
    'forza': 'piano_forza.md',
    'easy-run': 'piano_easy_run.md',
    'qualita': 'piano_qualita.md',
    'tempo': 'piano_tempo.md',
    'lungo': 'piano_lungo.md',
    'rest': 'piano_rest.md',
    'pizza-day': 'piano_pizza_day.md',
    'domenica': 'piano_domenica.md'
}


def get_current_bmr():
    """Ottieni BMR attuale da composition.json"""
    with open(COMPOSITION_FILE, 'r') as f:
        data = json.load(f)

    # Ultima misurazione
    latest = data['measurements'][-1]
    return int(latest['bmr'])


def format_ingredient_line(ing_data):
    """Formatta linea ingrediente"""
    if ing_data['type'] == 'single':
        return f"- {ing_data['name']}: {ing_data['amount']:.0f} {ing_data['unit']}"
    elif ing_data['type'] == 'alternatives':
        items_str = ' OR '.join(ing_data['items'])
        return f"- {items_str}: {ing_data['amount']:.0f} {ing_data['unit']}"


def generate_plan_markdown(category, plan_data, current_bmr):
    """Genera markdown completo per un piano"""

    lines = []

    # META comment
    lines.append(f"<!-- META")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"FFM: {plan_data.get('ffm', 'N/A')} kg")
    lines.append(f"BMR: {current_bmr} kcal")
    lines.append(f"Status: CURRENT")
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


def generate_plan(category, current_bmr):
    """Genera piano completo per categoria"""

    # Trova file sorgente
    source_file = CATEGORY_SOURCES.get(category)

    if not source_file:
        print(f"  ❌ Categoria {category} non trovata in mapping")
        return False

    source_path = SOURCES_DIR / source_file

    if not source_path.exists():
        print(f"  ❌ File sorgente non trovato: {source_path}")
        return False

    # Parse
    parser = StalePlanParser()
    plan_data = parser.parse_plan_file(source_path)

    old_bmr = plan_data['bmr']

    if not old_bmr:
        print(f"  ❌ BMR non trovato nel piano STALE")
        return False

    # Scala
    plan_scaled = parser.scale_plan(plan_data, current_bmr)

    # Genera markdown
    markdown = generate_plan_markdown(category, plan_scaled, current_bmr)

    # Salva
    output_file = PLANS_DIR / f"{category}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    # Report
    num_options = sum(len(meal['options']) for meal in plan_scaled['meals'].values())
    print(f"  ✅ {category}: {num_options} opzioni totali")
    print(f"     Scaled: BMR {old_bmr} → {current_bmr} (ratio {current_bmr/old_bmr:.3f})")
    print(f"     Target: {plan_scaled['target_kcal']} kcal")

    return True


def generate_all_plans():
    """Genera tutti gli 8 piani"""

    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║           RIGENERAZIONE PIANI NUTRIZIONALI COMPLETI               ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()

    current_bmr = get_current_bmr()
    print(f"BMR attuale: {current_bmr} kcal (da composition.json)")
    print()

    # Genera ogni categoria
    success_count = 0

    for category in CATEGORY_SOURCES.keys():
        print(f"Generando {category}...")
        if generate_plan(category, current_bmr):
            success_count += 1
        print()

    # Summary
    print("─" * 70)
    print(f"Completato: {success_count}/{len(CATEGORY_SOURCES)} piani generati con successo")
    print()


if __name__ == '__main__':
    generate_all_plans()
