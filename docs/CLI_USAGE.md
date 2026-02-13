# Training Vantage CLI - Usage Guide

**Version**: 2.0
**Status**: Production-ready
**Date**: 2026-02-12

---

## Overview

Training Vantage CLI is a command-line tool for generating optimized meal plans based on day profiles (rest, training intensity, etc.). The CLI integrates:

- **Data validation** - Ensures data integrity before plan generation
- **Meal balancer** - Beam search optimizer with constraint layers
- **Multiple output modes** - Realistic, unconstrained, or recommended
- **JSON export** - Machine-readable output for integrations

---

## Installation

No installation required. Run directly with Python 3:

```bash
python3 scripts/cli.py <command> [options]
```

---

## Commands

### `plan <profile_id>`

Generate meal plan for a specific day profile.

### `plan all`

**NEW in v2.1** - Regenerate all 8 nutrition plans and save as markdown files.

**Syntax:**
```bash
python3 scripts/cli.py plan all
```

**What it does:**
- Generates optimized meal plans for all 8 categories (rest, forza, easy_run, qualita, tempo, lungo, pizza_day, domenica)
- Each plan contains multiple options per meal with:
  - Grammature ottimizzate dal meal balancer
  - Swap alternatives (iso-proteico, iso-grassi, iso-CHO, iso-calorico)
  - Yogurt special case (2 variants: magro+mandorle vs greco)
- Exports to `plans/nutrition/{category}.md`
- Total generation time: ~2-3 minutes (~184 meal balancer calls)

**Output example:**
```
================================================================================
GENERATING ALL NUTRITION PLANS
================================================================================

Categories: 8
Output: plans/nutrition

[1/8] Generating rest... ✅ (12.1 KB, 29 options)
[2/8] Generating forza... ✅ (11.8 KB, 27 options)
[3/8] Generating easy_run... ✅ (11.9 KB, 28 options)
[4/8] Generating qualita... ✅ (12.0 KB, 29 options)
[5/8] Generating tempo... ✅ (12.1 KB, 28 options)
[6/8] Generating lungo... ✅ (9.8 KB, 24 options)
[7/8] Generating pizza_day... ✅ (11.7 KB, 27 options)
[8/8] Generating domenica... ✅ (9.9 KB, 24 options)

================================================================================
SUMMARY
================================================================================
✅ Success: 8/8
🎉 All plans generated successfully!
```

**When to use:**
- After updating composition (FFM/peso changed significantly)
- After modifying FOOD_DB or piano_base
- To regenerate all plans with updated macro targets

---

### `plan <profile_id>` (original command)

**Syntax:**
```bash
python3 scripts/cli.py plan <profile_id> [options]
```

**Available Profiles:**
- `rest` - Rest day (no training, focus recovery)
- `easy_run` - Easy run day (aerobic base)
- `qualita` - Quality workout day (intervals, tempo)
- `tempo` - Tempo run day
- `lungo` - Long run day (endurance)
- `forza` - Strength training day
- `pizza_day` - Weekly treat day
- `domenica` - Sunday long run + social

---

## Options

### `--mode <mode>`

Select which version of the meal plan to display:

- **`recommended`** (default) - Shows the recommended version (realistic if constraints met, unconstrained otherwise)
- **`realistic`** - Shows the realistic version (respects personal limits)
- **`unconstrained`** - Shows the unconstrained version (ignores personal limits for better macro accuracy)

**Example:**
```bash
python3 scripts/cli.py plan rest --mode realistic
```

### `--json`

Output plan as JSON instead of formatted text. Useful for integrations or data analysis.

**Example:**
```bash
python3 scripts/cli.py plan rest --json > rest_plan.json
```

**JSON Structure:**
```json
{
  "profile_id": "rest",
  "mode": "recommended",
  "plan": {
    "day_profile": { ... },
    "meals": [ ... ],
    "actual_daily_totals": { ... }
  }
}
```

### `--debug`

Show detailed stacktraces on errors. Useful for debugging data issues or plan generation failures.

**Example:**
```bash
python3 scripts/cli.py plan rest --debug
```

---

## Exit Codes

The CLI uses standard exit codes for CI/CD integration:

- **`0`** - Success (plan generated successfully)
- **`1`** - Data validation or configuration error
  - Invalid profile_id
  - Data validation failed
  - Missing distribution or template
- **`2`** - Runtime error during plan building
  - Solver failure
  - Unexpected exceptions

**Example in script:**
```bash
#!/bin/bash
python3 scripts/cli.py plan rest
if [ $? -eq 0 ]; then
  echo "Plan generated successfully"
else
  echo "Plan generation failed"
  exit 1
fi
```

---

## Examples

### Basic Usage

Generate plan for rest day:
```bash
python3 scripts/cli.py plan rest
```

