#!/usr/bin/env python3
"""
Importa export futuri TrainingPeaks (workouts CSV) e costruisce training_load.json.

Uso:
  python3 scripts/import_training_load.py sources/workouts-2.csv
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
COMPOSITION_FILE = DATA_DIR / "composition.json"
TRAINING_LOAD_FILE = DATA_DIR / "training_load.json"
CHANGELOG_FILE = DATA_DIR / "changelog.json"


DAY_TYPES = ["rest", "easy", "qualita", "lungo", "forza", "progressivo"]
MET_BY_DAY_TYPE = {
    "rest": 0.0,
    "easy": 9.0,
    "qualita": 11.5,
    "lungo": 9.5,
    "forza": 6.0,
    "progressivo": 10.5,
}


def to_float(value):
    """Converte stringa numerica in float, fallback 0."""
    if value is None:
        return 0.0
    txt = str(value).strip().replace(",", ".")
    if txt == "":
        return 0.0
    try:
        return float(txt)
    except ValueError:
        return 0.0


def get_current_weight_kg():
    """Legge peso corrente da composition.json."""
    try:
        data = json.loads(COMPOSITION_FILE.read_text(encoding="utf-8"))
        latest = data["measurements"][-1]
        return float(latest["weight"])
    except Exception:
        return 70.0


def classify_day_type(title, workout_type):
    """Classifica seduta in uno dei day-type del motore nutrizionale."""
    t = (title or "").lower()
    wt = (workout_type or "").lower()

    if any(k in t for k in ["forza", "strength", "gym", "calisthenics", "weights"]):
        return "forza"

    if any(k in t for k in ["progressivo", "1l+1m+1tr", "+1tr"]):
        return "progressivo"

    quality_keywords = [
        "rm",
        "ripet",
        "interval",
        "tempo run",
        "soglia",
        "vo2",
    ]
    if any(k in t for k in quality_keywords):
        return "qualita"

    if any(k in t for k in ["all", "allungh", "d.a."]):
        return "easy"

    if "lungo" in t:
        return "lungo"
    if re.search(r"\b\d+\s*l\b", t):
        return "lungo"
    if re.search(r"\d+h\d*'?\s*l\b", t):
        return "lungo"

    if wt == "run":
        return "easy"
    return "forza"


def iso_week_str(date_str):
    """Converte data YYYY-MM-DD in ISO week YYYY-Www."""
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def estimate_energy_kcal(day_type, duration_h, weight_kg):
    """Stima kcal seduta da MET * peso * ore."""
    met = MET_BY_DAY_TYPE.get(day_type, 8.0)
    return int(round(met * weight_kg * duration_h))


def build_training_load_payload(csv_path):
    """Parse CSV e costruisce payload training_load."""
    rows = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows.append(raw)

    if not rows:
        raise ValueError("CSV vuoto, nessun workout trovato.")

    weight_kg = get_current_weight_kg()
    sessions = []

    for idx, row in enumerate(rows, 1):
        date = (row.get("WorkoutDay") or "").strip()
        if not date:
            continue

        planned_duration_h = to_float(row.get("PlannedDuration"))
        planned_distance_km = to_float(row.get("PlannedDistanceInMeters")) / 1000.0
        title = (row.get("Title") or "").strip()
        workout_type = (row.get("WorkoutType") or "").strip()
        day_type = classify_day_type(title, workout_type)
        estimated_energy_kcal = estimate_energy_kcal(day_type, planned_duration_h, weight_kg)

        sessions.append(
            {
                "session_id": f"s{idx:03d}",
                "date": date,
                "iso_week": iso_week_str(date),
                "title": title,
                "workout_type": workout_type or "Unknown",
                "day_type": day_type,
                "planned_duration_h": round(planned_duration_h, 3),
                "planned_distance_km": round(planned_distance_km, 3),
                "estimated_energy_kcal": estimated_energy_kcal,
            }
        )

    if not sessions:
        raise ValueError("Nessuna sessione valida con WorkoutDay trovata nel CSV.")

    sessions.sort(key=lambda x: x["date"])

    weeks = defaultdict(
        lambda: {
            "start_date": None,
            "end_date": None,
            "sessions_count": 0,
            "planned_distance_km": 0.0,
            "planned_duration_h": 0.0,
            "estimated_energy_kcal": 0,
            "day_type_counts": Counter(),
            "day_type_energy_kcal": Counter(),
        }
    )

    for s in sessions:
        wk = weeks[s["iso_week"]]
        wk["sessions_count"] += 1
        wk["planned_distance_km"] += s["planned_distance_km"]
        wk["planned_duration_h"] += s["planned_duration_h"]
        wk["estimated_energy_kcal"] += s["estimated_energy_kcal"]
        wk["day_type_counts"][s["day_type"]] += 1
        wk["day_type_energy_kcal"][s["day_type"]] += s["estimated_energy_kcal"]
        wk["start_date"] = s["date"] if wk["start_date"] is None else min(wk["start_date"], s["date"])
        wk["end_date"] = s["date"] if wk["end_date"] is None else max(wk["end_date"], s["date"])

    weeks_out = []
    for iso_week in sorted(weeks.keys()):
        wk = weeks[iso_week]
        day_type_avg_kcal = {}
        for day_type, total_kcal in wk["day_type_energy_kcal"].items():
            count = wk["day_type_counts"][day_type]
            day_type_avg_kcal[day_type] = round(total_kcal / count, 1) if count else 0.0

        weeks_out.append(
            {
                "iso_week": iso_week,
                "start_date": wk["start_date"],
                "end_date": wk["end_date"],
                "sessions_count": wk["sessions_count"],
                "planned_distance_km": round(wk["planned_distance_km"], 2),
                "planned_duration_h": round(wk["planned_duration_h"], 2),
                "estimated_energy_kcal": int(wk["estimated_energy_kcal"]),
                "day_type_counts": dict(wk["day_type_counts"]),
                "day_type_avg_energy_kcal": day_type_avg_kcal,
            }
        )

    aggregate_counts = Counter(s["day_type"] for s in sessions)
    aggregate_energy = Counter()
    for s in sessions:
        aggregate_energy[s["day_type"]] += s["estimated_energy_kcal"]

    profile_costs = {}
    for day_type in DAY_TYPES:
        cnt = aggregate_counts[day_type]
        profile_costs[day_type] = round(aggregate_energy[day_type] / cnt, 1) if cnt else None

    payload = {
        "meta": {
            "version": "v1.0",
            "generated_at": datetime.now().isoformat(),
            "source_file": str(csv_path.relative_to(ROOT_DIR)),
            "mode": "planned_only",
            "weight_used_kg": round(weight_kg, 2),
        },
        "assumptions": {
            "energy_model": "MET * body_weight_kg * planned_duration_h",
            "met_by_day_type": MET_BY_DAY_TYPE,
        },
        "summary": {
            "sessions_count": len(sessions),
            "date_range": {
                "from": sessions[0]["date"],
                "to": sessions[-1]["date"],
            },
            "planned_distance_km": round(sum(s["planned_distance_km"] for s in sessions), 2),
            "planned_duration_h": round(sum(s["planned_duration_h"] for s in sessions), 2),
            "estimated_energy_kcal": int(sum(s["estimated_energy_kcal"] for s in sessions)),
        },
        "profile_costs_kcal": profile_costs,
        "weeks": weeks_out,
        "sessions": sessions,
    }
    return payload


def append_changelog_entry(source_file, payload):
    """Aggiunge entry nel changelog."""
    try:
        changelog = json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        changelog = {"entries": []}

    details = {
        "source_file": source_file,
        "sessions_count": payload["summary"]["sessions_count"],
        "date_from": payload["summary"]["date_range"]["from"],
        "date_to": payload["summary"]["date_range"]["to"],
        "planned_distance_km": payload["summary"]["planned_distance_km"],
        "planned_duration_h": payload["summary"]["planned_duration_h"],
        "estimated_energy_kcal": payload["summary"]["estimated_energy_kcal"],
        "updated_files": ["data/training_load.json"],
    }
    changelog.setdefault("entries", []).append(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "load import",
            "details": details,
        }
    )
    CHANGELOG_FILE.write_text(json.dumps(changelog, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 scripts/import_training_load.py <csv_path>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.is_absolute():
        csv_path = ROOT_DIR / csv_path
    if not csv_path.exists():
        print(f"Errore: file non trovato: {csv_path}")
        sys.exit(1)

    try:
        payload = build_training_load_payload(csv_path)
    except Exception as exc:
        print(f"Errore parsing CSV: {exc}")
        sys.exit(1)

    TRAINING_LOAD_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_changelog_entry(str(csv_path.relative_to(ROOT_DIR)), payload)

    summary = payload["summary"]
    print(f"[OK] Training load importato: {TRAINING_LOAD_FILE}")
    print(
        "  sessioni={sessions} periodo={date_from}->{date_to} km={km:.2f} h={hours:.2f} kcal={kcal}".format(
            sessions=summary["sessions_count"],
            date_from=summary["date_range"]["from"],
            date_to=summary["date_range"]["to"],
            km=summary["planned_distance_km"],
            hours=summary["planned_duration_h"],
            kcal=summary["estimated_energy_kcal"],
        )
    )
    print(f"  profile_costs_kcal={payload['profile_costs_kcal']}")


if __name__ == "__main__":
    main()
