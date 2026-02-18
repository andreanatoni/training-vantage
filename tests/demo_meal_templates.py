#!/usr/bin/env python3
"""
Demo: Meal Template Validation in Action

Shows:
1. Valid colazione → builds successfully
2. Invalid colazione (no protein) → fails validation before calling solver
3. Invalid colazione (has veg) → fails validation before calling solver
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.nutrition.plan_builder import PlanBuilder


def demo_valid_colazione():
    """Demo 1: Valid colazione builds successfully"""
    print("=" * 80)
    print("DEMO 1: VALID COLAZIONE")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n✅ Valid colazione: carb + protein + fat + fruit")
    print("   Foods: yogurt_greco_0_lipidi, fette_biscottate, marmellata, mandorle\n")

    try:
        plan = builder.build_day_plan(
            profile_id='rest',
            allowed_foods_per_meal={
                'colazione': ['yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata', 'mandorle'],
                'spuntino_mattina': ['mela'],
                'pranzo': ['pasta_di_semola', 'pollo_petto_cotto_in_padella', 'zucchine_crude', 'olio_di_oliva_extra_vergine'],
                'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
                'cena': ['salmone', 'patate_bollite_senza_buccia', 'insalata', 'olio_di_oliva_extra_vergine']
            }
        )

        print("\n✅ SUCCESS: Plan built without validation errors")

    except ValueError as e:
        print(f"\n❌ UNEXPECTED: Validation failed - {e}")


def demo_invalid_colazione_no_protein():
    """Demo 2: Invalid colazione (no protein) fails BEFORE calling solver"""
    print("\n\n" + "=" * 80)
    print("DEMO 2: INVALID COLAZIONE (missing protein)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n❌ Invalid colazione: only carb + fruit (NO PROTEIN)")
    print("   Foods: fette_biscottate, marmellata\n")

    try:
        plan = builder.build_day_plan(
            profile_id='rest',
            allowed_foods_per_meal={
                'colazione': ['fette_biscottate', 'marmellata'],  # NO PROTEIN!
                'spuntino_mattina': ['mela'],
                'pranzo': ['pasta_di_semola', 'pollo_petto_cotto_in_padella', 'zucchine_crude', 'olio_di_oliva_extra_vergine'],
                'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
                'cena': ['salmone', 'patate_bollite_senza_buccia', 'insalata', 'olio_di_oliva_extra_vergine']
            }
        )

        print("\n❌ UNEXPECTED: Plan built (should have failed validation)")

    except ValueError as e:
        print(f"✅ EXPECTED: Validation caught error BEFORE calling solver")
        print(f"   Error: {e}")


def demo_invalid_colazione_has_veg():
    """Demo 3: Invalid colazione (has veg) fails BEFORE calling solver"""
    print("\n\n" + "=" * 80)
    print("DEMO 3: INVALID COLAZIONE (forbidden veg)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n❌ Invalid colazione: has vegetables (FORBIDDEN)")
    print("   Foods: yogurt_greco_0_lipidi, fette_biscottate, zucchine_crude\n")

    try:
        plan = builder.build_day_plan(
            profile_id='rest',
            allowed_foods_per_meal={
                'colazione': ['yogurt_greco_0_lipidi', 'fette_biscottate', 'zucchine_crude'],  # VEG FORBIDDEN!
                'spuntino_mattina': ['mela'],
                'pranzo': ['pasta_di_semola', 'pollo_petto_cotto_in_padella', 'zucchine_crude', 'olio_di_oliva_extra_vergine'],
                'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
                'cena': ['salmone', 'patate_bollite_senza_buccia', 'insalata', 'olio_di_oliva_extra_vergine']
            }
        )

        print("\n❌ UNEXPECTED: Plan built (should have failed validation)")

    except ValueError as e:
        print(f"✅ EXPECTED: Validation caught error BEFORE calling solver")
        print(f"   Error: {e}")


def main():
    """Run all demos"""
    print("\n")
    print("=" * 80)
    print("🎬 MEAL TEMPLATE VALIDATION - LIVE DEMOS")
    print("=" * 80)
    print("\nShowing template validation BEFORE solver is called\n")

    demo_valid_colazione()
    demo_invalid_colazione_no_protein()
    demo_invalid_colazione_has_veg()

    print("\n\n" + "=" * 80)
    print("✅ DEMOS COMPLETED")
    print("=" * 80)
    print("\nKey takeaway: Template validation catches structural errors")
    print("BEFORE calling meal_balancer.py (solver remains untouched)")
    print("=" * 80)


if __name__ == '__main__':
    main()
