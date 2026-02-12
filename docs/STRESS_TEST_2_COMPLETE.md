# Stress Test #2: Fibre vs Volume (COMPLETE) ✅

## Status: ARCHITECTURALLY COMPLETE

Date: 2026-02-12
Version: v1.0 (refactored)

---

## Summary

Successfully implemented **soft volume penalty** for excessive veg with callback pattern in orchestrator.

**Key Achievement**:
- **Solver core invariato**: beam_search + scoring + pruning unchanged
- **Solver API estesa**: added `extra_penalty_fn` callback parameter
- **Orchestrator-only logic**: volume penalty calculation in plan_builder.py
- Clean architectural separation maintained

---

## Implementation Details

### 1. Configuration (REALISM_RULES.json)

Created soft constraint configuration:

```json
{
  "rules": {
    "volume_penalty_enabled": true,
    "veg_soft_cap_item_g": 400,
    "veg_soft_cap_total_g": 600,
    "veg_penalty_per_100g_over_item": 0.8,
    "veg_penalty_per_100g_over_total": 0.6,
    "apply_only_in_mode": "realistic",
    "groups_considered_veg": ["veg"],
    "exclude_ingredients_from_volume": true
  }
}
```

**Penalty Calibration** (why 0.8 and 0.6):
- Strong enough to prefer fiber-dense alternatives (avena/fruit/nuts)
- Weak enough to allow high veg when necessary (no alternatives)
- At 600g single item: penalty ~1.6
- At 800g total: penalty ~1.2
- Max penalty ~3-4 in extreme cases
- Typical macro error ~2-5, so penalty is significant but not dominant

### 2. Architectural Pattern (Callback Injection)

**Solver Layer (meal_balancer.py)** - FROZEN at v1.0:
```python
def calculate_score(self, ..., extra_penalty_fn: Optional[callable] = None):
    # Base score (macro delta)
    error = sum(abs(totals[n] - target[n]) / target[n] for n in nutrients)

    # External penalty injection (backward compatible)
    if extra_penalty_fn:
        extra = extra_penalty_fn(items, mode)
        error += extra

    return error
```

**Orchestrator Layer (plan_builder.py)** - Volume penalty logic:
```python
def create_volume_penalty_fn(self):
    """Create volume penalty closure for realistic mode."""
    rules = self.realism_rules.get('rules', {})
    if not rules.get('volume_penalty_enabled', False):
        return None

    # Capture parameters in closure
    veg_groups = set(rules.get('groups_considered_veg', ['veg']))
    veg_soft_cap_item_g = rules.get('veg_soft_cap_item_g', 400)
    # ... etc

    def volume_penalty(items, mode):
        if mode != apply_mode:
            return 0.0

        # Calculate veg volumes (exclude ingredients)
        veg_items = [...]

        # Penalty for items > 400g
        penalty = 0.0
        for item, qty in veg_items:
            if qty > veg_soft_cap_item_g:
                overage = qty - veg_soft_cap_item_g
                penalty += (overage / 100.0) * penalty_per_100g_item

        # Penalty for total > 600g
        total_veg = sum(qty for _, qty in veg_items)
        if total_veg > veg_soft_cap_total_g:
            overage = total_veg - veg_soft_cap_total_g
            penalty += (overage / 100.0) * penalty_per_100g_total

        return penalty

    return volume_penalty
```

**Integration**:
```python
def build_day_plan(self, ...):
    # Create penalty function (orchestrator layer)
    volume_penalty_fn = self.create_volume_penalty_fn()

    # Call solver with callback
    result = self.balancer.balance_meal(
        target=targets,
        meal_context=meal_context,
        allowed_food_db_ids=allowed_foods,
        extra_penalty_fn=volume_penalty_fn  # ← Injection point
    )
```

### 3. Behavior

**With volume penalty ENABLED (realistic mode)**:
- Prefers fiber-dense alternatives (avena, mela, mandorle) over excessive veg
- Can still exceed cap when necessary (no alternatives available)
- Ingredients (passata) excluded from volume counting

**With volume penalty DISABLED**:
- Solver behaves exactly as v1.0 (backward compatible)
- No performance impact

---

## Test Results

### All 23/23 Tests PASS ✅

1. **Meal Balancer v1.0 (5/5)** - Solver unchanged, all regression tests pass
2. **Plan Builder (3/3)** - Distribution math, context propagation
3. **Meal Templates (6/6)** - Required/forbidden groups, max_per_group
4. **Template Fixes v1.1 (4/4)** - Sweetener group, forbidden_food_ids, error messages
5. **Volume Penalty (4/4)** - Prefers fiber-dense, allows high veg when needed, excludes ingredients
6. **Architectural Verification (1/1)** - ✅ **NEW**: Verifies solver doesn't reference REALISM_RULES

### Architectural Test (test_solver_frozen.py)

```
✅ PASS: Solver is clean
   - No REALISM_RULES references
   - No volume_penalty logic
   - Callback pattern (extra_penalty_fn) present
   - Architectural separation maintained
```

This test **prevents regression** - ensures no one accidentally puts orchestration logic back into the solver.

---

## Files Modified

### Created
- `data/REALISM_RULES.json` - Soft constraint configuration
- `tests/test_volume_penalty.py` - 4 tests for volume penalty behavior
- `tests/test_solver_frozen.py` - Architectural verification test
- `tests/demo_volume_penalty.py` - Before/after demo
- `docs/STRESS_TEST_2_COMPLETE.md` - This file

### Modified
- `scripts/plan_builder.py` - Added `create_volume_penalty_fn()` and `generate_volume_warning_notes()`
- `scripts/meal_balancer.py` - Added `extra_penalty_fn` parameter (backward compatible)

---

## Key Takeaways

1. **Architectural Separation**: Solver (meal_balancer.py) remains configuration-agnostic. All domain logic lives in orchestrator (plan_builder.py).

2. **Callback Pattern**: Flexible extension mechanism. Orchestrator can inject ANY penalty function without modifying solver.

3. **Soft Constraints**: Penalties guide behavior without prohibiting solutions. System remains robust to edge cases.

4. **Backward Compatibility**: `extra_penalty_fn` is optional. Existing code works unchanged.

5. **Test Coverage**: 23/23 tests including architectural verification ensure no regression.

---

## Next Steps (Suggested)

Based on user request history, potential next stress tests:

- **Stress Test #5**: Must-include foods (e.g., "pasta always at pranzo")
- **Stress Test #6**: Variety penalty (discourage repetition within day)
- **Stress Test #7**: Ingredient pairing rules (e.g., "olio with veg")
- **Stress Test #8**: Practicality scoring (prep time, cookware)

All can follow the same callback pattern established here.

---

## Conclusion

✅ **Stress Test #2 is ARCHITECTURALLY COMPLETE**

The volume penalty feature is production-ready:
- Clean architecture (solver frozen)
- Full test coverage (23/23 tests pass)
- Well-documented calibration
- Behavioral demo provided
- Architectural verification prevents regression

The system is now ready for additional stress tests or production use.
