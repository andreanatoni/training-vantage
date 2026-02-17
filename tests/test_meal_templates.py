#!/usr/bin/env python3
"""
Test suite for meal template validation (Stress Test #3)

4 tests:
1. Required groups - colazione senza protein → FAIL
2. Forbidden groups - colazione con veg → FAIL
3. max_per_group - snack con 2 alimenti fat → FAIL
4. Valid case - colazione con carb+protein+fat → PASS
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.plan_builder import PlanBuilder


def test_required_groups():
    """
    Test 1: Required groups - colazione DEVE avere carb + protein
    """
    print("=" * 80)
    print("TEST 1: Required Groups")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: Colazione without protein (MUST FAIL)")

    # Colazione con solo carb (no protein) → DEVE fallire
    invalid_foods = ['fette_biscottate', 'marmellata', 'caffe_espresso']

    try:
        builder.validate_meal_template('colazione', invalid_foods)
        print("   ❌ FAIL: Validation should have raised ValueError (missing protein)")
        return False
    except ValueError as e:
        print(f"   ✅ PASS: Correctly rejected - {e}")
        return True


def test_forbidden_groups():
    """
    Test 2: Forbidden groups - colazione NON può avere veg
    """
    print("\n" + "=" * 80)
    print("TEST 2: Forbidden Groups")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: Colazione with veg (MUST FAIL)")

    # Colazione con veg → DEVE fallire
    invalid_foods = ['yogurt_greco_0_lipidi', 'fette_biscottate', 'zucchine_crude']

    try:
        builder.validate_meal_template('colazione', invalid_foods)
        print("   ❌ FAIL: Validation should have raised ValueError (forbidden veg)")
        return False
    except ValueError as e:
        print(f"   ✅ PASS: Correctly rejected - {e}")
        return True


def test_max_per_group():
    """
    Test 3: max_per_group - snack max 1 fat
    """
    print("\n" + "=" * 80)
    print("TEST 3: max_per_group")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: Snack with 2 fat items (MUST FAIL)")

    # Snack con 2 fat (mandorle + noci) → DEVE fallire (max 1)
    invalid_foods = ['mandorle', 'noci']

    try:
        builder.validate_meal_template('spuntino_mattina', invalid_foods)
        print("   ❌ FAIL: Validation should have raised ValueError (too many fats)")
        return False
    except ValueError as e:
        print(f"   ✅ PASS: Correctly rejected - {e}")
        return True


def test_valid_case():
    """
    Test 4: Valid case - colazione strutturalmente corretta
    """
    print("\n" + "=" * 80)
    print("TEST 4: Valid Case")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: Valid colazione (carb + protein + fat + fruit + beverage)")

    # Colazione valida: tutti i gruppi corretti
    valid_foods = [
        'yogurt_greco_0_lipidi',       # protein
        'fette_biscottate',     # carb
        'marmellata',           # fruit
        'mandorle',             # fat
        'caffe_espresso'        # beverage
    ]

    try:
        builder.validate_meal_template('colazione', valid_foods)
        print("   ✅ PASS: Valid colazione accepted")
        print(f"      Foods: {valid_foods}")

        # Show groups
        groups = {}
        for food_id in valid_foods:
            group = builder.food_group_map.get(food_id, 'unknown')
            groups[food_id] = group

        print(f"      Groups: {groups}")
        return True

    except ValueError as e:
        print(f"   ❌ FAIL: Valid colazione rejected - {e}")
        return False


def test_valid_pranzo():
    """
    Test 5 (bonus): Valid pranzo - protein + veg + carb
    """
    print("\n" + "=" * 80)
    print("TEST 5 (BONUS): Valid Pranzo")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: Valid pranzo (protein + veg + carb + fat)")

    # Pranzo valido
    valid_foods = [
        'pasta_di_semola',        # carb
        'pollo_petto_cotto_in_padella', # protein
        'zucchine_crude',               # veg
        'olio_di_oliva_extra_vergine',                     # fat
        'parmigiano_reggiano_dop'           # protein
    ]

    try:
        builder.validate_meal_template('pranzo', valid_foods)
        print("   ✅ PASS: Valid pranzo accepted")
        print(f"      Foods: {valid_foods}")

        # Show groups
        groups = {}
        for food_id in valid_foods:
            group = builder.food_group_map.get(food_id, 'unknown')
            groups[food_id] = group

        print(f"      Groups: {groups}")
        return True

    except ValueError as e:
        print(f"   ❌ FAIL: Valid pranzo rejected - {e}")
        return False


def test_invalid_pranzo_no_veg():
    """
    Test 6 (bonus): Invalid pranzo - missing required veg
    """
    print("\n" + "=" * 80)
    print("TEST 6 (BONUS): Invalid Pranzo (no veg)")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🧪 Test: Pranzo without veg (MUST FAIL)")

    # Pranzo senza veg → DEVE fallire
    invalid_foods = [
        'pasta_di_semola',        # carb
        'pollo_petto_cotto_in_padella', # protein
        'olio_di_oliva_extra_vergine'                      # fat
    ]

    try:
        builder.validate_meal_template('pranzo', invalid_foods)
        print("   ❌ FAIL: Validation should have raised ValueError (missing veg)")
        return False
    except ValueError as e:
        print(f"   ✅ PASS: Correctly rejected - {e}")
        return True


def main():
    """Run all tests"""
    print("\n")
    print("=" * 80)
    print("🧪 MEAL TEMPLATE VALIDATION TEST SUITE (Stress Test #3)")
    print("=" * 80)
    print()

    results = []

    # Required tests (4)
    results.append(('test_required_groups', test_required_groups()))
    results.append(('test_forbidden_groups', test_forbidden_groups()))
    results.append(('test_max_per_group', test_max_per_group()))
    results.append(('test_valid_case', test_valid_case()))

    # Bonus tests (2)
    results.append(('test_valid_pranzo', test_valid_pranzo()))
    results.append(('test_invalid_pranzo_no_veg', test_invalid_pranzo_no_veg()))

    # Summary
    print("\n" + "=" * 80)
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
        print("\n🎉 ALL TESTS PASSED - Meal Template validation is robust!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
