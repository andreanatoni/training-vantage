#!/usr/bin/env python3
"""
Estrae le tabelle principali da:
sources/Standard-Quantitativi-delle-Porzioni.pdf

Output:
- data/PORTION_STANDARDS.json
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber

from clean_portion_standards import clean_portion_file

ROOT = Path(__file__).parent.parent
PDF_FILE = ROOT / "sources" / "Standard-Quantitativi-delle-Porzioni.pdf"
OUTPUT_FILE = ROOT / "data" / "PORTION_STANDARDS.json"


def clean_cell(value):
    if value is None:
        return None
    text = str(value).replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def to_float(value):
    if value is None:
        return None
    text = str(value).strip().lower().replace(",", ".")
    if text in {"", "-", "tr"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def get_table(pdf, page_num):
    page = pdf.pages[page_num - 1]
    tables = page.extract_tables()
    if not tables:
        raise ValueError(f"Nessuna tabella trovata a pagina {page_num}")
    table = tables[0]
    return [[clean_cell(cell) for cell in row] for row in table]


def parse_table1(table):
    entries = []
    for row in table[1:]:
        term = row[0]
        description = row[1] if len(row) > 1 else None
        if not term or not description:
            continue
        bullets = [part.strip() for part in description.split("■") if part.strip()]
        entries.append({"term": term, "description": description, "bullets": bullets})
    return entries


def parse_table2(table16, table17):
    rows = table16[1:] + table17[1:]
    out = []
    current_group = None
    for row in rows:
        if not row or len(row) < 4:
            continue
        if row[0]:
            current_group = row[0]
        food = row[1]
        portion = row[2]
        practical = row[3]
        if not food:
            continue
        out.append(
            {
                "group": current_group,
                "food": food,
                "portion_standard": portion,
                "practical_unit": practical,
            }
        )
    return out


def parse_table3(table20, table21):
    rows = table20[2:] + table21[2:]
    out = []
    current_group = None
    current_method = None
    for row in rows:
        if not row or len(row) < 6:
            continue
        if row[0]:
            current_group = row[0]
        if row[1]:
            current_method = row[1]
        food = row[2]
        factor = row[3]
        raw = row[4]
        cooked = row[5]
        if not food:
            continue
        out.append(
            {
                "group": current_group,
                "cooking_method": current_method,
                "food": food,
                "conversion_factor": to_float(factor),
                "portion_raw_g": to_float(raw),
                "portion_cooked_g": to_float(cooked),
            }
        )
    return out


def parse_table4(table22):
    age_bands = ["1 anno", "2-3 anni", "4-6 anni", "7-10 anni", "11-14 anni", "15-17 anni"]
    rows = table22[2:]
    out = []
    current_group = None
    for row in rows:
        if not row or len(row) < 15:
            continue
        if row[0]:
            current_group = row[0]

        food_type = row[1]
        standard = row[2]
        if not food_type:
            continue

        ages = {}
        col = 3
        for band in age_bands:
            portion_value = row[col] if col < len(row) else None
            multiple_value = row[col + 1] if (col + 1) < len(row) else None
            ages[band] = {
                "portion_g_ml": to_float(portion_value),
                "multiple_of_standard": to_float(multiple_value),
            }
            col += 2

        out.append(
            {
                "group": current_group,
                "food_type": food_type,
                "portion_standard": standard,
                "age_portions": ages,
            }
        )
    return out


def parse_table5(table23):
    rows = table23[1:]
    out = []
    for row in rows:
        if not row or len(row) < 4:
            continue
        container = row[0]
        if not container:
            continue
        out.append(
            {
                "container": container,
                "small_ml": to_float(row[1]),
                "medium_ml": to_float(row[2]),
                "large_ml": to_float(row[3]),
            }
        )
    return out


def parse_table6(table24):
    rows = table24[1:]
    out = []
    current_item = None
    for row in rows:
        if not row or len(row) < 4:
            continue
        if row[0]:
            current_item = row[0]
        level = row[1]
        if not current_item or not level:
            continue
        out.append(
            {
                "item": current_item,
                "level": level,
                "tablespoon_g": to_float(row[2]),
                "teaspoon_g": to_float(row[3]),
            }
        )
    return out


def extract_portion_standards():
    with pdfplumber.open(PDF_FILE) as pdf:
        t1 = get_table(pdf, 15)
        t2a = get_table(pdf, 16)
        t2b = get_table(pdf, 17)
        t3a = get_table(pdf, 20)
        t3b = get_table(pdf, 21)
        t4 = get_table(pdf, 22)
        t5 = get_table(pdf, 23)
        t6 = get_table(pdf, 24)

    payload = {
        "meta": {
            "source_pdf": str(PDF_FILE.relative_to(ROOT)),
            "generated_at": datetime.now().isoformat(),
            "tables_extracted": [1, 2, 3, 4, 5, 6],
        },
        "table_1_definitions": parse_table1(t1),
        "table_2_standard_portions": parse_table2(t2a, t2b),
        "table_3_raw_to_cooked": parse_table3(t3a, t3b),
        "table_4_pediatric_portions": parse_table4(t4),
        "table_5_household_volumes_ml": parse_table5(t5),
        "table_6_spoon_weights_g": parse_table6(t6),
    }

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main():
    extract_portion_standards()
    payload = clean_portion_file()
    print(f"[OK] Estratto database porzioni: {OUTPUT_FILE}")
    print("[OK] Pulizia automatica applicata")
    print(f"  - table_1_definitions: {len(payload['table_1_definitions'])}")
    print(f"  - table_2_standard_portions: {len(payload['table_2_standard_portions'])}")
    print(f"  - table_3_raw_to_cooked: {len(payload['table_3_raw_to_cooked'])}")
    print(f"  - table_4_pediatric_portions: {len(payload['table_4_pediatric_portions'])}")
    print(f"  - table_5_household_volumes_ml: {len(payload['table_5_household_volumes_ml'])}")
    print(f"  - table_6_spoon_weights_g: {len(payload['table_6_spoon_weights_g'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Errore: {exc}")
        sys.exit(1)
