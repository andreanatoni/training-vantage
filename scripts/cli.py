#!/usr/bin/env python3
"""
Training Vantage CLI v2.0

Usage:
    python3 scripts/cli.py plan <day_profile_id> [options]

Commands:
    plan <profile_id>    Generate day plan for profile

Options:
    --mode <mode>        Output mode: realistic|unconstrained|recommended (default: recommended)
    --json              Output plan as JSON instead of formatted text
    --debug             Show detailed stacktrace on errors

Examples:
    python3 scripts/cli.py plan rest
    python3 scripts/cli.py plan lungo --mode realistic
    python3 scripts/cli.py plan easy_run --json
"""

import sys
import json
import traceback
from pathlib import Path
from typing import Dict, Any
from contextlib import redirect_stdout
from io import StringIO

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.plan_builder import PlanBuilder
from scripts.data_validator import validate_all


def print_banner(profile_id: str):
    """Print CLI banner"""
    print("=" * 80)
    print("Training Vantage v2.0 - Meal Planner")
    print(f"Day Profile: {profile_id.upper()}")
    print("=" * 80)
    print()


def print_meal_detailed(meal: Dict[str, Any], mode: str = 'recommended'):
    """
    Print single meal in detailed format

    Shows: name, timing, context, target macros, recommended version, items, delta
    """
    meal_id = meal['meal_id']
    meal_name = meal.get('meal_name', meal_id)
    timing = meal.get('timing', 'N/A')
    context = meal.get('context', 'N/A')

    # Header
    print(f"{'─' * 80}")
    print(f"🍽️  {meal_name.upper()}")
    print(f"    Timing: {timing}")
    print(f"    Context: {context}")
    print()

    # Target macros
    targets = meal.get('targets', {})
    print(f"    Target: kcal {targets.get('kcal', 0):.0f} | P {targets.get('P', 0):.1f}g | CHO {targets.get('CHO', 0):.1f}g | F {targets.get('F', 0):.1f}g")
    print()

    # Get version to display based on mode
    result = meal['result']
    if mode == 'recommended':
        recommendation = result['recommendation']
        version = result[recommendation]
        version_name = recommendation
    elif mode == 'realistic':
        version = result['best_match_realistic']
        version_name = 'realistic'
    elif mode == 'unconstrained':
        version = result['best_match_unconstrained']
        version_name = 'unconstrained'
    else:
        # Default to recommendation
        recommendation = result['recommendation']
        version = result[recommendation]
        version_name = recommendation

    print(f"    Version: {version_name}")
    print()

    # Print items with qty > 0
    print("    Items:")
    for item in version['items']:
        if item['qty']['amount'] > 0:
            name = item['name']
            qty = item['qty']['amount']
            unit = item['qty']['unit']
            print(f"      • {name}: {qty}{unit}")
    print()

    # Print totals and delta
    totals = version['totals']
    delta = version.get('delta', {})

    print(f"    Actual: kcal {totals['kcal']:.0f} | P {totals['P']:.1f}g | CHO {totals['CHO']:.1f}g | F {totals['F']:.1f}g")

    if delta:
        kcal_pct = delta.get('kcal_pct', 0.0)
        P_pct = delta.get('P_pct', 0.0)
        CHO_pct = delta.get('CHO_pct', 0.0)
        F_pct = delta.get('F_pct', 0.0)
        print(f"    Delta:  kcal {kcal_pct:+.1f}% | P {P_pct:+.1f}% | CHO {CHO_pct:+.1f}% | F {F_pct:+.1f}%")

    # Print notes if present
    notes = result.get('notes', [])
    if notes:
        print()
        print(f"    ℹ️  Note: {notes[0]}")

    print()


