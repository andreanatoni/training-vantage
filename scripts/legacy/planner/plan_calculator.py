#!/usr/bin/env python3
"""
Calcolatore piani nutrizionali

Genera piani quantitativi basati su:
- FFM e BMR attuali
- Categoria giorno (rest, forza, easy-run, etc.)
- Piano base validato
- Food DB
"""

import json
from pathlib import Path
from datetime import datetime

# Import parsers
from food_db import FoodDB
from piano_base import PianoBase

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
COMP_FILE = DATA_DIR / "composition.json"


# Moltiplicatori BMR per categoria
CATEGORY_MULTIPLIERS = {
    'rest': 1.30,
    'forza': 1.50,
    'easy-run': 1.55,
    'qualita': 1.60,
    'tempo': 1.55,
    'lungo': 1.65,
    'pizza-day': 1.55,
    'domenica': 1.33
}

# Distribuzione % kcal per pasto (da validare)
MEAL_DISTRIBUTION = {
    'rest': {'COLAZIONE': 18, 'SPUNTINO MATTINA': 8, 'PRANZO': 35,
             'SPUNTINO POMERIGGIO': 13, 'SPUNTINO SERA': 0, 'CENA': 26},
    'forza': {'COLAZIONE': 18, 'SPUNTINO MATTINA': 8, 'PRANZO': 34,
              'SPUNTINO POMERIGGIO': 15, 'SPUNTINO SERA': 4, 'CENA': 26},
    'easy-run': {'COLAZIONE': 18, 'SPUNTINO MATTINA': 8, 'PRANZO': 35,
                 'SPUNTINO POMERIGGIO': 13, 'SPUNTINO SERA': 4, 'CENA': 27},
    'qualita': {'COLAZIONE': 17, 'SPUNTINO MATTINA': 7, 'PRANZO': 33,
                'SPUNTINO POMERIGGIO': 18, 'SPUNTINO SERA': 5, 'CENA': 25},
    'tempo': {'COLAZIONE': 18, 'SPUNTINO MATTINA': 8, 'PRANZO': 35,
              'SPUNTINO POMERIGGIO': 13, 'SPUNTINO SERA': 4, 'CENA': 27},
    'lungo': {'COLAZIONE': 18, 'SPUNTINO MATTINA': 8, 'PRANZO': 34,
              'SPUNTINO POMERIGGIO': 15, 'SPUNTINO SERA': 5, 'CENA': 25},
    'pizza-day': {'COLAZIONE': 16, 'SPUNTINO MATTINA': 8, 'PRANZO': 28,
                  'SPUNTINO POMERIGGIO': 10, 'SPUNTINO SERA': 0, 'CENA': 38},
    'domenica': {'COLAZIONE': 20, 'SPUNTINO MATTINA': 9, 'PRANZO': 33,
                 'SPUNTINO POMERIGGIO': 12, 'SPUNTINO SERA': 0, 'CENA': 26}
}

# Distribuzione macro target (% kcal)
MACRO_DISTRIBUTION = {
    'rest': {'protein_pct': 24, 'fat_pct': 25, 'cho_pct': 51},
    'forza': {'protein_pct': 23, 'fat_pct': 23, 'cho_pct': 54},
    'easy-run': {'protein_pct': 23, 'fat_pct': 24, 'cho_pct': 53},
    'qualita': {'protein_pct': 22, 'fat_pct': 23, 'cho_pct': 55},
    'tempo': {'protein_pct': 23, 'fat_pct': 24, 'cho_pct': 53},
    'lungo': {'protein_pct': 22, 'fat_pct': 23, 'cho_pct': 55},
    'pizza-day': {'protein_pct': 24, 'fat_pct': 30, 'cho_pct': 46},
    'domenica': {'protein_pct': 24, 'fat_pct': 30, 'cho_pct': 46}
}


