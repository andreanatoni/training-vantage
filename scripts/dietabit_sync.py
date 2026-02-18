#!/usr/bin/env python3
"""
Dietabit sync utility.

Pipeline:
1) Crawl Dietabit categories + foods -> data/DIETABIT_DB.json
2) Compare with data/FOOD_DB.json -> data/DIETABIT_COMPARE_REPORT.json
3) Merge safe additions into FOOD_DB + mapping -> report counters

Source priority policy:
CREA > BDA > DIETABIT
DIETABIT never overwrites existing foods from higher-priority sources.
"""

import argparse
import json
import re
import ssl
import time
import urllib.request
from copy import deepcopy
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urljoin

try:
    from scripts.food.food_add import make_food_id
except ModuleNotFoundError:
    from food.food_add import make_food_id


ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
FOOD_DB_JSON = DATA_DIR / "FOOD_DB.json"
FOOD_DB_MAPPING_JSON = DATA_DIR / "FOOD_DB_TO_LARN_MAPPING.json"
DIETABIT_DB_JSON = DATA_DIR / "DIETABIT_DB.json"
DIETABIT_COMPARE_REPORT_JSON = DATA_DIR / "DIETABIT_COMPARE_REPORT.json"
CHANGELOG_FILE = DATA_DIR / "changelog.json"

DIETABIT_ROOT = "https://www.dietabit.it/alimenti/"
USER_AGENT = "training-vantage/1.0 (+dietabit-sync)"
SOURCE_PRIORITY = {"CREA": 3, "BDA": 2, "DIETABIT": 1}


def now_iso():
    return datetime.now().isoformat()


def today_iso():
    return datetime.now().strftime("%Y-%m-%d")


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        # Dietabit currently serves a cert chain that may fail on some local trust stores.
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        insecure_ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=30, context=insecure_ctx) as response:
            return response.read().decode("utf-8", errors="ignore")