def print_day_summary(plan: Dict[str, Any], profile: Dict[str, Any]):
    """
    Print day summary with totals and comparison vs targets
    """
    if 'actual_daily_totals' not in plan:
        print("=" * 80)
        print("⚠️  WARNING: Day plan incomplete (some meals may have failed)")
        print("=" * 80)
        return

    actual = plan['actual_daily_totals']
    target = profile['totals_daily']

    print("=" * 80)
    print("📊 DAY TOTALS")
    print("=" * 80)
    print()

    # Target row
    print(f"Target:  kcal {target['kcal']:.0f} | P {target['P']:.1f}g | CHO {target['CHO']:.1f}g | F {target['F']:.1f}g | Fibre {target['Fibre']:.1f}g")

    # Actual row
    print(f"Actual:  kcal {actual['kcal']:.0f} | P {actual['P']:.1f}g | CHO {actual['CHO']:.1f}g | F {actual['F']:.1f}g | Fibre {actual['Fibre']:.1f}g")
    print()

    # Delta calculation
    delta_kcal = actual['kcal'] - target['kcal']
    delta_P = actual['P'] - target['P']
    delta_CHO = actual['CHO'] - target['CHO']
    delta_F = actual['F'] - target['F']
    delta_Fibre = actual['Fibre'] - target['Fibre']

    delta_kcal_pct = (delta_kcal / target['kcal'] * 100) if target['kcal'] > 0 else 0
    delta_P_pct = (delta_P / target['P'] * 100) if target['P'] > 0 else 0
    delta_CHO_pct = (delta_CHO / target['CHO'] * 100) if target['CHO'] > 0 else 0
    delta_F_pct = (delta_F / target['F'] * 100) if target['F'] > 0 else 0
    delta_Fibre_pct = (delta_Fibre / target['Fibre'] * 100) if target['Fibre'] > 0 else 0

    print(f"Delta:   kcal {delta_kcal_pct:+.1f}% | P {delta_P_pct:+.1f}% | CHO {delta_CHO_pct:+.1f}% | F {delta_F_pct:+.1f}% | Fibre {delta_Fibre_pct:+.1f}%")
    print()
    print("=" * 80)


def validate_data(data_dir: Path, debug: bool = False) -> bool:
    """
    Validate data files before building plan

    Args:
        data_dir: Path to data directory
        debug: Show detailed error info

    Returns:
        True if validation passed, False otherwise
    """
    print("🔍 Validating data files...")
    report = validate_all(data_dir)

    if report.has_errors():
        print()
        print("❌ DATA VALIDATION FAILED")
        print("=" * 80)

        # Show first 10 errors
        for i, error in enumerate(report.errors[:10], 1):
            print(f"  {i}. {error}")

        if len(report.errors) > 10:
            print(f"  ... and {len(report.errors) - 10} more errors")

        print("=" * 80)
        print()
        print("❌ Fix data errors before running plan.")
        print("   Run: python3 scripts/data_validator.py data")

        if debug:
            print()
            print("Full error list:")
            for error in report.errors:
                print(f"  - {error}")

        return False

    print("✅ Data validation passed")
    print()
    return True


def build_plan(profile_id: str, data_dir: Path, debug: bool = False) -> Dict[str, Any]:
    """
    Build day plan for given profile

    Args:
        profile_id: Day profile ID (e.g., 'rest', 'lungo')
        data_dir: Path to data directory
        debug: Show detailed error info

    Returns:
        Plan dict

    Raises:
        ValueError: If profile not found or invalid configuration
        RuntimeError: If plan building fails
    """
    builder = PlanBuilder(data_dir)

    # Get profile
    try:
        profile = builder.get_day_profile(profile_id)
    except KeyError:
        available = list(builder.data.day_profiles.keys())
        raise ValueError(
            f"Profile '{profile_id}' not found.\n"
            f"Available profiles: {', '.join(available)}"
        )

    # Get distribution
    try:
        distribution = builder.get_meal_distribution(profile['distribution_id'])
    except KeyError:
        raise ValueError(
            f"Distribution '{profile['distribution_id']}' not found in MEAL_DISTRIBUTION.json"
        )

    # Build allowed_foods_per_meal
    # Use curated lists optimized for template constraints
    base_foods = {
        # Breakfast (colazione) - MAX 6, no veg
        'breakfast': [
            'fette_biscottate',  # carb
            'yogurt_greco_0',  # protein
            'mandorle',  # fat
            'marmellata',  # sweetener
            'mela',  # fruit
            'caffe_espresso'  # beverage
        ],
        # Snack (spuntino) - MAX 3, no veg
        'snack': [
            'pane_integrale',  # carb
            'yogurt_greco_0',  # protein
            'mela'  # fruit
        ],
        # Main meal (pranzo/cena) - MAX 6, can have veg
        'main_meal': [
            'pasta_secca_di_semola',  # carb
            'pollo_petto_cotto_in_padella',  # protein
            'olio_evo',  # fat
            'zucchine_crude',  # veg
            'passata_di_pomodoro',  # veg/ingredient
            'mela'  # fruit
        ]
    }

    # Assign foods based on meal type
    allowed_foods_per_meal = {}
    for slot in distribution['meal_slots']:
        meal_id = slot['id'].lower()

        # Choose food set based on meal name
        if 'colazione' in meal_id:
            food_set = base_foods['breakfast']
        elif any(keyword in meal_id for keyword in ['spuntino', 'snack', 'post', 'recovery']):
            food_set = base_foods['snack']
        else:
            food_set = base_foods['main_meal']

        # Filter to only foods that exist in FOOD_DB
        meal_foods = [
            food_id
            for food_id in food_set
            if food_id in builder.balancer_data.food_db_index
        ]

        # Ensure we always provide allowed_foods_per_meal (never None)
        if not meal_foods:
            raise ValueError(
                f"No valid foods available for meal '{slot['id']}'. "
                "Check FOOD_DB integrity."
            )

        allowed_foods_per_meal[slot['id']] = meal_foods

    # Build plan
    try:
        plan = builder.build_day_plan(
            profile_id=profile_id,
            allowed_foods_per_meal=allowed_foods_per_meal
        )
    except Exception as e:
        if debug:
            raise RuntimeError(f"Plan building failed: {e}") from e
        else:
            raise RuntimeError(
                f"Plan building failed: {e}\n"
                "Use --debug for detailed stacktrace"
            )

    return plan