class PlanCalculator:
    """Calcolatore piani nutrizionali"""

    def __init__(self):
        self.food_db = FoodDB()
        self.piano_base = PianoBase()
        self.current_ffm = None
        self.current_bmr = None
        self._load_current_data()

    def _load_current_data(self):
        """Carica FFM e BMR attuali"""
        with open(COMP_FILE, 'r') as f:
            data = json.load(f)

        last_measurement = data['measurements'][-1]
        self.current_ffm = last_measurement['ffm']
        self.current_bmr = last_measurement['bmr']

    def calculate_target_kcal(self, category):
        """Calcola target kcal giornaliero per categoria"""
        multiplier = CATEGORY_MULTIPLIERS.get(category, 1.5)
        return int(self.current_bmr * multiplier)

    def calculate_target_macros(self, category, total_kcal):
        """Calcola target macro giornalieri"""
        dist = MACRO_DISTRIBUTION.get(category, {'protein_pct': 23, 'fat_pct': 25, 'cho_pct': 52})

        protein_g = int((total_kcal * dist['protein_pct'] / 100) / 4)
        fat_g = int((total_kcal * dist['fat_pct'] / 100) / 9)
        cho_g = int((total_kcal * dist['cho_pct'] / 100) / 4)

        return {
            'protein': protein_g,
            'fat': fat_g,
            'cho': cho_g
        }

    def distribute_kcal_to_meals(self, category, total_kcal):
        """Distribuisce kcal totali tra i pasti"""
        dist = MEAL_DISTRIBUTION.get(category, MEAL_DISTRIBUTION['rest'])

        meal_targets = {}
        for meal_name, pct in dist.items():
            meal_targets[meal_name] = int(total_kcal * pct / 100)

        return meal_targets

    def generate_plan_summary(self, category):
        """Genera summary piano per categoria"""

        # Calcola target
        total_kcal = self.calculate_target_kcal(category)
        macros = self.calculate_target_macros(category, total_kcal)
        meal_targets = self.distribute_kcal_to_meals(category, total_kcal)

        # Crea summary
        plan = {
            'category': category,
            'generated': datetime.now().isoformat(),
            'ffm': self.current_ffm,
            'bmr': self.current_bmr,
            'target_kcal': total_kcal,
            'target_macros': macros,
            'meals': {}
        }

        # Per ogni pasto, mostra prima opzione come esempio
        for meal_name in ['COLAZIONE', 'SPUNTINO MATTINA', 'PRANZO',
                          'SPUNTINO POMERIGGIO', 'SPUNTINO SERA', 'CENA']:

            target_kcal = meal_targets.get(meal_name, 0)

            if target_kcal == 0:
                continue

            # Prendi prima opzione dal piano base
            options = self.piano_base.get_meal_options(meal_name)

            if options:
                first_option = options[0]

                plan['meals'][meal_name] = {
                    'target_kcal': target_kcal,
                    'option_name': first_option['name'],
                    'ingredients': first_option['ingredients'],
                    'note': 'Piano semplificato — mostra solo prima opzione. Implementazione completa in sviluppo.'
                }

        return plan

    def print_plan_summary(self, category):
        """Stampa summary piano"""
        plan = self.generate_plan_summary(category)

        print(f"╔═══════════════════════════════════════════════════════════════════╗")
        print(f"║          PIANO {category.upper()} (SUMMARY - WORK IN PROGRESS)          ║")
        print(f"╚═══════════════════════════════════════════════════════════════════╝")
        print()
        print(f"FFM: {plan['ffm']:.2f}kg | BMR: {plan['bmr']} kcal")
        print(f"Target: {plan['target_kcal']} kcal")
        print(f"Macro: P {plan['target_macros']['protein']}g | F {plan['target_macros']['fat']}g | CHO {plan['target_macros']['cho']}g")
        print()

        for meal_name, meal_data in plan['meals'].items():
            print(f"{meal_name} ({meal_data['target_kcal']} kcal)")
            print(f"  Opzione: {meal_data['option_name']}")
            print()


# Test rapido
if __name__ == '__main__':
    calc = PlanCalculator()

    print(f"FFM attuale: {calc.current_ffm:.2f}kg")
    print(f"BMR attuale: {calc.current_bmr} kcal")
    print()

    # Test calcolo target
    for cat in ['rest', 'forza', 'lungo']:
        target = calc.calculate_target_kcal(cat)
        print(f"{cat}: {target} kcal")

    print()
    print("=" * 70)
    print()

    # Test piano summary
    calc.print_plan_summary('forza')
