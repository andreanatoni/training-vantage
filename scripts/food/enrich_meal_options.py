#!/usr/bin/env python3
"""Archived helper.

The old hardcoded name->food_db_id enrichment flow does not scale for multi-user.
Use canonical flow:
1) data/food_mapped.md (food_db_id|larn_portion_id|display_name)
2) ./tv food import-mapped --strict-complete
3) meal_options with explicit food_db_id (or custom_recipe + recipe_id)
"""

raise SystemExit(
    "[ERR] Comando/script archiviato: enrich_meal_options.py\n"
    "Usa il bridge canonico FOOD_NAME_BRIDGE derivato da food_mapped.md e "
    "salva food_db_id direttamente nei meal_options."
)
