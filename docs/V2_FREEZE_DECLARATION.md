# Training Vantage v2.0 - FREEZE DECLARATION

**Date**: 2026-02-12
**Status**: FROZEN - Feature Complete
**Version**: 2.0

---

## Architecture Overview

Training Vantage is a **CLI tool** for meal planning optimized for runner nutrition. The system is built on:

1. **Solver Core** (meal_balancer.py)
   - Beam search discrete optimizer (width 300)
   - Scoring function with weighted macro deltas
   - Pruning logic (kcal-based)
   - Status: **FROZEN** - No modifications

2. **Orchestrator** (plan_builder.py)
   - Day profile management
   - Meal distribution calculation
   - Constraint coordination
   - Status: **STABLE** - Only bug fixes

3. **Data Layer** (10 JSON files)
   - FOOD_DB, LARN_PORTIONS, OPERATIVE_PORTIONS
   - FOOD_DB_TO_LARN_MAPPING, PERSONAL_LIMITS
   - DAY_PROFILES, MEAL_DISTRIBUTION
   - FOOD_GROUPS, MEAL_TEMPLATES, REALISM_RULES
   - Status: **VALIDATED** - data_validator.py enforces integrity

4. **Validation Layer** (data_validator.py)
   - Structural integrity checks
   - Cross-reference validation
   - Exit code 0/1 for CI/CD
   - Status: **COMPLETE**

---

## Feature List (v2.0)

### Core Features ✅

- [x] Beam search meal optimizer
- [x] Dual solution (realistic + unconstrained)
- [x] LARN portion system
- [x] Personal limits (context-dependent, ingredient mode)
- [x] Day profile planning
- [x] Meal distribution management

### Constraint Layers ✅

1. **Volume Penalty** (Soft)
   - Excessive vegetable volume → penalty
   - Implementation: Callback (extra_penalty_fn)
   - Test: 4/4 pass

2. **Must Include** (Hard)
   - Required foods in meal
   - Implementation: Candidate filter (skip qty=0)
   - Test: 5/5 pass

3. **Protein Floor** (Hard)
   - Minimum protein per meal slot
   - Implementation: Target adjustment (orchestrator-only)
   - Test: 4/4 pass

### Validation ✅

- [x] Data validator (10 JSON files)
- [x] Fail-fast on structural errors
- [x] CLI integration (exit codes)
- [x] Test: 8/8 pass

### Test Coverage ✅

**Total: 32/32 tests pass**
- Meal Balancer v1.0: 5/5
- Plan Builder: 3/3
- Meal Templates: 6/6
- Template Fixes: 4/4
- Volume Penalty: 4/4
- Must Include: 5/5
- Protein Floor: 4/4
- Data Validator: 8/8 (includes baseline + 7 error scenarios)

---

## Constraint Pattern Reference

All constraints implemented in v2.0 follow one of three patterns:

### Pattern 1: Soft Constraint (Callback)

**When**: Guidance, not prohibition. Solver can violate if needed.

**Implementation**:
```python
# Orchestrator creates penalty function
def volume_penalty_fn(state, food_id, qty_g):
    # Calculate penalty based on state
    return penalty_value

# Pass to solver via API
result = balancer.balance_meal(
    target=targets,
    extra_penalty_fn=volume_penalty_fn  # ← API extension
)
```

**Example**: Volume penalty for excessive vegetables

**Layer**: Orchestrator creates callback, solver API extended

**Solver changes**: API parameter added (backward compatible)

---

### Pattern 2: Hard Structural Constraint (Candidate Filter)

**When**: Structural requirement (food must appear with qty > 0).

**Implementation**:
```python
# Orchestrator passes constraint to solver
result = balancer.balance_meal(
    target=targets,
    must_include_food_db_ids=['pollo_petto_cotto_in_padella']  # ← API extension
)

# Solver modifies candidate generation
def generate_quantity_candidates(food_db_id, ...):
    candidates = [...]

    # Skip qty=0 for must_include foods
    if food_db_id in must_include_food_db_ids:
        candidates = [c for c in candidates if c > 0]

    return candidates
```

**Example**: Must include (required foods)

**Layer**: Solver API extended + candidate generation modified

**Solver changes**: API parameter + candidate filter logic

---

### Pattern 3: Hard Target Constraint (Target Adjustment)

**When**: Minimum/maximum nutrient per meal slot.

**Implementation**:
```python
# Orchestrator adjusts target BEFORE solver call
P_floor_g = slot.get('P_floor_g', None)

if P_floor_g and targets['P'] < P_floor_g:
    target_adjustments.append({
        'nutrient': 'P',
        'from': targets['P'],
        'to': P_floor_g,
        'reason': 'protein_floor'
    })
    targets['P'] = P_floor_g  # Bump target

# Call solver with adjusted target (transparent)
result = balancer.balance_meal(target=targets, ...)

# Post-process: check if floor reached, add note if not
```

**Example**: Protein floor (minimum protein per meal)

**Layer**: Orchestrator-only (ZERO solver changes)

**Solver changes**: NONE (purest implementation)

---

## Rules for Future Development

### ✅ Allowed

