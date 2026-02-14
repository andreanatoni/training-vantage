#!/usr/bin/env python3
"""
Rigenera data/LARN_PORTIONS.json allineato strettamente a
data/PORTION_STANDARDS.json -> table_2_standard_portions.
"""

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
PORTIONS_FILE = ROOT / "data" / "PORTION_STANDARDS.json"
LARN_FILE = ROOT / "data" / "LARN_PORTIONS.json"


def make_slug(text):
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def parse_portion_standard(text):
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(mL|g)", text, re.IGNORECASE)
    if not match:
        raise ValueError(f"Formato porzione non riconosciuto: {text}")
    qty = float(match.group(1).replace(",", "."))
    unit = "mL" if match.group(2).lower() == "ml" else "g"
    return qty, unit


def split_practical(text):
    if not text:
        return []
    parts = re.split(r"[;,]", text)
    return [p.strip() for p in parts if p and p.strip()]


def parse_practical_token(raw):
    token = {"raw": raw}
    text = raw.strip()

    # Normalizza alcune frazioni comuni solo per parsing quantità
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
        "bicchiere",
        "tazza",
        "vasetto",
        "fetta",
        "fettine",
        "cucchiaio",
        "cucchiaini",
        "cucchiaino",
        "pezzo",
        "pezzi",
        "frutto",
        "frutti",
        "scatola",
        "bottiglia",
        "lattina",
        "piatto",
        "scodella",
    ]
    rest_l = rest.lower()
    token["unit_hint"] = next((u for u in unit_hints if u in rest_l), None)
    token["item_hint"] = rest
    return token


def rebuild():
    payload = json.loads(PORTIONS_FILE.read_text(encoding="utf-8"))
    rows = payload["table_2_standard_portions"]

    portions = []
    used_ids = set()
    for idx, row in enumerate(rows, 1):
        qty, unit = parse_portion_standard(row["portion_standard"])
        base_id = make_slug(row["food"])
        item_id = base_id
        n = 2
        while item_id in used_ids:
            item_id = f"{base_id}_{n}"
            n += 1
        used_ids.add(item_id)
        practical = split_practical(row.get("practical_unit"))
        page = 16 if idx <= 20 else 17

        portions.append(
            {
                "id": item_id,
                "canonical_id": item_id,
                "group": make_slug(row["group"]).upper(),
                "item_label": row["food"],
                "item": row["food"],
                "standard": {"qty": qty, "unit": unit},
                "practical": practical,
                "practical_tokens": [parse_practical_token(p) for p in practical],
                "source": {
                    "table": 2,
                    "page": page,
                    "row_index_in_table2": idx,
                },
            }
        )

    out = {
        "meta": {
            "name": "LARN_PORTIONS",
            "source_of_truth": "PORTION_STANDARDS.json (table_2_standard_portions)",
            "units": ["g", "mL"],
            "version": "v3",
            "rules": {
                "strict_alignment_with_table_2": True,
                "quantities_are_multiples_of_portion": True,
                "food_db_is_only_nutrition_source": True,
            },
            "compatibility": {
                "legacy_fields_preserved": ["id", "group", "item", "standard", "practical"]
            },
            "generated_at": datetime.now().isoformat(),
            "generated_count": len(portions),
        },
        "portions": portions,
    }

    LARN_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    result = rebuild()
    print(f"[OK] Rigenerato {LARN_FILE}")
    print(f"  portions: {len(result['portions'])}")
