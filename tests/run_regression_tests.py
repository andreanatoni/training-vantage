#!/usr/bin/env python3
"""
Regression test suite per meal_balancer.py

Esegue 5 test automatici per validare:
1. Colazione standard (baseline)
2. Context-dependent (snack vs meal)
3. Ingredient mode (passata step libero)
4. Target impossibile (failure mode)
5. Pareggio rule (+5%)

Usage:
    python tests/run_regression_tests.py
    python tests/run_regression_tests.py --verbose
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.meal_balancer import MealBalancerData, MealBalancer


class RegressionTester:
    """Regression test runner"""

    def __init__(self, data_dir: Path, test_cases_dir: Path, verbose: bool = False):
        self.data_dir = data_dir
        self.test_cases_dir = test_cases_dir
        self.verbose = verbose

        # Load data
        print("📂 Loading meal balancer data...")
        self.data = MealBalancerData(data_dir)
        self.balancer = MealBalancer(self.data)
        print("✅ Data loaded\n")

    def load_test_case(self, filepath: Path) -> Dict[str, Any]:
        """Load test case JSON"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def run_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Run single test case"""
        test_name = test_case['test_name']
        description = test_case['description']
        input_data = test_case['input']

        print(f"🧪 Test: {test_name}")
        print(f"   {description}")

        # Run balancer
        result = self.balancer.balance_meal(
            target=input_data['target'],
            meal_context=input_data['meal_context'],
            allowed_food_db_ids=input_data['allowed_food_db_ids']
        )

        # Validate
        validations = self.validate_result(test_case, result)

        # Report
        passed = all(v['passed'] for v in validations)

        if passed:
            print(f"   ✅ PASSED ({len(validations)} checks)")
        else:
            print(f"   ❌ FAILED")
            for v in validations:
                if not v['passed']:
                    print(f"      - {v['check']}: {v['message']}")

        if self.verbose:
            print(f"\n   📊 Result summary:")
            print(f"      Realistic: {result['best_match_realistic']['totals']}")
            print(f"      Delta: {result['best_match_realistic']['delta']}")
            print(f"      Recommendation: {result['recommendation']}")

        print()

        return {
            'test_name': test_name,
            'passed': passed,
            'validations': validations,
            'result': result
        }

    def validate_result(self, test_case: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate result against expected"""
        validations = []
        expected = test_case.get('expected', {})

        # Extract data
        realistic = result['best_match_realistic']
        unconstrained = result['best_match_unconstrained']

        # Test 1: Colazione standard
        if test_case['test_name'] == 'colazione_standard':
            validations.extend(self._validate_colazione(expected, realistic, unconstrained, result))

        # Test 2: Context-dependent
        elif test_case['test_name'] == 'snack_context_dependent':
            validations.extend(self._validate_context_dependent(expected, realistic, unconstrained))

        # Test 3: Ingredient mode
        elif test_case['test_name'] == 'ingredient_mode':
            validations.extend(self._validate_ingredient_mode(expected, realistic))

        # Test 4: Target impossibile
        elif test_case['test_name'] == 'target_impossibile':
            validations.extend(self._validate_impossible_target(expected, realistic, result))

        # Test 5: Pareggio rule
        elif test_case['test_name'] == 'pareggio_rule':
            validations.extend(self._validate_pareggio_rule(expected, realistic, unconstrained, result))

        return validations

    def _validate_colazione(self, expected, realistic, unconstrained, result) -> List[Dict]:
        """Validate colazione standard test"""
        checks = []

        # Check alimenti presenti
        realistic_items = {item['food_db_id'] for item in realistic['items'] if item['qty']['amount'] > 0}
        should_have = set(expected['realistic_should_have'])

        checks.append({
            'check': 'Alimenti richiesti presenti',
            'passed': should_have.issubset(realistic_items),
            'message': f"Expected {should_have}, got {realistic_items}"
        })

        # Check max quantities
        for item in realistic['items']:
            food_id = item['food_db_id']
            qty = item['qty']['amount']

            if food_id in expected['realistic_should_not_exceed']:
                max_qty = expected['realistic_should_not_exceed'][food_id]
                passed = qty <= max_qty
                checks.append({
                    'check': f'{food_id} max qty',
                    'passed': passed,
                    'message': f"{qty}g {'<=' if passed else '>'} {max_qty}g"
                })

        # Check delta tolerance
        tolerances = expected['totals_tolerance']
        for nutrient, tolerance in tolerances.items():
            delta_pct = abs(realistic['delta'][nutrient])
            passed = delta_pct <= tolerance

            checks.append({
                'check': f'{nutrient} tolerance',
                'passed': passed,
                'message': f"{delta_pct:.1f}% {'<=' if passed else '>'} {tolerance}%"
            })

        # Check recommendation
        checks.append({
            'check': 'Recommendation',
            'passed': result['recommendation'] == expected['recommendation'],
            'message': f"Expected {expected['recommendation']}, got {result['recommendation']}"
        })

        return checks

    def _validate_context_dependent(self, expected, realistic, unconstrained) -> List[Dict]:
        """Validate context-dependent test"""
        checks = []

        # Check realistic rispetta snack_max
        for item in realistic['items']:
            food_id = item['food_db_id']
            qty = item['qty']['amount']

            if food_id in expected['realistic_must_respect']:
                max_info = expected['realistic_must_respect'][food_id]
                max_qty = max_info['max_qty']
                passed = qty <= max_qty

                checks.append({
                    'check': f'{food_id} snack_max (realistic)',
                    'passed': passed,
                    'message': f"{qty}g {'<=' if passed else '>'} {max_qty}g ({max_info['reason']})"
                })

        # Check unconstrained può violare e marca violations
        if expected.get('violations_must_be_marked'):
            violating_items = [
                item for item in unconstrained['items']
                if item.get('violations')
            ]

            checks.append({
                'check': 'Unconstrained violations marked',
                'passed': len(violating_items) > 0,
                'message': f"Found {len(violating_items)} items with violations"
            })

        return checks

    def _validate_ingredient_mode(self, expected, realistic) -> List[Dict]:
        """Validate ingredient mode test"""
        checks = []

        # Find passata item
        passata = None
        for item in realistic['items']:
            if item['food_db_id'] == 'passata_di_pomodoro':
                passata = item
                break

        if passata:
            # Check is_ingredient
            checks.append({
                'check': 'Passata is_ingredient flag',
                'passed': passata.get('is_ingredient', False),
                'message': f"is_ingredient={passata.get('is_ingredient', False)}"
            })

            # Check multiplier is None
            checks.append({
                'check': 'Passata multiplier is None',
                'passed': passata.get('multiplier') is None,
                'message': f"multiplier={passata.get('multiplier')}"
            })

            # Check qty is multiple of step
            qty = passata['qty']['amount']
            step = expected['passata_behavior']['qty_must_be_multiple_of']
            passed = qty % step == 0

            checks.append({
                'check': f'Passata qty multiple of {step}g',
                'passed': passed,
                'message': f"{qty}g {'%' if passed else 'NOT %'} {step}g"
            })

            # Check realistic max
            max_realistic = expected['passata_behavior']['realistic_max']
            checks.append({
                'check': f'Passata realistic max {max_realistic}g',
                'passed': qty <= max_realistic,
                'message': f"{qty}g {'<=' if qty <= max_realistic else '>'} {max_realistic}g"
            })

        # Check olio max
        olio = None
        for item in realistic['items']:
            if item['food_db_id'] == 'olio_di_oliva_extra_vergine':
                olio = item
                break

        if olio:
            max_olio = expected['realistic_must_respect']['olio_di_oliva_extra_vergine']
            qty_olio = olio['qty']['amount']

            checks.append({
                'check': f'Olio realistic max {max_olio}g',
                'passed': qty_olio <= max_olio,
                'message': f"{qty_olio}g {'<=' if qty_olio <= max_olio else '>'} {max_olio}g"
            })

        return checks

    def _validate_impossible_target(self, expected, realistic, result) -> List[Dict]:
        """Validate impossible target test"""
        checks = []

        # Check P gap significativo
        P_gap_pct = abs(realistic['delta']['P_pct'])
        expected_gap = 30.0  # >30%

        checks.append({
            'check': f'P gap > {expected_gap}%',
            'passed': P_gap_pct > expected_gap,
            'message': f"P gap: {P_gap_pct:.1f}%"
        })

        # Check notes spiegano problema
        notes = result['notes']
        has_explanation = any('Target P' in note and 'non raggiunto' in note for note in notes)

        checks.append({
            'check': 'Notes explain failure',
            'passed': has_explanation,
            'message': f"Notes: {len(notes)} entries, {'explains' if has_explanation else 'missing explanation'}"
        })

        return checks

    def _validate_pareggio_rule(self, expected, realistic, unconstrained, result) -> List[Dict]:
        """Validate pareggio rule test"""
        checks = []
        rule = expected.get('unconstrained_vs_realistic', {})

        # Calculate errors
        error_realistic = self._calculate_total_error(realistic['delta'])
        error_unconstrained = self._calculate_total_error(unconstrained['delta'])

        # Check unconstrained is better
        checks.append({
            'check': 'Unconstrained is better',
            'passed': error_unconstrained < error_realistic,
            'message': f"Unconstrained {error_unconstrained:.1f} < Realistic {error_realistic:.1f}"
        })

        # Check difference threshold from expected
        if error_unconstrained > 0:
            increase_pct = ((error_realistic - error_unconstrained) / error_unconstrained) * 100
            expect_small = '<' in str(rule.get('but_difference_is_small', '< 5%'))
            threshold = 5.0
            checks.append({
                'check': 'Difference threshold check',
                'passed': (increase_pct < threshold) if expect_small else (increase_pct > threshold),
                'message': f"Increase: {increase_pct:.1f}%"
            })

        # Check recommendation
        expected_recommendation = rule.get('recommendation_should_be', 'best_match_realistic')
        checks.append({
            'check': f"Recommendation is {expected_recommendation}",
            'passed': result['recommendation'] == expected_recommendation,
            'message': f"Recommendation: {result['recommendation']}"
        })

        return checks

    def _calculate_total_error(self, delta: Dict[str, float]) -> float:
        """Calculate weighted error"""
        weights = {'kcal': 5.0, 'P': 4.0, 'CHO': 3.0, 'F': 2.0, 'Fibre': 1.0}
        total = 0
        for nutrient, weight in weights.items():
            pct_key = f'{nutrient}_pct'
            if pct_key in delta:
                total += abs(delta[pct_key]) * weight
        return total

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test cases"""
        print("=" * 80)
        print("🧪 MEAL BALANCER v1.0 - REGRESSION TEST SUITE")
        print("=" * 80)
        print()

        # Find all test case files
        test_files = sorted(self.test_cases_dir.glob('*.json'))

        if not test_files:
            print("❌ No test files found in", self.test_cases_dir)
            return {'passed': False, 'results': []}

        print(f"Found {len(test_files)} test cases\n")

        results = []
        for test_file in test_files:
            test_case = self.load_test_case(test_file)
            result = self.run_test(test_case)
            results.append(result)

        # Summary
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)

        passed_count = sum(1 for r in results if r['passed'])
        total_count = len(results)

        for result in results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"  {status}  {result['test_name']}")

        print()
        print(f"Result: {passed_count}/{total_count} tests passed")

        if passed_count == total_count:
            print("\n🎉 ALL TESTS PASSED - v1.0 is stable!")
            return {'passed': True, 'results': results}
        else:
            print(f"\n⚠️  {total_count - passed_count} test(s) failed")
            return {'passed': False, 'results': results}


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run meal_balancer regression tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    # Paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    test_cases_dir = base_dir / 'tests' / 'test_cases'

    # Run tests
    tester = RegressionTester(data_dir, test_cases_dir, verbose=args.verbose)
    summary = tester.run_all_tests()

    # Exit code
    sys.exit(0 if summary['passed'] else 1)


if __name__ == '__main__':
    main()
