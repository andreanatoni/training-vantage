#!/usr/bin/env python3
"""Import mapping file (food_db_id|larn_portion_id[|display_name]) into FOOD_DB_TO_LARN_MAPPING.

Accepts 2-column (legacy) or 3-column format.  When the third column is present
it is collected into data/FOOD_NAME_BRIDGE.json."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
BACKUPS_DIR = DATA_DIR / "backups"

DEFAULT_INPUT = DATA_DIR / "food_mapped.md"
FOOD_DB_JSON = DATA_DIR / "FOOD_DB.json"
LARN_JSON = DATA_DIR / "LARN_PORTIONS.json"
MAPPING_JSON = DATA_DIR / "FOOD_DB_TO_LARN_MAPPING.json"
REPORT_JSON = DATA_DIR / "FOOD_MAPPED_IMPORT_REPORT.json"
REPORT_MD = DATA_DIR / "FOOD_MAPPED_IMPORT_REPORT.md"
BRIDGE_JSON = DATA_DIR / "FOOD_NAME_BRIDGE.json"


def now_iso():
    return datetime.now().isoformat()


def parse_mapping_lines(path: Path):
    rows = []
    errors = []
    display_names = {}  # food_db_id -> display_name (from optional 3rd column)
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        txt = raw.strip()
        if not txt:
            continue
        if txt.startswith("#"):
            continue
        parts = [p.strip() for p in txt.split("|")]
        if len(parts) not in (2, 3):
            errors.append({"line": line_no, "raw": raw, "error": "invalid_format"})
            continue
        fid, lid = parts[0], parts[1]
        dname = parts[2] if len(parts) == 3 else None
        if not fid or not lid:
            errors.append({"line": line_no, "raw": raw, "error": "empty_token"})
            continue
        rows.append({"line": line_no, "food_db_id": fid, "larn_portion_id": lid})
        if dname:
            display_names[fid] = dname
    return rows, errors, display_names


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_markdown_report(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Food Mapped Import Report",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- source_file: `{report['source_file']}`",
        f"- dry_run: {report['dry_run']}",
        f"- strict_complete: {report['strict_complete']}",
        "",
        "## Summary",
        "",
        f"- parsed_rows: {s['parsed_rows']}",
        f"- food_db_total: {s['food_db_total']}",
        f"- larn_total: {s['larn_total']}",
        f"- parse_errors: {s['parse_errors']}",
        f"- duplicate_food_ids: {s['duplicate_food_ids']}",
        f"- invalid_food_ids: {s['invalid_food_ids']}",
        f"- invalid_larn_ids: {s['invalid_larn_ids']}",
        f"- missing_food_ids: {s['missing_food_ids']}",
        f"- extra_food_ids: {s['extra_food_ids']}",
        f"- upsert_created: {s['upsert_created']}",
        f"- upsert_updated: {s['upsert_updated']}",
        f"- upsert_unchanged: {s['upsert_unchanged']}",
        "",
    ]

    for key in [
        "parse_errors_preview",
        "duplicate_food_ids_preview",
        "invalid_food_ids_preview",
        "invalid_larn_ids_preview",
        "missing_food_ids_preview",
        "extra_food_ids_preview",
    ]:
        items = report.get(key, [])
        if not items:
            continue
        lines.append(f"## {key}")
        lines.append("")
        for item in items[:50]:
            lines.append(f"- `{item}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def run(input_file: Path, dry_run: bool, strict_complete: bool):
    if not input_file.exists():
        raise SystemExit(f"[ERR] file not found: {input_file}")

    food_db = load_json(FOOD_DB_JSON)
    larn_db = load_json(LARN_JSON)
    mapping_db = load_json(MAPPING_JSON)

    food_by_id = {f.get("id"): f for f in food_db.get("foods", []) if f.get("id")}
    valid_larn = {p.get("id") for p in larn_db.get("portions", []) if p.get("id")}

    rows, parse_errors, display_names = parse_mapping_lines(input_file)

    # duplicates
    ctr = Counter(r["food_db_id"] for r in rows)
    duplicate_food_ids = sorted([fid for fid, c in ctr.items() if c > 1])

    invalid_food_ids = sorted({r["food_db_id"] for r in rows if r["food_db_id"] not in food_by_id})
    invalid_larn_ids = sorted({r["larn_portion_id"] for r in rows if r["larn_portion_id"] not in valid_larn})

    parsed_food_ids = {r["food_db_id"] for r in rows}
    db_food_ids = set(food_by_id.keys())
    missing_food_ids = sorted(db_food_ids - parsed_food_ids)
    extra_food_ids = sorted(parsed_food_ids - db_food_ids)

    hard_fail = bool(parse_errors or duplicate_food_ids or invalid_food_ids or invalid_larn_ids)
    strict_fail = bool(missing_food_ids or extra_food_ids) if strict_complete else False
    ok = not hard_fail and not strict_fail

    upsert_created = 0
    upsert_updated = 0
    upsert_unchanged = 0

    if ok and not dry_run:
        mapping_entries = mapping_db.get("mapping", [])
        by_food = {m.get("food_db_id"): m for m in mapping_entries if m.get("food_db_id")}
        today = datetime.now().strftime("%Y-%m-%d")

        for r in rows:
            fid = r["food_db_id"]
            lid = r["larn_portion_id"]
            entry = by_food.get(fid)
            if not entry:
                entry = {
                    "food_db_id": fid,
                    "food_db_name": food_by_id[fid].get("name", fid),
                    "larn_portion_id": None,
                    "operational_portion_id": None,
                    "note": "",
                    "review_status": "pending_review",
                    "mapping_confidence": 0.0,
                    "mapping_source": "none",
                    "last_reviewed_at": None,
                }
                mapping_entries.append(entry)
                by_food[fid] = entry
                upsert_created += 1

            before = (
                entry.get("larn_portion_id"),
                entry.get("operational_portion_id"),
                entry.get("review_status"),
                entry.get("mapping_confidence"),
                entry.get("mapping_source"),
            )

            entry["food_db_name"] = food_by_id[fid].get("name", fid)
            entry["larn_portion_id"] = lid
            entry["operational_portion_id"] = None
            entry["review_status"] = "reviewed"
            entry["mapping_confidence"] = 1.0
            entry["mapping_source"] = "import_mapped_file"
            entry["last_reviewed_at"] = today
            entry["note"] = f"Imported from {input_file.name}"

            after = (
                entry.get("larn_portion_id"),
                entry.get("operational_portion_id"),
                entry.get("review_status"),
                entry.get("mapping_confidence"),
                entry.get("mapping_source"),
            )
            if before == after:
                upsert_unchanged += 1
            else:
                upsert_updated += 1

        # dedup by food_db_id
        seen = set()
        dedup = []
        for m in mapping_entries:
            fid = m.get("food_db_id")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            dedup.append(m)

        mapping_db["mapping"] = dedup
        mapping_db.setdefault("meta", {})
        mapping_db["meta"]["generated_at"] = now_iso()
        mapping_db["meta"]["mapping_import_source"] = str(input_file)

        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = BACKUPS_DIR / f"FOOD_DB_TO_LARN_MAPPING-before-import-mapped-{stamp}.json"
        backup.write_text(json.dumps(load_json(MAPPING_JSON), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        MAPPING_JSON.write_text(json.dumps(mapping_db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        # estimate upsert counts in dry-run/failed mode
        mapping_entries = mapping_db.get("mapping", [])
        by_food = {m.get("food_db_id"): m for m in mapping_entries if m.get("food_db_id")}
        for r in rows:
            fid = r["food_db_id"]
            if fid not in food_by_id:
                continue
            entry = by_food.get(fid)
            if not entry:
                upsert_created += 1
                continue
            if entry.get("larn_portion_id") == r["larn_portion_id"] and entry.get("operational_portion_id") is None:
                upsert_unchanged += 1
            else:
                upsert_updated += 1

    # --- Write FOOD_NAME_BRIDGE.json if display_names present ---
    if display_names and ok and not dry_run:
        bridge = {
            "meta": {
                "generated_at": now_iso(),
                "source": str(input_file),
                "total_entries": len(display_names),
            },
            "names": {fid: display_names[fid] for fid in sorted(display_names)},
        }
        BRIDGE_JSON.write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[BRIDGE] Written {len(display_names)} display names → {BRIDGE_JSON.name}")

    report = {
        "generated_at": now_iso(),
        "source_file": str(input_file),
        "dry_run": dry_run,
        "strict_complete": strict_complete,
        "ok": ok,
        "summary": {
            "parsed_rows": len(rows),
            "food_db_total": len(db_food_ids),
            "larn_total": len(valid_larn),
            "parse_errors": len(parse_errors),
            "duplicate_food_ids": len(duplicate_food_ids),
            "invalid_food_ids": len(invalid_food_ids),
            "invalid_larn_ids": len(invalid_larn_ids),
            "missing_food_ids": len(missing_food_ids),
            "extra_food_ids": len(extra_food_ids),
            "upsert_created": upsert_created,
            "upsert_updated": upsert_updated,
            "upsert_unchanged": upsert_unchanged,
            "display_names_found": len(display_names),
        },
        "parse_errors_preview": [f"line={e['line']} error={e['error']} raw={e['raw']}" for e in parse_errors[:50]],
        "duplicate_food_ids_preview": duplicate_food_ids[:50],
        "invalid_food_ids_preview": invalid_food_ids[:50],
        "invalid_larn_ids_preview": invalid_larn_ids[:50],
        "missing_food_ids_preview": missing_food_ids[:50],
        "extra_food_ids_preview": extra_food_ids[:50],
    }

    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(build_markdown_report(report), encoding="utf-8")

    return report


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Import food_db_id|larn_portion_id mapping file.")
    p.add_argument("--file", default=str(DEFAULT_INPUT), help="Input mapping file (default: data/food_mapped.md)")
    p.add_argument("--dry-run", action="store_true", help="Validate and report only, no write")
    p.add_argument(
        "--strict-complete",
        action="store_true",
        help="Fail if file does not cover exactly all FOOD_DB ids (missing/extra)",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    report = run(Path(args.file), dry_run=bool(args.dry_run), strict_complete=bool(args.strict_complete))

    s = report["summary"]
    if report["ok"]:
        print("[OK] mapped import completed.")
    else:
        print("[ERR] mapped import validation failed.")

    print(f"- parsed_rows: {s['parsed_rows']}")
    print(f"- food_db_total: {s['food_db_total']}")
    print(f"- parse_errors: {s['parse_errors']}")
    print(f"- duplicate_food_ids: {s['duplicate_food_ids']}")
    print(f"- invalid_food_ids: {s['invalid_food_ids']}")
    print(f"- invalid_larn_ids: {s['invalid_larn_ids']}")
    print(f"- missing_food_ids: {s['missing_food_ids']}")
    print(f"- extra_food_ids: {s['extra_food_ids']}")
    print(f"- upsert_created: {s['upsert_created']}")
    print(f"- upsert_updated: {s['upsert_updated']}")
    print(f"- upsert_unchanged: {s['upsert_unchanged']}")
    print(f"- report_json: {REPORT_JSON}")
    print(f"- report_md: {REPORT_MD}")

    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
