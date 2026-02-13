#!/usr/bin/env python3
"""
Test Suite: Tracking Commands

Tests for /weigh, /status, /zones commands
"""

import sys
import subprocess
import json
import tempfile
import shutil
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import tracking


def test_ffm_bmr_calculation():
    """
    Test 1: FFM and BMR calculation

    Verifica formule:
    - FFM = peso × (1 - bf/100)
    - BMR = 370 + 21.6 × FFM
    """
    print("=" * 80)
    print("TEST 1: FFM and BMR calculation")
    print("=" * 80)
    print()

    # Test case 1: From PRD example
    weight = 68.65
    bf_pct = 13.2
    expected_ffm = 59.57  # From PRD
    expected_bmr = 1657   # From PRD (rounded)

    ffm, bmr = tracking.calculate_ffm_bmr(weight, bf_pct)

    print(f"  Input: weight={weight} kg, BF={bf_pct}%")
    print(f"  Calculated FFM: {ffm:.2f} kg (expected: {expected_ffm} kg)")
    print(f"  Calculated BMR: {bmr:.0f} kcal (expected: {expected_bmr} kcal)")
    print()

    # Check FFM (allow 0.1 kg tolerance)
    if abs(ffm - expected_ffm) < 0.1:
        print("  ✅ FFM calculation correct")
    else:
        print(f"  ❌ FFM mismatch: {ffm:.2f} vs {expected_ffm}")
        return False

    # Check BMR (allow 5 kcal tolerance due to rounding)
    if abs(bmr - expected_bmr) < 5:
        print("  ✅ BMR calculation correct")
    else:
        print(f"  ❌ BMR mismatch: {bmr:.0f} vs {expected_bmr}")
        return False

    print()
    print("=" * 80)
    print("✅ TEST 1 PASSED")
    print("=" * 80)
    return True


def test_zones_calculation():
    """
    Test 2: Zones calculation from 5km test

    Verifica formule zone dal PRD test time 18:27
    """
    print("\n\n" + "=" * 80)
    print("TEST 2: Zones calculation")
    print("=" * 80)
    print()

    # Test case: From zones.json
    test_time = "18:27"
    expected_pace = "3:41"  # 18:27 / 5 km

    # Expected zones from zones.json
    expected_zones = {
        'Z1': {'from': '5:11', 'to': None},
        'Z2': {'from': '4:40', 'to': '5:11'},
        'Z3': {'from': '4:16', 'to': '4:40'},
        'Z4': {'from': '4:02', 'to': '4:16'},
        'Z5': {'from': '3:50', 'to': '4:02'},
        'Z6': {'from': '3:42', 'to': '3:50'},
        'Z7': {'from': '3:29', 'to': '3:42'},
        'Z8': {'from': '3:25', 'to': '3:29'}
    }

    # Calculate zones
    zones = tracking.calculate_zones(test_time)

    print(f"  Input: test time {test_time}")
    print(f"  Expected pace: {expected_pace}/km")
    print()

    # Check each zone
    all_correct = True
    for zone_id in ['Z1', 'Z2', 'Z3', 'Z4', 'Z5', 'Z6', 'Z7', 'Z8']:
        calc = zones[zone_id]
        exp = expected_zones[zone_id]

        match = calc['from'] == exp['from'] and calc['to'] == exp['to']

        if match:
            print(f"  ✅ {zone_id}: {calc['from']}-{calc['to'] or 'open'}")
        else:
            print(f"  ❌ {zone_id}: got {calc['from']}-{calc['to']}, expected {exp['from']}-{exp['to']}")
            all_correct = False

    print()

    if all_correct:
        print("=" * 80)
        print("✅ TEST 2 PASSED")
        print("=" * 80)
        return True
    else:
        print("=" * 80)
        print("❌ TEST 2 FAILED")
        print("=" * 80)
        return False


