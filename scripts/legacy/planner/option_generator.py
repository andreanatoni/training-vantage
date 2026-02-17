#!/usr/bin/env python3
"""
option_generator.py - Generatore singola opzione pasto

Prende un'opzione dal piano_base parser e genera:
1. Chiamata meal_balancer per grammature ottimizzate
2. Calcolo swap per alternative OR
3. Gestione caso speciale yogurt (2 versioni)
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.ingredient_mapper import (
    map_ingredient_to_food_id,
    get_ingredient_category
)
from scripts.swap_calculator import SwapCalculator
from scripts.meal_balancer import MealBalancerData, MealBalancer
from scripts.generation_logger import get_logger


class OptionGenerator:
    """Generatore per singola opzione di pasto"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

        # Initialize components
        self.swap_calc = SwapCalculator(data_dir / 'FOOD_DB.json')
        self.balancer_data = MealBalancerData(data_dir)
        self.balancer = MealBalancer(self.balancer_data)

    def generate_option(
        self,
        option: Dict[str, Any],
        meal_target: Dict[str, float],
        meal_context: str = 'regular'
    ) -> List[Dict[str, Any]]:
        """
        Genera opzione(i) per un pasto

        Args:
            option: Opzione dal parser (con ingredients, title, when, etc.)
            meal_target: Target macro per pasto {'kcal': X, 'P': X, 'CHO': X, 'F': X}
            meal_context: Contesto pasto (regular, pre_run, post_run, recovery)

        Returns:
            Lista di varianti generate (1 se normale, 2 se yogurt special case)
            [
                {
                    'variant': 'main' o 'a'/'b',
                    'title': str,
                    'items': [
                        {
                            'food_id': str,
                            'name': str,
                            'qty': float,
                            'unit': 'g',
                            'alternatives': [
                                {'food_id': str, 'name': str, 'qty': float, 'swap_method': str},
                                ...
                            ]
                        },
                        ...
                    ],
                    'totals': {'kcal': X, 'P': X, 'CHO': X, 'F': X, 'Fibre': X},
                    'delta': {'kcal_pct': X, 'P_pct': X, ...},
                    'when': str
                },
                ...
            ]
        """
        # Generate single variant
        variant = self._generate_single_variant(option, meal_target, meal_context, variant_id='main')
        return [variant]

    def _generate_single_variant(
        self,
        option: Dict[str, Any],
        meal_target: Dict[str, float],
        meal_context: str,
        variant_id: str = 'main',
        override_ingredients: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Genera singola variante di opzione

        Args:
            option: Opzione dal parser
            meal_target: Target macro
            meal_context: Contesto
            variant_id: ID variante ('main', 'a', 'b')
            override_ingredients: Se fornito, usa questi invece di option['ingredients']

        Returns:
            Dict con variante generata
        """
        ingredients = override_ingredients if override_ingredients else option['ingredients']

        # 1. Map ingredienti → food_db_ids (prendi prima alternativa di ogni OR)
        allowed_foods = []
        ingredient_mapping = []  # Track mapping for swap calculation

        for ing in ingredients:
            food_id = map_ingredient_to_food_id(ing['name'])

            if not food_id:
                warning_msg = f"Ingredient '{ing['name']}' not found in mapping, skipping"
                print(f"⚠️  Warning: {warning_msg}")

                # Log to report
                logger = get_logger()
                logger.warning(warning_msg, {
                    'ingredient': ing['name'],
                    'category': ing.get('category', 'Unknown')
                })
                continue

            allowed_foods.append(food_id)

            # Store for later swap calculation
            ingredient_mapping.append({
                'original_name': ing['name'],
                'category': ing['category'],
                'food_id': food_id,
                'alternatives': ing['alternatives']
            })

        if not allowed_foods:
            raise ValueError(f"No valid foods mapped for option '{option['title']}'")

        # 2. Call meal balancer
        try:
            result = self.balancer.balance_meal(
                target=meal_target,
                meal_context=meal_context,
                allowed_food_db_ids=allowed_foods
            )
        except Exception as e:
            raise RuntimeError(f"Meal balancer failed for option '{option['title']}': {e}")

        # Get recommended version (realistic or unconstrained)
        recommendation = result['recommendation']
        solution = result[recommendation]

        # 3. Build items with quantities from balancer
        items = []

        for ing_map in ingredient_mapping:
            food_id = ing_map['food_id']

            # Find qty from balancer solution
            food_item = next((item for item in solution['items'] if item['food_db_id'] == food_id), None)

            if not food_item or food_item['qty']['amount'] == 0:
                # Food not used in solution, skip
                continue

            qty = food_item['qty']['amount']

            # Get category for swap calculation
            category = get_ingredient_category(food_id)

            # Calculate swaps for alternatives
            alternatives = []

            for alt_name in ing_map['alternatives']:
                alt_food_id = map_ingredient_to_food_id(alt_name)

                if not alt_food_id:
                    print(f"⚠️  Warning: Alternative '{alt_name}' not found in mapping, skipping")
                    continue

                # Skip if alternative is the same food as base (dedup)
                if alt_food_id == food_id:
                    continue

                try:
                    swap_result = self.swap_calc.calculate_swap(
                        food_id,
                        qty,
                        alt_food_id,
                        category
                    )

                    alternatives.append({
                        'food_id': swap_result['alt_food_id'],
                        'name': self.balancer_data.food_db_index[swap_result['alt_food_id']]['name'],
                        'qty': swap_result['alt_qty_g'],
                        'swap_method': swap_result['swap_method']
                    })
                except Exception as e:
                    print(f"⚠️  Warning: Swap calculation failed for '{alt_name}': {e}")
                    continue

            items.append({
                'food_id': food_id,
                'name': self.balancer_data.food_db_index[food_id]['name'],
                'qty': qty,
                'unit': 'g',
                'category': ing_map['category'],
                'alternatives': alternatives
            })

        # 4. Calculate totals and delta
        totals = solution['totals']

        delta = {
            'kcal_pct': ((totals['kcal'] - meal_target['kcal']) / meal_target['kcal'] * 100) if meal_target['kcal'] > 0 else 0,
            'P_pct': ((totals['P'] - meal_target['P']) / meal_target['P'] * 100) if meal_target['P'] > 0 else 0,
            'CHO_pct': ((totals['CHO'] - meal_target['CHO']) / meal_target['CHO'] * 100) if meal_target['CHO'] > 0 else 0,
            'F_pct': ((totals['F'] - meal_target['F']) / meal_target['F'] * 100) if meal_target['F'] > 0 else 0,
        }

        return {
            'variant': variant_id,
            'title': option['title'],
            'items': items,
            'totals': totals,
            'delta': delta,
            'when': option['when']
        }



if __name__ == '__main__':
    # Test option generator
    from scripts.piano_base_parser import parse_piano_base

    data_dir = Path('data')
    piano_base_path = Path('sources/piano_base_ottimizzato.md')

    # Parse piano base
    piano_base = parse_piano_base(piano_base_path)

    # Get first breakfast option (should have yogurt special case)
    colazione = piano_base['COLAZIONE']
    option1 = colazione['options'][0]

    print("=" * 80)
    print("OPTION GENERATOR - Test")
    print("=" * 80)
    print(f"\nTesting option: {option1['title']}")
    print(f"Ingredients: {len(option1['ingredients'])}")
    for ing in option1['ingredients']:
        alts = f" (OR {', '.join(ing['alternatives'])})" if ing['alternatives'] else ""
        print(f"  - {ing['category']}: {ing['name']}{alts}")

    # Define meal target (example for REST day breakfast)
    meal_target = {
        'kcal': 484,
        'P': 30.8,
        'CHO': 55.0,
        'F': 12.6
    }

    # Generate option
    generator = OptionGenerator(data_dir)

    try:
        variants = generator.generate_option(option1, meal_target, 'meal')

        print(f"\n✅ Generated {len(variants)} variant(s)")

        for variant in variants:
            print(f"\n{'─' * 80}")
            print(f"Variant: {variant['variant']} - {variant['title']}")
            print(f"When: {variant['when']}")
            print(f"\nItems:")

            for item in variant['items']:
                alts_str = ""
                if item['alternatives']:
                    alts_list = [f"{a['name']} {a['qty']}g ({a['swap_method']})" for a in item['alternatives']]
                    alts_str = f" OR {' OR '.join(alts_list)}"

                print(f"  - {item['name']}: {item['qty']}{item['unit']}{alts_str}")

            print(f"\nTotals: kcal {variant['totals']['kcal']:.0f} | P {variant['totals']['P']:.1f}g | CHO {variant['totals']['CHO']:.1f}g | F {variant['totals']['F']:.1f}g")
            print(f"Delta:  kcal {variant['delta']['kcal_pct']:+.1f}% | P {variant['delta']['P_pct']:+.1f}% | CHO {variant['delta']['CHO_pct']:+.1f}% | F {variant['delta']['F_pct']:+.1f}%")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
