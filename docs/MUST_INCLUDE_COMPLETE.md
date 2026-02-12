# must_include_food_db_ids Support (COMPLETE) ✅

## Status: IMPLEMENTED & VERIFIED

Date: 2026-02-12
Implementation: Hard constraint (structural, not penalty)
Pattern: Candidate filtering at solver layer

---

## Summary

Successfully implemented **must_include_food_db_ids** as a hard constraint with solver API extension (added parameter) and candidate generation modification.

**Key Achievement**:
- **Solver core invariato**: beam_search + scoring + pruning logic unchanged
- **Solver API estesa**: added `must_include_food_db_ids` parameter (backward compatible)
- **Candidate generation estesa**: skip qty=0 for must_include foods
- **Orchestrator validation**: pre-solver checks for template rules

---

## Implementation Details

### 1. Solver Layer (meal_balancer.py)

**Pattern**: Candidate filtering - disable qty=0 option for must_include foods

```python
def generate_quantity_candidates(self,
                                 food_db_id: str,
                                 meal_context: str,
                                 mode: str,
                                 must_include_food_db_ids: Optional[List[str]] = None):
    """
    Generate quantity candidates for a food.

    If food_db_id in must_include_food_db_ids → skip option 0 (no qty=0).
    """
    # ... portion info logic ...

    candidates = []

    # Opzione 0: skip se must-include (HARD CONSTRAINT)
    is_must_include = (must_include_food_db_ids is not None and
                      food_db_id in must_include_food_db_ids)

    if not is_must_include:
        candidates.append((0, None, []))

    # ... generate other quantity candidates ...

    return candidates
```

**Signature Updates** (backward compatible):
- `generate_quantity_candidates()` - added `must_include_food_db_ids` parameter
- `beam_search()` - added `must_include_food_db_ids` parameter
- `optimize_for_food_set()` - added `must_include_food_db_ids` parameter
- `balance_meal()` - added `must_include_food_db_ids` parameter

All parameters are **Optional** with default `None` → full backward compatibility.

### 2. Orchestrator Layer (plan_builder.py)

**Added**: `must_include_foods_per_meal` parameter to `build_day_plan()`

**Validation** (pre-solver):
1. **Must be in allowed_foods**: All must_include foods must be in allowed_food_db_ids
2. **Template rules**: Must_include foods must not violate template rules (forbidden groups/foods)
3. **max_per_group**: Must_include alone must not exceed max_per_group

```python
# Validate: all must_include in allowed_foods
for food_id in must_include_foods:
    if food_id not in allowed_foods:
        raise ValueError(
            f"{meal_id}: must_include food '{food_id}' not in allowed_foods. "
            f"Must_include: {must_include_foods}. Allowed: {allowed_foods}. "
            f"Fix: add '{food_id}' to allowed_foods or remove from must_include"
        )

# Validate: must_include against template rules
self.validate_must_include_against_template(meal_id, must_include_foods)
```

**New Method**: `validate_must_include_against_template()`
- Checks forbidden groups
- Checks forbidden_food_ids (hard blocks)
- Checks max_per_group violations

### 3. Behavior

**With must_include**:
- Foods MUST be present in solution (qty > 0)
- Solver can vary quantity (respecting LARN/PERSONAL_LIMITS)
- If target mathematically hard → solution still produced (high delta OK)

**Without must_include**:
- Solver free to use qty=0 for any food
- Exact same behavior as before (backward compatible)

---

## Test Results

### All 28/28 Tests PASS ✅

1. **Meal Balancer v1.0 (5/5)** - Solver core invariato (beam/scoring/pruning), all regression tests pass
2. **Plan Builder (3/3)** - Distribution math, context propagation
3. **Meal Templates (6/6)** - Required/forbidden groups, max_per_group
4. **Template Fixes v1.1 (4/4)** - Sweetener group, forbidden_food_ids, error messages
5. **Volume Penalty (4/4)** - Prefers fiber-dense, allows high veg when needed
6. **Solver Core Invariato (1/1)** - ✅ Verifies core logic unchanged, API extended OK
7. **Must Include (5/5)** - ✅ **NEW**: Valid, not in allowed, violates template, impossible target, **integrity check**

### Must Include Test Suite Details

**Test 1: Valid case** ✅
```
🧪 pranzo with must_include=['pollo_petto_cotto_in_padella']
✅ PASS: pollo presente in pranzo
   Qty: 100.0g
   Other items: ['pasta_secca_di_semola', 'zucchine_crude', 'olio_evo']
```

**Test 2: Not in allowed_foods** ✅
```
🧪 must_include=['pollo'] but NOT in allowed_foods
✅ Correctly raised ValueError:
   "pranzo: must_include food 'pollo_petto_cotto_in_padella' not in allowed_foods.
    Must_include: ['pollo_petto_cotto_in_padella'].
    Allowed: ['pasta_secca_di_semola', 'zucchine_crude', 'olio_evo', 'parmigiano_reggiano'].
    Fix: add 'pollo_petto_cotto_in_padella' to allowed_foods or remove from must_include"
```

**Test 3: Violates template rules** ✅
```
🧪 must_include=['pasta_secca_di_semola'] at colazione (forbidden)
✅ Correctly raised ValueError:
   "colazione: forbidden food 'pasta_secca_di_semola' present (hard block).
    All forbidden foods: ['pasta_secca_di_semola', 'riso_basmati_crudo', 'tortellini_vitello'].
    Fix: remove 'pasta_secca_di_semola' from allowed_foods"
```