def test_weigh_command():
    """
    Test 3: /weigh command via CLI

    Test end-to-end del comando weigh
    """
    print("\n\n" + "=" * 80)
    print("TEST 3: /weigh command")
    print("=" * 80)
    print()

    # Create temporary data directory
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)

        # Initialize empty composition.json
        comp_file = data_dir / 'composition.json'
        comp_file.write_text('{"measurements": []}')

        print("  🧪 Testing: python3 scripts/cli.py weigh 68.5 13.0")
        print()

        # Call tracking module directly (not via subprocess for easier testing)
        result = tracking.add_measurement(data_dir, 68.5, 13.0, "Test measurement")

        # Check result
        if result['measurement']['weight'] == 68.5:
            print("  ✅ Weight recorded correctly")
        else:
            print("  ❌ Weight mismatch")
            return False

        if abs(result['measurement']['ffm'] - 59.59) < 0.1:
            print("  ✅ FFM calculated correctly")
        else:
            print(f"  ❌ FFM mismatch: {result['measurement']['ffm']:.2f}")
            return False

        if abs(result['measurement']['bmr'] - 1657) < 5:
            print("  ✅ BMR calculated correctly")
        else:
            print(f"  ❌ BMR mismatch: {result['measurement']['bmr']}")
            return False

        # Check file was saved
        data = json.loads(comp_file.read_text())
        if len(data['measurements']) == 1:
            print("  ✅ Measurement saved to file")
        else:
            print("  ❌ File save failed")
            return False

    print()
    print("=" * 80)
    print("✅ TEST 3 PASSED")
    print("=" * 80)
    return True


def test_zones_command():
    """
    Test 4: /zones command via CLI

    Test end-to-end del comando zones
    """
    print("\n\n" + "=" * 80)
    print("TEST 4: /zones command")
    print("=" * 80)
    print()

    # Create temporary data directory
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)

        # Initialize empty zones.json
        zones_file = data_dir / 'zones.json'
        zones_file.write_text('{"current": null, "history": []}')

        print("  🧪 Testing: python3 scripts/cli.py zones 18:27")
        print()

        # Call tracking module directly
        result = tracking.update_zones(data_dir, "18:27", note="Test")

        # Check result
        new_zones = result['new_zones']

        if new_zones['test_time'] == "18:27":
            print("  ✅ Test time recorded correctly")
        else:
            print("  ❌ Test time mismatch")
            return False

        if new_zones['test_pace'] == "3:41":
            print("  ✅ Pace calculated correctly")
        else:
            print(f"  ❌ Pace mismatch: {new_zones['test_pace']}")
            return False

        # Check Z6 (should be pace + 9")
        if new_zones['zones']['Z6']['from'] == "3:42":
            print("  ✅ Z6 calculated correctly")
        else:
            print(f"  ❌ Z6 mismatch: {new_zones['zones']['Z6']['from']}")
            return False

        # Check file was saved
        data = json.loads(zones_file.read_text())
        if len(data['history']) == 1:
            print("  ✅ Test saved to history")
        else:
            print("  ❌ History save failed")
            return False

    print()
    print("=" * 80)
    print("✅ TEST 4 PASSED")
    print("=" * 80)
    return True


def test_alerts_generation():
    """
    Test 5: Alerts generation

    Verifica generazione alerts per FFM low, weight loss, etc.
    """
    print("\n\n" + "=" * 80)
    print("TEST 5: Alerts generation")
    print("=" * 80)
    print()

    # Test case: FFM below red flag
    current = {
        'date': '2026-02-12',
        'weight': 68.0,
        'bf_pct': 13.5,
        'ffm': 59.3,  # Below 59.5 red flag
        'bmr': 1650
    }

    previous = {
        'date': '2026-02-05',
        'weight': 68.5,
        'bf_pct': 13.2,
        'ffm': 59.5,
        'bmr': 1655
    }

    analysis = tracking.analyze_measurement(current, previous, [previous, current])

    # Should have FFM critical alert
    ffm_alert = None
    for alert in analysis['alerts']:
        if alert['type'] == 'ffm_critical':
            ffm_alert = alert
            break

    if ffm_alert:
        print("  ✅ FFM critical alert generated")
        print(f"     Message: {ffm_alert['message']}")
    else:
        print("  ❌ FFM critical alert NOT generated")
        return False

    print()
    print("=" * 80)
    print("✅ TEST 5 PASSED")
    print("=" * 80)
    return True


def main():
    """Run all tracking tests"""
    print("\n")
    print("=" * 80)
    print("🧪 TRACKING TEST SUITE (Training Vantage v2.0)")
    print("=" * 80)
    print("\nTests for /weigh, /status, /zones commands\n")

    results = []

    # Test 1: FFM/BMR calculation
    results.append(('ffm_bmr_calculation', test_ffm_bmr_calculation()))

    # Test 2: Zones calculation
    results.append(('zones_calculation', test_zones_calculation()))

    # Test 3: Weigh command
    results.append(('weigh_command', test_weigh_command()))

    # Test 4: Zones command
    results.append(('zones_command', test_zones_command()))

    # Test 5: Alerts generation
    results.append(('alerts_generation', test_alerts_generation()))

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
        print("\n🎉 ALL TRACKING TESTS PASSED")
        print("   Tracking commands ready for use!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
