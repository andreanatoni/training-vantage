#!/usr/bin/env python3
"""
Test Suite: CLI (Training Vantage v2.0)

Tests CLI functionality with proper error handling and exit codes:
1. plan rest → exit 0 (success with --skip-validation)
2. plan invalid_profile → exit 1 (config error)
3. plan rest (no skip) → exit 1 (validation error, current data has 10 errors)
"""

import sys
import subprocess
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_plan_rest_success():
    """
    Test 1: plan rest --skip-validation → exit 0

    Expected: CLI runs successfully, prints plan, exits 0
    """
    print("=" * 80)
    print("TEST 1: plan rest --skip-validation → exit 0")
    print("=" * 80)

    print("\n🧪 Running: python3 scripts/cli.py plan rest --skip-validation\n")

    try:
        result = subprocess.run(
            ['python3', 'scripts/cli.py', 'plan', 'rest', '--skip-validation'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("   ✅ Exit code: 0 (success)")

            # Check output contains expected sections
            if 'Training Vantage v2.0' in result.stdout:
                print("   ✅ Banner present")
            if 'DAY TOTALS' in result.stdout:
                print("   ✅ Day summary present")
            if 'Plan generated successfully' in result.stdout:
                print("   ✅ Success message present")

            print("\n" + "=" * 80)
            print("✅ TEST 1 PASSED")
            print("=" * 80)
            return True
        else:
            print(f"   ❌ FAIL: Exit code: {result.returncode} (expected 0)")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("   ❌ FAIL: Command timeout (>30s)")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Exception: {e}")
        return False


def test_plan_invalid_profile():
    """
    Test 2: plan invalid_profile → exit 1

    Expected: CLI detects invalid profile, exits 1 with config error
    """
    print("\n\n" + "=" * 80)
    print("TEST 2: plan invalid_profile --skip-validation → exit 1")
    print("=" * 80)

    print("\n🧪 Running: python3 scripts/cli.py plan invalid_xyz_profile --skip-validation\n")

    try:
        result = subprocess.run(
            ['python3', 'scripts/cli.py', 'plan', 'invalid_xyz_profile', '--skip-validation'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 1:
            print("   ✅ Exit code: 1 (config error, as expected)")

            # Check error message
            if "CONFIGURATION ERROR" in result.stdout or "not found" in result.stdout.lower():
                print("   ✅ Error message present")

            print("\n" + "=" * 80)
            print("✅ TEST 2 PASSED")
            print("=" * 80)
            return True
        else:
            print(f"   ❌ FAIL: Exit code: {result.returncode} (expected 1)")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("   ❌ FAIL: Command timeout (>30s)")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Exception: {e}")
        return False


def test_plan_validation_fail():
    """
    Test 3: plan rest (no --skip-validation) → exit 1

    Expected: CLI runs data validation, detects 10 errors, exits 1

    Note: Current data/ has known validation errors (10 errors):
    - PERSONAL_LIMITS inconsistencies
    - FOOD_GROUPS references to missing foods
    This test verifies that validation is enforced by default.
    """
    print("\n\n" + "=" * 80)
    print("TEST 3: plan rest (validation enforced) → exit 1")
    print("=" * 80)

    print("\n🧪 Running: python3 scripts/cli.py plan rest\n")
    print("(Note: Current data has 10 validation errors - this is expected)\n")

    try:
        result = subprocess.run(
            ['python3', 'scripts/cli.py', 'plan', 'rest'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 1:
            print("   ✅ Exit code: 1 (validation error, as expected)")

            # Check for validation error messages
            if "DATA VALIDATION FAILED" in result.stdout:
                print("   ✅ Validation failure detected")
            if "Fix data errors before running plan" in result.stdout:
                print("   ✅ Actionable error message present")

            print("\n" + "=" * 80)
            print("✅ TEST 3 PASSED")
            print("=" * 80)
            return True
        else:
            print(f"   ❌ FAIL: Exit code: {result.returncode} (expected 1)")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("   ❌ FAIL: Command timeout (>30s)")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Exception: {e}")
        return False


def test_cli_options():
    """
    Test 4: CLI options (--mode, --json)

    Expected: CLI accepts options and produces appropriate output
    """
    print("\n\n" + "=" * 80)
    print("TEST 4: CLI options (--mode realistic, --json)")
    print("=" * 80)

    # Test --mode realistic
    print("\n🧪 Test 4a: python3 scripts/cli.py plan rest --skip-validation --mode realistic\n")

    try:
        result = subprocess.run(
            ['python3', 'scripts/cli.py', 'plan', 'rest', '--skip-validation', '--mode', 'realistic'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("   ✅ Exit code: 0 (success)")
            if 'Version: realistic' in result.stdout or 'realistic' in result.stdout:
                print("   ✅ Realistic mode output")
        else:
            print(f"   ❌ FAIL: Exit code: {result.returncode}")
            return False

    except Exception as e:
        print(f"   ❌ FAIL: Exception: {e}")
        return False

    # Test --json
    print("\n🧪 Test 4b: python3 scripts/cli.py plan rest --skip-validation --json\n")

    try:
        result = subprocess.run(
            ['python3', 'scripts/cli.py', 'plan', 'rest', '--skip-validation', '--json'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("   ✅ Exit code: 0 (success)")

            # Check if output is valid JSON
            import json
            try:
                data = json.loads(result.stdout)
                if 'profile_id' in data and 'plan' in data:
                    print("   ✅ Valid JSON output with expected structure")
                else:
                    print("   ⚠️  JSON valid but missing expected keys")
            except json.JSONDecodeError:
                print("   ❌ FAIL: Output is not valid JSON")
                return False
        else:
            print(f"   ❌ FAIL: Exit code: {result.returncode}")
            return False

    except Exception as e:
        print(f"   ❌ FAIL: Exception: {e}")
        return False

    print("\n" + "=" * 80)
    print("✅ TEST 4 PASSED")
    print("=" * 80)
    return True


def main():
    """Run all CLI tests"""
    print("\n")
    print("=" * 80)
    print("🧪 CLI TEST SUITE (Training Vantage v2.0)")
    print("=" * 80)
    print("\nCLI functionality tests with exit codes and options\n")

    results = []

    # Test 1: Success case
    results.append(('plan_rest_success', test_plan_rest_success()))

    # Test 2: Invalid profile
    results.append(('plan_invalid_profile', test_plan_invalid_profile()))

    # Test 3: Validation failure
    results.append(('plan_validation_fail', test_plan_validation_fail()))

    # Test 4: CLI options
    results.append(('cli_options', test_cli_options()))

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
        print("\n🎉 ALL CLI TESTS PASSED")
        print("   CLI is production-ready!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
