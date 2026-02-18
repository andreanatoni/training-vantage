#!/usr/bin/env python3
"""
Pulisce data/PORTION_STANDARDS.json:
- normalizza maiuscole/minuscole su campi testuali
- rimuove marker nota appesi alle parole (es. "derivati2")
- ricompone parole spezzate da OCR/impaginazione (es. "moz- zarella")
- normalizza spazi e punteggiatura base
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
PORTIONS_FILE = ROOT / "data" / "PORTION_STANDARDS.json"


def clean_spaces(text):
    text = text.replace("\u00a0", " ")
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)  # moz- zarella -> mozzarella
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,;:.])", r"\1", text)
    return text.strip()


def remove_footnote_markers(text):
    # Rimuove cifre appese a parole: "derivati2" -> "derivati"
    text = re.sub(r"([A-Za-zÀ-ÿ])\d+(?=\b)", r"\1", text)
    # Pulisce eventuali marcatori residui tipo "^2" o "2)" dopo parole
    text = re.sub(r"\^?\d+(?=[)\]])", "", text)
    return text


def sentence_case_italian(text):
    if not text:
        return text
    lowered = text.lower()
    # Mantieni mL standard
    lowered = re.sub(r"\bml\b", "mL", lowered)
    lowered = re.sub(r"\bcc\b", "cc", lowered)
    for idx, char in enumerate(lowered):
        if char.isalpha():
            return lowered[:idx] + char.upper() + lowered[idx + 1 :]
    return lowered


def normalize_portion_units(text):
    text = re.sub(r"(\d)\s*ML\b", r"\1 mL", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d)\s*G\b", r"\1 g", text, flags=re.IGNORECASE)
    return text


def clean_text(text, apply_sentence_case=True):
    if text is None:
        return None
    text = str(text)
    text = clean_spaces(text)
    text = remove_footnote_markers(text)
    text = clean_spaces(text)
    if apply_sentence_case:
        text = sentence_case_italian(text)
    return text


def clean_portion_file():
    payload = json.loads(PORTIONS_FILE.read_text(encoding="utf-8"))

    for item in payload.get("table_1_definitions", []):
        item["term"] = clean_text(item.get("term"))
        item["description"] = clean_text(item.get("description"))
        item["bullets"] = [clean_text(x) for x in item.get("bullets", [])]

    for item in payload.get("table_2_standard_portions", []):
        item["group"] = clean_text(item.get("group"))
        item["food"] = clean_text(item.get("food"))
        item["portion_standard"] = normalize_portion_units(
            clean_text(item.get("portion_standard"), apply_sentence_case=False)
        )
        item["practical_unit"] = clean_text(item.get("practical_unit"))

    for item in payload.get("table_3_raw_to_cooked", []):
        item["group"] = clean_text(item.get("group"))
        item["cooking_method"] = clean_text(item.get("cooking_method"))
        item["food"] = clean_text(item.get("food"))

    for item in payload.get("table_4_pediatric_portions", []):
        item["group"] = clean_text(item.get("group"))
        item["food_type"] = clean_text(item.get("food_type"))
        item["portion_standard"] = normalize_portion_units(
            clean_text(item.get("portion_standard"), apply_sentence_case=False)
        )

    for item in payload.get("table_5_household_volumes_ml", []):
        item["container"] = clean_text(item.get("container"))

    for item in payload.get("table_6_spoon_weights_g", []):
        item["item"] = clean_text(item.get("item"))
        item["level"] = clean_text(item.get("level"))

    PORTIONS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return payload


def main():
    payload = clean_portion_file()
    print(f"[OK] Pulizia completata: {PORTIONS_FILE}")
    print(
        f"rows t2={len(payload.get('table_2_standard_portions', []))} "
        f"t3={len(payload.get('table_3_raw_to_cooked', []))} "
        f"t4={len(payload.get('table_4_pediatric_portions', []))}"
    )


if __name__ == "__main__":
    main()