def cmd_plan(
    profile_id: str,
    mode: str = 'recommended',
    output_json: bool = False,
    debug: bool = False,
    skip_validation: bool = False
) -> int:
    """
    Plan command: build and display day plan

    Args:
        profile_id: Day profile ID
        mode: Output mode (realistic|unconstrained|recommended)
        output_json: Output as JSON instead of formatted text
        debug: Show detailed error info
        skip_validation: Skip data validation (for testing only, not documented)

    Returns:
        Exit code:
        - 0: Success
        - 1: Data validation or configuration errors
        - 2: Runtime errors during plan building
    """
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    # Validate mode
    valid_modes = ['realistic', 'unconstrained', 'recommended']
    if mode not in valid_modes:
        print(f"❌ ERROR: Invalid mode '{mode}'")
        print(f"   Valid modes: {', '.join(valid_modes)}")
        return 1

    # Validate data (required unless explicitly skipped for testing)
    if not skip_validation:
        if output_json:
            # Suppress validation output in JSON mode
            with redirect_stdout(StringIO()):
                if not validate_data(data_dir, debug=debug):
                    return 1
        else:
            if not validate_data(data_dir, debug=debug):
                return 1
    else:
        if not output_json:
            print("⚠️  Data validation skipped (testing mode)")
            print()

    # Build plan (suppress output if JSON mode)
    try:
        if output_json:
            # Suppress verbose output from plan_builder in JSON mode
            with redirect_stdout(StringIO()):
                plan = build_plan(profile_id, data_dir, debug=debug)
        else:
            plan = build_plan(profile_id, data_dir, debug=debug)
    except ValueError as e:
        # Configuration/validation errors
        print(f"❌ CONFIGURATION ERROR: {e}")
        return 1
    except RuntimeError as e:
        # Runtime errors during plan building
        print(f"❌ RUNTIME ERROR: {e}")
        if debug:
            print()
            print("Stacktrace:")
            traceback.print_exc()
        return 2
    except Exception as e:
        # Unexpected errors
        print(f"❌ UNEXPECTED ERROR: {e}")
        if debug:
            print()
            print("Stacktrace:")
            traceback.print_exc()
        return 2

    # Get profile for summary
    builder = PlanBuilder(data_dir)
    profile = builder.get_day_profile(profile_id)

    # Output
    if output_json:
        # JSON output
        output = {
            'profile_id': profile_id,
            'mode': mode,
            'plan': plan
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Formatted text output
        print_banner(profile_id)

        # Print meals
        for meal in plan['meals']:
            print_meal_detailed(meal, mode=mode)

        # Print day summary
        print_day_summary(plan, profile)

        print()
        print("✅ Plan generated successfully")

    return 0


def print_usage():
    """Print usage information"""
    print(__doc__)


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1]

    if command == 'plan':
        if len(sys.argv) < 3:
            print("❌ ERROR: Missing profile_id")
            print()
            print("Usage: python3 scripts/cli.py plan <profile_id> [options]")
            return 1

        profile_id = sys.argv[2]

        # Parse options
        mode = 'recommended'
        output_json = False
        debug = False
        skip_validation = False

        i = 3
        while i < len(sys.argv):
            arg = sys.argv[i]

            if arg == '--mode':
                if i + 1 >= len(sys.argv):
                    print("❌ ERROR: --mode requires an argument")
                    return 1
                mode = sys.argv[i + 1]
                i += 2
            elif arg == '--json':
                output_json = True
                i += 1
            elif arg == '--debug':
                debug = True
                i += 1
            elif arg == '--skip-validation':
                # Undocumented flag for testing
                skip_validation = True
                i += 1
            else:
                print(f"❌ ERROR: Unknown option: {arg}")
                return 1

        return cmd_plan(profile_id, mode=mode, output_json=output_json, debug=debug, skip_validation=skip_validation)
    else:
        print(f"❌ ERROR: Unknown command: {command}")
        print()
        print_usage()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