1. **Bug fixes** in solver or orchestrator
2. **Data updates** (new foods, updated portions)
3. **New constraints following existing patterns**:
   - Soft → Callback pattern
   - Hard structural → Candidate filter pattern
   - Hard target → Target adjustment pattern
4. **CLI improvements** (better output formatting, new commands)
5. **Documentation updates**

### ❌ Forbidden

1. **New constraint patterns** - Use existing patterns only
2. **Solver core modifications** (beam_search, scoring weights, pruning logic)
   - Exception: Bug fixes with test coverage
3. **Breaking API changes** - All changes must be backward compatible
4. **Schema changes without data_validator updates**
5. **Performance optimizations without benchmarks**

---

## Architectural Principles

### 1. Separation of Concerns

- **Solver**: Pure optimization (beam search + scoring)
- **Orchestrator**: Business logic (constraints, validation, context)
- **Data**: Single source of truth (10 JSON files)
- **Validation**: Structural integrity (data_validator.py)

### 2. Constraint Layering

Constraints are **layered**, not mixed:
- Solver core: Unchanged optimization algorithm
- Solver API: Optional parameters (backward compatible)
- Candidate generation: Filter candidates before beam search
- Orchestrator: Soft rules, target adjustments, callbacks

### 3. Fail-Fast Data Validation

- Validate structure, not runtime behavior
- Catch errors early (ID mismatches, percentages ≠100, dangling refs)
- Never check "target reachable" (solver's job)

### 4. Test-Driven Stability

- Every constraint has dedicated test suite
- Regression tests prevent breaking changes
- 32/32 tests must pass before any release

### 5. Configuration Over Code

- Constraints defined in JSON (MEAL_DISTRIBUTION, MEAL_TEMPLATES, REALISM_RULES)
- Orchestrator reads config, solver is generic
- Easy to customize without code changes

---

## Example Constraint Implementation (Future)

**Hypothetical**: CHO floor (minimum carbs for pre-run meals)

**Pattern**: Target adjustment (orchestrator-only)

**Implementation**:
```python
# In MEAL_DISTRIBUTION.json (v3):
{
  "meal_id": "colazione",
  "CHO_pct": 55.0,
  "CHO_floor_g": 60  // ← NEW
}

# In plan_builder.py:
CHO_floor_g = slot.get('CHO_floor_g', None)

if CHO_floor_g and targets['CHO'] < CHO_floor_g:
    target_adjustments.append({
        'nutrient': 'CHO',
        'from': targets['CHO'],
        'to': CHO_floor_g,
        'reason': 'carb_floor'
    })
    targets['CHO'] = CHO_floor_g

# Solver call: unchanged
result = balancer.balance_meal(target=targets, ...)
```

**Solver changes**: ZERO (same pattern as protein floor)

**Tests required**: 4 tests (floor applied, no floor, unreachable, regression)

**Status**: Approved pattern, can be implemented without freeze violation

---

## Stress Test History

All stress tests completed and documented:

1. **Stress Test #1**: Template fixes (sweetener group, forbidden_food_ids) ✅
2. **Stress Test #2**: Volume penalty (soft constraint via callback) ✅
3. **Stress Test #3**: Solver core invariance verification ✅
4. **Stress Test #4**: Protein floor (hard target via orchestrator) ✅
5. **Stress Test #5**: Must include (hard structural via candidate filter) ✅
6. **Stress Test #6**: Data validation layer (fail-fast integrity) ✅

---

## Version History

### v1.0 (2026-02-10)
- Initial stable release
- Beam search optimizer
- LARN portion system
- 5/5 regression tests

### v2.0 (2026-02-12)
- Volume penalty (soft constraint)
- Must include (hard structural)
- Protein floor (hard target)
- Data validation layer
- 32/32 tests pass
- **STATUS: FROZEN**

---

## Maintenance Guidelines

### When to Update

1. **New food needed**: Add to FOOD_DB + mapping + limits
2. **Portion adjustment**: Update LARN_PORTIONS or OPERATIVE_PORTIONS
3. **User constraint**: Add to PERSONAL_LIMITS or MEAL_TEMPLATES
4. **Bug found**: Fix with test coverage, verify no regression

### When NOT to Update

1. **"Better" algorithm**: v2.0 is stable and validated
2. **Performance "optimization"**: Current performance is adequate
3. **"Cleaner" refactor**: Code works, don't break it
4. **New constraint pattern**: Use existing patterns only

### Release Checklist

Before any update (even data):
1. ✅ Run `python3 scripts/data_validator.py data` → exit 0
2. ✅ Run all test suites → 32/32 pass
3. ✅ Update changelog.json with change
4. ✅ Commit with descriptive message

---

## Conclusion

Training Vantage v2.0 is **feature complete** and **FROZEN**.

The architecture is:
- ✅ Proven (32/32 tests pass)
- ✅ Documented (6 stress test reports + this declaration)
- ✅ Stable (constraint patterns established)
- ✅ Validated (data integrity enforced)
- ✅ Maintainable (clear rules for future changes)

**No new features.** Only bug fixes, data updates, and constraints following existing patterns.

---

**Signed**: Claude Sonnet 4.5
**Date**: 2026-02-12
**Status**: FROZEN
