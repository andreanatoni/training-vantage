#!/usr/bin/env python3
"""
Test Suite: must_include_food_db_ids Support

Verifica hard constraint: alimenti MUST be used (no qty=0 option).

5 test cases:
1. Valid case: must_include presente e rispettato
2. Missing in allowed: ValueError (must_include not in allowed_foods)
3. Conflict template: ValueError (must_include viola template rules)
4. Impossible target: soluzione con delta alto (non crash)
5. Integrity: must_include presente in ENTRAMBE le soluzioni (realistic + unconstrained)
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.nutrition.plan_builder import PlanBuilder
from scripts.nutrition.meal_balancer import MealBalancerData, MealBalancer


def test_valid_must_include():
    """
    Test 1: Valid case - must_include presente e rispettato

    Expected: pollo sempre presente nel risultato, qty variabile
    """
    print("=" * 80)
    print("TEST 1: Valid must_include (pollo MUST be in pranzo)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: pranzo with must_include=['pollo_petto_cotto_in_padella']")

    try:
        plan = builder.build_day_plan(
            profile_id='rest',
            allowed_foods_per_meal={
                'colazione': ['yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata', 'mandorle'],
                'spuntino_mattina': ['mandorle', 'mela'],
                'pranzo': ['pasta_di_semola', 'pollo_petto_cotto_in_padella', 'zucchine_crude', 'olio_di_oliva_extra_vergine', 'parmigiano_reggiano_dop'],
                'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
                'cena': ['salmone', 'patate_bollite_senza_buccia', 'olio_di_oliva_extra_vergine', 'insalata']
            },
            must_include_foods_per_meal={
                'pranzo': ['pollo_petto_cotto_in_padella']  # ← MUST include
            }
        )

        # Check pranzo
        pranzo = None
        for meal in plan['meals']:
            if meal['meal_id'] == 'pranzo':
                pranzo = meal
                break

        if not pranzo:
            print("   ❌ FAIL: pranzo not found in plan")
            return False

        # Check pollo presente
        recommended_version = pranzo['result']['recommendation']
        recommended = pranzo['result'][recommended_version]

        pollo_present = False
        pollo_qty = 0

        for item in recommended['items']:
            if item['food_db_id'] == 'pollo_petto_cotto_in_padella' and item['qty']['amount'] > 0:
                pollo_present = True
                pollo_qty = item['qty']['amount']
                break

        if not pollo_present:
            print(f"\n   ❌ FAIL: pollo NOT present in pranzo (must_include violated!)")
            print(f"   Items: {[item['food_db_id'] for item in recommended['items'] if item['qty']['amount'] > 0]}")
            return False

        print(f"\n   ✅ PASS: pollo presente in pranzo")
        print(f"      Qty: {pollo_qty}g")
        print(f"      Other items: {[item['food_db_id'] for item in recommended['items'] if item['qty']['amount'] > 0 and item['food_db_id'] != 'pollo_petto_cotto_in_padella']}")

        print("\n" + "=" * 80)
        print("✅ TEST 1 PASSED")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n   ❌ FAIL: unexpected exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_must_include_not_in_allowed():
    """
    Test 2: must_include not in allowed_foods → ValueError

    Expected: Clear error message indicating the issue
    """
    print("\n\n" + "=" * 80)
    print("TEST 2: must_include not in allowed_foods (MUST FAIL)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: must_include=['pollo_petto_cotto_in_padella'] but NOT in allowed_foods")

    try:
        plan = builder.build_day_plan(
            profile_id='rest',
            allowed_foods_per_meal={
                'colazione': ['yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata'],
                'spuntino_mattina': ['mandorle', 'mela'],
                'pranzo': ['pasta_di_semola', 'zucchine_crude', 'olio_di_oliva_extra_vergine', 'parmigiano_reggiano_dop'],  # NO pollo
                'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
                'cena': ['salmone', 'patate_bollite_senza_buccia', 'olio_di_oliva_extra_vergine', 'insalata']
            },
            must_include_foods_per_meal={
                'pranzo': ['pollo_petto_cotto_in_padella']  # ← NOT in allowed!
            }
        )

        print(f"\n   ❌ FAIL: No error raised (expected ValueError)")
        return False

    except ValueError as e:
        error_msg = str(e)
        print(f"\n   ✅ Correctly raised ValueError:")
        print(f"      {error_msg}")

        # Check error message quality
        checks = [
            'must_include' in error_msg.lower(),
            'allowed_foods' in error_msg.lower() or 'allowed' in error_msg.lower(),
            'pollo_petto_cotto_in_padella' in error_msg
        ]

        if all(checks):
            print(f"\n   ✅ Error message is actionable")
            print("\n" + "=" * 80)
            print("✅ TEST 2 PASSED")
            print("=" * 80)
            return True
        else:
            print(f"\n   ⚠️  Error message missing key info")
            print(f"      Has 'must_include': {checks[0]}")
            print(f"      Has 'allowed': {checks[1]}")
            print(f"      Has food_id: {checks[2]}")
            return False

    except Exception as e:
        print(f"\n   ❌ FAIL: wrong exception type: {type(e).__name__}: {e}")
        return False


def test_must_include_violates_template():
    """
    Test 3: must_include violates template rules → ValueError

    Expected: Error before solver runs (e.g., pasta at colazione is forbidden)
    """
    print("\n\n" + "=" * 80)
    print("TEST 3: must_include violates template (pasta at colazione, MUST FAIL)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: must_include=['pasta_di_semola'] at colazione (forbidden)")

    try:
        plan = builder.build_day_plan(
            profile_id='rest',
            allowed_foods_per_meal={
                'colazione': ['yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata', 'pasta_di_semola'],  # pasta allowed
                'spuntino_mattina': ['mandorle', 'mela'],
                'pranzo': ['pasta_di_semola', 'pollo_petto_cotto_in_padella', 'zucchine_crude', 'olio_di_oliva_extra_vergine'],
                'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
                'cena': ['salmone', 'patate_bollite_senza_buccia', 'olio_di_oliva_extra_vergine', 'insalata']
            },
            must_include_foods_per_meal={
                'colazione': ['pasta_di_semola']  # ← FORBIDDEN at colazione!
            }
        )

        print(f"\n   ❌ FAIL: No error raised (expected ValueError)")
        return False

    except ValueError as e:
        error_msg = str(e)
        print(f"\n   ✅ Correctly raised ValueError:")
        print(f"      {error_msg}")

        # Check error mentions forbidden/template
        checks = [
            'forbidden' in error_msg.lower() or 'template' in error_msg.lower(),
            'colazione' in error_msg.lower(),
            'pasta_di_semola' in error_msg
        ]

        if all(checks):
            print(f"\n   ✅ Error message is actionable")
            print("\n" + "=" * 80)
            print("✅ TEST 3 PASSED")
            print("=" * 80)
            return True
        else:
            print(f"\n   ⚠️  Error message missing key info")
            print(f"      Has 'forbidden/template': {checks[0]}")
            print(f"      Has 'colazione': {checks[1]}")
            print(f"      Has food_id: {checks[2]}")
            return False

    except Exception as e:
        print(f"\n   ❌ FAIL: wrong exception type: {type(e).__name__}: {e}")
        return False


def test_must_include_impossible_target():
    """
    Test 4: must_include makes target mathematically hard → solution with delta

    Expected: Solver still produces solution (doesn't crash), but delta may be high
    """
    print("\n\n" + "=" * 80)
    print("TEST 4: must_include with impossible target (no crash)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: spuntino (low kcal ~200) but must_include=['salmone'] (high P/F)")
    print("   Expected: solution produced (no crash), but likely high delta")

    try:
        # Build single meal plan (easier to test)
        from scripts.nutrition.meal_balancer import MealBalancer, MealBalancerData

        balancer_data = MealBalancerData(data_dir)
        balancer = MealBalancer(balancer_data)

        result = balancer.balance_meal(
            target={'kcal': 200, 'P': 10, 'CHO': 25, 'F': 5, 'Fibre': 3},
            meal_context='snack',
            allowed_food_db_ids=['salmone', 'pane_integrale', 'mela'],
            must_include_food_db_ids=['salmone']  # ← Must include, but high kcal/P/F
        )

        # Check salmone presente
        recommended_version = result['recommendation']
        recommended = result[recommended_version]

        salmone_present = False
        salmone_qty = 0

        for item in recommended['items']:
            if item['food_db_id'] == 'salmone' and item['qty']['amount'] > 0:
                salmone_present = True
                salmone_qty = item['qty']['amount']
                break

        if not salmone_present:
            print(f"\n   ❌ FAIL: salmone NOT present (must_include violated!)")
            print(f"   Items: {[item['food_db_id'] for item in recommended['items'] if item['qty']['amount'] > 0]}")
            return False

        print(f"\n   ✅ PASS: solution produced (no crash)")
        print(f"      Salmone qty: {salmone_qty}g")
        print(f"      Total kcal: {recommended['totals']['kcal']:.1f} (target: 200)")
        print(f"      Total P: {recommended['totals']['P']:.1f}g (target: 10)")
        print(f"      Delta kcal: {recommended['delta']['kcal_pct']:+.1f}%")
        print(f"      Delta P: {recommended['delta']['P_pct']:+.1f}%")

        # Expect large delta (target is impossible with salmone)
        delta_kcal_pct = abs(recommended['delta']['kcal_pct'])
        if delta_kcal_pct > 10:
            print(f"\n   ✅ Large delta expected (target mathematically hard with must_include)")

        print("\n" + "=" * 80)
        print("✅ TEST 4 PASSED")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n   ❌ FAIL: unexpected exception (solver should handle gracefully): {e}")
        import traceback
        traceback.print_exc()
        return False


def test_must_include_integrity():
    """
    Test 5: Integrity check - must_include present in BOTH solutions

    Expected: must_include foods have qty > 0 in BOTH realistic AND unconstrained
              and NEVER appear with qty=0 in items list
    """
    print("\n\n" + "=" * 80)
    print("TEST 5: Integrity - must_include in BOTH solutions")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    balancer_data = MealBalancerData(data_dir)
    balancer = MealBalancer(balancer_data)

    print("\n🧪 Test: must_include=['pollo_petto_cotto_in_padella']")
    print("   Expected: pollo qty > 0 in BOTH realistic AND unconstrained\n")

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
        must_include_food_db_ids=['pollo_petto_cotto_in_padella']
    )

    passed = True

    # Check UNCONSTRAINED solution
    unconstrained = result['best_match_unconstrained']
    pollo_qty_uncon = None

    for item in unconstrained['items']:
        if item['food_db_id'] == 'pollo_petto_cotto_in_padella':
            pollo_qty_uncon = item['qty']['amount']
            break

    if pollo_qty_uncon is None or pollo_qty_uncon == 0:
        print(f"   ❌ FAIL: pollo NOT in unconstrained solution (qty={pollo_qty_uncon})")
        passed = False
    else:
        print(f"   ✅ Unconstrained: pollo qty={pollo_qty_uncon}g (present)")

    # Check REALISTIC solution
    realistic = result['best_match_realistic']
    pollo_qty_real = None

    for item in realistic['items']:
        if item['food_db_id'] == 'pollo_petto_cotto_in_padella':
            pollo_qty_real = item['qty']['amount']
            break

    if pollo_qty_real is None or pollo_qty_real == 0:
        print(f"   ❌ FAIL: pollo NOT in realistic solution (qty={pollo_qty_real})")
        passed = False
    else:
        print(f"   ✅ Realistic: pollo qty={pollo_qty_real}g (present)")

    # Check that pollo NEVER appears with qty=0
    for item in unconstrained['items']:
        if item['food_db_id'] == 'pollo_petto_cotto_in_padella' and item['qty']['amount'] == 0:
            print(f"   ❌ FAIL: pollo appears with qty=0 in unconstrained items")
            passed = False

    for item in realistic['items']:
        if item['food_db_id'] == 'pollo_petto_cotto_in_padella' and item['qty']['amount'] == 0:
            print(f"   ❌ FAIL: pollo appears with qty=0 in realistic items")
            passed = False

    if passed:
        print(f"\n   ✅ Integrity verified: must_include present in BOTH solutions")
        print(f"      NEVER appears with qty=0 in items")

    print("\n" + "=" * 80)
    if passed:
        print("✅ TEST 5 PASSED")
    else:
        print("❌ TEST 5 FAILED")
    print("=" * 80)

    return passed


def main():
    """Run all 5 tests"""
    print("\n")
    print("=" * 80)
    print("🧪 MUST_INCLUDE TEST SUITE")
    print("=" * 80)
    print("\nHard constraint: foods MUST be used (no qty=0 option)")
    print("Pattern: candidate filtering at solver layer\n")

    results = []

    # Test 1: Valid case
    results.append(('valid_must_include', test_valid_must_include()))

    # Test 2: Not in allowed
    results.append(('must_include_not_in_allowed', test_must_include_not_in_allowed()))

    # Test 3: Violates template
    results.append(('must_include_violates_template', test_must_include_violates_template()))

    # Test 4: Impossible target
    results.append(('must_include_impossible_target', test_must_include_impossible_target()))

    # Test 5: Integrity check
    results.append(('must_include_integrity', test_must_include_integrity()))

    # Summary
    print("\n\n" + "=" * 80)
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
        print("\n🎉 ALL TESTS PASSED - must_include support is robust!")
        print("   Integrity verified: must_include in BOTH solutions (realistic + unconstrained)")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