**Output:**
```
🔍 Validating data files...
✅ Data validation passed

================================================================================
Training Vantage v2.0 - Meal Planner
Day Profile: REST
================================================================================

────────────────────────────────────────────────────────────────────────────────
🍽️  COLAZIONE
    Timing: 07:30-08:30
    Context: meal

    Target: kcal 484 | P 30.8g | CHO 55.0g | F 12.6g

    Version: best_match_unconstrained

    Items:
      • Fette biscottate: 15.0g
      • Yogurt greco 0%: 250.0g
      • Mandorle: 22.5g
      • Marmellata: 25.0g
      • Mela: 112.5g

    Actual: kcal 462 | P 31.6g | CHO 61.3g | F 12.8g
    Delta:  kcal -4.5% | P +2.7% | CHO +11.5% | F +2.0%

[... more meals ...]

================================================================================
📊 DAY TOTALS
================================================================================

Target:  kcal 2200 | P 140.0g | CHO 220.0g | F 70.0g | Fibre 30.0g
Actual:  kcal 2138 | P 146.2g | CHO 225.5g | F 71.1g | Fibre 27.0g

Delta:   kcal -2.8% | P +4.4% | CHO +2.5% | F +1.6% | Fibre -10.0%

================================================================================

✅ Plan generated successfully
```

---

### Output Modes

Show realistic version (respects personal limits):
```bash
python3 scripts/cli.py plan rest --mode realistic
```

Show unconstrained version (better macro accuracy):
```bash
python3 scripts/cli.py plan rest --mode unconstrained
```

---

### JSON Export

Export plan as JSON:
```bash
python3 scripts/cli.py plan rest --json > plans/rest.json
```

Generate all profiles and save as JSON:
```bash
for profile in rest easy_run qualita tempo lungo forza pizza_day domenica; do
  python3 scripts/cli.py plan $profile --json > plans/${profile}.json
done
```

---

### CI/CD Integration

```bash
#!/bin/bash
# Generate all plans and verify they succeed

PROFILES="rest easy_run qualita tempo lungo forza pizza_day domenica"
FAILED=0

for profile in $PROFILES; do
  echo "Generating plan for $profile..."
  python3 scripts/cli.py plan $profile --json > /dev/null 2>&1

  if [ $? -ne 0 ]; then
    echo "❌ FAIL: $profile"
    FAILED=$((FAILED+1))
  else
    echo "✅ OK: $profile"
  fi
done

if [ $FAILED -gt 0 ]; then
  echo ""
  echo "❌ $FAILED plan(s) failed"
  exit 1
else
  echo ""
  echo "✅ All plans generated successfully"
  exit 0
fi
```

---

## Data Validation

The CLI automatically validates data files before generating plans. Validation checks:

- **Structural integrity** - JSON schema compliance
- **Cross-references** - ID consistency across files
- **Percentage totals** - Distribution percentages = 100%
- **Personal limits** - meal_max_qty_g ≤ max_qty_g
- **Food groups** - All food_db_ids referenced exist in FOOD_DB

If validation fails, the CLI will:
1. Print first 10 errors
2. Show actionable error message
3. Exit with code 1

**Example validation error:**
```
❌ DATA VALIDATION FAILED
================================================================================
  1. PERSONAL_LIMITS: formaggio_spalmabile_light: meal_max_qty_g 100 > max_qty_g 50
  2. FOOD_GROUPS: Unknown food_db_id: ragu_di_vitello_40_vitello_60_passata (not in FOOD_DB)
  ... and 8 more errors
================================================================================

❌ Fix data errors before running plan.
   Run: python3 scripts/data_validator.py data
```

**To fix validation errors:**
```bash
# Run data validator to see all errors
python3 scripts/data_validator.py data

# Fix errors in data/*.json files

# Re-run CLI
python3 scripts/cli.py plan rest
```

---

## Error Handling

The CLI provides clear, actionable error messages for common issues.

### Invalid Profile

```bash
python3 scripts/cli.py plan invalid_profile
```

**Output:**
```
❌ CONFIGURATION ERROR: Profile 'invalid_profile' not found.
Available profiles: rest, easy_run, qualita, tempo, lungo, forza, pizza_day, domenica
```

### Missing Distribution

If a day profile references a non-existent distribution:

```
❌ CONFIGURATION ERROR: Distribution 'missing_dist' not found in MEAL_DISTRIBUTION.json
```

### Runtime Errors

If plan building fails unexpectedly:

```
❌ RUNTIME ERROR: Plan building failed: [error message]
Use --debug for detailed stacktrace
```

With `--debug`:
```bash
python3 scripts/cli.py plan rest --debug
```

Shows full Python stacktrace for debugging.

---

## Troubleshooting

### "Data validation failed"

**Cause:** Data files have structural errors or inconsistencies.

**Solution:**
```bash
# Run validator to see all errors
python3 scripts/data_validator.py data

# Fix errors in data/*.json

# Verify fix
python3 scripts/data_validator.py data
```

### "No valid foods available for meal"

**Cause:** None of the curated foods exist in FOOD_DB.

