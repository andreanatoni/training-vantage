#!/usr/bin/env python3
"""
Test suite for plan_builder.py

3 tests critici:
1. sum_to_100: Percentuali sommano esattamente a 100 per ogni nutriente
2. targets_sum_to_daily_totals: Target pasti sommano a totali giornalieri
3. context_propagation: Context (snack/meal) viene passato correttamente al solver
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.plan_builder import PlanBuilder


def test_sum_to_100():
    """
    Test 1: Validate che percentuali sommano a 100 per ogni nutriente
    """
    print("=" * 80)
    print("TEST 1: sum_to_100 - Percentuali validation")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    # Test tutte e 3 le distribuzioni
    distribution_ids = ['standard', 'rest_like', 'lungo_like']
    nutrients = ['kcal', 'P', 'CHO', 'F', 'Fibre']

    passed = True

    for dist_id in distribution_ids:
        print(f"\n🧪 Testing distribution: {dist_id}")

        try:
            builder.validate_distribution(dist_id)
            print(f"   ✅ PASS: Percentages sum to 100")

            # Show actual sums for verification
            dist = builder.get_meal_distribution(dist_id)
            for nutrient in nutrients:
                pct_key = f'{nutrient}_pct'
                total = sum(slot[pct_key] for slot in dist['meal_slots'])
                print(f"      {nutrient}: {total:.2f}%")

        except ValueError as e:
            print(f"   ❌ FAIL: {e}")
            passed = False

    print(f"\n{'='*80}")
    if passed:
        print("✅ TEST 1 PASSED: All distributions valid")
    else:
        print("❌ TEST 1 FAILED: Some distributions invalid")
    print(f"{'='*80}\n")

    return passed


def test_targets_sum_to_daily_totals():
    """
    Test 2: Verify che somma target pasti = totali giornalieri
    """
    print("=" * 80)
    print("TEST 2: targets_sum_to_daily_totals - Remainder logic")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    # Test con rest profile
    profile = builder.get_day_profile('rest')
    distribution = builder.get_meal_distribution(profile['distribution_id'])

    day_totals = profile['totals_daily']
    meal_slots = distribution['meal_slots']

    print(f"\n🧪 Testing profile: {profile['name']}")
    print(f"   Daily totals: {day_totals}")

    # Calculate meal targets
    meal_targets = builder.calculate_day_meal_targets(day_totals, meal_slots)

    # Sum up meal targets
    summed = {'kcal': 0, 'P': 0, 'CHO': 0, 'F': 0, 'Fibre': 0}
    for targets in meal_targets:
        for nutrient in summed:
            summed[nutrient] += targets[nutrient]

    # Compare
    print(f"\n   Meal targets summed:")
    nutrients = ['kcal', 'P', 'CHO', 'F', 'Fibre']
    passed = True

    for nutrient in nutrients:
        expected = day_totals[nutrient]
        actual = summed[nutrient]
        diff = abs(actual - expected)

        status = "✅" if diff < 0.1 else "❌"
        print(f"      {nutrient}: expected {expected}, got {actual:.1f} (diff: {diff:.2f}) {status}")

        if diff >= 0.1:
            passed = False

    print(f"\n{'='*80}")
    if passed:
        print("✅ TEST 2 PASSED: Meal targets sum exactly to daily totals")
    else:
        print("❌ TEST 2 FAILED: Meal targets don't sum correctly (rounding drift)")
    print(f"{'='*80}\n")

    return passed


def test_context_propagation():
    """
    Test 3: Verify che context (snack/meal) viene passato correttamente
    """
    print("=" * 80)
    print("TEST 3: context_propagation - Snack vs Meal context")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    # Test con rest profile che ha sia snack che meal
    profile = builder.get_day_profile('rest')
    distribution = builder.get_meal_distribution(profile['distribution_id'])

    print(f"\n🧪 Testing profile: {profile['name']}")
    print(f"   Distribution: {profile['distribution_id']}")

    # Build minimal plan (solo 2 pasti: 1 snack, 1 meal)
    print("\n   Building plan with context-dependent foods...")

    try:
        # Use prosciutto_crudo (context-dependent: snack_max 40g, meal_max 120g)
        plan = builder.build_day_plan(
            profile_id='rest',
            allowed_foods_per_meal={
                'colazione': ['yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata'],
                'spuntino_mattina': ['prosciutto_crudo', 'pane_integrale'],  # snack context
                'pranzo': ['prosciutto_crudo', 'pane_integrale', 'insalata'],  # meal context
                'spuntino_pomeriggio': ['mandorle'],
                'cena': ['salmone', 'patate_bollite_senza_buccia', 'olio_di_oliva_extra_vergine', 'insalata']
            }
        )

        # Check snack context (spuntino_mattina)
        spuntino = None
        pranzo = None

        for meal in plan['meals']:
            if meal['meal_id'] == 'spuntino_mattina':
                spuntino = meal
            elif meal['meal_id'] == 'pranzo':
                pranzo = meal

        passed = True

        # Check spuntino (snack context)
        if spuntino:
            print(f"\n   📋 Spuntino mattina (snack context):")
            print(f"      Context passed: {spuntino['context']}")

            if spuntino['context'] != 'snack':
                print(f"      ❌ FAIL: Expected 'snack', got '{spuntino['context']}'")
                passed = False
            else:
                print(f"      ✅ PASS: Context = 'snack'")

                # Check prosciutto qty if present
                recommended = spuntino['result'][spuntino['result']['recommendation']]
                for item in recommended['items']:
                    if item['food_db_id'] == 'prosciutto_crudo' and item['qty']['amount'] > 0:
                        qty = item['qty']['amount']
                        print(f"      Prosciutto qty: {qty}g (snack_max = 40g)")
                        if qty > 40:
                            print(f"      ⚠️  WARNING: Prosciutto {qty}g > snack_max 40g")

        # Check pranzo (meal context)
        if pranzo:
            print(f"\n   📋 Pranzo (meal context):")
            print(f"      Context passed: {pranzo['context']}")

            if pranzo['context'] != 'meal':
                print(f"      ❌ FAIL: Expected 'meal', got '{pranzo['context']}'")
                passed = False
            else:
                print(f"      ✅ PASS: Context = 'meal'")

                # Check prosciutto qty if present
                recommended = pranzo['result'][pranzo['result']['recommendation']]
                for item in recommended['items']:
                    if item['food_db_id'] == 'prosciutto_crudo' and item['qty']['amount'] > 0:
                        qty = item['qty']['amount']
                        print(f"      Prosciutto qty: {qty}g (meal_max = 120g)")
                        if qty > 120:
                            print(f"      ⚠️  WARNING: Prosciutto {qty}g > meal_max 120g")

        print(f"\n{'='*80}")
        if passed:
            print("✅ TEST 3 PASSED: Context propagated correctly to solver")
        else:
            print("❌ TEST 3 FAILED: Context not propagated correctly")
        print(f"{'='*80}\n")

        return passed

    except Exception as e:
        print(f"\n❌ TEST 3 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all 3 tests"""
    print("\n")
    print("=" * 80)
    print("🧪 PLAN BUILDER TEST SUITE")
    print("=" * 80)
    print()

    results = []

    # Test 1: Percentages sum to 100
    results.append(('sum_to_100', test_sum_to_100()))

    # Test 2: Targets sum to daily totals
    results.append(('targets_sum_to_daily_totals', test_targets_sum_to_daily_totals()))

    # Test 3: Context propagation
    results.append(('context_propagation', test_context_propagation()))

    # Summary
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test_name}")

    print()
    print(f"Result: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED - PlanBuilder is robust!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
