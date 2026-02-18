#!/usr/bin/env python3
"""
Upgrade non distruttivo di data/OPERATIVE_PORTIONS.json a v2.

Mantiene i campi legacy e aggiunge:
- canonical_id
- item_label
- practical_tokens
- source
"""

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OPER_FILE = ROOT / "data" / "OPERATIVE_PORTIONS.json"


def parse_practical_token(raw):
    token = {"raw": raw}
    text = raw.strip()

    normalized = text.replace("½", "1/2").replace("¼", "1/4").replace("¾", "3/4")
    qty_match = re.match(r"^([0-9]+(?:-[0-9]+)?(?:\s*e\s*[0-9]+/[0-9]+|/[0-9]+)?)\s+(.+)$", normalized, re.IGNORECASE)
    if qty_match:
        token["quantity_text"] = qty_match.group(1).strip()
        rest = qty_match.group(2).strip()
    else:
        frac_match = re.match(r"^(1/2|1/4|3/4)\s+(.+)$", normalized, re.IGNORECASE)
        if frac_match:
            token["quantity_text"] = frac_match.group(1)
            rest = frac_match.group(2).strip()
        else:
            token["quantity_text"] = None
            rest = text

    unit_hints = [
        "cucchiaio",
        "cucchiaino",
        "piatto",
        "scodella",
        "pezzetto",
        "grattugiata",
    ]
    rest_l = rest.lower()
    token["unit_hint"] = next((u for u in unit_hints if u in rest_l), None)
    token["item_hint"] = rest
    return token


def upgrade():
    data = json.loads(OPER_FILE.read_text(encoding="utf-8"))

    meta = data.setdefault("meta", {})
    meta["version"] = "v2"
    meta["compatibility"] = {
        "legacy_fields_preserved": [
            "id",
            "group",
            "item",
            "standard",
            "practical",
            "allowed_multipliers",
            "notes",
            "max_qty",
        ]
    }
    meta["updated_at"] = datetime.now().isoformat()
    meta["source_of_truth"] = "Curated operational fallback portions"

    for idx, portion in enumerate(data.get("portions", []), 1):
        portion["canonical_id"] = portion["id"]
        portion["item_label"] = portion["item"]
        practical = portion.get("practical", [])
        portion["practical_tokens"] = [parse_practical_token(x) for x in practical]
        portion["source"] = {
            "type": "operational",
            "origin": "manual_curation",
            "row_index": idx,
        }

        # Normalize numeric types in standard/max_qty
        if "standard" in portion:
            portion["standard"]["qty"] = float(portion["standard"]["qty"])
        if "max_qty" in portion:
            portion["max_qty"]["qty"] = float(portion["max_qty"]["qty"])

    OPER_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    result = upgrade()
    print(f"[OK] Upgrade completato: {OPER_FILE}")
    print(f"  portions: {len(result.get('portions', []))}")
