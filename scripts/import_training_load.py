#!/usr/bin/env python3
"""
Importa storico/planning da CSV TrainingPeaks e/o Garmin in training_load.json.

Esempi:
  python3 scripts/import_training_load.py sources/workouts-2.csv
  python3 scripts/import_training_load.py --tp sources/workouts-2.csv
  python3 scripts/import_training_load.py --garmin sources/garmin-last-year.csv
  python3 scripts/import_training_load.py --tp sources/trainingpeaks-last-year.csv --garmin sources/garmin-last-year.csv
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    from scripts.athlete_context import data_file, ensure_athlete_dirs, get_athlete_id
except ModuleNotFoundError:
    from athlete_context import data_file, ensure_athlete_dirs, get_athlete_id


ROOT_DIR = Path(__file__).parent.parent
COMPOSITION_FILE = data_file("composition.json")
TRAINING_LOAD_FILE = data_file("training_load.json")
CHANGELOG_FILE = data_file("changelog.json")


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


def to_float_locale(value):
    """Converte numeri con separatori locali/commerciali in float."""
    if value is None:
        return 0.0
    txt = str(value).strip()
    if not txt:
        return 0.0
    txt = txt.replace(" ", "")
    if "," in txt and "." in txt:
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    elif "," in txt:
        parts = txt.split(",")
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            txt = "".join(parts)
        else:
            txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return 0.0


def parse_hms_to_hours(value):
    """Converte stringhe HH:MM:SS o MM:SS in ore."""
    txt = (value or "").strip()
    if not txt:
        return 0.0
    parts = txt.split(":")
    try:
        nums = [int(float(p)) for p in parts]
    except ValueError:
        return 0.0
    if len(nums) == 3:
        h, m, s = nums
    elif len(nums) == 2:
        h, m, s = 0, nums[0], nums[1]
    else:
        return 0.0
    return (h * 3600 + m * 60 + s) / 3600.0


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

    if wt in {"run", "corsa"}:
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


def load_csv_rows(csv_path):
    """Legge righe CSV restituendo lista dict."""
    rows = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows.append(raw)
    return rows


def detect_csv_format(rows):
    """Riconosce formato CSV principale."""
    if not rows:
        return "unknown"
    keys = set(rows[0].keys())
    if {"WorkoutDay", "Title", "WorkoutType"}.issubset(keys):
        return "trainingpeaks"
    if {"Tipo di attività", "Data", "Titolo"}.issubset(keys):
        return "garmin"
    return "unknown"


def parse_trainingpeaks_csv(csv_path):
    """Parsa CSV TrainingPeaks in formato canonico."""
    rows = load_csv_rows(csv_path)
    if not rows:
        raise ValueError(f"CSV vuoto: {csv_path}")
    if detect_csv_format(rows) != "trainingpeaks":
        raise ValueError(f"Formato non TrainingPeaks: {csv_path}")

    sessions = []
    for idx, row in enumerate(rows, 1):
        date = (row.get("WorkoutDay") or "").strip()
        if not date:
            continue
        title = (row.get("Title") or "").strip()
        workout_type = (row.get("WorkoutType") or "").strip() or "Unknown"
        planned_duration_h = to_float(row.get("PlannedDuration"))
        if planned_duration_h <= 0:
            planned_duration_h = to_float(row.get("TimeTotalInHours"))
        planned_distance_km = to_float(row.get("PlannedDistanceInMeters")) / 1000.0
        if planned_distance_km <= 0:
            planned_distance_km = to_float(row.get("DistanceInMeters")) / 1000.0
        energy_reported = int(round(to_float(row.get("Energy"))))
        day_type = classify_day_type(title, workout_type)
        sessions.append(
            {
                "source": "trainingpeaks",
                "source_session_id": f"tp{idx:04d}",
                "date": date,
                "title": title,
                "workout_type": workout_type,
                "day_type": day_type,
                "duration_h": round(planned_duration_h, 3),
                "distance_km": round(planned_distance_km, 3),
                "energy_reported_kcal": energy_reported if energy_reported > 0 else None,
                "if": to_float(row.get("IF")) or None,
                "tss": to_float(row.get("TSS")) or None,
                "raw": {"source_file": relpath_or_str(csv_path)},
            }
        )
    return sessions


def parse_garmin_date(value):
    txt = (value or "").strip()
    if not txt:
        return ""
    try:
        return datetime.strptime(txt, "%Y-%m-%d %H:%M:%S").date().isoformat()
    except ValueError:
        return txt[:10]


def parse_garmin_csv(csv_path):
    """Parsa CSV Garmin (italiano) in formato canonico."""
    rows = load_csv_rows(csv_path)
    if not rows:
        raise ValueError(f"CSV vuoto: {csv_path}")
    if detect_csv_format(rows) != "garmin":
        raise ValueError(f"Formato non Garmin: {csv_path}")

    sessions = []
    for idx, row in enumerate(rows, 1):
        date = parse_garmin_date(row.get("Data"))
        if not date:
            continue
        title = (row.get("Titolo") or "").strip()
        workout_type = (row.get("Tipo di attività") or "").strip() or "Unknown"
        duration_h = parse_hms_to_hours(row.get("Tempo"))
        if duration_h <= 0:
            duration_h = parse_hms_to_hours(row.get("Tempo in movimento"))
        distance_km = to_float_locale(row.get("Distanza"))
        calories = int(round(to_float_locale(row.get("Calorie"))))
        day_type = classify_day_type(title, workout_type)
        sessions.append(
            {
                "source": "garmin",
                "source_session_id": f"gm{idx:04d}",
                "date": date,
                "title": title,
                "workout_type": workout_type,
                "day_type": day_type,
                "duration_h": round(duration_h, 3),
                "distance_km": round(distance_km, 3),
                "energy_reported_kcal": calories if calories > 0 else None,
                "if": None,
                "tss": None,
                "raw": {"source_file": relpath_or_str(csv_path)},
            }
        )
    return sessions


def normalize_title(title):
    txt = (title or "").lower()
    txt = re.sub(r"\blatina\b", "", txt)
    txt = re.sub(r"[^a-z0-9]+", "", txt)
    return txt


def choose_garmin_match(tp_session, garmin_candidates):
    """Trova miglior match Garmin per una seduta TP della stessa data."""
    if not garmin_candidates:
        return None
    tp_title = normalize_title(tp_session["title"])
    if tp_title:
        for candidate in garmin_candidates:
            if normalize_title(candidate["title"]) == tp_title:
                return candidate
    best = None
    best_score = 9999.0
    for candidate in garmin_candidates:
        dd = abs(tp_session["distance_km"] - candidate["distance_km"])
        dt = abs(tp_session["duration_h"] - candidate["duration_h"])
        score = dd + (dt * 2.0)
        if score < best_score:
            best = candidate
            best_score = score
    if best and (best_score <= 1.2 or len(garmin_candidates) == 1):
        return best
    return None


def merge_sources(tp_sessions, garmin_sessions, weight_kg):
    """Merge tra sessioni TP e Garmin; mantiene anche unmatched."""
    by_date_tp = defaultdict(list)
    by_date_gm = defaultdict(list)
    for s in tp_sessions:
        by_date_tp[s["date"]].append(s)
    for s in garmin_sessions:
        by_date_gm[s["date"]].append(s)

    merged = []
    matched_garmin_ids = set()
    merge_stats = {"matched": 0, "tp_only": 0, "garmin_only": 0}

    all_dates = sorted(set(by_date_tp.keys()) | set(by_date_gm.keys()))
    for date in all_dates:
        day_tp = by_date_tp.get(date, [])
        day_gm = by_date_gm.get(date, [])
        for tp in day_tp:
            gm_pool = [x for x in day_gm if x["source_session_id"] not in matched_garmin_ids]
            gm = choose_garmin_match(tp, gm_pool)
            if gm:
                matched_garmin_ids.add(gm["source_session_id"])
                merge_stats["matched"] += 1
                duration_h = tp["duration_h"] if tp["duration_h"] > 0 else gm["duration_h"]
                distance_km = tp["distance_km"] if tp["distance_km"] > 0 else gm["distance_km"]
                day_type = tp["day_type"] or gm["day_type"]
                estimated_energy_kcal = estimate_energy_kcal(day_type, duration_h, weight_kg)
                merged.append(
                    {
                        "date": date,
                        "iso_week": iso_week_str(date),
                        "title": tp["title"] or gm["title"],
                        "workout_type": tp["workout_type"] or gm["workout_type"],
                        "day_type": day_type,
                        "planned_duration_h": round(duration_h, 3),
                        "planned_distance_km": round(distance_km, 3),
                        "estimated_energy_kcal": estimated_energy_kcal,
                        "reported_energy_kcal": tp["energy_reported_kcal"] or gm["energy_reported_kcal"],
                        "source": "trainingpeaks+garmin",
                        "source_session_ids": [tp["source_session_id"], gm["source_session_id"]],
                        "source_metrics": {
                            "trainingpeaks": {
                                "tss": tp["tss"],
                                "if": tp["if"],
                                "duration_h": tp["duration_h"],
                                "distance_km": tp["distance_km"],
                                "energy_kcal": tp["energy_reported_kcal"],
                            },
                            "garmin": {
                                "duration_h": gm["duration_h"],
                                "distance_km": gm["distance_km"],
                                "energy_kcal": gm["energy_reported_kcal"],
                            },
                        },
                    }
                )
            else:
                merge_stats["tp_only"] += 1
                estimated_energy_kcal = estimate_energy_kcal(tp["day_type"], tp["duration_h"], weight_kg)
                merged.append(
                    {
                        "date": date,
                        "iso_week": iso_week_str(date),
                        "title": tp["title"],
                        "workout_type": tp["workout_type"],
                        "day_type": tp["day_type"],
                        "planned_duration_h": tp["duration_h"],
                        "planned_distance_km": tp["distance_km"],
                        "estimated_energy_kcal": estimated_energy_kcal,
                        "reported_energy_kcal": tp["energy_reported_kcal"],
                        "source": "trainingpeaks",
                        "source_session_ids": [tp["source_session_id"]],
                        "source_metrics": {
                            "trainingpeaks": {
                                "tss": tp["tss"],
                                "if": tp["if"],
                                "duration_h": tp["duration_h"],
                                "distance_km": tp["distance_km"],
                                "energy_kcal": tp["energy_reported_kcal"],
                            }
                        },
                    }
                )
        for gm in day_gm:
            if gm["source_session_id"] in matched_garmin_ids:
                continue
            merge_stats["garmin_only"] += 1
            estimated_energy_kcal = estimate_energy_kcal(gm["day_type"], gm["duration_h"], weight_kg)
            merged.append(
                {
                    "date": date,
                    "iso_week": iso_week_str(date),
                    "title": gm["title"],
                    "workout_type": gm["workout_type"],
                    "day_type": gm["day_type"],
                    "planned_duration_h": gm["duration_h"],
                    "planned_distance_km": gm["distance_km"],
                    "estimated_energy_kcal": estimated_energy_kcal,
                    "reported_energy_kcal": gm["energy_reported_kcal"],
                    "source": "garmin",
                    "source_session_ids": [gm["source_session_id"]],
                    "source_metrics": {
                        "garmin": {
                            "duration_h": gm["duration_h"],
                            "distance_km": gm["distance_km"],
                            "energy_kcal": gm["energy_reported_kcal"],
                        }
                    },
                }
            )
    return merged, merge_stats


def summarize_weeks(sessions):
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
    return weeks_out


def build_training_load_payload(tp_files, garmin_files):
    """Costruisce payload training_load da uno o entrambi i provider CSV."""
    if not tp_files and not garmin_files:
        raise ValueError("Nessun file CSV passato.")

    weight_kg = get_current_weight_kg()
    tp_sessions = []
    gm_sessions = []
    for path in tp_files:
        tp_sessions.extend(parse_trainingpeaks_csv(path))
    for path in garmin_files:
        gm_sessions.extend(parse_garmin_csv(path))

    if not tp_sessions and not gm_sessions:
        raise ValueError("Nessuna sessione valida trovata nei CSV.")

    if tp_sessions and gm_sessions:
        merged, merge_stats = merge_sources(tp_sessions, gm_sessions, weight_kg)
        source_mode = "trainingpeaks+garmin"
    elif tp_sessions:
        merged = []
        for tp in tp_sessions:
            merged.append(
                {
                    "date": tp["date"],
                    "iso_week": iso_week_str(tp["date"]),
                    "title": tp["title"],
                    "workout_type": tp["workout_type"],
                    "day_type": tp["day_type"],
                    "planned_duration_h": tp["duration_h"],
                    "planned_distance_km": tp["distance_km"],
                    "estimated_energy_kcal": estimate_energy_kcal(tp["day_type"], tp["duration_h"], weight_kg),
                    "reported_energy_kcal": tp["energy_reported_kcal"],
                    "source": "trainingpeaks",
                    "source_session_ids": [tp["source_session_id"]],
                    "source_metrics": {"trainingpeaks": {"tss": tp["tss"], "if": tp["if"]}},
                }
            )
        merge_stats = {"matched": 0, "tp_only": len(merged), "garmin_only": 0}
        source_mode = "trainingpeaks"
    else:
        merged = []
        for gm in gm_sessions:
            merged.append(
                {
                    "date": gm["date"],
                    "iso_week": iso_week_str(gm["date"]),
                    "title": gm["title"],
                    "workout_type": gm["workout_type"],
                    "day_type": gm["day_type"],
                    "planned_duration_h": gm["duration_h"],
                    "planned_distance_km": gm["distance_km"],
                    "estimated_energy_kcal": estimate_energy_kcal(gm["day_type"], gm["duration_h"], weight_kg),
                    "reported_energy_kcal": gm["energy_reported_kcal"],
                    "source": "garmin",
                    "source_session_ids": [gm["source_session_id"]],
                    "source_metrics": {"garmin": {"energy_kcal": gm["energy_reported_kcal"]}},
                }
            )
        merge_stats = {"matched": 0, "tp_only": 0, "garmin_only": len(merged)}
        source_mode = "garmin"

    merged.sort(key=lambda x: (x["date"], x["title"]))
    sessions = []
    for idx, session in enumerate(merged, 1):
        item = dict(session)
        item["session_id"] = f"s{idx:03d}"
        sessions.append(item)

    weeks_out = summarize_weeks(sessions)

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
            "version": "v2.0",
            "generated_at": datetime.now().isoformat(),
            "athlete_id": get_athlete_id(),
            "source_file": (
                relpath_or_str(tp_files[0])
                if tp_files
                else relpath_or_str(garmin_files[0])
            ),
            "source_files": {
                "trainingpeaks": [relpath_or_str(x) for x in tp_files],
                "garmin": [relpath_or_str(x) for x in garmin_files],
            },
            "mode": source_mode,
            "weight_used_kg": round(weight_kg, 2),
        },
        "assumptions": {
            "energy_model": "MET * body_weight_kg * planned_duration_h",
            "met_by_day_type": MET_BY_DAY_TYPE,
        },
        "merge": merge_stats,
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


def append_changelog_entry(source_files, payload):
    """Aggiunge entry nel changelog."""
    try:
        changelog = json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        changelog = {"entries": []}

    details = {
        "source_files": source_files,
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


def resolve_path(raw_path):
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def relpath_or_str(path):
    """Restituisce path relativo alla root quando possibile."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT_DIR / p
    try:
        return str(p.relative_to(ROOT_DIR))
    except Exception:
        return str(p)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="import_training_load.py",
        description="Importa TrainingPeaks e/o Garmin CSV in data/training_load.json",
    )
    parser.add_argument("csv", nargs="*", help="CSV path legacy (auto-detect formato)")
    parser.add_argument("--tp", action="append", default=[], help="CSV TrainingPeaks (ripetibile)")
    parser.add_argument("--garmin", action="append", default=[], help="CSV Garmin (ripetibile)")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    tp_files = [resolve_path(p) for p in args.tp]
    garmin_files = [resolve_path(p) for p in args.garmin]

    # Backward compatibility: positional CSV con auto-detect.
    for raw in args.csv:
        path = resolve_path(raw)
        rows = load_csv_rows(path)
        fmt = detect_csv_format(rows)
        if fmt == "trainingpeaks":
            tp_files.append(path)
        elif fmt == "garmin":
            garmin_files.append(path)
        else:
            print(f"Errore: formato CSV non supportato: {path}")
            sys.exit(1)

    if not tp_files and not garmin_files:
        print("Uso: python3 scripts/import_training_load.py <csv_path> [--tp <file>] [--garmin <file>]")
        sys.exit(1)

    for path in tp_files + garmin_files:
        if not path.exists():
            print(f"Errore: file non trovato: {path}")
            sys.exit(1)

    try:
        payload = build_training_load_payload(tp_files, garmin_files)
    except Exception as exc:
        print(f"Errore parsing CSV: {exc}")
        sys.exit(1)

    ensure_athlete_dirs()
    TRAINING_LOAD_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_changelog_entry(payload["meta"]["source_files"], payload)

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
    print(f"  mode={payload['meta']['mode']} merge={payload.get('merge', {})}")
    print(f"  profile_costs_kcal={payload['profile_costs_kcal']}")


if __name__ == "__main__":
    main()
