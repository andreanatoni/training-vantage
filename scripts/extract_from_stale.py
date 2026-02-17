#!/usr/bin/env python3
"""
DEPRECATO (fallback temporaneo).

Parser legacy dei piani STALE markdown in sources/piano_*.md.
Path primario corrente: knowledge/meal_options/*.json (vedi scripts/build_meal_options.py).
"""

import re
from pathlib import Path

try:
    from scripts.food_db import FoodDB
except ModuleNotFoundError:
    from food_db import FoodDB

SOURCES_DIR = Path(__file__).parent.parent / "sources"


class StalePlanParser:
    """Parser per piani STALE completi"""

    # Mapping nomi piani STALE → nomi food-db
    NAME_MAPPING = {
        'Pasta secca': 'Pasta secca (di semola)',
        'Tonno al naturale': 'Tonno al naturale (drenato)',
        'Pollo piastra': 'Pollo petto (cotto in padella)',
        'Pollo alla piastra': 'Pollo petto (cotto in padella)',
        'Pollo': 'Pollo petto (cotto in padella)',
        'Zucchine': 'Zucchine (crude)',
        'Carote': 'Carote (crude)',
        'Passatina di pomodoro': 'Passata di pomodoro',
        'Passatina pomodoro': 'Passata di pomodoro',
        'Riso basmati': 'Riso basmati (crudo)',
        'Patate lesse': 'Patate (senza buccia, bollite)',
        'Patate': 'Patate (senza buccia, bollite)',
        'Merluzzo': 'Merluzzo (surgelato, cotto al forno)',
        'Fesa tacchino': 'Fesa tacchino (affettato)',
        'Tonno in scatola': 'Tonno al naturale (drenato)',
        'Tonno tagliata': 'Tonno tagliata (fresco)',
        'Vitello': 'Vitello (filetto, cotto in padella)',
        'Tacchino': 'Tacchino, fesa (cotto al forno)',
        'Uova': 'Uova intere (gallina)',
        'Uova strapazzate': 'Uova intere (gallina)',
        'Piselli': 'Piselli (in scatola, scolati)',
        'Ragù di vitello': 'Ragù di vitello (40% vitello / 60% passata)',
        'Zenzero grattuggiato': 'Zenzero fresco',
        'Zenzero': 'Zenzero fresco',
        'Parmigiano grattugiato': 'Parmigiano Reggiano',
        'Parmigiano': 'Parmigiano Reggiano',
        'Formaggio spalmabile (Philadelphia Light)': 'Formaggio spalmabile light',
        'Yogurt greco': 'Yogurt greco 0%',
        'Plum cake': 'Plum cake (senza latte/burro)',
        'Ciambellone': 'Plum cake (senza latte/burro)',
        'Ciambellone (senza latte/burro)': 'Plum cake (senza latte/burro)',
    }

    def __init__(self):
        self.food_db = FoodDB()

    def parse_plan_file(self, filepath):
        """Legge piano STALE e estrae struttura completa"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Estrai metadati
        ffm_match = re.search(r'FFM\s+([\d.]+)\s+kg', content)
        bmr_match = re.search(r'BMR.*?=\s+(\d+)\s+kcal', content)
        target_match = re.search(r'arrotondo\s+(\d+)\s+kcal', content)

        ffm = float(ffm_match.group(1)) if ffm_match else None
        bmr = int(bmr_match.group(1)) if bmr_match else None
        target_kcal = int(target_match.group(1)) if target_match else None

        # Estrai pasti
        meals = self._extract_meals(content)

        return {
            'ffm': ffm,
            'bmr': bmr,
            'target_kcal': target_kcal,
            'meals': meals
        }

    def _extract_meals(self, content):
        """Estrae tutti i pasti con opzioni"""
        meals = {}

        # Split per sezioni pasto (es: # ☕ COLAZIONE)
        meal_pattern = r'#\s+[^#\n]+\s+(COLAZIONE|SPUNTINO MATTINA|SPUNTINO SERA|PRANZO|SPUNTINO POMERIGGIO|CENA)[^\n]*\n'
        meal_sections = re.split(meal_pattern, content)

        for i in range(1, len(meal_sections), 2):
            meal_name = meal_sections[i].strip()
            meal_content = meal_sections[i + 1] if i + 1 < len(meal_sections) else ""

            # Estrai target del pasto
            target_match = re.search(r'\*\*Target\*\*:\s*(\d+)\s*kcal\s*\|\s*(\d+)g\s*P\s*\|\s*(\d+)g\s*F\s*\|\s*(\d+)g\s*CHO', meal_content)

            if target_match:
                target = {
                    'kcal': int(target_match.group(1)),
                    'protein': int(target_match.group(2)),
                    'fat': int(target_match.group(3)),
                    'cho': int(target_match.group(4))
                }

                # Estrai opzioni
                options = self._extract_options(meal_content)

                meals[meal_name] = {
                    'target': target,
                    'options': options
                }

        return meals

    def _extract_options(self, meal_content):
        """Estrae tutte le opzioni di un pasto"""
        options = []

        # Split per opzioni (###)
        option_pattern = r'###\s+Opzione\s+\d+\s*-\s*([^\n]+)'
        option_sections = re.split(option_pattern, meal_content)

        for i in range(1, len(option_sections), 2):
            option_name = option_sections[i].strip()
            option_content = option_sections[i + 1] if i + 1 < len(option_sections) else ""

            # Estrai ingredienti
            ingredients = self._extract_ingredients(option_content)

            # Estrai totali
            totals_match = re.search(
                r'\*\*Totali\*\*:\s*(\d+)\s*kcal\s*\|\s*([\d.]+)g\s*P\s*\|\s*([\d.]+)g\s*F\s*\|\s*([\d.]+)g\s*CHO',
                option_content
            )

            totals = None
            if totals_match:
                totals = {
                    'kcal': int(totals_match.group(1)),
                    'protein': float(totals_match.group(2)),
                    'fat': float(totals_match.group(3)),
                    'cho': float(totals_match.group(4))
                }

            # Estrai swap
            swap_match = re.search(r'\*\*Swap\*\*:\s*([^\n]+)', option_content)
            swap = swap_match.group(1).strip() if swap_match else None

            # Estrai quando
            quando_match = re.search(r'\*\*Quando\*\*:\s*([^\n]+)', option_content)
            quando = quando_match.group(1).strip() if quando_match else None

            options.append({
                'name': option_name,
                'ingredients': ingredients,
                'totals': totals,
                'swap': swap,
                'quando': quando
            })

        return options

    def _extract_ingredients(self, option_content):
        """Estrae lista ingredienti con grammature"""
        ingredients = []

        # Pattern: - Nome: quantità unità
        ingredient_pattern = r'-\s+([^:]+):\s*([\d.]+)\s*(g|ml)'

        for match in re.finditer(ingredient_pattern, option_content):
            name = match.group(1).strip()
            amount = float(match.group(2))
            unit = match.group(3)

            # Gestisci OR (alternative)
            if ' OR ' in name:
                parts = [p.strip() for p in name.split(' OR ')]
                ingredients.append({
                    'type': 'alternatives',
                    'items': parts,
                    'amount': amount,
                    'unit': unit
                })
            else:
                ingredients.append({
                    'type': 'single',
                    'name': name,
                    'amount': amount,
                    'unit': unit
                })

        return ingredients

    def scale_plan(self, plan_data, new_bmr):
        """Scala piano per nuovo BMR"""
        old_bmr = plan_data['bmr']
        ratio = new_bmr / old_bmr

        print(f"Scaling: BMR {old_bmr} → {new_bmr} (ratio: {ratio:.3f})")

        # Scala target giornaliero
        plan_data['target_kcal'] = int(plan_data['target_kcal'] * ratio)

        # Scala ogni pasto
        for meal_name, meal_data in plan_data['meals'].items():
            # Scala target pasto
            meal_data['target']['kcal'] = int(meal_data['target']['kcal'] * ratio)
            meal_data['target']['protein'] = int(meal_data['target']['protein'] * ratio)
            meal_data['target']['fat'] = int(meal_data['target']['fat'] * ratio)
            meal_data['target']['cho'] = int(meal_data['target']['cho'] * ratio)

            # Scala opzioni
            for option in meal_data['options']:
                # Scala ingredienti
                for ing in option['ingredients']:
                    ing['amount'] = round(ing['amount'] * ratio, 1)

                # Ricalcola totali
                option['totals'] = self._recalculate_totals(option['ingredients'])

        return plan_data

    def _find_food_name(self, ingredient_name):
        """Trova nome alimento nel food-db (con fuzzy matching se necessario)"""
        # 1. Prova mapping esplicito
        if ingredient_name in self.NAME_MAPPING:
            return self.NAME_MAPPING[ingredient_name]

        # 2. Prova match esatto
        if self.food_db.get(ingredient_name):
            return ingredient_name

        # 3. Prova ricerca parziale
        results = self.food_db.search(ingredient_name.lower())
        if results:
            # Restituisci primo match
            return results[0]['name']

        return None

    def _recalculate_totals(self, ingredients):
        """Ricalcola totali da ingredienti"""
        total_kcal = 0
        total_protein = 0
        total_fat = 0
        total_cho = 0

        for ing in ingredients:
            if ing['type'] == 'single':
                # Trova nome esatto nel food-db
                food_name = self._find_food_name(ing['name'])

                if food_name:
                    nutrients = self.food_db.calculate_nutrients(food_name, ing['amount'])
                    if nutrients:
                        total_kcal += nutrients['kcal']
                        total_protein += nutrients['protein']
                        total_fat += nutrients['fat']
                        total_cho += nutrients['cho']

            elif ing['type'] == 'alternatives':
                # Usa primo alternativo per calcolo
                first_alt = ing['items'][0]
                food_name = self._find_food_name(first_alt)

                if food_name:
                    nutrients = self.food_db.calculate_nutrients(food_name, ing['amount'])
                    if nutrients:
                        total_kcal += nutrients['kcal']
                        total_protein += nutrients['protein']
                        total_fat += nutrients['fat']
                        total_cho += nutrients['cho']

        return {
            'kcal': round(total_kcal, 0),
            'protein': round(total_protein, 1),
            'fat': round(total_fat, 1),
            'cho': round(total_cho, 1)
        }


# Test
if __name__ == '__main__':
    parser = StalePlanParser()

    # Test su piano forza
    plan_file = SOURCES_DIR / "piano_forza.md"
    plan_data = parser.parse_plan_file(plan_file)

    print(f"Piano FORZA estratto:")
    print(f"  FFM: {plan_data['ffm']}kg")
    print(f"  BMR: {plan_data['bmr']} kcal")
    print(f"  Target: {plan_data['target_kcal']} kcal")
    print()

    print("PASTI:")
    for meal_name, meal_data in plan_data['meals'].items():
        print(f"\n{meal_name}: {len(meal_data['options'])} opzioni")
        print(f"  Target: {meal_data['target']['kcal']} kcal")

        # Mostra prima opzione
        if meal_data['options']:
            opt = meal_data['options'][0]
            print(f"  Opzione 1: {opt['name']}")
            print(f"    Ingredienti: {len(opt['ingredients'])}")
            if opt['totals']:
                print(f"    Totali: {opt['totals']['kcal']} kcal")

    # Test scaling
    print("\n" + "=" * 70)
    print("TEST SCALING (1690 → 1657)")
    print("=" * 70)

    plan_scaled = parser.scale_plan(plan_data, 1657)

    print(f"Nuovo target: {plan_scaled['target_kcal']} kcal (era {plan_data['target_kcal']})")
