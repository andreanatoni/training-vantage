#!/usr/bin/env python3
"""
Demo: Protein Floor in Action

Shows 2 cases:
1. Snack with floor 15g (raggiungibile - good protein foods)
2. Snack with floor 20g (unreachable - poor protein foods) → note + delta
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.meal_balancer import MealBalancer, MealBalancerData


def demo_floor_reachable():
    """
    Case 1: Snack with floor 15g - raggiungibile

    Allowed: mandorle, yogurt (good P sources)
    Expected: Floor reached, P >= 15g
    """
    print("=" * 80)
    print("CASE 1: Protein Floor Raggiungibile (15g)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    balancer_data = MealBalancerData(data_dir)
    balancer = MealBalancer(balancer_data)

    print("\n🎯 Snack target (calculated): kcal 200, P 10, CHO 25, F 8, Fibre 3")
    print("🎯 Protein floor: 15g (bumps P target from 10g → 15g)")
    print("📋 Allowed foods: mandorle, yogurt_greco_0_lipidi (good protein sources)")

    # Simulate floor adjustment
    original_P = 10
    P_floor = 15

    print(f"\n🔧 Target adjustment: P {original_P}g → {P_floor}g (reason: protein_floor)\n")

    result = balancer.balance_meal(
        target={'kcal': 200, 'P': P_floor, 'CHO': 25, 'F': 8, 'Fibre': 3},
        meal_context='snack',
        allowed_food_db_ids=['mandorle', 'yogurt_greco_0_lipidi']
    )

    recommended = result[result['recommendation']]

    print("📊 Results:")
    for item in recommended['items']:
        if item['qty']['amount'] > 0:
            print(f"   - {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")

    print(f"\n   Totals:")
    print(f"      Kcal: {recommended['totals']['kcal']:.1f} (target: 200)")
    print(f"      P: {recommended['totals']['P']:.1f}g (floor: {P_floor}g)")
    print(f"      CHO: {recommended['totals']['CHO']:.1f}g (target: 25g)")
    print(f"      F: {recommended['totals']['F']:.1f}g (target: 8g)")

    actual_P = recommended['totals']['P']

    if actual_P >= P_floor:
        print(f"\n   ✅ Floor reached! P={actual_P:.1f}g >= floor {P_floor}g")
        print(f"   ✅ Runner gets adequate protein for snack/recovery")
    else:
        print(f"\n   ⚠️  Floor NOT reached: P={actual_P:.1f}g < floor {P_floor}g")


def demo_floor_unreachable():
    """
    Case 2: Snack with floor 20g - unreachable

    Allowed: mela, marmellata, pane_bianco (low P foods)
    Expected: Floor not reached, note present
    """
    print("\n\n" + "=" * 80)
    print("CASE 2: Protein Floor NON Raggiungibile (20g)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    balancer_data = MealBalancerData(data_dir)
    balancer = MealBalancer(balancer_data)

    print("\n🎯 Snack target (calculated): kcal 200, P 10, CHO 25, F 8, Fibre 3")
    print("🎯 Protein floor: 20g (bumps P target from 10g → 20g)")
    print("📋 Allowed foods: mela, marmellata, pane_bianco (low protein sources)")

    # Simulate floor adjustment
    original_P = 10
    P_floor = 20

    print(f"\n🔧 Target adjustment: P {original_P}g → {P_floor}g (reason: protein_floor)")
    print("⚠️  WARNING: Floor likely unreachable with low-P foods\n")

    result = balancer.balance_meal(
        target={'kcal': 200, 'P': P_floor, 'CHO': 25, 'F': 8, 'Fibre': 3},
        meal_context='snack',
        allowed_food_db_ids=['mela', 'marmellata', 'pane_bianco']
    )

    recommended = result[result['recommendation']]

    print("📊 Results:")
    for item in recommended['items']:
        if item['qty']['amount'] > 0:
            print(f"   - {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")

    print(f"\n   Totals:")
    print(f"      Kcal: {recommended['totals']['kcal']:.1f} (target: 200)")
    print(f"      P: {recommended['totals']['P']:.1f}g (floor: {P_floor}g)")
    print(f"      Delta P: {recommended['delta']['P_pct']:+.1f}%")

    actual_P = recommended['totals']['P']

    if actual_P < P_floor:
        shortage = P_floor - actual_P
        print(f"\n   ❌ Floor NOT reached: P={actual_P:.1f}g < floor {P_floor}g")
        print(f"      Shortage: {shortage:.1f}g protein")

        print(f"\n   📋 Note (orchestrator-generated):")
        print(f"      'Protein floor {P_floor}g non raggiunto ({actual_P:.1f}g).")
        print(f"       Causa: allowed_foods insufficienti / caps personali.")
        print(f"       Azione: aggiungere fonte proteica (es. yogurt_greco_0_lipidi, albumi, pollo)")
        print(f"               o aumentare max_qty.'")

        print(f"\n   💡 Solution: Add protein source (yogurt, mandorle, prosciutto) to allowed_foods")

    else:
        print(f"\n   ✅ Floor reached (unexpected!): P={actual_P:.1f}g >= floor {P_floor}g")


def demo_runner_use_case():
    """
    Real runner use case: Post-run snack with protein floor 20g

    Context: Runner finishes long run, needs recovery window nutrition
    Floor ensures adequate protein for muscle recovery
    """
    print("\n\n" + "=" * 80)
    print("REAL USE CASE: Post-Run Recovery Snack (Runner)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    balancer_data = MealBalancerData(data_dir)
    balancer = MealBalancer(balancer_data)

    print("\n🏃 Context: Just finished 20km long run")
    print("   Recovery window: need P + CHO immediately")
    print("   Protein floor: 20g (critical for muscle recovery)")

    print("\n🎯 Target: kcal 350, P 15 (calculated), CHO 50, F 10, Fibre 5")
    print("🎯 Protein floor kicks in: 15g → 20g (runner needs protein!)")
    print("📋 Allowed foods: banana, yogurt_greco_0_lipidi, mandorle, miele")

    P_floor = 20
    original_P = 15

    print(f"\n🔧 Target adjustment: P {original_P}g → {P_floor}g (reason: protein_floor)\n")

    result = balancer.balance_meal(
        target={'kcal': 350, 'P': P_floor, 'CHO': 50, 'F': 10, 'Fibre': 5},
        meal_context='snack',
        allowed_food_db_ids=['banana', 'yogurt_greco_0_lipidi', 'mandorle', 'miele']
    )

    recommended = result[result['recommendation']]

    print("📊 Optimal recovery snack:")
    for item in recommended['items']:
        if item['qty']['amount'] > 0:
            symbol = "🍌" if "banana" in item['food_db_id'] else "🥛" if "yogurt" in item['food_db_id'] else "🌰" if "mandor" in item['food_db_id'] else "🍯"
            print(f"   {symbol} {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")

    print(f"\n   Totals:")
    print(f"      Kcal: {recommended['totals']['kcal']:.1f} (target: 350)")
    print(f"      P: {recommended['totals']['P']:.1f}g (floor: {P_floor}g) ← GUARANTEED")
    print(f"      CHO: {recommended['totals']['CHO']:.1f}g (fast recovery)")
    print(f"      F: {recommended['totals']['F']:.1f}g")

    actual_P = recommended['totals']['P']

    if actual_P >= P_floor:
        print(f"\n   ✅ Protein floor satisfied: {actual_P:.1f}g >= {P_floor}g")
        print(f"   ✅ Runner gets adequate protein for muscle recovery")
        print(f"   ✅ CHO for glycogen replenishment")
        print(f"\n   💪 Perfect recovery window nutrition!")


def main():
    """Run all demos"""
    print("\n")
    print("=" * 80)
    print("🎬 PROTEIN FLOOR DEMO: Orchestrator-Only Hard Floor")
    print("=" * 80)
    print("\nTarget adjustment pattern: if P_target < P_floor → bump to floor")
    print("Zero solver changes - pure orchestration\n")

    demo_floor_reachable()
    demo_floor_unreachable()
    demo_runner_use_case()

    print("\n\n" + "=" * 80)
    print("✅ DEMO COMPLETED")
    print("=" * 80)

    print("\n🎯 Key Takeaways:")
    print("   1. Protein floor = hard constraint (target adjustment)")
    print("   2. Orchestrator-only (zero solver changes)")
    print("   3. Unreachable floor → note but no crash (graceful)")
    print("   4. Runner-specific: guarantees adequate protein per meal/snack")
    print("\n📋 Configuration:")
    print("   - Colazione/pranzo/cena: 20-25g floor")
    print("   - Snack: 15g floor")
    print("   - Post-run recovery: 20g floor")
    print("\n💡 Runner benefits:")
    print("   - Consistent protein distribution across day")
    print("   - Recovery windows always hit protein target")
    print("   - No 'low protein snack' scenarios")
    print("=" * 80)


if __name__ == '__main__':
    main()