**Solution:**
- Check FOOD_DB.json contains required foods
- Verify food_db_ids match exactly (case-sensitive)
- Ensure FOOD_GROUPS.json maps all foods

### "Plan building failed"

**Cause:** Meal balancer could not find feasible solution.

**Solution:**
- Check target macros are reachable with allowed foods
- Verify personal limits are not too restrictive
- Try with `--debug` to see detailed error

---

## Advanced Usage

### Custom Food Lists

The CLI uses curated food lists optimized for each meal type. To customize:

1. Edit `scripts/cli.py`
2. Modify `base_foods` dict in `build_plan()` function
3. Restart CLI

**Example:**
```python
base_foods = {
    'breakfast': [
        'fette_biscottate',
        'yogurt_greco_0',
        'mandorle',
        'marmellata',
        'mela',
        'caffe_espresso'
    ],
    'snack': [
        'pane_integrale',
        'yogurt_greco_0',
        'mela'
    ],
    'main_meal': [
        'pasta_secca_di_semola',
        'pollo_petto_cotto_in_padella',
        'olio_evo',
        'zucchine_crude',
        'passata_di_pomodoro',
        'mela'
    ]
}
```

### Batch Processing

Generate all plans and analyze:
```bash
#!/bin/bash
# Generate all plans and extract daily totals

for profile in rest easy_run qualita tempo lungo forza pizza_day domenica; do
  python3 scripts/cli.py plan $profile --json | \
    jq -r '.plan.actual_daily_totals | "\(.kcal) kcal, \(.P)g P, \(.CHO)g CHO, \(.F)g F"' | \
    sed "s/^/$profile: /"
done
```

**Output:**
```
rest: 2138 kcal, 146.2g P, 225.5g CHO, 71.1g F
easy_run: 2400 kcal, 150.0g P, 280.0g CHO, 70.0g F
...
```

---

## FAQ

### Q: Can I skip data validation for testing?

**A:** Yes, use the undocumented `--skip-validation` flag (for testing only):
```bash
python3 scripts/cli.py plan rest --skip-validation
```

⚠️ **Warning:** Only use this for testing with imperfect data. Production usage should always validate.

### Q: How do I add a new day profile?

**A:**
1. Add profile to `data/DAY_PROFILES.json`
2. Add meal distribution to `data/MEAL_DISTRIBUTION.json` (or reuse existing)
3. Run validator to verify structure
4. Generate plan: `python3 scripts/cli.py plan <new_profile>`

### Q: Can I modify meal templates?

**A:**
Yes, edit `data/MEAL_TEMPLATES.json`:
- `required_groups` - Foods that must be included
- `forbidden_groups` - Foods that cannot be included
- `forbidden_food_ids` - Specific foods to exclude
- `max_items` - Maximum number of items in meal
- `max_per_group` - Maximum items per food group

### Q: What's the difference between realistic and unconstrained?

**A:**
- **Realistic** - Respects personal limits (max_qty_g, meal_max_qty_g)
- **Unconstrained** - Ignores personal limits for better macro accuracy
- **Recommended** - Chooses realistic if it meets targets well enough, otherwise unconstrained

---

## Technical Notes

### Data Files Required

The CLI requires these 10 JSON files in `data/`:

1. `FOOD_DB.json` - Nutritional database (49 foods)
2. `LARN_PORTIONS.json` - LARN reference portions
3. `OPERATIVE_PORTIONS.json` - Operative portion sizes
4. `FOOD_DB_TO_LARN_MAPPING.json` - Maps food_db_id to LARN portions
5. `PERSONAL_LIMITS.json` - Personal quantity limits per food
6. `DAY_PROFILES.json` - Day profiles (rest, training, etc.)
7. `MEAL_DISTRIBUTION.json` - Meal slot distributions
8. `FOOD_GROUPS.json` - Food group assignments
9. `MEAL_TEMPLATES.json` - Meal structure rules
10. `REALISM_RULES.json` - Realism constraints (volume penalties, etc.)

### Constraint Layers

The meal balancer applies constraints in layers:

1. **Template validation** (hard) - Required/forbidden groups, max items
2. **Personal limits** (soft) - Realistic mode respects limits
3. **Volume penalty** (soft) - Penalizes excessive vegetable volume
4. **Protein floor** (hard) - Minimum protein per meal slot
5. **Must include** (hard) - Required foods with qty > 0

### Performance

- Validation: ~1s for 10 files
- Plan generation: ~2-5s per profile (5 meals)
- JSON export: Same as formatted output + serialization (~100ms)

---

## Support

For issues, bugs, or feature requests:
- Run with `--debug` to see detailed errors
- Check `docs/V2_FREEZE_DECLARATION.md` for architecture reference
- Review test suite: `tests/test_cli.py`

---

**Version**: 2.0
**Status**: FROZEN - No new features, only bug fixes
**Last Updated**: 2026-02-12