**Test 4: Impossible target** ✅
```
🧪 spuntino (low kcal ~200) but must_include=['salmone'] (high P/F)
✅ PASS: solution produced (no crash)
   Salmone qty: 37.5g
   Total kcal: 192.5 (target: 200)
   Delta kcal: -3.8%
```

**Test 5: Integrity check** ✅
```
🧪 must_include=['pollo_petto_cotto_in_padella']
✅ Unconstrained: pollo qty=75.0g (present)
✅ Realistic: pollo qty=75.0g (present)
✅ Integrity verified: must_include present in BOTH solutions
   NEVER appears with qty=0 in items
```

---

## Demo: Real Use Case

**Scenario**: User wants to hit 50g protein for pranzo, with pollo (lean protein) guaranteed

```python
result = balancer.balance_meal(
    target={'kcal': 700, 'P': 50, 'CHO': 80, 'F': 20, 'Fibre': 10},
    meal_context='meal',
    allowed_food_db_ids=['pasta_secca_di_semola', 'pollo_petto_cotto_in_padella',
                         'zucchine_crude', 'olio_evo', 'parmigiano_reggiano'],
    must_include_food_db_ids=['pollo_petto_cotto_in_padella']  # ← FORCED
)
```

**Result**:
```
📊 Optimal solution:
      Pasta secca (di semola): 100.0g
   🎯 Pollo petto (cotto in padella): 100.0g (FORCED)
      Zucchine (crude): 250.0g
      Olio EVO: 10.0g
      Parmigiano Reggiano: 12.5g

   Totals:
      Kcal: 699.1 (target: 700)  → -0.1% delta
      P: 50.6g (target: 50g)     → +1.2% delta
      CHO: 79.8g (target: 80g)   → -0.2% delta
      F: 19.6g (target: 20g)     → -2.0% delta

   Pollo contribution:
      Qty: 100.0g
      P from pollo: 31.0g (61% of total P)

   ✅ User gets: lean protein source (pollo) + optimized macros!
```

---

## Use Cases

1. **Guarantee protein source**
   - "Always have pollo at pranzo"
   - "Must use salmone for omega-3"

2. **Dietary requirements**
   - "Must have veg at every meal"
   - "Must include legumes for fiber"

3. **Personal preferences**
   - "I always want pasta at pranzo"
   - "Must have yogurt at colazione"

4. **Meal prep constraints**
   - "Use chicken I already cooked"
   - "Must use ingredients about to expire"

5. **Training nutrition**
   - "Must have banana post-run (fast CHO)"
   - "Must include recovery shake after training"

---

## Files Modified

### Created
- `tests/test_must_include.py` - 4 tests for must_include behavior
- `tests/demo_must_include.py` - Practical demo with real use cases
- `docs/MUST_INCLUDE_COMPLETE.md` - This file

### Modified
- `scripts/meal_balancer.py`:
  - Added `must_include_food_db_ids` parameter to 4 methods (backward compatible)
  - Modified `generate_quantity_candidates()` to skip qty=0 for must_include foods

- `scripts/plan_builder.py`:
  - Added `must_include_foods_per_meal` parameter to `build_day_plan()`
  - Added validation: must_include in allowed_foods
  - Added `validate_must_include_against_template()` method
  - Pass must_include to solver

---

## Design Principles

1. **Hard Constraint (Structural)**: Not a penalty, but a structural constraint on candidate set
   - Penalty = guide behavior (soft)
   - Must_include = enforce presence (hard)

2. **Candidate Filtering**: Disable qty=0 option, don't modify scoring
   - Keeps solver core logic frozen
   - Clean separation of concerns

3. **Orchestrator Validation**: Check rules before solver runs
   - Fast fail on invalid input
   - Clear error messages with fix suggestions

4. **Backward Compatibility**: All parameters optional (default None)
   - Existing code works unchanged
   - Zero performance impact when not used

5. **Solver Core Invariato**: Beam/scoring/pruning unchanged
   - Beam search algorithm: unchanged
   - Scoring weights: unchanged
   - Pruning logic: unchanged
   - API extended: must_include_food_db_ids parameter added
   - Candidate generation: extended (skip qty=0 logic)

---

## Architectural Verification

**Solver Core Invariato** ✅
```
✅ PASS: Solver core logic preserved
   - Beam search algorithm: unchanged
   - Scoring weights: unchanged
   - Pruning logic: unchanged
   - No REALISM_RULES references (orchestrator-only)
   - No volume_penalty logic (orchestrator-only)
   - API extended: extra_penalty_fn + must_include_food_db_ids parameters
   - Candidate generation: extended (skip qty=0 for must_include)
```

---

## Next Steps (Suggested)

Other hard constraints that could follow the same pattern:

1. **must_exclude_food_db_ids**: Opposite of must_include (blacklist)
2. **min_qty_per_food**: Force minimum quantity for specific foods
3. **max_total_items**: Hard cap on number of items in meal
4. **required_food_groups**: Force presence of specific groups (e.g., "must have veg AND protein")

All can use the same candidate filtering pattern without touching solver core.

---

## Conclusion

✅ **must_include_food_db_ids Support is COMPLETE**

The feature is production-ready:
- Clean architecture (solver core invariato: beam/scoring/pruning unchanged)
- Solver API extended (must_include parameter, backward compatible)
- Candidate generation extended (skip qty=0 for must_include)
- Full test coverage (28/28 tests pass, including integrity check)
- Comprehensive validation (pre-solver checks)
- Clear error messages (actionable)
- Real use case demo provided
- Architectural verification passes (terminology corrected)
- Integrity verified (must_include in BOTH realistic + unconstrained)
- Backward compatible (zero breaking changes)

The candidate filtering pattern is now established for future hard constraints without modifying solver core logic (beam/scoring/pruning).
