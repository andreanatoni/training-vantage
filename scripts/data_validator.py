#!/usr/bin/env python3
"""
Data Validation Layer (Stress Test #6)

Validates ALL JSON data files for structural integrity and consistency.
Fails fast on data incoherence, NEVER on "target unreachable".

Usage:
    python3 scripts/data_validator.py [data_dir]

Returns:
    Exit code 0: All validations passed
    Exit code 1: Validation errors found
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any


class ValidationReport:
    """Structured validation report"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def add_error(self, file: str, message: str):
        """Add error (blocking issue)"""
        self.errors.append(f"{file}: {message}")

    def add_warning(self, file: str, message: str):
        """Add warning (non-blocking issue)"""
        self.warnings.append(f"{file}: {message}")

    def has_errors(self) -> bool:
        """Check if report has errors"""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if report has warnings"""
        return len(self.warnings) > 0

    def print_report(self):
        """Print formatted report"""
        if not self.errors and not self.warnings:
            print("\n✅ ALL VALIDATIONS PASSED")
            print("=" * 80)
            print("All data files are structurally consistent.")
            print("=" * 80)
            return

        print("\n" + "=" * 80)
        print("📋 DATA VALIDATION REPORT")
        print("=" * 80)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   {warning}")

        print("\n" + "=" * 80)
        if self.errors:
            print(f"❌ VALIDATION FAILED: {len(self.errors)} error(s) found")
        else:
            print(f"⚠️  VALIDATION PASSED with {len(self.warnings)} warning(s)")
        print("=" * 80)


def load_json(file_path: Path, report: ValidationReport, file_label: str) -> Dict:
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        report.add_error(file_label, f"File not found: {file_path}")
        return {}
    except json.JSONDecodeError as e:
        report.add_error(file_label, f"Invalid JSON: {e}")
        return {}


def validate_food_db(data_dir: Path, report: ValidationReport) -> Dict:
    """
    Validate FOOD_DB.json

    Checks:
    - id unique (field name is 'id', not 'food_db_id')
    - reference.amount > 0
    - reference.unit in {g, mL}
    - nutrients non-negative
    """
    food_db = load_json(data_dir / 'FOOD_DB.json', report, 'FOOD_DB')
    if not food_db:
        return {}

    seen_ids = set()
    food_db_index = {}

    for food in food_db.get('foods', []):
        # Note: actual data uses 'id', not 'food_db_id'
        food_id = food.get('id')

        # Check id exists and unique
        if not food_id:
            report.add_error('FOOD_DB', f"Missing id for food: {food.get('name', 'unknown')}")
            continue

        if food_id in seen_ids:
            report.add_error('FOOD_DB', f"Duplicate id: {food_id}")
        else:
            seen_ids.add(food_id)
            food_db_index[food_id] = food

        # Check reference
        ref = food.get('reference', {})
        amount = ref.get('amount')
        unit = ref.get('unit')

        if not amount or amount <= 0:
            report.add_error('FOOD_DB', f"{food_id}: reference.amount must be > 0 (got: {amount})")

        if unit not in ['g', 'mL']:
            report.add_error('FOOD_DB', f"{food_id}: reference.unit must be 'g' or 'mL' (got: {unit})")

        # Check nutrients - field is nutrients_per_reference in actual data
        nutrients = food.get('nutrients_per_reference', food.get('nutrients', {}))
        for nutrient, value in nutrients.items():
            if value < 0:
                report.add_error('FOOD_DB', f"{food_id}: nutrient '{nutrient}' cannot be negative (got: {value})")

    return food_db_index


def validate_larn_portions(data_dir: Path, report: ValidationReport) -> Tuple[Set[str], Dict[str, Dict[str, Any]]]:
    """
    Validate LARN_PORTIONS.json

    Checks:
    - portion_id unique
    - amount > 0
    - unit valid {g, mL}
    - variants coherent
    """
    larn = load_json(data_dir / 'LARN_PORTIONS.json', report, 'LARN_PORTIONS')
    if not larn:
        return set(), {}

    seen_ids = set()
    larn_index = {}

    for portion in larn.get('portions', []):
        # Note: actual file uses 'id', not 'portion_id'
        portion_id = portion.get('id')

        if not portion_id:
            report.add_error('LARN_PORTIONS', f"Missing id for portion: {portion.get('item', 'unknown')}")
            continue

        if portion_id in seen_ids:
            report.add_error('LARN_PORTIONS', f"Duplicate id: {portion_id}")
        else:
            seen_ids.add(portion_id)
            larn_index[portion_id] = portion

        # Check standard (not standard_qty)
        standard = portion.get('standard', {})
        qty = standard.get('qty')
        unit = standard.get('unit')

        if not qty or qty <= 0:
            report.add_error('LARN_PORTIONS', f"{portion_id}: standard.qty must be > 0 (got: {qty})")

        if unit not in ['g', 'mL']:
            report.add_error('LARN_PORTIONS', f"{portion_id}: standard.unit must be 'g' or 'mL' (got: {unit})")

        # Check variants (if present)
        for variant in portion.get('variants', []):
            v_amount = variant.get('amount')
            v_unit = variant.get('unit')

            if v_amount and v_amount <= 0:
                report.add_error('LARN_PORTIONS', f"{portion_id}: variant amount must be > 0 (got: {v_amount})")

            if v_unit and v_unit != unit:
                report.add_warning('LARN_PORTIONS', f"{portion_id}: variant unit '{v_unit}' differs from standard '{unit}'")

    return seen_ids, larn_index


def validate_operative_portions(data_dir: Path, report: ValidationReport) -> Set[str]:
    """
    Validate OPERATIVE_PORTIONS.json

    Checks:
    - portion_id unique
    - amount > 0
    - unit valid {g, mL, unit}
    """
    operative = load_json(data_dir / 'OPERATIVE_PORTIONS.json', report, 'OPERATIVE_PORTIONS')
    if not operative:
        return set()

    seen_ids = set()

    for portion in operative.get('portions', []):
        # Note: actual file uses 'id', not 'portion_id'
        portion_id = portion.get('id')

        if not portion_id:
            report.add_error('OPERATIVE_PORTIONS', f"Missing id for portion: {portion.get('item', 'unknown')}")
            continue

        if portion_id in seen_ids:
            report.add_error('OPERATIVE_PORTIONS', f"Duplicate id: {portion_id}")
        else:
            seen_ids.add(portion_id)

        # Check standard (not standard_qty)
        standard = portion.get('standard', {})
        qty = standard.get('qty')
        unit = standard.get('unit')

        if not qty or qty <= 0:
            report.add_error('OPERATIVE_PORTIONS', f"{portion_id}: standard.qty must be > 0 (got: {qty})")

        if unit not in ['g', 'mL', 'unit']:
            report.add_error('OPERATIVE_PORTIONS', f"{portion_id}: standard.unit must be 'g', 'mL', or 'unit' (got: {unit})")

    return seen_ids


def validate_mapping(data_dir: Path, report: ValidationReport,
                     food_db_ids: Set[str], larn_ids: Set[str], operative_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    """
    Validate FOOD_DB_TO_LARN_MAPPING.json

    Checks:
    - Every food_db_id exists in FOOD_DB
    - larn_portion_id or operational_portion_id must exist
    - No dangling mappings
    """
    mapping_data = load_json(data_dir / 'FOOD_DB_TO_LARN_MAPPING.json', report, 'FOOD_DB_TO_LARN_MAPPING')
    if not mapping_data:
        return {}

    mapping_index = {}

    # Note: actual file uses 'mapping', not 'mappings'
    for entry in mapping_data.get('mapping', []):
        food_id = entry.get('food_db_id')

        # Check food_db_id exists
        if not food_id:
            report.add_error('FOOD_DB_TO_LARN_MAPPING', "Missing food_db_id in mapping entry")
            continue

        if food_id not in food_db_ids:
            report.add_error('FOOD_DB_TO_LARN_MAPPING', f"Dangling food_db_id: {food_id} (not found in FOOD_DB)")
        else:
            mapping_index[food_id] = entry

        # Check at least one portion mapping
        larn_portion_id = entry.get('larn_portion_id')
        operational_portion_id = entry.get('operational_portion_id')

        if not larn_portion_id and not operational_portion_id:
            report.add_error('FOOD_DB_TO_LARN_MAPPING', f"{food_id}: must have either larn_portion_id or operational_portion_id")

        # Check larn_portion_id exists
        if larn_portion_id and larn_portion_id not in larn_ids:
            report.add_error('FOOD_DB_TO_LARN_MAPPING', f"{food_id}: larn_portion_id '{larn_portion_id}' not found in LARN_PORTIONS")

        # Check operational_portion_id exists
        if operational_portion_id and operational_portion_id not in operative_ids:
            report.add_error('FOOD_DB_TO_LARN_MAPPING', f"{food_id}: operational_portion_id '{operational_portion_id}' not found in OPERATIVE_PORTIONS")

    return mapping_index


def validate_personal_limits(data_dir: Path, report: ValidationReport, food_db_ids: Set[str]) -> Tuple[Dict[str, Dict[str, Any]], int]:
    """
    Validate PERSONAL_LIMITS.json

    Checks:
    - food_db_id exists
    - max_qty_g > 0
    - preferred_qty_g <= max_qty_g
    - step_g > 0 (if ingredient)
    - context caps <= max_qty_g
    """
    limits = load_json(data_dir / 'PERSONAL_LIMITS.json', report, 'PERSONAL_LIMITS')
    if not limits:
        return {}, 0

    limits_index = {}
    limits_total = len(limits.get('limits', []))

    for entry in limits.get('limits', []):
        food_id = entry.get('food_db_id')

        # Check food_db_id exists
        if not food_id:
            report.add_error('PERSONAL_LIMITS', "Missing food_db_id")
            continue

        if food_id not in food_db_ids:
            report.add_error('PERSONAL_LIMITS', f"Unknown food_db_id: {food_id} (not in FOOD_DB)")
        else:
            limits_index[food_id] = entry

        # Check max_qty_g
        max_qty = entry.get('max_qty_g')
        if max_qty is not None and max_qty <= 0:
            report.add_error('PERSONAL_LIMITS', f"{food_id}: max_qty_g must be > 0 (got: {max_qty})")

        # Check preferred_qty_g <= max_qty_g
        preferred_qty = entry.get('preferred_qty_g', [])
        if max_qty and preferred_qty:
            for pref in preferred_qty:
                if pref > max_qty:
                    report.add_error('PERSONAL_LIMITS', f"{food_id}: preferred_qty_g {pref} > max_qty_g {max_qty}")

        # Check step_g > 0 (if ingredient)
        is_ingredient = entry.get('is_ingredient', False)
        step_g = entry.get('step_g')

        if is_ingredient and step_g and step_g <= 0:
            report.add_error('PERSONAL_LIMITS', f"{food_id}: step_g must be > 0 for ingredients (got: {step_g})")

        # Check context caps <= max_qty_g
        snack_max = entry.get('snack_max_qty_g')
        meal_max = entry.get('meal_max_qty_g')

        if max_qty:
            if snack_max and snack_max > max_qty:
                report.add_error('PERSONAL_LIMITS', f"{food_id}: snack_max_qty_g {snack_max} > max_qty_g {max_qty}")
            if meal_max and meal_max > max_qty:
                report.add_error('PERSONAL_LIMITS', f"{food_id}: meal_max_qty_g {meal_max} > max_qty_g {max_qty}")

    return limits_index, limits_total


def validate_food_catalog(data_dir: Path,
                         report: ValidationReport,
                         food_db_index: Dict[str, Dict[str, Any]],
                         mapping_index: Dict[str, Dict[str, Any]],
                         larn_index: Dict[str, Dict[str, Any]],
                         personal_limits_index: Dict[str, Dict[str, Any]],
                         personal_limits_total: int):
    """
    Validate FOOD_CATALOG.json as derived/coherent view.

    Checks:
    - file exists and has meta.derived=true
    - stats consistent with source datasets
    - exact 1:1 coverage on FOOD_DB ids (no missing/extra/duplicates)
    - food reference/nutrients consistent with FOOD_DB
    - portion mapping consistent with FOOD_DB_TO_LARN_MAPPING + LARN_PORTIONS
    - personal_limits snapshot coherent with PERSONAL_LIMITS
    """
    catalog = load_json(data_dir / 'FOOD_CATALOG.json', report, 'FOOD_CATALOG')
    if not catalog:
        return

    meta = catalog.get('meta', {})
    if not meta.get('derived'):
        report.add_error('FOOD_CATALOG', "meta.derived must be true")

    foods = catalog.get('foods')
    if not isinstance(foods, list):
        report.add_error('FOOD_CATALOG', "foods must be a list")
        return

    stats = catalog.get('stats', {})
    expected_food_count = len(food_db_index)
    expected_mapping_count = len(mapping_index)
    expected_larn_count = len(larn_index)
    expected_limits_count = personal_limits_total

    if stats.get('foods_total') != expected_food_count:
        report.add_error('FOOD_CATALOG', f"stats.foods_total={stats.get('foods_total')} expected {expected_food_count}")
    if stats.get('catalog_foods_total') != len(foods):
        report.add_error('FOOD_CATALOG', f"stats.catalog_foods_total={stats.get('catalog_foods_total')} expected {len(foods)}")
    if stats.get('mappings_total') != expected_mapping_count:
        report.add_error('FOOD_CATALOG', f"stats.mappings_total={stats.get('mappings_total')} expected {expected_mapping_count}")
    if stats.get('larn_portions_total') != expected_larn_count:
        report.add_error('FOOD_CATALOG', f"stats.larn_portions_total={stats.get('larn_portions_total')} expected {expected_larn_count}")
    if stats.get('limits_total') != expected_limits_count:
        report.add_error('FOOD_CATALOG', f"stats.limits_total={stats.get('limits_total')} expected {expected_limits_count}")

    seen = set()
    missing_mapping_count = 0
    invalid_mapping_count = 0

    for row in foods:
        food_id = row.get('id')
        if not food_id:
            report.add_error('FOOD_CATALOG', "food row missing id")
            continue
        if food_id in seen:
            report.add_error('FOOD_CATALOG', f"duplicate food id: {food_id}")
            continue
        seen.add(food_id)

        source_food = food_db_index.get(food_id)
        if not source_food:
            report.add_error('FOOD_CATALOG', f"unknown food id: {food_id}")
            continue

        if row.get('reference') != source_food.get('reference'):
            report.add_error('FOOD_CATALOG', f"{food_id}: reference mismatch vs FOOD_DB")
        if row.get('nutrients_per_reference') != source_food.get('nutrients_per_reference'):
            report.add_error('FOOD_CATALOG', f"{food_id}: nutrients_per_reference mismatch vs FOOD_DB")

        source_mapping = mapping_index.get(food_id)
        source_larn = source_mapping.get('larn_portion_id') if source_mapping else None
        portion = row.get('portion') or {}
        catalog_larn = portion.get('larn_portion_id')

        if source_mapping is None:
            missing_mapping_count += 1
        elif not source_larn or source_larn not in larn_index:
            invalid_mapping_count += 1

        if catalog_larn != source_larn:
            report.add_error('FOOD_CATALOG', f"{food_id}: portion.larn_portion_id mismatch vs mapping source")

        if source_larn and source_larn in larn_index:
            larn_portion = larn_index[source_larn]
            if portion.get('standard') != larn_portion.get('standard'):
                report.add_error('FOOD_CATALOG', f"{food_id}: portion.standard mismatch vs LARN")

        source_limit = personal_limits_index.get(food_id)
        if row.get('personal_limits') != source_limit:
            report.add_error('FOOD_CATALOG', f"{food_id}: personal_limits mismatch vs PERSONAL_LIMITS")

    missing_foods = set(food_db_index.keys()) - seen
    extra_foods = seen - set(food_db_index.keys())
    if missing_foods:
        report.add_error('FOOD_CATALOG', f"missing ids vs FOOD_DB: {list(sorted(missing_foods))[:5]}...")
    if extra_foods:
        report.add_error('FOOD_CATALOG', f"extra ids not in FOOD_DB: {list(sorted(extra_foods))[:5]}...")

    if stats.get('missing_mapping_count') != missing_mapping_count:
        report.add_error('FOOD_CATALOG', f"stats.missing_mapping_count={stats.get('missing_mapping_count')} expected {missing_mapping_count}")
    if stats.get('invalid_larn_mapping_count') != invalid_mapping_count:
        report.add_error('FOOD_CATALOG', f"stats.invalid_larn_mapping_count={stats.get('invalid_larn_mapping_count')} expected {invalid_mapping_count}")


def validate_day_profiles(data_dir: Path, report: ValidationReport) -> Tuple[Set[str], Set[str]]:
    """
    Validate DAY_PROFILES.json

    Checks:
    - profile_id unique
    - distribution_id referenced exists (checked later)
    - totals_daily values > 0
    """
    profiles = load_json(data_dir / 'DAY_PROFILES.json', report, 'DAY_PROFILES')
    if not profiles:
        return set(), set()

    seen_ids = set()
    distribution_refs = set()

    for profile in profiles.get('profiles', []):
        profile_id = profile.get('id')

        if not profile_id:
            report.add_error('DAY_PROFILES', "Missing profile id")
            continue

        if profile_id in seen_ids:
            report.add_error('DAY_PROFILES', f"Duplicate profile_id: {profile_id}")
        else:
            seen_ids.add(profile_id)

        # Track distribution_id reference
        dist_id = profile.get('distribution_id')
        if dist_id:
            distribution_refs.add(dist_id)
        else:
            report.add_error('DAY_PROFILES', f"{profile_id}: missing distribution_id")

        # Check totals_daily
        totals = profile.get('totals_daily', {})
        for nutrient, value in totals.items():
            if value <= 0:
                report.add_error('DAY_PROFILES', f"{profile_id}: totals_daily.{nutrient} must be > 0 (got: {value})")

    return seen_ids, distribution_refs


def validate_meal_distribution(data_dir: Path, report: ValidationReport,
                               distribution_refs: Set[str]):
    """
    Validate MEAL_DISTRIBUTION.json

    Checks:
    - distribution_id unique
    - Referenced by DAY_PROFILES
    - Percentages sum to 100 (tolerance 1e-6)
    - P_floor_g >= 0
    """
    distributions = load_json(data_dir / 'MEAL_DISTRIBUTION.json', report, 'MEAL_DISTRIBUTION')
    if not distributions:
        return

    seen_ids = set()
    nutrients = ['kcal', 'P', 'CHO', 'F', 'Fibre']

    for dist in distributions.get('distributions', []):
        dist_id = dist.get('id')

        if not dist_id:
            report.add_error('MEAL_DISTRIBUTION', "Missing distribution id")
            continue

        if dist_id in seen_ids:
            report.add_error('MEAL_DISTRIBUTION', f"Duplicate distribution_id: {dist_id}")
        else:
            seen_ids.add(dist_id)

        # Check if referenced by profiles
        if dist_id not in distribution_refs:
            report.add_warning('MEAL_DISTRIBUTION', f"{dist_id}: not referenced by any DAY_PROFILE")

        # Check percentages sum to 100
        meal_slots = dist.get('meal_slots', [])

        for nutrient in nutrients:
            pct_key = f'{nutrient}_pct'
            total_pct = sum(slot.get(pct_key, 0) for slot in meal_slots)

            if abs(total_pct - 100.0) > 1e-6:
                report.add_error('MEAL_DISTRIBUTION',
                               f"{dist_id}: {pct_key} sums to {total_pct:.2f}, expected 100.0")

        # Check P_floor_g >= 0
        for slot in meal_slots:
            slot_id = slot.get('id', 'unknown')
            P_floor = slot.get('P_floor_g')

            if P_floor is not None and P_floor < 0:
                report.add_error('MEAL_DISTRIBUTION', f"{dist_id}.{slot_id}: P_floor_g must be >= 0 (got: {P_floor})")


def validate_food_groups(data_dir: Path, report: ValidationReport,
                        food_db_ids: Set[str]) -> Dict[str, str]:
    """
    Validate FOOD_GROUPS.json

    Checks:
    - All food_db_id exist in FOOD_DB
    - All food_db_id mapped to a group
    """
    groups = load_json(data_dir / 'FOOD_GROUPS.json', report, 'FOOD_GROUPS')
    if not groups:
        return {}

    food_group_map = {}
    seen_food_ids = set()

    for entry in groups.get('food_groups', []):
        food_id = entry.get('food_db_id')
        group = entry.get('group')

        if not food_id:
            report.add_error('FOOD_GROUPS', "Missing food_db_id")
            continue

        if food_id not in food_db_ids:
            report.add_error('FOOD_GROUPS', f"Unknown food_db_id: {food_id} (not in FOOD_DB)")

        if food_id in seen_food_ids:
            report.add_error('FOOD_GROUPS', f"Duplicate food_db_id: {food_id}")
        else:
            seen_food_ids.add(food_id)
            food_group_map[food_id] = group

    # In full-db mode FOOD_DB can be much larger than active planning set:
    # keep this as warning so validator remains useful without forcing 1:1 coverage.
    unmapped = food_db_ids - seen_food_ids
    if unmapped:
        report.add_warning('FOOD_GROUPS', f"Unmapped foods (no group assigned): {list(unmapped)[:5]}...")

    return food_group_map


def validate_meal_templates(data_dir: Path, report: ValidationReport,
                           food_group_map: Dict[str, str], food_db_ids: Set[str]):
    """
    Validate MEAL_TEMPLATES.json

    Checks:
    - required/forbidden groups exist
    - forbidden_food_ids exist in FOOD_DB
    - max_per_group >= 0
    """
    templates = load_json(data_dir / 'MEAL_TEMPLATES.json', report, 'MEAL_TEMPLATES')
    if not templates:
        return

    valid_groups = set(food_group_map.values())

    for template in templates.get('templates', []):
        meal_id = template.get('meal_id', 'unknown')
        rules = template.get('rules', {})

        # Check required/forbidden groups exist
        for req_group in rules.get('required_groups', []):
            if req_group not in valid_groups:
                report.add_error('MEAL_TEMPLATES', f"{meal_id}: required_group '{req_group}' not in FOOD_GROUPS")

        for forb_group in rules.get('forbidden_groups', []):
            if forb_group not in valid_groups:
                report.add_error('MEAL_TEMPLATES', f"{meal_id}: forbidden_group '{forb_group}' not in FOOD_GROUPS")

        # Check forbidden_food_ids exist
        for forb_food in rules.get('forbidden_food_ids', []):
            if forb_food not in food_db_ids:
                report.add_error('MEAL_TEMPLATES', f"{meal_id}: forbidden_food_id '{forb_food}' not in FOOD_DB")

        # Check max_per_group >= 0
        for group, max_count in rules.get('max_per_group', {}).items():
            if max_count < 0:
                report.add_error('MEAL_TEMPLATES', f"{meal_id}: max_per_group['{group}'] must be >= 0 (got: {max_count})")


def validate_realism_rules(data_dir: Path, report: ValidationReport):
    """
    Validate REALISM_RULES.json

    Checks:
    - Values >= 0
    - cap_total >= cap_item
    - penalty rates >= 0
    - apply_only_in_mode valid
    """
    rules = load_json(data_dir / 'REALISM_RULES.json', report, 'REALISM_RULES')
    if not rules:
        return

    r = rules.get('rules', {})

    # Check caps
    veg_cap_item = r.get('veg_soft_cap_item_g')
    veg_cap_total = r.get('veg_soft_cap_total_g')

    if veg_cap_item and veg_cap_item < 0:
        report.add_error('REALISM_RULES', f"veg_soft_cap_item_g must be >= 0 (got: {veg_cap_item})")

    if veg_cap_total and veg_cap_total < 0:
        report.add_error('REALISM_RULES', f"veg_soft_cap_total_g must be >= 0 (got: {veg_cap_total})")

    if veg_cap_item and veg_cap_total and veg_cap_total < veg_cap_item:
        report.add_error('REALISM_RULES', f"veg_soft_cap_total_g ({veg_cap_total}) should be >= veg_soft_cap_item_g ({veg_cap_item})")

    # Check penalty rates >= 0
    penalty_item = r.get('veg_penalty_per_100g_over_item')
    penalty_total = r.get('veg_penalty_per_100g_over_total')

    if penalty_item and penalty_item < 0:
        report.add_error('REALISM_RULES', f"veg_penalty_per_100g_over_item must be >= 0 (got: {penalty_item})")

    if penalty_total and penalty_total < 0:
        report.add_error('REALISM_RULES', f"veg_penalty_per_100g_over_total must be >= 0 (got: {penalty_total})")

    # Check apply_only_in_mode valid
    mode = r.get('apply_only_in_mode')
    if mode and mode not in ['realistic', 'unconstrained', 'both']:
        report.add_error('REALISM_RULES', f"apply_only_in_mode must be 'realistic', 'unconstrained', or 'both' (got: {mode})")


def validate_all(data_dir: Path) -> ValidationReport:
    """
    Validate all data files

    Returns:
        ValidationReport with errors/warnings
    """
    report = ValidationReport()

    print(f"📂 Validating data files in: {data_dir}\n")

    # 1. FOOD_DB
    print("   Validating FOOD_DB.json...")
    food_db_index = validate_food_db(data_dir, report)  # Returns Dict[str, Dict]
    food_db_ids_set = set(food_db_index.keys())  # Convert to set for set operations

    # 2. LARN_PORTIONS
    print("   Validating LARN_PORTIONS.json...")
    larn_ids, larn_index = validate_larn_portions(data_dir, report)

    # 3. OPERATIVE_PORTIONS
    print("   Validating OPERATIVE_PORTIONS.json...")
    operative_ids = validate_operative_portions(data_dir, report)

    # 4. FOOD_DB_TO_LARN_MAPPING
    print("   Validating FOOD_DB_TO_LARN_MAPPING.json...")
    mapping_index = validate_mapping(data_dir, report, food_db_ids_set, larn_ids, operative_ids)

    # 5. PERSONAL_LIMITS
    print("   Validating PERSONAL_LIMITS.json...")
    personal_limits_index, personal_limits_total = validate_personal_limits(data_dir, report, food_db_ids_set)

    # 6. FOOD_CATALOG
    print("   Validating FOOD_CATALOG.json...")
    validate_food_catalog(
        data_dir=data_dir,
        report=report,
        food_db_index=food_db_index,
        mapping_index=mapping_index,
        larn_index=larn_index,
        personal_limits_index=personal_limits_index,
        personal_limits_total=personal_limits_total,
    )

    # 7. DAY_PROFILES
    print("   Validating DAY_PROFILES.json...")
    profile_ids, distribution_refs = validate_day_profiles(data_dir, report)

    # 8. MEAL_DISTRIBUTION
    print("   Validating MEAL_DISTRIBUTION.json...")
    validate_meal_distribution(data_dir, report, distribution_refs)

    # 9. FOOD_GROUPS
    print("   Validating FOOD_GROUPS.json...")
    food_group_map = validate_food_groups(data_dir, report, food_db_ids_set)

    # 10. MEAL_TEMPLATES
    print("   Validating MEAL_TEMPLATES.json...")
    validate_meal_templates(data_dir, report, food_group_map, food_db_ids_set)

    # 11. REALISM_RULES
    print("   Validating REALISM_RULES.json...")
    validate_realism_rules(data_dir, report)

    return report


def main():
    """CLI entry point"""
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('data')

    if not data_dir.exists():
        print(f"❌ ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    report = validate_all(data_dir)
    report.print_report()

    sys.exit(1 if report.has_errors() else 0)


if __name__ == '__main__':
    main()