def clean_html(text: str) -> str:
    txt = unescape(text or "")
    txt = re.sub(r"<[^>]+>", " ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def to_float(txt: str) -> float:
    raw = (txt or "").strip().replace(",", ".")
    if raw in {"", "-", "tr"}:
        return 0.0
    return float(raw)


def normalize_name_for_match(name: str) -> str:
    txt = (name or "").strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def extract_category_links(root_html: str) -> List[Tuple[str, str]]:
    # Restrict parsing to "Categorie alimenti" section.
    start_match = re.search(r"Categorie alimenti", root_html, re.IGNORECASE)
    if not start_match:
        raise ValueError("Sezione 'Categorie alimenti' non trovata in Dietabit root.")
    tail = root_html[start_match.start():]
    end_match = re.search(r"Indicazioni mediche", tail, re.IGNORECASE)
    section = tail[: end_match.start()] if end_match else tail

    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', section, flags=re.IGNORECASE | re.DOTALL)
    items = []
    seen = set()
    for href, label_html in links:
        name = clean_html(label_html)
        if not name:
            continue
        absolute = urljoin(DIETABIT_ROOT, href)
        # Category pages have exactly one slug after /alimenti/
        if not re.search(r"/alimenti/[^/]+/?$", absolute):
            continue
        key = (absolute.rstrip("/") + "/", name)
        if key in seen:
            continue
        seen.add(key)
        items.append((name, key[0]))
    return items


def parse_category_table(category_name: str, category_url: str, html: str) -> List[Dict]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    foods = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 5:
            continue
        href_match = re.search(r'<a[^>]+href="([^"]+)"', cells[0], flags=re.IGNORECASE)
        if not href_match:
            continue
        food_url = urljoin(category_url, href_match.group(1))
        name = clean_html(cells[0])
        if not name:
            continue
        try:
            cho = to_float(clean_html(cells[1]))
            protein = to_float(clean_html(cells[2]))
            fat = to_float(clean_html(cells[3]))
            kcal = to_float(clean_html(cells[4]))
        except ValueError:
            continue
        foods.append(
            {
                "id": make_food_id(name),
                "name": name,
                "reference": {
                    "amount": 100.0,
                    "unit": "g",
                    "label": "100 g",
                },
                "nutrients_per_reference": {
                    "kcal": round(kcal, 3),
                    "P": round(protein, 3),
                    "CHO": round(cho, 3),
                    "F": round(fat, 3),
                    "Fibre": 0.0,
                },
                "data_source": "DIETABIT",
                "source_type": "DIETABIT",
                "source_url": food_url,
                "dietabit_category": category_name,
                "last_verified_at": today_iso(),
            }
        )
    return foods


def crawl_dietabit_db() -> Dict:
    root_html = fetch_text(DIETABIT_ROOT)
    categories = extract_category_links(root_html)
    all_foods = []
    failed_categories = []
    for idx, (cat_name, cat_url) in enumerate(categories, start=1):
        last_exc = None
        rows = None
        for attempt in range(1, 4):
            try:
                html = fetch_text(cat_url)
                rows = parse_category_table(cat_name, cat_url, html)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 3:
                    time.sleep(1.5 * attempt)
        if rows is not None:
            all_foods.extend(rows)
            print(f"[{idx}/{len(categories)}] {cat_name}: {len(rows)} foods")
        else:
            failed_categories.append({"category": cat_name, "url": cat_url, "error": str(last_exc)})
            print(f"[{idx}/{len(categories)}] {cat_name}: ERROR {last_exc}")

    # Deduplicate by id, preserving first occurrence.
    dedup = {}
    duplicates = []
    for food in all_foods:
        fid = food["id"]
        if fid in dedup:
            duplicates.append(fid)
            continue
        dedup[fid] = food

    payload = {
        "meta": {
            "name": "DIETABIT_DB",
            "source_of_truth": "Dietabit category pages",
            "units": "per 100 g",
            "nutrition_fields": ["kcal", "P", "CHO", "F", "Fibre"],
            "generated_at": now_iso(),
            "generated_from": DIETABIT_ROOT,
            "categories_count": len(categories),
            "imported_count_raw": len(all_foods),
            "imported_count_unique": len(dedup),
            "duplicates_skipped": len(duplicates),
            "failed_categories": failed_categories,
        },
        "foods": sorted(dedup.values(), key=lambda x: x["name"].lower()),
    }
    DIETABIT_DB_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def nutrients_equal(a: Dict, b: Dict, tol=1e-6) -> bool:
    for key in ["kcal", "P", "CHO", "F", "Fibre"]:
        if abs(float(a.get(key, 0.0)) - float(b.get(key, 0.0))) > tol:
            return False
    return True


def references_equal(a: Dict, b: Dict) -> bool:
    if float(a.get("amount", 0.0)) != float(b.get("amount", 0.0)):
        return False
    if str(a.get("unit", "")).strip() != str(b.get("unit", "")).strip():
        return False
    return True


def compare_and_merge(apply_merge: bool = True) -> Dict:
    food_db = load_json(FOOD_DB_JSON)
    mapping_db = load_json(FOOD_DB_MAPPING_JSON)
    dietabit_db = load_json(DIETABIT_DB_JSON)

    food_items = food_db.get("foods", [])
    diet_items = dietabit_db.get("foods", [])
    by_id = {f["id"]: f for f in food_items}
    by_name = {normalize_name_for_match(f["name"]): f for f in food_items}

    stats = {
        "dietabit_total": len(diet_items),
        "food_db_before": len(food_items),
        "identical_existing": 0,
        "conflicting_existing": 0,
        "conflicts_higher_priority_existing": 0,
        "conflicts_same_or_lower_priority_existing": 0,
        "missing_added": 0,
        "missing_skipped": 0,
        "food_db_after": len(food_items),
    }
    conflicts = []
    added = []

    for item in diet_items:
        existing = by_id.get(item["id"])
        if not existing:
            existing = by_name.get(normalize_name_for_match(item["name"]))

        if existing:
            existing_source = str(existing.get("source_type") or existing.get("data_source") or "").upper()
            existing_priority = SOURCE_PRIORITY.get(existing_source, 99)
            dietabit_priority = SOURCE_PRIORITY.get("DIETABIT", 1)
            same_ref = references_equal(existing.get("reference", {}), item.get("reference", {}))
            same_nutrients = nutrients_equal(
                existing.get("nutrients_per_reference", {}),
                item.get("nutrients_per_reference", {}),
            )
            if same_ref and same_nutrients:
                stats["identical_existing"] += 1
            else:
                stats["conflicting_existing"] += 1
                if existing_priority > dietabit_priority:
                    stats["conflicts_higher_priority_existing"] += 1
                else:
                    stats["conflicts_same_or_lower_priority_existing"] += 1
                conflicts.append(
                    {
                        "dietabit_id": item["id"],
                        "dietabit_name": item["name"],
                        "existing_id": existing.get("id"),
                        "existing_name": existing.get("name"),
                        "existing_source_type": existing_source or "UNKNOWN",
                        "policy": "keep_existing_due_to_priority" if existing_priority > dietabit_priority else "keep_existing_no_override",
                        "dietabit_reference": item.get("reference"),
                        "existing_reference": existing.get("reference"),
                        "dietabit_nutrients": item.get("nutrients_per_reference"),
                        "existing_nutrients": existing.get("nutrients_per_reference"),
                    }
                )
            continue

        if apply_merge:
            new_item = deepcopy(item)
            new_item.pop("dietabit_category", None)
            food_items.append(new_item)
            by_id[new_item["id"]] = new_item
            by_name[normalize_name_for_match(new_item["name"])] = new_item

            mapping_entries = mapping_db.get("mapping", [])
            mapping_entries.append(
                {
                    "food_db_id": new_item["id"],
                    "food_db_name": new_item["name"],
                    "larn_portion_id": None,
                    "operational_portion_id": None,
                    "note": "Auto-added from DIETABIT_DB sync. Assegnare larn_portion_id o operational_portion_id.",
                    "review_status": "pending_review",
                    "mapping_confidence": 0.0,
                    "mapping_source": "dietabit_sync_auto",
                    "last_reviewed_at": None,
                }
            )
            stats["missing_added"] += 1
            added.append({"id": new_item["id"], "name": new_item["name"]})
        else:
            stats["missing_skipped"] += 1

    if apply_merge:
        food_db["foods"] = sorted(food_items, key=lambda x: x["name"].lower())
        food_db.setdefault("meta", {})
        food_db["meta"]["generated_at"] = now_iso()
        food_db["meta"]["imported_count"] = len(food_db["foods"])
        FOOD_DB_JSON.write_text(json.dumps(food_db, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Dedup mapping by food_db_id, keep first.
        seen = set()
        dedup_mapping = []
        for m in mapping_db.get("mapping", []):
            fid = m.get("food_db_id")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            dedup_mapping.append(m)
        mapping_db["mapping"] = dedup_mapping
        mapping_db.setdefault("meta", {})
        mapping_db["meta"]["generated_at"] = now_iso()
        FOOD_DB_MAPPING_JSON.write_text(
            json.dumps(mapping_db, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    stats["food_db_after"] = len(load_json(FOOD_DB_JSON).get("foods", []))
    report = {
        "meta": {
            "generated_at": now_iso(),
            "apply_merge": apply_merge,
            "source_priority_policy": "CREA > BDA > DIETABIT",
            "sources": {
                "dietabit_db": str(DIETABIT_DB_JSON.relative_to(ROOT)),
                "food_db": str(FOOD_DB_JSON.relative_to(ROOT)),
                "mapping_db": str(FOOD_DB_MAPPING_JSON.relative_to(ROOT)),
            },
        },
        "stats": stats,
        "added_preview": added[:200],
        "conflicts_preview": conflicts[:200],
    }
    DIETABIT_COMPARE_REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def append_changelog(entry):
    if not CHANGELOG_FILE.exists():
        return
    data = load_json(CHANGELOG_FILE)
    data.setdefault("entries", []).append(entry)
    CHANGELOG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_sync(args):
    print("[STEP 1] Crawl Dietabit -> DIETABIT_DB.json")
    dietabit_db = crawl_dietabit_db()
    print(f"[OK] Dietabit foods: {dietabit_db['meta']['imported_count_unique']}")

    print("[STEP 2/3] Compare + merge")
    report = compare_and_merge(apply_merge=not args.no_merge)
    stats = report["stats"]
    print(
        "[OK] compare/merge: identical={identical} conflicts={conflicts} added={added} total_after={after}".format(
            identical=stats["identical_existing"],
            conflicts=stats["conflicting_existing"],
            added=stats["missing_added"],
            after=stats["food_db_after"],
        )
    )

    append_changelog(
        {
            "timestamp": now_iso(),
            "command": "food sync-dietabit",
            "details": {
                "dietabit_count": dietabit_db["meta"]["imported_count_unique"],
                "no_merge": bool(args.no_merge),
                "stats": stats,
                "updated_files": [
                    "data/DIETABIT_DB.json",
                    "data/DIETABIT_COMPARE_REPORT.json",
                    "data/FOOD_DB.json",
                    "data/FOOD_DB_TO_LARN_MAPPING.json",
                ],
            },
        }
    )

    print(f"[OK] Export: {DIETABIT_DB_JSON}")
    print(f"[OK] Report: {DIETABIT_COMPARE_REPORT_JSON}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Crawl Dietabit e sincronizza con FOOD_DB.",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Esegue crawl+compare senza scrivere merge su FOOD_DB.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd_sync(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
