#!/usr/bin/env python3
"""
/food add "<nome>" <riferimento> <kcal> <proteine> <cho> <grassi> <fibre> [fonte]

Aggiunge una riga alla tabella in knowledge/food-db.md.
"""

import json
import re
import sys
import urllib.request
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime
from html import unescape
from pathlib import Path
from sync_food_db import sync_food_db_files

ROOT = Path(__file__).parent.parent
FOOD_DB_FILE = ROOT / "knowledge" / "food-db.md"
FOOD_DB_JSON_FILE = ROOT / "data" / "FOOD_DB.json"
FOOD_DB_MAPPING_FILE = ROOT / "data" / "FOOD_DB_TO_LARN_MAPPING.json"
CHANGELOG_FILE = ROOT / "data" / "changelog.json"


class SimilarFoodError(ValueError):
    def __init__(self, message, proposed, matches):
        super().__init__(message)
        self.proposed = proposed
        self.matches = matches


def print_usage():
    print('Usage (manuale): food_add.py [--replace "<nome_o_id>"] "<nome>" <riferimento> <kcal> <proteine> <cho> <grassi> <fibre> [fonte]')
    print('Esempio: food_add.py "Gallette riso" "100 g" 387 7.4 81.0 2.8 3.5 CREA')
    print("Usage (CREA URL): food_add.py [--replace \"<nome_o_id>\"] <url_crea>")
    print("Esempio: food_add.py https://www.alimentinutrizione.it/tabelle-nutrizionali/150030")
    print("Esempio replace: food_add.py --replace \"Yogurt greco 0%\" https://www.alimentinutrizione.it/tabelle-nutrizionali/150030")


def is_affirmative(answer):
    return answer.strip().lower() in {"y", "yes", "s", "si"}


def parse_float(value, field_name):
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{field_name} deve essere numerico: {value}")


def to_float(value):
    text = str(value).strip().lower()
    if text in {"tr", "trace", "-", ""}:
        return 0.0

    # Estrai il primo numero utile (es. "44", "0,8", " 10.2 ")
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)", text)
    if match:
        return float(match.group(1).replace(",", "."))

    raise ValueError(f"valore non numerico: {value}")


def normalize_text(text):
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_crea_text(text):
    # 1) Nome alimento: prova title e poi H1
    title_match = re.search(r"<title[^>]*>\s*([^<]+)\s*</title>", text, re.IGNORECASE | re.DOTALL)
    if title_match:
        raw_title = normalize_text(title_match.group(1))
        food_name = raw_title.split(" - ", 1)[-1].strip()
    else:
        h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", text, re.IGNORECASE | re.DOTALL)
        if not h1_matches:
            raise ValueError("Nome alimento non trovato nel contenuto CREA")
        food_name = normalize_text(h1_matches[-1]).strip(" -:")

    reference = "100 g"
    source = "CREA"

    # 2) Valori nutrizionali: righe tabella CREA (tr.corponutriente)
    nutrient_rows = re.findall(r"<tr class=\"corponutriente\">(.*?)</tr>", text, re.IGNORECASE | re.DOTALL)
    row_values = {}
    for row in nutrient_rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.IGNORECASE | re.DOTALL)
        if len(cells) < 3:
            continue
        label = normalize_text(cells[0])
        raw_value = normalize_text(cells[2]).replace("\xa0", "").strip()
        if raw_value:
            row_values[label] = raw_value

    def from_row(labels, field):
        for label in labels:
            if label in row_values:
                return to_float(row_values[label])
        raise ValueError(f"Campo non trovato nel contenuto CREA: {field}")

    kcal = from_row(["Energia (kcal)"], "kcal")
    protein = from_row(["Proteine (g)"], "proteine")
    cho = from_row(
        ["Carboidrati disponibili (g)", "Carboidrati solubili (g)", "Carboidrati (g)"],
        "carboidrati",
    )
    fat = from_row(["Lipidi (g)"], "grassi")
    try:
        fiber = from_row(["Fibra totale (g)"], "fibre")
    except ValueError:
        fiber = 0.0

    return {
        "food_name": food_name,
        "reference": reference,
        "kcal": kcal,
        "protein": protein,
        "cho": cho,
        "fat": fat,
        "fiber": fiber,
        "source": source,
    }


