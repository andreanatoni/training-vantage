#!/usr/bin/env python3
"""
Upgrade non distruttivo di data/FOOD_DB_TO_LARN_MAPPING.json con campi audit.
"""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAPPING_FILE = ROOT / "data" / "FOOD_DB_TO_LARN_MAPPING.json"


def upgrade():
    data = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    meta = data.setdefault("meta", {})
    meta["version"] = "v2.1"
    meta["updated_at"] = datetime.now().isoformat()
    meta["audit_fields"] = [
        "review_status",
        "mapping_confidence",
        "mapping_source",
        "last_reviewed_at",
    ]

    updated = 0
    for row in data.get("mapping", []):
        has_any_mapping = row.get("larn_portion_id") is not None or row.get("operational_portion_id") is not None
        if "review_status" not in row:
            row["review_status"] = "mapped" if has_any_mapping else "pending_review"
            updated += 1
        if "mapping_confidence" not in row:
            row["mapping_confidence"] = 1.0 if has_any_mapping else 0.0
            updated += 1
        if "mapping_source" not in row:
            row["mapping_source"] = "manual" if has_any_mapping else "none"
            updated += 1
        if "last_reviewed_at" not in row:
            row["last_reviewed_at"] = None
            updated += 1

    MAPPING_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data, updated


if __name__ == "__main__":
    data, updated_fields = upgrade()
    print(f"[OK] Upgrade completato: {MAPPING_FILE}")
    print(f"  entries: {len(data.get('mapping', []))}")
    print(f"  fields_initialized: {updated_fields}")
