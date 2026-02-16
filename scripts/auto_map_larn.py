#!/usr/bin/env python3
"""Auto-map FOOD_DB items to LARN portions using deterministic rules."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

FOOD_DB_JSON = DATA_DIR / "FOOD_DB.json"
MAPPING_JSON = DATA_DIR / "FOOD_DB_TO_LARN_MAPPING.json"
LARN_JSON = DATA_DIR / "LARN_PORTIONS.json"
REPORT_JSON = DATA_DIR / "LARN_AUTOMAP_REPORT.json"
QUEUE_JSON = DATA_DIR / "LARN_MAPPING_REVIEW_QUEUE.json"


def normalize(text: str) -> str:
    txt = (text or "").lower()
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def has_any(text: str, terms):
    return any(t in text for t in terms)


def has_token(tokens, terms):
    pool = set(tokens)
    return any(t in pool for t in terms)


def suggest_larn(food_name: str, food_id: str):
    t = normalize(f"{food_name} {food_id}")
    tokens = t.split()
    starts_olio = t.startswith("olio ") or food_id.startswith("olio_")

    # High-confidence exact classes
    if "caffe espresso" in t or "caffe_espresso" in t:
        return "caffe_espresso", 1.0, "exact_caffe_espresso"
    if has_any(t, ["caffe", "orzo"]) and not has_any(t, ["gelato"]):
        return "caffe_orzo", 0.95, "coffee_family"
    if has_any(t, ["acqua", "water"]):
        return "acqua_di_rubinetto_o_imbottigliata", 0.98, "water_family"
    if has_token(tokens, ["vino", "wine"]) and "aceto" not in t:
        return "vino", 0.98, "wine_family"
    if has_token(tokens, ["birra", "beer"]):
        return "birra", 0.98, "beer_family"
    if has_any(t, ["whisky", "vodka", "brandy", "superalcol"]) or has_token(tokens, ["rum", "gin"]):
        return "superalcolici", 0.98, "spirits_family"

    # Dairy / eggs
    if has_any(t, ["yogurt", "yoghurt", "skyr", "kefir", "latti fermentati"]):
        return "yogurt_e_altri_latti_fermentati", 0.95, "fermented_dairy"
    if "latte" in t and not has_any(t, ["yogurt", "gelato"]):
        return "latte", 0.93, "milk_family"
    if has_any(t, ["uovo", "uova", "egg"]):
        return "uova", 0.95, "eggs_family"

    # Sweet condiments
    if "marmellata" in t:
        return "marmellata", 0.97, "jam_family"
    if has_any(t, ["zucchero", "miele", "caramell", "sciroppo"]):
        return "zucchero_miele_caramelle", 0.90, "sugar_honey_candy"

    # Sweet bakery products
    if has_any(t, ["biscott", "wafer", "waff", "brioche", "croissant", "cornetto", "merendin", "barretta", "torta", "plum cake", "ciambell", "muffin"]):
        return "prodotti_da_forno_dolci_brioche_croissant_cornetti_biscotti_merendine_barrette_ecc", 0.92, "sweet_bakery"

    # Sauces / ready condiments
    if has_any(t, ["sugo", "salsa", "pesto", "passata", "ragu", "ragu"]):
        return "sughi_pronti_arrabbiata_ragu_ecc", 0.92, "sauces_ready"

    # Fish before oils to avoid "sott'olio" false positives.
    if has_any(t, ["salmone", "tonno", "merluzzo", "orata", "branzino", "trota", "pesce", "polpo", "calam", "cozz", "gamber", "aragosta", "acciug", "aringa", "sgombro"]):
        if has_any(t, ["conserv", "sottolio", "sott olio", "sotto olio", "scatola", "in scatola"]):
            return "pesce_molluschi_crostacei_conservati", 0.92, "fish_seafood_conserved"
        return "pesce_molluschi_crostacei_freschi_surgelati", 0.90, "fish_seafood"

    # Fats
    if starts_olio:
        return "oli_extravergine_doliva_di_semi_di_mais_ecc", 0.93, "oils_family"
    if has_any(t, ["burro", "strutto", "lardo"]):
        return "burro_strutto_e_lardo", 0.95, "butter_lard"
    if has_any(t, ["arachidi", "nocciole", "mandorle", "pistacchi", "noci", "pinoli", "semi di"]):
        return "noci_nocciole_pistacchi_mandorle_semi_di_lino_semi_di_sesamo_semi_di_zucca_ecc", 0.90, "nuts_seeds"

    # Carbs
    if "pane" in t:
        return "pane", 0.93, "bread_family"
    if has_any(t, ["cracker", "grissini", "friselle", "taralli", "gallette", "fette biscottate"]):
        return "sostituti_del_pane_cracker_grissini_friselle_tarallini_gallette_ecc", 0.90, "bread_substitutes"
    if has_any(t, ["cereali per la colazione", "muesli", "corn flakes"]):
        return "cereali_per_la_colazione_e_fette_biscottate", 0.90, "breakfast_cereal"
    if has_any(t, ["pasta", "spaghett", "riso", "farro", "orzo perlato", "cous cous", "quinoa", "semola", "farina", "mais", "polenta", "tortellini", "gnocchi"]):
        return "pasta_cous_cous_riso_mais_farro_orzo_quinoa_farine_ecc", 0.90, "grains_starches"
    if has_any(t, ["patate", "tubero"]):
        return "patate_e_altri_tuberi", 0.93, "potatoes_tubers"

    # Protein foods
    if has_any(t, ["prosciutto", "salame", "bresaola", "mortadella", "coppa", "speck", "salsiccia", "insaccat"]):
        return "salumi", 0.95, "cold_cuts"
    if has_any(t, ["pancetta", "guanciale", "wurstel", "zampone"]):
        return "salumi", 0.93, "processed_meat"
    if has_any(t, ["mozzarella", "parmigiano", "grana", "pecorino", "feta", "gorgonzola", "cheddar", "fontina", "brie", "camembert", "formaggio"]):
        return "altri_formaggi_25_di_grassi", 0.88, "cheese_family"
    if has_any(t, ["pollo", "tacchino", "coniglio"]):
        return "carne_bianca_fresca_surgelata_pollo_tacchino_coniglio", 0.92, "white_meat"
    if has_any(t, ["manzo", "vitello", "bov", "suin", "maiale", "agnello", "equin", "fegato", "frattaglie", "carne"]):
        return "carne_rossa_fresca_surgelata_bovina_ovina_suina_equina", 0.86, "red_meat"

    # Produce
    if has_any(t, ["fagioli", "lenticchie", "ceci", "piselli", "legumi"]) and not has_any(t, ["fagiolin", "fagiolo_verde"]):
        return "legumi_secchi", 0.88, "legumes"
    if has_any(t, ["insalata", "lattuga", "rucola", "radicchio", "valeriana"]):
        return "insalate_a_foglia", 0.95, "leafy_salads"
    if has_any(t, ["zucchine", "carote", "spinaci", "broccoli", "melanzane", "pomodoro", "verdura", "ortaggi", "cavolo", "asparagi", "peperon", "sedano", "cipolla", "cicoria", "porri", "prezzemolo", "carciof", "fungh", "zucca", "cardi"]):
        return "verdure_e_ortaggi", 0.90, "vegetables"

    if has_any(t, ["succo", "spremuta", "nettare", "tisana", "te ", "the ", "bevanda"]) and not has_any(t, ["alcol", "vino", "birra"]):
        return "spremute_succhi_di_verdura_e_di_frutta_100_te_tisane_ed_altre_bibite_non_zuccherate_senza_zuccheri_aggiunti", 0.92, "juices_tea_tisane"

    if (
        has_any(t, ["mela", "banana", "pera", "ananas", "arancia", "fragol", "uva", "pesca", "prugna", "albicocc", "cilieg", "kiwi", "limone", "pompelmo", "melone"])
        and not has_any(t, ["succo", "spremuta", "nettare", "shake", "torta", "gelato"])
    ):
        return "frutta_fresca", 0.90, "fresh_fruit"
    if has_any(t, ["uvetta", "datter", "fichi secchi", "prugne secche", "frutta secca disidratata"]):
        return "frutta_secca_disidratata", 0.88, "dried_fruit"

    # Fallbacks
    if has_any(t, ["gelato"]):
        return "torte_gelati", 0.90, "dessert_family"
    if has_any(t, ["spez", "pepe", "zafferano", "zenzero", "wasabi", "aromi"]):
        return "oli_extravergine_doliva_di_semi_di_mais_ecc", 0.60, "spices_low_conf"

    return None, 0.0, "no_rule_match"


def run(threshold: float, apply: bool):
    food_db = json.loads(FOOD_DB_JSON.read_text(encoding="utf-8"))
    mapping_db = json.loads(MAPPING_JSON.read_text(encoding="utf-8"))
    larn = json.loads(LARN_JSON.read_text(encoding="utf-8"))
    valid_larn_ids = {p.get("id") for p in larn.get("portions", [])}

    foods = food_db.get("foods", [])
    mapping_entries = mapping_db.get("mapping", [])
    by_food_id = {m.get("food_db_id"): m for m in mapping_entries}

    applied = 0
    candidates = []
    skipped_already_mapped = 0

    for food in foods:
        fid = food.get("id")
        name = food.get("name", "")
        if not fid:
            continue
        entry = by_food_id.get(fid)
        if not entry:
            entry = {
                "food_db_id": fid,
                "food_db_name": name,
                "larn_portion_id": None,
                "operational_portion_id": None,
                "note": "Auto-created during LARN automap.",
                "review_status": "pending_review",
                "mapping_confidence": 0.0,
                "mapping_source": "none",
                "last_reviewed_at": None,
            }
            mapping_entries.append(entry)
            by_food_id[fid] = entry

        if entry.get("larn_portion_id") or entry.get("operational_portion_id"):
            skipped_already_mapped += 1
            continue

        larn_id, conf, reason = suggest_larn(name, fid)
        if larn_id and larn_id in valid_larn_ids and conf >= threshold:
            candidates.append(
                {
                    "food_db_id": fid,
                    "food_db_name": name,
                    "suggested_larn_portion_id": larn_id,
                    "confidence": conf,
                    "reason": reason,
                    "action": "auto_apply" if apply else "suggest_only",
                }
            )
            if apply:
                entry["larn_portion_id"] = larn_id
                entry["review_status"] = "reviewed"
                entry["mapping_confidence"] = round(conf, 3)
                entry["mapping_source"] = "auto_map_larn_rules"
                entry["last_reviewed_at"] = datetime.now().strftime("%Y-%m-%d")
                entry["note"] = f"Auto-mapped via rules ({reason})."
                applied += 1
        else:
            if larn_id and larn_id in valid_larn_ids:
                action = "review_queue"
            else:
                action = "no_match"
            candidates.append(
                {
                    "food_db_id": fid,
                    "food_db_name": name,
                    "suggested_larn_portion_id": larn_id,
                    "confidence": conf,
                    "reason": reason,
                    "action": action,
                }
            )

    if apply:
        # Dedup mapping by food_db_id
        seen = set()
        dedup = []
        for m in mapping_entries:
            k = m.get("food_db_id")
            if not k or k in seen:
                continue
            seen.add(k)
            dedup.append(m)
        mapping_db["mapping"] = dedup
        mapping_db.setdefault("meta", {})
        mapping_db["meta"]["generated_at"] = datetime.now().isoformat()
        MAPPING_JSON.write_text(json.dumps(mapping_db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review_queue = [c for c in candidates if c["action"] in {"review_queue", "no_match"}]
    review_queue.sort(key=lambda x: (x["action"], x["confidence"], x["food_db_name"]), reverse=True)
    QUEUE_JSON.write_text(json.dumps({"generated_at": datetime.now().isoformat(), "items": review_queue}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "generated_at": datetime.now().isoformat(),
        "threshold": threshold,
        "apply": apply,
        "foods_total": len(foods),
        "skipped_already_mapped": skipped_already_mapped,
        "auto_mapped_count": applied if apply else len([c for c in candidates if c["action"] == "suggest_only"]),
        "review_queue_count": len(review_queue),
        "preview_auto": [c for c in candidates if c["action"] in {"auto_apply", "suggest_only"}][:200],
        "preview_review_queue": review_queue[:200],
        "files": {
            "mapping": str(MAPPING_JSON.relative_to(ROOT)),
            "queue": str(QUEUE_JSON.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Auto-map LARN portions for FOOD_DB.")
    parser.add_argument("--threshold", type=float, default=0.90, help="Min confidence to auto-apply (default 0.90).")
    parser.add_argument("--dry-run", action="store_true", help="Do not write mapping updates.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    report = run(threshold=args.threshold, apply=not args.dry_run)
    print("[OK] LARN automap completed.")
    print(f"- Total foods: {report['foods_total']}")
    print(f"- Already mapped skipped: {report['skipped_already_mapped']}")
    print(f"- Auto mapped: {report['auto_mapped_count']}")
    print(f"- Review queue: {report['review_queue_count']}")
    print(f"- Report: {REPORT_JSON}")
    print(f"- Queue:  {QUEUE_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