def parse_crea_url(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        html = response.read().decode("utf-8", errors="ignore")
    data = parse_crea_text(html)
    data["source"] = "CREA"
    data["source_url"] = url
    return data


def build_source_metadata(source, source_url=None):
    source_type = source.strip().split("(", 1)[0].strip()
    metadata = {
        "data_source": source,
        "source_type": source_type,
        "last_verified_at": datetime.now().strftime("%Y-%m-%d"),
    }
    if source_url:
        metadata["source_url"] = source_url
    return metadata


def make_food_id(food_name):
    normalized = unicodedata.normalize("NFKD", food_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9]+", "_", ascii_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("_")
    return ascii_name


def normalize_for_similarity(food_name):
    normalized = unicodedata.normalize("NFKD", food_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9]+", " ", ascii_name)
    ascii_name = re.sub(r"\s+", " ", ascii_name).strip()
    return ascii_name


def find_similar_food_names(food_name, existing_names, threshold=0.82):
    needle = normalize_for_similarity(food_name)
    if not needle:
        return []

    matches = []
    for existing in existing_names:
        candidate = normalize_for_similarity(existing)
        if not candidate:
            continue

        ratio = SequenceMatcher(None, needle, candidate).ratio()
        contains = needle in candidate or candidate in needle
        if ratio >= threshold or contains:
            matches.append((existing, ratio))

    matches.sort(key=lambda item: item[1], reverse=True)
    return matches


def parse_reference(reference):
    match = re.match(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(g|ml|mL)\s*(.*)$", reference, re.IGNORECASE)
    if not match:
        raise ValueError(f"Riferimento non valido: '{reference}'. Usa ad esempio '100 g' o '50 ml'.")

    amount = to_float(match.group(1))
    unit_raw = match.group(2)
    remainder = match.group(3).strip()

    unit = "mL" if unit_raw.lower() == "ml" else "g"
    payload = {
        "amount": amount,
        "unit": unit,
        "label": reference,
    }
    if remainder:
        payload["note"] = remainder
    return payload


def get_entry_by_name(foods, food_name):
    for item in foods:
        if item.get("name") == food_name:
            return item
    return None


def extract_nutrients(entry):
    nutrients = entry.get("nutrients_per_reference", {})
    return {
        "kcal": float(nutrients.get("kcal", 0.0)),
        "P": float(nutrients.get("P", 0.0)),
        "CHO": float(nutrients.get("CHO", 0.0)),
        "F": float(nutrients.get("F", 0.0)),
        "Fibre": float(nutrients.get("Fibre", 0.0)),
    }


def format_similarity_table(proposed, existing_entries):
    header = (
        "| Tipo | Nome | Score | Rif. | kcal | P | CHO | F | Fibre |\n"
        "|---|---|---:|---|---:|---:|---:|---:|---:|"
    )
    rows = []

    rows.append(
        "| PROPOSTO | {name} | - | {ref} | {kcal:.1f} | {P:.1f} | {CHO:.1f} | {F:.1f} | {Fibre:.1f} |".format(
            name=proposed["food_name"],
            ref=proposed["reference"],
            kcal=proposed["kcal"],
            P=proposed["protein"],
            CHO=proposed["cho"],
            F=proposed["fat"],
            Fibre=proposed["fiber"],
        )
    )

    for entry in existing_entries:
        n = extract_nutrients(entry["food"])
        rows.append(
            "| MATCH | {name} | {score:.2f} | {ref} | {kcal:.1f} | {P:.1f} | {CHO:.1f} | {F:.1f} | {Fibre:.1f} |".format(
                name=entry["food"]["name"],
                score=entry["score"],
                ref=entry["food"]["reference"]["label"],
                kcal=n["kcal"],
                P=n["P"],
                CHO=n["CHO"],
                F=n["F"],
                Fibre=n["Fibre"],
            )
        )

    return "\n".join([header] + rows)


def find_food_by_target(foods, target):
    for item in foods:
        if item.get("id") == target:
            return item
    for item in foods:
        if item.get("name") == target:
            return item
    return None


def add_food_everywhere(food_name, reference, kcal, protein, cho, fat, fiber, source, replace_target=None, source_url=None):
    # Load all files first (no writes yet)
    food_db = json.loads(FOOD_DB_JSON_FILE.read_text(encoding="utf-8"))
    mapping_db = json.loads(FOOD_DB_MAPPING_FILE.read_text(encoding="utf-8"))

    food_id = make_food_id(food_name)
    if not food_id:
        raise ValueError(f"Impossibile generare id valido da nome alimento: {food_name}")

    foods = food_db.get("foods", [])
    existing_ids = {item["id"] for item in foods}
    existing_names = {item["name"] for item in foods}

    reference_payload = parse_reference(reference)
    nutrients_payload = {
        "kcal": float(kcal),
        "P": float(protein),
        "CHO": float(cho),
        "F": float(fat),
        "Fibre": float(fiber),
    }

    if replace_target:
        current = find_food_by_target(foods, replace_target)
        if current is None:
            raise ValueError(f"Target replace non trovato (nome o id): {replace_target}")

        current_id = current["id"]
        current_name = current["name"]

        # Se rinominiamo, non deve esistere un altro alimento con lo stesso nome.
        if food_name != current_name and food_name in existing_names:
            raise ValueError(f"Nome gia presente in FOOD_DB.json: {food_name}")

        # Replace FOOD_DB entry preserving id
        current["name"] = food_name
        current["reference"] = reference_payload
        current["nutrients_per_reference"] = nutrients_payload
        current.update(build_source_metadata(source, source_url=source_url))

        # Replace mapping display name for same id
        updated_mapping = False
        for item in mapping_db.get("mapping", []):
            if item.get("food_db_id") == current_id:
                item["food_db_name"] = food_name
                updated_mapping = True
                break
        if not updated_mapping:
            raise ValueError(f"Mapping non trovato per id: {current_id}")

        FOOD_DB_JSON_FILE.write_text(json.dumps(food_db, indent=2, ensure_ascii=False), encoding="utf-8")
        FOOD_DB_MAPPING_FILE.write_text(
            json.dumps(mapping_db, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        sync_food_db_files(write=True)
        return {"food_id": current_id, "action": "replaced", "replaced_name": current_name}

    if food_id in existing_ids:
        raise ValueError(f"ID gia presente in FOOD_DB.json: {food_id}")
    if food_name in existing_names:
        raise ValueError(f"Nome gia presente in FOOD_DB.json: {food_name}")

    similar = find_similar_food_names(food_name, existing_names)
    if similar:
        matched_entries = []
        for name, score in similar[:5]:
            existing = get_entry_by_name(foods, name)
            if existing:
                matched_entries.append({"food": existing, "score": score})

        raise SimilarFoodError(
            "Trovati alimenti con nome simile. Verifica tabella confronto.",
            proposed={
                "food_name": food_name,
                "reference": reference,
                "kcal": float(kcal),
                "protein": float(protein),
                "cho": float(cho),
                "fat": float(fat),
                "fiber": float(fiber),
            },
            matches=matched_entries,
        )

    existing_mapping_ids = {item["food_db_id"] for item in mapping_db.get("mapping", [])}
    if food_id in existing_mapping_ids:
        raise ValueError(f"food_db_id gia presente in FOOD_DB_TO_LARN_MAPPING.json: {food_id}")

    food_entry = {
        "id": food_id,
        "name": food_name,
        "reference": reference_payload,
        "nutrients_per_reference": nutrients_payload,
    }
    food_entry.update(build_source_metadata(source, source_url=source_url))

    mapping_entry = {
        "food_db_id": food_id,
        "food_db_name": food_name,
        "larn_portion_id": None,
        "operational_portion_id": None,
        "note": "Auto-added da tv food add. Assegnare larn_portion_id o operational_portion_id.",
    }

    food_db.setdefault("foods", []).append(food_entry)
    mapping_db.setdefault("mapping", []).append(mapping_entry)

    # Write JSON first, markdown is generated from JSON via sync
    FOOD_DB_JSON_FILE.write_text(json.dumps(food_db, indent=2, ensure_ascii=False), encoding="utf-8")
    FOOD_DB_MAPPING_FILE.write_text(
        json.dumps(mapping_db, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    sync_food_db_files(write=True)

    return {"food_id": food_id, "action": "added"}


def update_changelog(details):
    data = json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))
    data.setdefault("entries", []).append(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "food add",
            "details": details,
        }
    )
    CHANGELOG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    args = sys.argv[1:]
    replace_target = None
    if len(args) >= 2 and args[0] == "--replace":
        replace_target = args[1].strip()
        args = args[2:]

    if len(args) == 1 and args[0].startswith(("http://", "https://")):
        parsed = parse_crea_url(args[0].strip())
        food_name = parsed["food_name"]
        reference = parsed["reference"]
        kcal = parsed["kcal"]
        protein = parsed["protein"]
        cho = parsed["cho"]
        fat = parsed["fat"]
        fiber = parsed["fiber"]
        source = parsed["source"]
        source_url = parsed.get("source_url")
    else:
        if len(args) < 7:
            print_usage()
            sys.exit(1)

        food_name = args[0].strip()
        reference = args[1].strip()
        kcal = parse_float(args[2], "kcal")
        protein = parse_float(args[3], "proteine")
        cho = parse_float(args[4], "cho")
        fat = parse_float(args[5], "grassi")
        fiber = parse_float(args[6], "fibre")
        source = args[7].strip() if len(args) > 7 else "manual_input"
        source_url = None

    try:
        result = add_food_everywhere(
            food_name,
            reference,
            kcal,
            protein,
            cho,
            fat,
        fiber,
        source,
        replace_target=replace_target,
        source_url=source_url,
    )
    except SimilarFoodError as exc:
        print(f"Errore: {exc}")
        print()
        print(format_similarity_table(exc.proposed, exc.matches))
        print()
        print("Azione consigliata:")
        print("- Se i valori coincidono: skippa l'inserimento.")

        best_match_name = exc.matches[0]["food"]["name"] if exc.matches else None
        if best_match_name:
            print(f"- Match principale: {best_match_name}")
            if sys.stdin.isatty():
                answer = input(f"Vuoi sostituire '{best_match_name}' con il nuovo alimento? [y/N]: ")
                if is_affirmative(answer):
                    result = add_food_everywhere(
                        food_name,
                        reference,
                        kcal,
                        protein,
                        cho,
                        fat,
                        fiber,
                        source,
                        replace_target=best_match_name,
                    )
                else:
                    print("Inserimento annullato.")
                    sys.exit(1)
            else:
                print(f"- Per sostituire subito: tv food add --replace \"{best_match_name}\" <stessi_argomenti>")
                sys.exit(1)
        else:
            print("- Se i valori differiscono: inserisci con nome piu specifico per distinguere l'alimento.")
            sys.exit(1)

    food_id = result["food_id"]
    update_changelog(
        {
            "mode": result["action"],
            "food_id": food_id,
            "food_name": food_name,
            "reference": reference,
            "kcal": kcal,
            "protein": protein,
            "cho": cho,
            "fat": fat,
            "fiber": fiber,
            "source": source,
            "source_url": source_url,
            "updated_files": [
                "knowledge/food-db.md",
                "data/FOOD_DB.json",
                "data/FOOD_DB_TO_LARN_MAPPING.json",
            ],
            "replace_target": replace_target,
            "replaced_name": result.get("replaced_name"),
        }
    )

    if result["action"] == "replaced":
        print(f"✓ Alimento sostituito: {result.get('replaced_name')} -> {food_name} ({food_id})")
    else:
        print(f"✓ Alimento aggiunto: {food_name} ({food_id})")
    print(f"  File aggiornati: {FOOD_DB_FILE}, {FOOD_DB_JSON_FILE}, {FOOD_DB_MAPPING_FILE}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Errore: {exc}")
        sys.exit(1)
