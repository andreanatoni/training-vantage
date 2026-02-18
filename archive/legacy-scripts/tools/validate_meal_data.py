#!/usr/bin/env python3
"""
Validatore completo per i 4 JSON del sistema meal balancer.

Verifica:
- Struttura e coerenza di ogni file
- Cross-references tra file
- Coverage completa (tutti gli alimenti mappati)
- Sanity checks sui valori
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional

# ANSI colors per output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_section(title: str):
    """Stampa sezione del report"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

def print_pass(msg: str):
    print(f"{Colors.GREEN}✅ PASS{Colors.END} {msg}")

def print_fail(msg: str):
    print(f"{Colors.RED}❌ FAIL{Colors.END} {msg}")

def print_warn(msg: str):
    print(f"{Colors.YELLOW}⚠️  WARN{Colors.END} {msg}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  INFO{Colors.END} {msg}")


class ValidationReport:
    """Colleziona risultati validazione"""
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passes: List[str] = []

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_pass(self, msg: str):
        self.passes.append(msg)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def print_summary(self):
        print_section("SUMMARY")
        print(f"\n{Colors.GREEN}✅ Passed:{Colors.END} {len(self.passes)}")
        print(f"{Colors.YELLOW}⚠️  Warnings:{Colors.END} {len(self.warnings)}")
        print(f"{Colors.RED}❌ Errors:{Colors.END} {len(self.errors)}")

        if self.has_errors():
            print(f"\n{Colors.RED}{Colors.BOLD}🚫 BLOCKERS FOUND - Fix before implementation!{Colors.END}")
            print("\nErrors to fix:")
            for i, err in enumerate(self.errors, 1):
                print(f"  {i}. {err}")
        else:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL VALIDATIONS PASSED!{Colors.END}")

        if self.warnings:
            print("\nWarnings (review recommended):")
            for i, warn in enumerate(self.warnings, 1):
                print(f"  {i}. {warn}")


