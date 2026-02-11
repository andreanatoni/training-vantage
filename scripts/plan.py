#!/usr/bin/env python3
"""
/tv plan <categoria> [--all]

Genera piano nutrizionale completo per categoria estraendo dai piani STALE validati.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from extract_from_stale import StalePlanParser

SOURCES_DIR = Path(__file__).parent.parent / "sources"
PLANS_DIR = Path(__file__).parent.parent / "plans" / "nutrition"
DATA_DIR = Path(__file__).parent.parent / "data"
COMPOSITION_FILE = DATA_DIR / "composition.json"
CHANGELOG_FILE = DATA_DIR / "changelog.json"

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

VALID_CATEGORIES = list(CATEGORY_SOURCES.keys())


def get_current_bmr():
    """Ottieni BMR attuale da composition.json"""
    with open(COMPOSITION_FILE, 'r') as f:
        data = json.load(f)
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


def generate_plan(category, silent=False):
    """Genera piano completo per categoria"""
    # Trova file sorgente
    source_file = CATEGORY_SOURCES.get(category)

    if not source_file:
        print(f"❌ Categoria {category} non trovata in mapping")
        return False

    source_path = SOURCES_DIR / source_file

    if not source_path.exists():
        print(f"❌ File sorgente non trovato: {source_path}")
        return False

    # Parse e scala
    parser = StalePlanParser()
    plan_data = parser.parse_plan_file(source_path)

    old_bmr = plan_data['bmr']
    current_bmr = get_current_bmr()

    if not old_bmr:
        print(f"❌ BMR non trovato nel piano STALE")
        return False

    plan_scaled = parser.scale_plan(plan_data, current_bmr)

    # Genera markdown
    markdown = generate_plan_markdown(category, plan_scaled, current_bmr)

    # Salva
    output_file = PLANS_DIR / f"{category}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    # Report
    num_options = sum(len(meal['options']) for meal in plan_scaled['meals'].values())

    if not silent:
        print(f"✓ Piano {category}: {plan_scaled['target_kcal']} kcal | {num_options} opzioni → {output_file}")

    return True


def generate_all():
    """Rigenera tutti gli 8 piani"""
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║           RIGENERAZIONE PIANI NUTRIZIONALI COMPLETI               ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
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


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in VALID_CATEGORIES + ['--all']:
        print(f"Usage: plan.py <categoria> | --all")
        print(f"Categorie: {', '.join(VALID_CATEGORIES)}")
        sys.exit(1)

    if sys.argv[1] == '--all':
        generate_all()
    else:
        generate_plan(sys.argv[1])
