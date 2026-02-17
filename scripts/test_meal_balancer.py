#!/usr/bin/env python3
"""
Test cases per meal_balancer.py
"""

import json
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from meal_balancer import MealBalancerData, MealBalancer

def test_ingredient_mode():
    """
    Test B - Passata ingredient (step libero)

    Deve verificare:
    - passata usa step 20g (es: 80, 100)
    - NON 200×multiplier
    - realistic non supera 100g passata
    - olio non supera 15g
    - niente qty strane (es: 83g)
    """
    print("=" * 80)
    print("TEST B - INGREDIENT MODE (Passata step libero)")
    print("=" * 80)

    # Load data
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    data = MealBalancerData(data_dir)
    balancer = MealBalancer(data)

    # Input test
    target = {
        'kcal': 650,
        'P': 35,
        'CHO': 85,
        'F': 18,
        'Fibre': 10
    }

    allowed_foods = [
        'pasta_di_semola',
        'salsa_di_carne_manzo',
        'passata_di_pomodoro',
        'olio_di_oliva_extra_vergine',
        'zucchine_crude'
    ]

    print("\n📋 Input:")
    print(f"  Target: {target}")
    print(f"  Meal context: meal")
    print(f"  Alimenti: {allowed_foods}")

    # Run
    result = balancer.balance_meal(
        target=target,
        meal_context='meal',
        allowed_food_db_ids=allowed_foods
    )

    print("\n✅ REALISTIC VERSION:")
    print("-" * 80)
    realistic = result['best_match_realistic']

    for item in realistic['items']:
        qty = item['qty']['amount']
        unit = item['qty']['unit']
        print(f"  - {item['name']}: {qty}{unit}")

        # Verifiche specifiche
        if item['food_db_id'] == 'passata_di_pomodoro':
            print(f"    ✓ Passata: is_ingredient={item.get('is_ingredient', False)}")
            if qty > 100:
                print(f"    ❌ FAIL: Passata {qty}g supera max 100g!")
            elif qty % 20 != 0 and qty != 0:
                print(f"    ⚠️  WARNING: Passata {qty}g non è multiplo di step 20g")
            else:
                print(f"    ✅ OK: Passata {qty}g rispetta vincoli (max 100g, step 20g)")

        if item['food_db_id'] == 'olio_di_oliva_extra_vergine':
            if qty > 15:
                print(f"    ❌ FAIL: Olio {qty}g supera max 15g!")
            else:
                print(f"    ✅ OK: Olio {qty}g rispetta max 15g")

    print("\n📊 Totals:")
    totals = realistic['totals']
    delta = realistic['delta']
    print(f"  Kcal: {totals['kcal']} (delta: {delta['kcal_pct']:+.1f}%)")
    print(f"  P: {totals['P']}g (delta: {delta['P_pct']:+.1f}%)")
    print(f"  CHO: {totals['CHO']}g (delta: {delta['CHO_pct']:+.1f}%)")
    print(f"  F: {totals['F']}g (delta: {delta['F_pct']:+.1f}%)")

    print("\n💡 Notes:")
    for note in result['notes']:
        print(f"  - {note}")

    return result


def test_context_dependent():
    """
    Test A - Salumi context (snack vs meal)

    Deve verificare:
    - prosciutto max 40g in realistic con context=snack
    - spalmabile max 50g in realistic con context=snack
    - unconstrained può superare e marca violations
    """
    print("\n\n" + "=" * 80)
    print("TEST A - CONTEXT-DEPENDENT (Salumi snack vs meal)")
    print("=" * 80)

    # Load data
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    data = MealBalancerData(data_dir)
    balancer = MealBalancer(data)

    # Input test SNACK
    target = {
        'kcal': 250,
        'P': 18,
        'CHO': 20,
        'F': 10,
        'Fibre': 3
    }

    allowed_foods = [
        'prosciutto_crudo',
        'pane_integrale',
        'formaggio_cremoso_spalmabile_light'
    ]

    print("\n📋 Input (SNACK context):")
    print(f"  Target: {target}")
    print(f"  Meal context: snack")
    print(f"  Alimenti: {allowed_foods}")

    # Run
    result = balancer.balance_meal(
        target=target,
        meal_context='snack',
        allowed_food_db_ids=allowed_foods
    )

    print("\n✅ REALISTIC VERSION (snack):")
    print("-" * 80)
    realistic = result['best_match_realistic']

    for item in realistic['items']:
        qty = item['qty']['amount']
        unit = item['qty']['unit']
        print(f"  - {item['name']}: {qty}{unit}")

        # Verifiche context snack
        if item['food_db_id'] == 'prosciutto_crudo':
            if qty > 40:
                print(f"    ❌ FAIL: Prosciutto {qty}g supera snack_max 40g!")
            else:
                print(f"    ✅ OK: Prosciutto {qty}g rispetta snack_max 40g")

        if item['food_db_id'] == 'formaggio_cremoso_spalmabile_light':
            if qty > 50:
                print(f"    ❌ FAIL: Spalmabile {qty}g supera snack_max 50g!")
            else:
                print(f"    ✅ OK: Spalmabile {qty}g rispetta snack_max 50g")

    print("\n⚠️  UNCONSTRAINED VERSION (può violare):")
    print("-" * 80)
    unconstrained = result['best_match_unconstrained']

    violations_found = False
    for item in unconstrained['items']:
        qty = item['qty']['amount']
        if item.get('violations'):
            violations_found = True
            print(f"  - {item['name']}: {qty}g → VIOLATIONS: {item['violations']}")

    if not violations_found:
        print("  (Nessuna violation in unconstrained per questo target)")

    print("\n📊 Totals (realistic):")
    totals = realistic['totals']
    delta = realistic['delta']
    print(f"  Kcal: {totals['kcal']} (delta: {delta['kcal_pct']:+.1f}%)")
    print(f"  P: {totals['P']}g (delta: {delta['P_pct']:+.1f}%)")

    return result


if __name__ == '__main__':
    # Run tests
    print("🧪 Running meal_balancer test suite\n")

    try:
        # Test B - Ingredient
        result_b = test_ingredient_mode()

        # Test A - Context
        result_a = test_context_dependent()

        print("\n\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
