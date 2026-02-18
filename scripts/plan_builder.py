#!/usr/bin/env python3
"""
plan_builder.py - Orchestratore per generazione piani giornalieri

ARCHITETTURA:
1. Carica DAY_PROFILES.json (macro totali per day type)
2. Carica MEAL_DISTRIBUTION.json (come distribuire macro nei pasti)
3. Per ogni pasto:
   - Calcola target assoluto da percentuali (con remainder logic)
   - Chiama meal_balancer.balance_meal(target, context, allowed_foods)
   - Raccoglie risultati

SEPARAZIONE:
- meal_balancer.py = SOLVER ENGINE (immutato v1.0)
- plan_builder.py = ORCHESTRATOR (logica day type + meal distribution)

ROBUSTEZZA v1:
- validate_distribution: percentuali sommano a 100
- remainder logic: ultimo pasto prende residuo per evitare drift
- allowed_foods_per_meal: obbligatorio (no None)
- slot_kind: supporta pre_run/post_run/recovery/regular
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.nutrition.meal_balancer import MealBalancerData, MealBalancer


class PlanBuilder:
    """Orchestratore per costruzione piani giornalieri"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

        # Load profile data
        self.day_profiles = self._load_json('DAY_PROFILES.json')
        self.meal_distributions = self._load_json('MEAL_DISTRIBUTION.json')

        # Load meal template data (v1.1)
        self.food_groups = self._load_json('FOOD_GROUPS.json')
        self.meal_templates = self._load_json('MEAL_TEMPLATES.json')
        self.realism_rules = self._load_json('REALISM_RULES.json')

        # Build indexes
        self.food_group_map = {
            f['food_db_id']: f['group']
            for f in self.food_groups['food_groups']
        }
        self.template_map = {
            t['meal_id']: t
            for t in self.meal_templates['templates']
        }

        # Load meal balancer data
        self.balancer_data = MealBalancerData(data_dir)
        self.balancer = MealBalancer(self.balancer_data)

    def _load_json(self, filename: str) -> Dict:
        """Load JSON file"""
        filepath = self.data_dir / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_day_profile(self, profile_id: str) -> Dict:
        """Get day profile by ID"""
        for profile in self.day_profiles['profiles']:
            if profile['id'] == profile_id:
                return profile
        raise ValueError(f"Day profile '{profile_id}' not found")

    def get_meal_distribution(self, distribution_id: str) -> Dict:
        """Get meal distribution by ID"""
        for dist in self.meal_distributions['distributions']:
            if dist['id'] == distribution_id:
                return dist
        raise ValueError(f"Meal distribution '{distribution_id}' not found")

    def create_volume_penalty_fn(self):
        """
        Create volume penalty function for realistic mode (Stress Test #2).

        ORCHESTRATOR LAYER: Volume penalty is realism logic, NOT solver logic.

        Returns closure that calculates soft penalty for excessive veg volume.

        Rules (from REALISM_RULES.json):
        - Single veg item > veg_soft_cap_item_g (400g) → penalty
        - Total veg in meal > veg_soft_cap_total_g (600g) → penalty
        - Ingredients (is_ingredient=true) excluded from volume counting
        - Apply only in realistic mode

        Penalty calibration (v1):
        - 0.8 per 100g over item cap: penalty~1.6 at 600g single item
        - 0.6 per 100g over total cap: penalty~1.2 at 800g total
        - These values are tuned to guide (not dominate) when alternatives exist
        - Max penalty ~3-4 in extreme cases (still allows solution if necessary)
        """
        rules = self.realism_rules.get('rules', {})

        if not rules.get('volume_penalty_enabled', False):
            return None

        # Get parameters
        veg_groups = set(rules.get('groups_considered_veg', ['veg']))
        veg_soft_cap_item_g = rules.get('veg_soft_cap_item_g', 400)
        veg_soft_cap_total_g = rules.get('veg_soft_cap_total_g', 600)
        penalty_per_100g_item = rules.get('veg_penalty_per_100g_over_item', 0.8)
        penalty_per_100g_total = rules.get('veg_penalty_per_100g_over_total', 0.6)
        exclude_ingredients = rules.get('exclude_ingredients_from_volume', True)
        apply_mode = rules.get('apply_only_in_mode', 'realistic')

        def volume_penalty(items, mode):
            """Calculate volume penalty for items"""
            # Apply only in specified mode
            if mode != apply_mode:
                return 0.0

            # Calculate veg volumes
            veg_total_g = 0.0
            veg_max_item_g = 0.0

            for item in items:
                # Skip if not veg group
                group = self.food_group_map.get(item.food_db_id, 'unknown')
                if group not in veg_groups:
                    continue

                # Skip ingredients if enabled
                if exclude_ingredients and item.is_ingredient:
                    continue

                qty_g = item.qty.amount
                veg_total_g += qty_g
                veg_max_item_g = max(veg_max_item_g, qty_g)

            # Calculate penalties
            penalty = 0.0

            # Single item penalty
            if veg_max_item_g > veg_soft_cap_item_g:
                over = veg_max_item_g - veg_soft_cap_item_g
                penalty += (over / 100.0) * penalty_per_100g_item

            # Total penalty
            if veg_total_g > veg_soft_cap_total_g:
                over = veg_total_g - veg_soft_cap_total_g
                penalty += (over / 100.0) * penalty_per_100g_total

            return penalty

        return volume_penalty

    def generate_volume_warning_notes(self, realistic_items) -> List[str]:
        """
        Generate warning notes for high veg volume (orchestrator layer).

        Args:
            realistic_items: Items from realistic solution

        Returns:
            List of warning notes (empty if no warning needed)
        """
        notes = []

        rules = self.realism_rules.get('rules', {})
        if not rules.get('volume_penalty_enabled'):
            return notes

        veg_groups = set(rules.get('groups_considered_veg', ['veg']))
        veg_soft_cap_total_g = rules.get('veg_soft_cap_total_g', 600)
        exclude_ingredients = rules.get('exclude_ingredients_from_volume', True)

        # Calculate veg total
        veg_total = 0.0
        for item in realistic_items:
            group = self.food_group_map.get(item['food_db_id'], 'unknown')
            if group in veg_groups:
                if not (exclude_ingredients and item.get('is_ingredient', False)):
                    veg_total += item['qty']['amount']

        if veg_total > veg_soft_cap_total_g:
            notes.append(
                f"Volume veg alto ({veg_total:.0f}g > {veg_soft_cap_total_g}g). "
                f"Soluzione: aggiungere fiocchi avena/frutta/semi tra allowed foods."
            )

        return notes

    def validate_meal_template(self, meal_id: str, allowed_foods: List[str]) -> None:
        """
        Validate that allowed_foods respects meal template rules.

        VALIDATION-ONLY (v1.1): Does NOT generate foods, only validates structure.

        Rules checked:
        1. Required groups present (e.g., colazione needs carb + protein)
        2. Forbidden groups absent (e.g., colazione forbids veg)
        2b. Forbidden food_ids absent (hard blocks, e.g., pasta at colazione)
        3. max_per_group respected (e.g., snack max 1 fat)
        4. min/max items count

        Args:
            meal_id: Meal slot ID (e.g., 'colazione', 'pranzo')
            allowed_foods: List of food_db_ids to validate

        Raises:
            ValueError: If template rules violated

        Example:
            >>> # Valid colazione
            >>> validate_meal_template('colazione', ['yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata'])
            # No error

            >>> # Invalid: missing protein
            >>> validate_meal_template('colazione', ['fette_biscottate', 'marmellata'])
            ValueError: colazione: missing required group 'protein'

            >>> # Invalid: has veg (forbidden)
            >>> validate_meal_template('colazione', ['yogurt_greco_0_lipidi', 'fette_biscottate', 'zucchine_crude'])
            ValueError: colazione: forbidden group 'veg' present
        """
        template = self.template_map.get(meal_id)
        if not template:
            # No template defined for this meal_id → skip validation
            return

        rules = template['rules']

        # Count groups present in allowed_foods
        group_counts = {}
        for food_id in allowed_foods:
            group = self.food_group_map.get(food_id, "unknown")
            group_counts[group] = group_counts.get(group, 0) + 1

        # 1️⃣ Check required groups
        required_groups = rules.get("required_groups", [])
        for req_group in required_groups:
            if group_counts.get(req_group, 0) == 0:
                present_groups = list(group_counts.keys())
                missing_groups = [g for g in required_groups if g not in present_groups]

                # Suggest foods from missing group
                suggested_foods = [
                    food_id for food_id, group in self.food_group_map.items()
                    if group == req_group
                ][:5]  # Max 5 suggestions

                raise ValueError(
                    f"{meal_id}: missing required group '{req_group}'. "
                    f"Required: {required_groups}. Present: {present_groups}. Missing: {missing_groups}. "
                    f"Fix: add one of {suggested_foods}"
                )

        # 2️⃣ Check forbidden groups
        for forb_group in rules.get("forbidden_groups", []):
            if group_counts.get(forb_group, 0) > 0:
                violating_foods = [
                    food_id for food_id in allowed_foods
                    if self.food_group_map.get(food_id) == forb_group
                ]
                raise ValueError(
                    f"{meal_id}: forbidden group '{forb_group}' present. "
                    f"Violating foods: {violating_foods}. "
                    f"Fix: remove these foods from allowed_foods"
                )

        # 2️⃣b Check forbidden_food_ids (hard blocks)
        forbidden_food_ids = rules.get("forbidden_food_ids", [])
        for food_id in allowed_foods:
            if food_id in forbidden_food_ids:
                raise ValueError(
                    f"{meal_id}: forbidden food '{food_id}' present (hard block). "
                    f"All forbidden foods: {forbidden_food_ids}. "
                    f"Fix: remove '{food_id}' from allowed_foods"
                )

        # 3️⃣ Check max_per_group
        for group, max_allowed in rules.get("max_per_group", {}).items():
            actual_count = group_counts.get(group, 0)
            if actual_count > max_allowed:
                violating_foods = [
                    food_id for food_id in allowed_foods
                    if self.food_group_map.get(food_id) == group
                ]
                excess = actual_count - max_allowed
                raise ValueError(
                    f"{meal_id}: too many items in group '{group}'. "
                    f"Max: {max_allowed}, actual: {actual_count} (excess: {excess}). "
                    f"Foods in this group: {violating_foods}. "
                    f"Fix: remove {excess} food(s) from this group"
                )

        # 4️⃣ Check min/max items
        min_items = rules.get("min_items", 0)
        max_items = rules.get("max_items", 999)

        if len(allowed_foods) < min_items:
            raise ValueError(
                f"{meal_id}: too few items. "
                f"Min: {min_items}, actual: {len(allowed_foods)}"
            )

        if len(allowed_foods) > max_items:
            raise ValueError(
                f"{meal_id}: too many items. "
                f"Max: {max_items}, actual: {len(allowed_foods)}"
            )

    def validate_must_include_against_template(self, meal_id: str, must_include_foods: List[str]) -> None:
        """
        Validate that must_include foods don't violate template rules.

        Checks:
        1. Must_include foods not in forbidden_groups
        2. Must_include foods not in forbidden_food_ids
        3. Must_include doesn't cause max_per_group violation (simple check)

        NOTE: This is a PRE-solver validation. The solver will handle quantity
        constraints (LARN limits, context-dependent caps, etc.).

        Args:
            meal_id: Meal slot ID
            must_include_foods: List of food_db_ids that MUST be included

        Raises:
            ValueError: If must_include violates template rules

        Example:
            >>> # Invalid: pasta at colazione (forbidden_food_ids)
            >>> validate_must_include_against_template('colazione', ['pasta_di_semola'])
            ValueError: colazione: must_include food 'pasta_di_semola' is forbidden
        """
        template = self.template_map.get(meal_id)
        if not template:
            # No template → no rules to check
            return

        rules = template['rules']

        # Check forbidden groups
        forbidden_groups = rules.get("forbidden_groups", [])
        for food_id in must_include_foods:
            group = self.food_group_map.get(food_id, "unknown")
            if group in forbidden_groups:
                raise ValueError(
                    f"{meal_id}: must_include food '{food_id}' belongs to forbidden group '{group}'. "
                    f"Forbidden groups: {forbidden_groups}. "
                    f"Fix: remove '{food_id}' from must_include or change meal template"
                )

        # Check forbidden_food_ids (hard blocks)
        forbidden_food_ids = rules.get("forbidden_food_ids", [])
        for food_id in must_include_foods:
            if food_id in forbidden_food_ids:
                raise ValueError(
                    f"{meal_id}: must_include food '{food_id}' is explicitly forbidden (hard block). "
                    f"All forbidden foods: {forbidden_food_ids}. "
                    f"Fix: remove '{food_id}' from must_include"
                )

        # Optional: Check if must_include alone would violate max_per_group
        # (simple heuristic - doesn't account for other allowed_foods)
        must_include_group_counts = {}
        for food_id in must_include_foods:
            group = self.food_group_map.get(food_id, "unknown")
            must_include_group_counts[group] = must_include_group_counts.get(group, 0) + 1

        for group, count in must_include_group_counts.items():
            max_allowed = rules.get("max_per_group", {}).get(group)
            if max_allowed and count > max_allowed:
                violating_foods = [
                    food_id for food_id in must_include_foods
                    if self.food_group_map.get(food_id) == group
                ]
                raise ValueError(
                    f"{meal_id}: must_include foods alone exceed max_per_group for '{group}'. "
                    f"Max: {max_allowed}, must_include has: {count}. "
                    f"Must_include foods in this group: {violating_foods}. "
                    f"Fix: reduce must_include foods in '{group}' group"
                )

    def validate_distribution(self, distribution_id: str) -> None:
        """
        Validate that percentages sum to 100 for each nutrient.

        Raises ValueError if sum != 100 (with 1e-6 tolerance).
        """
        dist = self.get_meal_distribution(distribution_id)
        nutrients = ['kcal', 'P', 'CHO', 'F', 'Fibre']

        for nutrient in nutrients:
            pct_key = f'{nutrient}_pct'
            total = sum(slot[pct_key] for slot in dist['meal_slots'])

            if abs(total - 100.0) > 1e-6:
                raise ValueError(
                    f"Distribution '{distribution_id}' invalid: "
                    f"{pct_key} sums to {total:.2f}, expected 100.0"
                )

    def calculate_day_meal_targets(self,
                                   day_totals: Dict[str, float],
                                   meal_slots: List[Dict]) -> List[Dict[str, float]]:
        """
        Calculate absolute targets for all meals from percentages.

        ROBUSTNESS: Uses "last slot takes remainder" logic to avoid rounding drift.

        Args:
            day_totals: Daily totals for each nutrient
            meal_slots: List of meal slot definitions with percentages

        Returns:
            List of target dicts (one per meal)

        Example:
            >>> day_totals = {'kcal': 2200, 'P': 140, 'CHO': 220, 'F': 70, 'Fibre': 30}
            >>> meal_slots = [
            ...     {'kcal_pct': 20, 'P_pct': 20, ...},  # colazione
            ...     {'kcal_pct': 10, 'P_pct': 12, ...},  # spuntino
            ...     ...
            ... ]
            >>> targets = calculate_day_meal_targets(day_totals, meal_slots)
            >>> # First 4 meals rounded, last takes exact remainder
        """
        nutrients = ['kcal', 'P', 'CHO', 'F', 'Fibre']

        # Step 1: Calculate raw targets (not rounded)
        raw_targets = []
        for slot in meal_slots:
            target = {}
            for nutrient in nutrients:
                pct_key = f'{nutrient}_pct'
                pct = slot[pct_key] / 100.0
                target[nutrient] = day_totals[nutrient] * pct
            raw_targets.append(target)

        # Step 2: Round all but last, track running totals
        final_targets = []
        running_totals = {n: 0.0 for n in nutrients}

        for i, target in enumerate(raw_targets):
            if i < len(raw_targets) - 1:
                # Round this meal
                rounded = {n: round(target[n], 1) for n in nutrients}
                final_targets.append(rounded)

                # Update running totals
                for n in nutrients:
                    running_totals[n] += rounded[n]
            else:
                # Last meal: take remainder to close exactly at daily totals
                remainder = {}
                for n in nutrients:
                    remainder[n] = round(day_totals[n] - running_totals[n], 1)
                final_targets.append(remainder)

        return final_targets

    def build_day_plan(self,
                      profile_id: str,
                      allowed_foods_per_meal: Dict[str, List[str]],
                      must_include_foods_per_meal: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """
        Build complete day plan for a given profile.

        ROBUSTNESS:
        - allowed_foods_per_meal is REQUIRED (no None fallback)
        - Validates distribution percentages sum to 100
        - Uses remainder logic to avoid rounding drift
        - must_include_foods_per_meal: Optional hard constraint (food MUST be used)

        Args:
            profile_id: Day profile ID (es. 'rest', 'lungo', 'qualita')
            allowed_foods_per_meal: Dict mapping meal_id → list of allowed food_db_ids
                REQUIRED for each meal in the distribution
            must_include_foods_per_meal: Optional dict mapping meal_id → list of food_db_ids
                that MUST be included in the meal (hard constraint, no qty=0 option)

        Returns:
            Complete day plan with all meals balanced

        Raises:
            ValueError: If allowed_foods_per_meal missing meal_id or distribution invalid
            ValueError: If must_include food not in allowed_foods
            ValueError: If must_include food violates template rules

        Example:
            >>> plan = builder.build_day_plan(
            ...     profile_id='rest',
            ...     allowed_foods_per_meal={
            ...         'colazione': ['yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata'],
            ...         'spuntino_mattina': ['mandorle', 'mela'],
            ...         'pranzo': ['pasta_di_semola', 'pollo_petto_cotto_in_padella'],
            ...         'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
            ...         'cena': ['salmone', 'patate_bollite_senza_buccia', 'olio_di_oliva_extra_vergine']
            ...     }
            ... )
        """
        # Get profile
        profile = self.get_day_profile(profile_id)
        distribution_id = profile['distribution_id']

        # Get and validate distribution
        distribution = self.get_meal_distribution(distribution_id)
        self.validate_distribution(distribution_id)

        # Check that allowed_foods_per_meal has all required meal_ids
        meal_slots = distribution['meal_slots']
        for slot in meal_slots:
            meal_id = slot['id']
            if meal_id not in allowed_foods_per_meal:
                raise ValueError(
                    f"allowed_foods_per_meal missing required meal_id: '{meal_id}'. "
                    f"Required meal_ids for distribution '{distribution_id}': "
                    f"{[s['id'] for s in meal_slots]}"
                )

        print(f"\n{'='*80}")
        print(f"📅 Building plan for: {profile['name']}")
        print(f"   {profile['description']}")
        print(f"   Distribution: {distribution_id}")
        print(f"{'='*80}\n")

        print(f"📊 Daily totals:")
        totals = profile['totals_daily']
        print(f"   Kcal: {totals['kcal']} | P: {totals['P']}g | CHO: {totals['CHO']}g | F: {totals['F']}g | Fibre: {totals['Fibre']}g")
        print(f"   Priority: {profile['priority']}\n")

        # Calculate targets for all meals (with remainder logic)
        meal_targets = self.calculate_day_meal_targets(totals, meal_slots)

        # Build each meal
        meals = []

        for slot, targets in zip(meal_slots, meal_targets):
            meal_id = slot['id']
            meal_name = slot['name']
            meal_context = slot['context']
            slot_kind = slot.get('slot_kind', 'regular')

            print(f"🍽️  {meal_name} ({slot['timing']}) [{slot_kind}]")
            print(f"   Context: {meal_context}")

            # Apply protein floor (Stress Test #4 - orchestrator-only, hard floor)
            P_floor_g = slot.get('P_floor_g', None)
            target_adjustments = []

            if P_floor_g and targets['P'] < P_floor_g:
                adjustment = {
                    'nutrient': 'P',
                    'from': targets['P'],
                    'to': P_floor_g,
                    'reason': 'protein_floor'
                }
                target_adjustments.append(adjustment)
                print(f"   🎯 Protein floor adjustment: {targets['P']:.1f}g → {P_floor_g}g")
                targets['P'] = P_floor_g

            print(f"   Targets: kcal {targets['kcal']} | P {targets['P']}g | CHO {targets['CHO']}g | F {targets['F']}g | Fibre {targets['Fibre']}g")

            # Get allowed foods for this meal
            allowed_foods = allowed_foods_per_meal[meal_id]

            # Get must_include foods for this meal (if any)
            must_include_foods = None
            if must_include_foods_per_meal and meal_id in must_include_foods_per_meal:
                must_include_foods = must_include_foods_per_meal[meal_id]

                # Validate: all must_include must be in allowed_foods
                for food_id in must_include_foods:
                    if food_id not in allowed_foods:
                        raise ValueError(
                            f"{meal_id}: must_include food '{food_id}' not in allowed_foods. "
                            f"Must_include: {must_include_foods}. Allowed: {allowed_foods}. "
                            f"Fix: add '{food_id}' to allowed_foods or remove from must_include"
                        )

            # Validate meal template (v1.1)
            self.validate_meal_template(meal_id, allowed_foods)

            # Validate must_include against template rules (if present)
            if must_include_foods:
                self.validate_must_include_against_template(meal_id, must_include_foods)

            # Create volume penalty function (orchestrator layer - Stress Test #2)
            volume_penalty_fn = self.create_volume_penalty_fn()

            # Call meal balancer (v1.0 + callback + must_include)
            result = self.balancer.balance_meal(
                target=targets,
                meal_context=meal_context,
                allowed_food_db_ids=allowed_foods,
                extra_penalty_fn=volume_penalty_fn,
                must_include_food_db_ids=must_include_foods
            )

            # Add volume warning notes if needed (orchestrator layer)
            realistic_items = result['best_match_realistic']['items']
            volume_notes = self.generate_volume_warning_notes(realistic_items)
            result['notes'].extend(volume_notes)

            # Add protein floor metadata and check (Stress Test #4 - orchestrator-only)
            result['constraints'] = {'P_floor_g': P_floor_g} if P_floor_g else {}
            result['target_adjustments'] = target_adjustments

            # Check if protein floor reached
            if P_floor_g:
                recommended_version_for_check = result['recommendation']
                actual_P = result[recommended_version_for_check]['totals']['P']

                if actual_P < P_floor_g:
                    floor_note = (
                        f"Protein floor {P_floor_g}g non raggiunto ({actual_P:.1f}g). "
                        f"Causa: allowed_foods insufficienti / caps personali. "
                        f"Azione: aggiungere fonte proteica (es. yogurt_greco_0_lipidi, albumi, pollo) "
                        f"o aumentare max_qty."
                    )
                    result['notes'].append(floor_note)

            # Show recommended version
            recommended_version = result['recommendation']
            recommended = result[recommended_version]

            print(f"   Recommended: {recommended_version}")
            print(f"   Items:")
            for item in recommended['items']:
                if item['qty']['amount'] > 0:
                    print(f"      - {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")

            delta = recommended['delta']
            print(f"   Delta: kcal {delta['kcal_pct']:+.1f}% | P {delta['P_pct']:+.1f}% | CHO {delta['CHO_pct']:+.1f}% | F {delta['F_pct']:+.1f}%\n")

            meals.append({
                'meal_id': meal_id,
                'meal_name': meal_name,
                'timing': slot['timing'],
                'context': meal_context,
                'slot_kind': slot_kind,
                'targets': targets,
                'result': result
            })

        # Calculate actual daily totals from meals
        actual_daily = {'kcal': 0, 'P': 0, 'CHO': 0, 'F': 0, 'Fibre': 0}
        for meal in meals:
            recommended_version = meal['result']['recommendation']
            totals = meal['result'][recommended_version]['totals']
            for nutrient in actual_daily:
                actual_daily[nutrient] += totals[nutrient]

        # Summary
        print(f"{'='*80}")
        print(f"✅ Day plan completed: {len(meals)} meals")
        print(f"\n📊 Daily totals verification:")
        print(f"   Target:  kcal {profile['totals_daily']['kcal']} | P {profile['totals_daily']['P']}g | CHO {profile['totals_daily']['CHO']}g | F {profile['totals_daily']['F']}g | Fibre {profile['totals_daily']['Fibre']}g")
        print(f"   Actual:  kcal {actual_daily['kcal']:.1f} | P {actual_daily['P']:.1f}g | CHO {actual_daily['CHO']:.1f}g | F {actual_daily['F']:.1f}g | Fibre {actual_daily['Fibre']:.1f}g")

        # Calculate daily delta
        daily_delta = {}
        for nutrient in actual_daily:
            target_val = profile['totals_daily'][nutrient]
            actual_val = actual_daily[nutrient]
            delta_abs = actual_val - target_val
            delta_pct = (delta_abs / target_val * 100) if target_val > 0 else 0
            daily_delta[nutrient] = {'abs': round(delta_abs, 1), 'pct': round(delta_pct, 1)}

        print(f"   Delta:   kcal {daily_delta['kcal']['pct']:+.1f}% | P {daily_delta['P']['pct']:+.1f}% | CHO {daily_delta['CHO']['pct']:+.1f}% | F {daily_delta['F']['pct']:+.1f}% | Fibre {daily_delta['Fibre']['pct']:+.1f}%")
        print(f"{'='*80}\n")

        return {
            'day_profile': profile,
            'distribution_id': distribution_id,
            'meals': meals,
            'actual_daily_totals': actual_daily,
            'daily_delta': daily_delta
        }


def main():
    """Example usage"""
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    builder = PlanBuilder(data_dir)

    # Example: Build rest day plan
    print("🧪 TEST 1: REST DAY PLAN\n")

    plan_rest = builder.build_day_plan(
        profile_id='rest',
        allowed_foods_per_meal={
            'colazione': ['caffe_espresso', 'yogurt_greco_0_lipidi', 'fette_biscottate', 'marmellata', 'mandorle'],
            'spuntino_mattina': ['mela', 'mandorle'],
            'pranzo': ['pasta_di_semola', 'pollo_petto_cotto_in_padella', 'olio_di_oliva_extra_vergine', 'zucchine_crude', 'parmigiano_reggiano_dop'],
            'spuntino_pomeriggio': ['pane_integrale', 'prosciutto_crudo'],
            'cena': ['salmone', 'patate_bollite_senza_buccia', 'olio_di_oliva_extra_vergine', 'insalata']
        }
    )

    # Example 2: Long run day
    print("\n" + "="*80)
    print("🧪 TEST 2: LONG RUN DAY PLAN\n")

    plan_lungo = builder.build_day_plan(
        profile_id='lungo',
        allowed_foods_per_meal={
            'colazione': ['caffe_espresso', 'fette_biscottate', 'miele', 'banana'],
            'post_lungo': ['yogurt_greco_0_lipidi', 'banana', 'mandorle'],
            'pranzo': ['riso_basmati_crudo', 'tacchino_fesa_cotta_al_forno', 'olio_di_oliva_extra_vergine', 'carote_crude', 'parmigiano_reggiano_dop'],
            'spuntino_pomeriggio': ['fette_biscottate', 'marmellata'],
            'cena': ['merluzzo_o_nasello_surgelato_cotto_in_forno', 'patate_bollite_senza_buccia', 'olio_di_oliva_extra_vergine', 'zucchine_crude']
        }
    )


if __name__ == '__main__':
    main()
