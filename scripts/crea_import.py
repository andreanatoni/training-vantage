#!/usr/bin/env python3
"""
Tool CREA:
- crawl-index: scarica indice alfabetico CREA (nome + url + id)
- import-crea: importa alimenti da CREA in FOOD_DB (uno, lista o tutti dall'indice)
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

try:
    from scripts.food.food_add import SimilarFoodError, add_food_everywhere, make_food_id, parse_crea_url
except ModuleNotFoundError:
    from food.food_add import SimilarFoodError, add_food_everywhere, make_food_id, parse_crea_url

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
FOOD_DB_JSON_FILE = DATA_DIR / "FOOD_DB.json"
CHANGELOG_FILE = DATA_DIR / "changelog.json"
CREA_INDEX_JSON = DATA_DIR / "CREA_INDEX.json"
CREA_INDEX_MD = KNOWLEDGE_DIR / "crea-index.md"

CREA_INDEX_URL = "https://www.alimentinutrizione.it/tabelle-nutrizionali/ricerca-per-ordine-alfabetico"
CREA_DETAIL_BASE = "https://www.alimentinutrizione.it/tabelle-nutrizionali/"


def fetch_text(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def normalize_space(text):
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("|", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.strip().strip('"').strip()
    text = text.replace('""', '"')
    return text


def parse_crea_index_text(html, base_url=CREA_DETAIL_BASE):
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    items = []
    seen_ids = set()

    for href, label_html in links:
        absolute = urljoin(base_url, href)
        match = re.search(r"/tabelle-nutrizionali/(\d+)$", absolute)
        if not match:
            continue
        crea_id = match.group(1)
        if crea_id in seen_ids:
            continue

        name = normalize_space(label_html)
        if not name:
            continue

        seen_ids.add(crea_id)
        items.append({"crea_id": crea_id, "name": name, "url": absolute})

    items.sort(key=lambda item: item["name"].lower())
    return items


def write_crea_index(items):
    payload = {
        "meta": {
            "source_url": CREA_INDEX_URL,
            "generated_at": datetime.now().isoformat(),
            "count": len(items),
        },
        "items": items,
    }
    CREA_INDEX_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# CREA Index",
        "",
        f"Generato: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| CREA ID | Alimento | URL |",
        "| ---: | --- | --- |",
    ]
    for item in items:
        lines.append(f"| {item['crea_id']} | {item['name']} | {item['url']} |")
    lines.append("")
    CREA_INDEX_MD.write_text("\n".join(lines), encoding="utf-8")


def load_food_db():
    return json.loads(FOOD_DB_JSON_FILE.read_text(encoding="utf-8"))


def append_changelog(entry):
    data = json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))
    data.setdefault("entries", []).append(entry)
    CHANGELOG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def import_one(url, replace_existing=False):
    parsed = parse_crea_url(url)
    name = parsed["food_name"]
    reference = parsed["reference"]
    kcal = parsed["kcal"]
    protein = parsed["protein"]
    cho = parsed["cho"]
    fat = parsed["fat"]
    fiber = parsed["fiber"]
    source = parsed["source"]
    source_url = parsed.get("source_url")

    food_db = load_food_db()
    foods = food_db.get("foods", [])
    existing_ids = {f["id"] for f in foods}
    existing_names = {f["name"] for f in foods}
    candidate_id = make_food_id(name)

    replace_target = None
    if candidate_id in existing_ids:
        if replace_existing:
            replace_target = candidate_id
        else:
            return {"action": "skipped_existing", "name": name, "url": url, "food_id": candidate_id}
    elif name in existing_names:
        if replace_existing:
            replace_target = name
        else:
            return {"action": "skipped_existing", "name": name, "url": url}

    try:
        result = add_food_everywhere(
            name,
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
        result["name"] = name
        result["url"] = url
        return result
    except SimilarFoodError as exc:
        return {
            "action": "skipped_similar",
            "name": name,
            "url": url,
            "matches": [m["food"]["name"] for m in exc.matches],
        }
    except ValueError as exc:
        return {"action": "error", "name": name, "url": url, "error": str(exc)}


def resolve_urls(args):
    urls = []
    if args.url:
        urls.append(args.url)
    if args.id:
        urls.append(urljoin(CREA_DETAIL_BASE, args.id))
    if args.ids:
        for item in args.ids.split(","):
            clean = item.strip()
            if clean:
                urls.append(urljoin(CREA_DETAIL_BASE, clean))

    if args.all:
        if not CREA_INDEX_JSON.exists():
            raise ValueError("Indice CREA non trovato. Esegui prima: tv food crawl-index")
        data = json.loads(CREA_INDEX_JSON.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            urls.append(item["url"])

    # De-dup preserving order
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    if args.limit and args.limit > 0:
        unique = unique[: args.limit]
    return unique


def cmd_crawl_index(_args):
    html = fetch_text(CREA_INDEX_URL)
    items = parse_crea_index_text(html)
    write_crea_index(items)
    append_changelog(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "food crawl-index",
            "details": {
                "count": len(items),
                "source_url": CREA_INDEX_URL,
                "updated_files": ["data/CREA_INDEX.json", "knowledge/crea-index.md"],
            },
        }
    )
    print(f"[OK] CREA index estratto: {len(items)} alimenti")
    print(f"[OK] Salvati: {CREA_INDEX_JSON}, {CREA_INDEX_MD}")


def cmd_import_crea(args):
    urls = resolve_urls(args)
    if not urls:
        raise ValueError("Nessun URL da importare. Usa --url, --id, --ids o --all.")

    stats = {"added": 0, "replaced": 0, "skipped_existing": 0, "skipped_similar": 0, "error": 0}
    details = []

    for idx, url in enumerate(urls, 1):
        print(f"[{idx}/{len(urls)}] Import {url}")
        result = import_one(url, replace_existing=args.replace_existing)
        action = result["action"]
        stats[action] = stats.get(action, 0) + 1
        details.append(result)

        if action == "added":
            print(f"  + added: {result['name']} ({result['food_id']})")
        elif action == "replaced":
            print(f"  ~ replaced: {result.get('replaced_name')} -> {result['name']} ({result['food_id']})")
        elif action == "skipped_similar":
            print(f"  ! skipped_similar: {result['name']} (match: {', '.join(result.get('matches', []))})")
        elif action == "skipped_existing":
            print(f"  = skipped_existing: {result['name']}")
        else:
            print(f"  x error: {result.get('error', 'unknown')}")

    append_changelog(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "food import-crea",
            "details": {
                "count": len(urls),
                "replace_existing": args.replace_existing,
                "stats": stats,
            },
        }
    )

    print()
    print("[SUMMARY]")
    print(
        "added={added} replaced={replaced} skipped_existing={skipped_existing} "
        "skipped_similar={skipped_similar} error={error}".format(**stats)
    )

    if args.fail_on_error and (stats["error"] > 0 or stats["skipped_similar"] > 0):
        sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(description="Import alimenti CREA")
    sub = parser.add_subparsers(dest="cmd", required=True)

    crawl = sub.add_parser("crawl-index", help="Estrai indice alfabetico CREA")
    crawl.set_defaults(func=cmd_crawl_index)

    imp = sub.add_parser("import-crea", help="Importa alimenti CREA")
    imp.add_argument("--url", help="URL completo scheda CREA")
    imp.add_argument("--id", help="ID numerico CREA (es. 150030)")
    imp.add_argument("--ids", help="Lista ID separati da virgola")
    imp.add_argument("--all", action="store_true", help="Importa tutti gli URL dall'indice locale")
    imp.add_argument("--limit", type=int, default=0, help="Limita numero import")
    imp.add_argument("--replace-existing", action="store_true", help="Sostituisce entry esistenti (id/nome)")
    imp.add_argument("--fail-on-error", action="store_true", help="Exit 1 se errori o skipped_similar")
    imp.set_defaults(func=cmd_import_crea)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Errore: {exc}")
        sys.exit(1)
