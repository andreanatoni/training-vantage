#!/usr/bin/env python3
"""
Demo: must_include_food_db_ids in Action

Shows practical use case: ensuring specific foods are ALWAYS included
regardless of solver optimization preferences.
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.meal_balancer import MealBalancer, MealBalancerData


def demo_without_must_include():
    """Demo WITHOUT must_include: solver may choose not to use pollo"""
    print("=" * 80)
    print("SCENARIO A: WITHOUT must_include")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    balancer_data = MealBalancerData(data_dir)
    balancer = MealBalancer(balancer_data)

    print("\n🎯 Target: kcal 600, P 40, CHO 70, F 15, Fibre 8")
    print("📋 Allowed foods: pasta, pollo, zucchine, olio, parmigiano")
    print("❌ No must_include constraint\n")

    result = balancer.balance_meal(
        target={'kcal': 600, 'P': 40, 'CHO': 70, 'F': 15, 'Fibre': 8},
        meal_context='meal',
        allowed_food_db_ids=[
            'pasta_di_semola',
            'pollo_petto_cotto_in_padella',
            'zucchine_crude',
            'olio_di_oliva_extra_vergine',
            'parmigiano_reggiano_dop'
        ]
    )

    recommended = result[result['recommendation']]

    print("📊 Results (solver's free choice):")
    foods_used = []
    for item in recommended['items']:
        if item['qty']['amount'] > 0:
            foods_used.append(item['food_db_id'])
            print(f"   - {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")

    print(f"\n   Total: kcal {recommended['totals']['kcal']:.1f}, P {recommended['totals']['P']:.1f}g")

    if 'pollo_petto_cotto_in_padella' in foods_used:
        print(f"   ✅ Pollo used (solver chose it)")
    else:
        print(f"   ⚠️  Pollo NOT used (solver didn't need it for target)")


def demo_with_must_include():
    """Demo WITH must_include: pollo MUST be present"""
    print("\n\n" + "=" * 80)
    print("SCENARIO B: WITH must_include=['pollo_petto_cotto_in_padella']")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    balancer_data = MealBalancerData(data_dir)
    balancer = MealBalancer(balancer_data)

    print("\n🎯 Target: kcal 600, P 40, CHO 70, F 15, Fibre 8")
    print("📋 Allowed foods: pasta, pollo, zucchine, olio, parmigiano")
    print("✅ must_include=['pollo_petto_cotto_in_padella'] (HARD CONSTRAINT)\n")

    result = balancer.balance_meal(
        target={'kcal': 600, 'P': 40, 'CHO': 70, 'F': 15, 'Fibre': 8},
        meal_context='meal',
        allowed_food_db_ids=[
            'pasta_di_semola',
            'pollo_petto_cotto_in_padella',
            'zucchine_crude',
            'olio_di_oliva_extra_vergine',
            'parmigiano_reggiano_dop'
        ],
        must_include_food_db_ids=['pollo_petto_cotto_in_padella']  # ← FORCED
    )

    recommended = result[result['recommendation']]

    print("📊 Results (with must_include constraint):")
    pollo_qty = 0
    for item in recommended['items']:
        if item['qty']['amount'] > 0:
            if item['food_db_id'] == 'pollo_petto_cotto_in_padella':
                pollo_qty = item['qty']['amount']
                print(f"   🎯 {item['name']}: {item['qty']['amount']}{item['qty']['unit']} (FORCED)")
            else:
                print(f"   - {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")

    print(f"\n   Total: kcal {recommended['totals']['kcal']:.1f}, P {recommended['totals']['P']:.1f}g")

    if pollo_qty > 0:
        print(f"   ✅ Pollo PRESENT (qty={pollo_qty}g) - constraint satisfied!")
    else:
        print(f"   ❌ ERROR: Pollo missing (must_include violated!)")


def demo_use_case_macros_target():
    """Real use case: hitting macros target with pollo guaranteed"""
    print("\n\n" + "=" * 80)
    print("REAL USE CASE: Macros Management with Guaranteed Protein Source")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    balancer_data = MealBalancerData(data_dir)
    balancer = MealBalancer(balancer_data)

    print("\n💡 Context: User wants to hit protein target (50g) for pranzo")
    print("   BUT also wants pollo (lean protein) guaranteed in the meal")
    print("   Solver can optimize other foods around pollo\n")

    print("🎯 Target: kcal 700, P 50, CHO 80, F 20, Fibre 10")
    print("📋 Allowed: pasta, pollo, zucchine, olio, parmigiano")
    print("✅ must_include=['pollo_petto_cotto_in_padella']\n")

    result = balancer.balance_meal(
        target={'kcal': 700, 'P': 50, 'CHO': 80, 'F': 20, 'Fibre': 10},
        meal_context='meal',
        allowed_food_db_ids=[
            'pasta_di_semola',
            'pollo_petto_cotto_in_padella',
            'zucchine_crude',
            'olio_di_oliva_extra_vergine',
            'parmigiano_reggiano_dop'
        ],
        must_include_food_db_ids=['pollo_petto_cotto_in_padella']
    )

    recommended = result[result['recommendation']]

    print("📊 Optimal solution:")
    pollo_qty = 0
    pollo_P = 0

    for item in recommended['items']:
        if item['qty']['amount'] > 0:
            symbol = "🎯" if item['food_db_id'] == 'pollo_petto_cotto_in_padella' else "  "
            print(f"   {symbol} {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")
            if item['food_db_id'] == 'pollo_petto_cotto_in_padella':
                pollo_qty = item['qty']['amount']
                pollo_P = item['macros']['P']

    print(f"\n   Totals:")
    print(f"      Kcal: {recommended['totals']['kcal']:.1f} (target: 700)")
    print(f"      P: {recommended['totals']['P']:.1f}g (target: 50g)")
    print(f"      CHO: {recommended['totals']['CHO']:.1f}g (target: 80g)")
    print(f"      F: {recommended['totals']['F']:.1f}g (target: 20g)")

    print(f"\n   Pollo contribution:")
    print(f"      Qty: {pollo_qty}g")
    print(f"      P from pollo: {pollo_P:.1f}g ({pollo_P/recommended['totals']['P']*100:.0f}% of total P)")

    print(f"\n   ✅ User gets: lean protein source (pollo) + optimized macros!")


def main():
    """Run all demos"""
    print("\n")
    print("=" * 80)
    print("🎬 MUST_INCLUDE DEMO: Practical Use Cases")
    print("=" * 80)
    print("\nHard constraint: foods MUST be used (no qty=0 option)\n")

    demo_without_must_include()
    demo_with_must_include()
    demo_use_case_macros_target()

    print("\n\n" + "=" * 80)
    print("✅ DEMO COMPLETED")
    print("=" * 80)
    print("\nKey takeaway: must_include ensures specific foods are ALWAYS present,")
    print("while solver still optimizes quantities to hit macros target.")
    print("\nUse cases:")
    print("- Guarantee lean protein source (pollo, salmone)")
    print("- Ensure dietary requirements (e.g., 'must have veg at every meal')")
    print("- Personal preferences (e.g., 'I always want pasta at pranzo')")
    print("- Meal prep constraints (e.g., 'use chicken I already cooked')")
    print("=" * 80)


if __name__ == '__main__':
    main()
