#!/usr/bin/env python3
"""
category_plan_generator.py - Generatore piano completo per categoria

Genera piano nutrizionale completo per una categoria (rest, forza, etc.)
Orchestra option_generator per tutti i pasti.
"""

from typing import Dict, Any
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.piano_base_parser import parse_piano_base
from scripts.option_generator import OptionGenerator
from scripts.generation_logger import get_logger


class CategoryPlanGenerator:
    """Generatore piano completo categoria"""

    # Meal order
    MEAL_ORDER = ['COLAZIONE', 'SPUNTINO_AM', 'PRANZO', 'SPUNTINO_PM', 'CENA']

    def __init__(self, data_dir: Path, piano_base_path: Path):
        self.data_dir = data_dir
        self.piano_base = parse_piano_base(piano_base_path)
        self.option_gen = OptionGenerator(data_dir)

        # Load category data
        self.day_profiles = self._load_json(data_dir / 'DAY_PROFILES.json')
        self.meal_distributions = self._load_json(data_dir / 'MEAL_DISTRIBUTION.json')
        self.composition = self._load_json(data_dir / 'composition.json')

    def _load_json(self, path: Path) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def generate_category_plan(self, category_id: str) -> Dict[str, Any]:
        """
        Genera piano completo per categoria

        Args:
            category_id: rest, forza, easy_run, qualita, tempo, lungo, pizza_day, domenica

        Returns:
            {
                'category_id': str,
                'category_name': str,
                'target_daily': dict,
                'ffm': float,
                'peso': float,
                'bmr': float,
                'generated': str (date),
                'meals': {
                    'COLAZIONE': {
                        'timing': str,
                        'target': dict,
                        'options': [...]
                    },
                    ...
                }
            }
        """
        # Get day profile
        profile = self._get_day_profile(category_id)

        # Get meal distribution
        distribution = self._get_meal_distribution(profile['distribution_id'])

        # Get current composition
        latest_comp = self.composition['measurements'][-1]

        # Generate meals
        meals = {}

        for meal_id in self.MEAL_ORDER:
            if meal_id not in self.piano_base:
                print(f"⚠️  Warning: Meal '{meal_id}' not found in piano_base, skipping")
                continue

            meal_data = self.piano_base[meal_id]

            # Find meal slot in distribution
            meal_slot = next(
                (slot for slot in distribution['meal_slots'] if self._match_meal_slot(slot['id'], meal_id)),
                None
            )

            if not meal_slot:
                print(f"⚠️  Warning: No distribution found for meal '{meal_id}', skipping")
                continue

            # Calculate meal target from distribution %
            meal_target = self._calculate_meal_target(profile['totals_daily'], meal_slot)

            # Generate options for this meal
            options = []

            for option in meal_data['options']:
                try:
                    variants = self.option_gen.generate_option(
                        option,
                        meal_target,
                        meal_context='meal'
                    )
                    options.extend(variants)
                except Exception as e:
                    error_msg = f"Failed to generate option '{option['title']}' for meal '{meal_id}': {e}"
                    print(f"⚠️  Warning: {error_msg}")

                    # Log to report
                    logger = get_logger()
                    logger.error(error_msg, {
                        'category': category_id,
                        'meal': meal_id,
                        'option': option['title']
                    })
                    continue

            meals[meal_id] = {
                'timing': meal_data['timing'],
                'target': meal_target,
                'options': options
            }

        return {
            'category_id': category_id,
            'category_name': profile['name'],
            'target_daily': profile['totals_daily'],
            'ffm': latest_comp['ffm'],
            'peso': latest_comp['weight'],
            'bmr': latest_comp['bmr'],
            'generated': latest_comp['date'],  # Use composition date as reference
            'meals': meals
        }

    def _get_day_profile(self, category_id: str) -> Dict:
        """Get day profile by ID"""
        for profile in self.day_profiles['profiles']:
            if profile['id'] == category_id:
                return profile
        raise ValueError(f"Day profile '{category_id}' not found")

    def _get_meal_distribution(self, distribution_id: str) -> Dict:
        """Get meal distribution by ID"""
        for dist in self.meal_distributions['distributions']:
            if dist['id'] == distribution_id:
                return dist
        raise ValueError(f"Meal distribution '{distribution_id}' not found")

    def _match_meal_slot(self, slot_id: str, meal_id: str) -> bool:
        """Match meal slot ID to meal ID"""
        slot_lower = slot_id.lower()
        meal_lower = meal_id.lower()

        # Direct match
        if slot_lower == meal_lower:
            return True

        # Pattern matching
        if 'colazione' in slot_lower and meal_lower == 'colazione':
            return True
        if 'spuntino' in slot_lower and 'mattina' in slot_lower and meal_lower == 'spuntino_am':
            return True
        if 'pranzo' in slot_lower and meal_lower == 'pranzo':
            return True
        if 'spuntino' in slot_lower and 'pomeriggio' in slot_lower and meal_lower == 'spuntino_pm':
            return True
        if 'cena' in slot_lower and meal_lower == 'cena':
            return True

        return False

    def _calculate_meal_target(self, daily_totals: Dict, meal_slot: Dict) -> Dict[str, float]:
        """Calculate meal target from daily totals and meal slot %"""
        return {
            'kcal': daily_totals['kcal'] * meal_slot['kcal_pct'] / 100.0,
            'P': daily_totals['P'] * meal_slot['P_pct'] / 100.0,
            'CHO': daily_totals['CHO'] * meal_slot['CHO_pct'] / 100.0,
            'F': daily_totals['F'] * meal_slot['F_pct'] / 100.0,
        }


if __name__ == '__main__':
    # Test category plan generator
    data_dir = Path('data')
    piano_base_path = Path('sources/piano_base_ottimizzato.md')

    generator = CategoryPlanGenerator(data_dir, piano_base_path)

    print("=" * 80)
    print("CATEGORY PLAN GENERATOR - Test")
    print("=" * 80)

    # Test with REST category
    category_id = 'rest'
    print(f"\nGenerating plan for category: {category_id}")

    try:
        plan = generator.generate_category_plan(category_id)

        print(f"\n✅ Plan generated successfully!")
        print(f"   Category: {plan['category_name']}")
        print(f"   Target daily: {plan['target_daily']['kcal']} kcal | {plan['target_daily']['P']}g P | {plan['target_daily']['CHO']}g CHO | {plan['target_daily']['F']}g F")
        print(f"   FFM: {plan['ffm']:.2f} kg | Peso: {plan['peso']:.2f} kg | BMR: {plan['bmr']} kcal")
        print(f"\n   Meals:")

        for meal_id, meal_data in plan['meals'].items():
            print(f"     {meal_id}: {len(meal_data['options'])} options")

        # Total options across all meals
        total_options = sum(len(m['options']) for m in plan['meals'].values())
        print(f"\n   Total options: {total_options}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