def load_json(filepath: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """Carica JSON file con error handling"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f), ""
    except FileNotFoundError:
        return None, f"File not found: {filepath}"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in {filepath}: {e}"
    except Exception as e:
        return None, f"Error loading {filepath}: {e}"


def validate_food_db(data: Dict, report: ValidationReport) -> Dict[str, Any]:
    """Valida FOOD_DB.json"""
    print_section("Validating FOOD_DB.json")

    # Struttura meta
    if 'meta' not in data:
        report.add_error("FOOD_DB: missing 'meta' section")
    if 'foods' not in data:
        report.add_error("FOOD_DB: missing 'foods' array")
        return {}

    foods = data['foods']
    print_info(f"Found {len(foods)} foods")

    # Tracking
    ids_seen: Set[str] = set()
    valid_units = {'g', 'mL'}

    for i, food in enumerate(foods):
        food_ref = f"foods[{i}]"

        # Campi obbligatori
        required = ['id', 'name', 'reference', 'nutrients_per_reference']
        for field in required:
            if field not in food:
                report.add_error(f"{food_ref}: missing required field '{field}'")
                continue

        if 'id' not in food:
            continue

        food_id = food['id']

        # ID univoci
        if food_id in ids_seen:
            report.add_error(f"{food_id}: duplicate ID")
        ids_seen.add(food_id)

        # Reference
        if 'reference' in food:
            ref = food['reference']
            if 'amount' not in ref or 'unit' not in ref:
                report.add_error(f"{food_id}: reference missing 'amount' or 'unit'")
            else:
                if ref['amount'] <= 0:
                    report.add_error(f"{food_id}: reference amount must be > 0 (found {ref['amount']})")
                if ref['unit'] not in valid_units:
                    report.add_error(f"{food_id}: invalid unit '{ref['unit']}' (must be 'g' or 'mL')")

        # Nutrients
        if 'nutrients_per_reference' in food:
            nutrients = food['nutrients_per_reference']
            required_nutrients = ['kcal', 'P', 'CHO', 'F', 'Fibre']

            for nutrient in required_nutrients:
                if nutrient not in nutrients:
                    report.add_error(f"{food_id}: missing nutrient '{nutrient}'")
                else:
                    value = nutrients[nutrient]
                    if value < 0:
                        report.add_error(f"{food_id}: {nutrient} cannot be negative (found {value})")

            # Sanity checks
            kcal = nutrients.get('kcal', 0)
            if kcal > 1000:
                report.add_warning(f"{food_id}: very high kcal ({kcal}/100g) - verify")
            if kcal < 0:
                report.add_error(f"{food_id}: negative kcal")

    if not report.has_errors():
        report.add_pass(f"FOOD_DB: {len(foods)} foods validated successfully")
        print_pass(f"{len(foods)} foods validated")
    else:
        print_fail("FOOD_DB has errors (see above)")

    # Ritorna dictionary per cross-validation
    return {food['id']: food for food in foods if 'id' in food}


def validate_larn_portions(data: Dict, report: ValidationReport) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Valida LARN_PORTIONS.json"""
    print_section("Validating LARN_PORTIONS.json")

    if 'portions' not in data:
        report.add_error("LARN_PORTIONS: missing 'portions' array")
        return {}, {}

    portions = data['portions']
    print_info(f"Found {len(portions)} standard portions")

    ids_seen: Set[str] = set()
    variant_ids_seen: Set[str] = set()
    valid_units = {'g', 'mL'}

    portions_dict = {}
    variants_dict = {}

    for i, portion in enumerate(portions):
        portion_ref = f"portions[{i}]"

        # Campi obbligatori
        required = ['id', 'group', 'item', 'standard']
        for field in required:
            if field not in portion:
                report.add_error(f"{portion_ref}: missing required field '{field}'")
                continue

        if 'id' not in portion:
            continue

        portion_id = portion['id']

        # ID univoci
        if portion_id in ids_seen:
            report.add_error(f"{portion_id}: duplicate ID")
        ids_seen.add(portion_id)
        portions_dict[portion_id] = portion

        # Standard
        if 'standard' in portion:
            std = portion['standard']
            if 'qty' not in std or 'unit' not in std:
                report.add_error(f"{portion_id}: standard missing 'qty' or 'unit'")
            else:
                if std['qty'] <= 0:
                    report.add_error(f"{portion_id}: standard qty must be > 0")
                if std['unit'] not in valid_units:
                    report.add_error(f"{portion_id}: invalid unit '{std['unit']}'")

        # Varianti
        if 'variants' in portion:
            for j, variant in enumerate(portion['variants']):
                if 'id' not in variant:
                    report.add_error(f"{portion_id}.variants[{j}]: missing 'id'")
                    continue

                variant_id = variant['id']
                if variant_id in variant_ids_seen:
                    report.add_error(f"{variant_id}: duplicate variant ID")
                variant_ids_seen.add(variant_id)
                variants_dict[variant_id] = variant

                if 'standard' in variant:
                    vstd = variant['standard']
                    if 'qty' not in vstd or 'unit' not in vstd:
                        report.add_error(f"{variant_id}: standard missing 'qty' or 'unit'")

    if not report.has_errors():
        report.add_pass(f"LARN_PORTIONS: {len(portions)} portions + {len(variants_dict)} variants validated")
        print_pass(f"{len(portions)} portions + {len(variants_dict)} variants validated")
    else:
        print_fail("LARN_PORTIONS has errors")

    return portions_dict, variants_dict


def validate_operative_portions(data: Dict, report: ValidationReport) -> Dict[str, Any]:
    """Valida OPERATIVE_PORTIONS.json"""
    print_section("Validating OPERATIVE_PORTIONS.json")

    if 'portions' not in data:
        report.add_error("OPERATIVE_PORTIONS: missing 'portions' array")
        return {}

    portions = data['portions']
    print_info(f"Found {len(portions)} operative portions")

    ids_seen: Set[str] = set()
    valid_units = {'g', 'mL'}

    portions_dict = {}

    for i, portion in enumerate(portions):
        portion_ref = f"portions[{i}]"

        # Campi obbligatori
        required = ['id', 'item', 'standard', 'allowed_multipliers']
        for field in required:
            if field not in portion:
                report.add_error(f"{portion_ref}: missing required field '{field}'")
                continue

        if 'id' not in portion:
            continue

        portion_id = portion['id']

        # ID univoci
        if portion_id in ids_seen:
            report.add_error(f"{portion_id}: duplicate ID")
        ids_seen.add(portion_id)
        portions_dict[portion_id] = portion

        # Standard
        if 'standard' in portion:
            std = portion['standard']
            if 'qty' not in std or 'unit' not in std:
                report.add_error(f"{portion_id}: standard missing 'qty' or 'unit'")
            else:
                if std['qty'] <= 0:
                    report.add_error(f"{portion_id}: standard qty must be > 0")
                if std['unit'] not in valid_units:
                    report.add_error(f"{portion_id}: invalid unit '{std['unit']}'")

        # Allowed multipliers
        if 'allowed_multipliers' in portion:
            mults = portion['allowed_multipliers']
            if not isinstance(mults, list) or len(mults) == 0:
                report.add_error(f"{portion_id}: allowed_multipliers must be non-empty array")

        # Max qty validation
        if 'max_qty' in portion:
            max_qty = portion['max_qty']
            std_qty = portion.get('standard', {}).get('qty', 0)
            if 'qty' in max_qty and max_qty['qty'] <= std_qty:
                report.add_warning(f"{portion_id}: max_qty ({max_qty['qty']}) should be > standard qty ({std_qty})")

    if not report.has_errors():
        report.add_pass(f"OPERATIVE_PORTIONS: {len(portions)} portions validated")
        print_pass(f"{len(portions)} operative portions validated")
    else:
        print_fail("OPERATIVE_PORTIONS has errors")

    return portions_dict


def validate_mapping(data: Dict, food_db: Dict, larn_portions: Dict, larn_variants: Dict,
                     operative_portions: Dict, report: ValidationReport) -> Dict[str, Any]:
    """Valida FOOD_DB_TO_LARN_MAPPING.json"""
    print_section("Validating FOOD_DB_TO_LARN_MAPPING.json")

    if 'mapping' not in data:
        report.add_error("MAPPING: missing 'mapping' array")
        return {}

    mappings = data['mapping']
    print_info(f"Found {len(mappings)} mappings")

    mapped_food_ids: Set[str] = set()
    used_larn_ids: Set[str] = set()
    used_variant_ids: Set[str] = set()
    used_operative_ids: Set[str] = set()

    mapping_dict = {}

    for i, mapping in enumerate(mappings):
        mapping_ref = f"mapping[{i}]"

        # Food DB ID (required)
        if 'food_db_id' not in mapping:
            report.add_error(f"{mapping_ref}: missing 'food_db_id'")
            continue

        food_db_id = mapping['food_db_id']

        # Check duplicati
        if food_db_id in mapped_food_ids:
            report.add_error(f"{food_db_id}: duplicate mapping entry")
        mapped_food_ids.add(food_db_id)
        mapping_dict[food_db_id] = mapping

        # Verifica food_db_id esiste
        if food_db_id not in food_db:
            report.add_error(f"{food_db_id}: food_db_id not found in FOOD_DB.json")
            continue

        larn_id = mapping.get('larn_portion_id')
        operational_id = mapping.get('operational_portion_id')
        variant_id = mapping.get('larn_variant_id')

        # CRITICAL: deve avere almeno larn_portion_id O operational_portion_id
        if larn_id is None and operational_id is None:
            report.add_error(f"{food_db_id}: must have either 'larn_portion_id' or 'operational_portion_id'")

        # Verifica larn_portion_id
        if larn_id is not None:
            if larn_id not in larn_portions:
                report.add_error(f"{food_db_id}: larn_portion_id '{larn_id}' not found in LARN_PORTIONS.json")
            else:
                used_larn_ids.add(larn_id)

        # Verifica operational_portion_id
        if operational_id is not None:
            if operational_id not in operative_portions:
                report.add_error(f"{food_db_id}: operational_portion_id '{operational_id}' not found in OPERATIVE_PORTIONS.json")
            else:
                used_operative_ids.add(operational_id)

        # Verifica larn_variant_id
        if variant_id is not None:
            if variant_id not in larn_variants:
                report.add_error(f"{food_db_id}: larn_variant_id '{variant_id}' not found in LARN_PORTIONS variants")
            else:
                used_variant_ids.add(variant_id)

    # Coverage analysis
    unmapped_foods = set(food_db.keys()) - mapped_food_ids
    coverage = len(mapped_food_ids) / len(food_db) * 100 if food_db else 0

    print_info(f"Coverage: {len(mapped_food_ids)}/{len(food_db)} foods mapped ({coverage:.1f}%)")

    if unmapped_foods:
        report.add_warning(f"MAPPING: {len(unmapped_foods)} foods in FOOD_DB have no mapping")
        print_warn(f"{len(unmapped_foods)} unmapped foods:")
        for food_id in sorted(unmapped_foods):
            food_name = food_db[food_id].get('name', food_id)
            print(f"    - {food_id} ({food_name})")

    # Unused portions (not critical, just info)
    unused_larn = set(larn_portions.keys()) - used_larn_ids
    unused_operative = set(operative_portions.keys()) - used_operative_ids

    if unused_larn:
        print_info(f"{len(unused_larn)} LARN portions not used by any mapping (OK if intentional)")

    if not report.has_errors():
        report.add_pass(f"MAPPING: {len(mappings)} mappings validated, {coverage:.1f}% coverage")
        print_pass(f"{len(mappings)} mappings validated")
    else:
        print_fail("MAPPING has errors")

    return mapping_dict


def main():
    """Main validation routine"""
    print_section("MEAL DATA VALIDATION REPORT")

    # Paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    food_db_path = data_dir / 'FOOD_DB.json'
    larn_path = data_dir / 'LARN_PORTIONS.json'
    mapping_path = data_dir / 'FOOD_DB_TO_LARN_MAPPING.json'
    operative_path = data_dir / 'OPERATIVE_PORTIONS.json'

    report = ValidationReport()

    # Load files
    print_info("Loading JSON files...")

    food_db_data, err = load_json(food_db_path)
    if err:
        report.add_error(err)
        print_fail(err)
        report.print_summary()
        return 1

    larn_data, err = load_json(larn_path)
    if err:
        report.add_error(err)
        print_fail(err)
        report.print_summary()
        return 1

    mapping_data, err = load_json(mapping_path)
    if err:
        report.add_error(err)
        print_fail(err)
        report.print_summary()
        return 1

    operative_data, err = load_json(operative_path)
    if err:
        report.add_error(err)
        print_fail(err)
        report.print_summary()
        return 1

    print_pass("All files loaded successfully")

    # Validate individual files
    food_db = validate_food_db(food_db_data, report)
    larn_portions, larn_variants = validate_larn_portions(larn_data, report)
    operative_portions = validate_operative_portions(operative_data, report)
    mapping = validate_mapping(mapping_data, food_db, larn_portions, larn_variants,
                               operative_portions, report)

    # Final summary
    report.print_summary()

    return 0 if not report.has_errors() else 1


if __name__ == '__main__':
    sys.exit(main())
