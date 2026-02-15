#!/usr/bin/env python3
"""
Running setup interattivo stile coach (Daniels + Pfitz + Canova + Seiler + Hudson).

Crea/aggiorna:
- data/RUNNING_ATHLETE_PROFILE.json
- data/RUNNING_PLAN_CONFIG.json
- knowledge/running-setup-report.md
"""

import json
from datetime import datetime

from import_training_load import (
    append_changelog_entry as append_training_load_changelog_entry,
    build_training_load_payload,
    resolve_path as resolve_csv_path,
)
from athlete_context import athlete_knowledge_dir, data_file, ensure_athlete_dirs, get_athlete_id

PROFILE_FILE = data_file("RUNNING_ATHLETE_PROFILE.json")
CONFIG_FILE = data_file("RUNNING_PLAN_CONFIG.json")
TRAINING_LOAD_FILE = data_file("training_load.json")
REPORT_FILE = athlete_knowledge_dir() / "running-setup-report.md"
CHANGELOG_FILE = data_file("changelog.json")


def ask_text(question, default=None, allow_empty=False):
    while True:
        suffix = f" [{default}]" if default is not None else ""
        ans = input(f"{question}{suffix}: ").strip()
        if not ans and default is not None:
            return str(default)
        if ans or allow_empty:
            return ans
        print("Valore richiesto.")


def ask_float(question, default):
    while True:
        raw = ask_text(question, default=default)
        try:
            return float(str(raw).replace(",", "."))
        except ValueError:
            print("Inserisci un numero valido.")


def ask_int(question, default):
    while True:
        raw = ask_text(question, default=default)
        try:
            return int(raw)
        except ValueError:
            print("Inserisci un intero valido.")


def ask_yes_no(question, default=True):
    d = "Y/n" if default else "y/N"
    raw = ask_text(f"{question} ({d})", default="y" if default else "n")
    return raw.lower() in ("y", "yes", "si", "s")


def ask_choice(question, choices, default_idx=0):
    labels = []
    for i, (key, desc) in enumerate(choices, 1):
        marker = " (default)" if i - 1 == default_idx else ""
        labels.append(f"{i}. {key} - {desc}{marker}")
    print("\n".join(labels))
    while True:
        raw = ask_text(question, default=str(default_idx + 1))
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx][0]
        except ValueError:
            pass
        print("Selezione non valida.")


def ask_csv_paths(prompt):
    """Richiede 0..N path CSV separati da virgola."""
    raw = ask_text(prompt, default="", allow_empty=True)
    if not raw:
        return []
    parts = [x.strip() for x in raw.split(",")]
    return [x for x in parts if x]


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def derive_volume_defaults(training_payload):
    """Deriva default volume medio/picco dallo storico importato."""
    weeks = training_payload.get("weeks", [])
    if not weeks:
        total_km = float(training_payload.get("summary", {}).get("planned_distance_km", 0.0) or 0.0)
        return {"avg_km": round(total_km, 1), "peak_km": round(total_km, 1)}

    weekly_km = [float(w.get("planned_distance_km", 0.0) or 0.0) for w in weeks]
    recent_window = weekly_km[-8:] if len(weekly_km) >= 8 else weekly_km
    avg_km = round(sum(recent_window) / len(recent_window), 1) if recent_window else 0.0
    peak_km = round(max(weekly_km), 1) if weekly_km else avg_km
    return {"avg_km": avg_km, "peak_km": peak_km}


def build_weekly_template(run_days, force_days, long_run_day):
    """
    Costruisce template settimana rispettando run_days/force_days.
    Priorita' sedute running: lungo > qualita > progressivo > easy.
    """
    run_days = max(1, min(6, int(run_days)))
    force_days = max(0, min(2, int(force_days)))

    run_slots = [
        ("Wednesday", "qualita"),
        ("Friday", "progressivo"),
        (long_run_day, "lungo"),
        ("Monday", "easy"),
        ("Sunday", "easy"),
        ("Thursday", "easy"),
    ]
    selected_run = []
    used_days = set()
    for day, day_type in run_slots:
        if day in used_days:
            continue
        selected_run.append((day, day_type))
        used_days.add(day)
        if len(selected_run) >= run_days:
            break

    force_candidates = ["Tuesday", "Thursday"]
    selected_force = []
    for day in force_candidates:
        if len(selected_force) >= force_days:
            break
        if day not in used_days:
            selected_force.append((day, "forza"))
            used_days.add(day)

    session_map = {d: t for d, t in selected_run + selected_force}
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    session_days = [d for d in day_order if d in session_map]
    return session_days, session_map


def compute_weekly_km_params(current_avg_km, max_recent_km, aggressiveness):
    if aggressiveness == "conservative":
        growth = 0.07
        peak_factor = 1.20
    elif aggressiveness == "aggressive":
        growth = 0.11
        peak_factor = 1.40
    else:
        growth = 0.09
        peak_factor = 1.30

    start_km = max(24.0, round(current_avg_km * 0.95, 1))
    peak_km = max(start_km + 8.0, round(max(max_recent_km, current_avg_km) * peak_factor, 1))
    peak_km = min(95.0, peak_km)
    return {
        "start": start_km,
        "peak": peak_km,
        "max_increase_pct": growth,
    }


def intensity_distribution_template(method):
    # Seiler-polarized, Pfitz-pyramidal, balanced hybrid.
    if method == "polarized":
        return {
            "build": {"target_low_pct": 0.82, "target_high_pct": 0.18, "max_moderate_pct": 0.08, "min_high_pct": 0.15},
            "specific": {"target_low_pct": 0.78, "target_high_pct": 0.18, "max_moderate_pct": 0.12, "min_high_pct": 0.15},
            "taper": {"target_low_pct": 0.88, "target_high_pct": 0.10, "max_moderate_pct": 0.08, "min_high_pct": 0.05},
            "race": {"target_low_pct": 0.82, "target_high_pct": 0.13, "max_moderate_pct": 0.08, "min_high_pct": 0.05},
        }
    if method == "pyramidal":
        return {
            "build": {"target_low_pct": 0.75, "target_high_pct": 0.12, "max_moderate_pct": 0.18, "min_high_pct": 0.10},
            "specific": {"target_low_pct": 0.70, "target_high_pct": 0.15, "max_moderate_pct": 0.20, "min_high_pct": 0.12},
            "taper": {"target_low_pct": 0.84, "target_high_pct": 0.08, "max_moderate_pct": 0.10, "min_high_pct": 0.05},
            "race": {"target_low_pct": 0.80, "target_high_pct": 0.12, "max_moderate_pct": 0.10, "min_high_pct": 0.05},
        }
    return {
        "build": {"target_low_pct": 0.80, "target_high_pct": 0.15, "max_moderate_pct": 0.12, "min_high_pct": 0.12},
        "specific": {"target_low_pct": 0.75, "target_high_pct": 0.18, "max_moderate_pct": 0.15, "min_high_pct": 0.14},
        "taper": {"target_low_pct": 0.86, "target_high_pct": 0.09, "max_moderate_pct": 0.10, "min_high_pct": 0.05},
        "race": {"target_low_pct": 0.82, "target_high_pct": 0.12, "max_moderate_pct": 0.10, "min_high_pct": 0.05},
    }


def append_changelog(details):
    data = load_json(CHANGELOG_FILE, {"entries": []})
    data.setdefault("entries", []).append(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "running setup",
            "details": details,
        }
    )
    CHANGELOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print("=== Running Setup - Colloquio Coach Integrato ===")
    print("Approcci guida: Daniels (zone), Pfitzinger (periodizzazione), Canova (specificita), Seiler (TID), Hudson (adattivita).")
    print(f"Atleta: {get_athlete_id()}")
    print()

    athlete_name = ask_text("Nome atleta", default="Andrea")
    goal_race_name = ask_text("Gara obiettivo principale", default="Maratona Latina")
    goal_race_date = ask_text("Data gara obiettivo (YYYY-MM-DD)", default="2026-12-06")
    target_pace = ask_text("Ritmo target gara (es. 4:00/km)", default="4:00/km")

    print("\nStato attuale performance:")
    tp_paths = ask_csv_paths("CSV TrainingPeaks (uno o piu', separati da virgola; invio se nessuno)")
    garmin_paths = ask_csv_paths("CSV Garmin (uno o piu', separati da virgola; invio se nessuno)")
    while not tp_paths and not garmin_paths:
        print("Inserisci almeno un CSV storico (TrainingPeaks o Garmin).")
        tp_paths = ask_csv_paths("CSV TrainingPeaks")
        garmin_paths = ask_csv_paths("CSV Garmin")

    tp_files = [resolve_csv_path(p) for p in tp_paths]
    garmin_files = [resolve_csv_path(p) for p in garmin_paths]
    for csv_file in tp_files + garmin_files:
        if not csv_file.exists():
            print(f"Errore: file non trovato: {csv_file}")
            return

    try:
        training_payload = build_training_load_payload(tp_files, garmin_files)
    except Exception as exc:
        print(f"Errore import CSV storico: {exc}")
        return

    volume_defaults = derive_volume_defaults(training_payload)
    current_avg_km = ask_float(
        "Volume medio attuale km/settimana (default da storico importato)",
        default=volume_defaults["avg_km"] if volume_defaults["avg_km"] > 0 else 38,
    )
    max_recent_km = ask_float(
        "Picco recente km/settimana (default da storico importato)",
        default=volume_defaults["peak_km"] if volume_defaults["peak_km"] > 0 else 50,
    )
    existing_profile = load_json(PROFILE_FILE, {})
    default_5k = existing_profile.get("athlete", {}).get("current_5k", "18:26") if isinstance(existing_profile, dict) else "18:26"
    current_5k = ask_text("PB/ultimo test 5km (mm:ss)", default=default_5k)

    print("\nDisponibilita settimanale (giorni disponibili per correre):")
    run_days = ask_int("Quanti giorni running/sett", default=4)
    force_days = ask_int("Quanti giorni forza/sett", default=2)
    long_run_day = ask_choice(
        "Giorno preferito per lungo",
        [
            ("Saturday", "Classico pre-gara domenica"),
            ("Sunday", "Lungo domenicale"),
            ("Friday", "Anticipo lungo"),
        ],
        default_idx=0,
    )

    method = ask_choice(
        "Metodo preferito per distribuzione intensita (TID)",
        [
            ("polarized", "Seiler-style 80/20"),
            ("balanced", "Ibrido Daniels/Pfitz/Canova"),
            ("pyramidal", "Pfitz-style piramidale"),
        ],
        default_idx=0,
    )
    aggressiveness = ask_choice(
        "Aggressivita progressione volume",
        [
            ("conservative", "Più prudente, rischio infortuni ridotto"),
            ("balanced", "Progressione equilibrata"),
            ("aggressive", "Più spinta, richiede recupero alto"),
        ],
        default_idx=1,
    )

    recovery_score = ask_int("Recupero medio percepito (1-10)", default=7)
    sleep_hours = ask_float("Ore sonno medie/notte", default=7.0)
    injury_risk = ask_choice(
        "Stato infortuni/fragilita attuale",
        [
            ("low", "Nessun problema rilevante"),
            ("medium", "Fastidi occasionali"),
            ("high", "Fragilita o infortuni ricorrenti"),
        ],
        default_idx=0,
    )
    confirm_force = ask_yes_no("Confermi vincolo forza 2x/sett come non negoziabile?", default=True)

    weekly = compute_weekly_km_params(current_avg_km, max_recent_km, aggressiveness)
    intensity_dist = intensity_distribution_template(method)

    # Costruzione session template giorni rispettando run_days/force_days.
    session_days, types = build_weekly_template(run_days, force_days, long_run_day)

    # Load/merge config esistente
    config = load_json(CONFIG_FILE, {})
    config.setdefault("meta", {})
    config["meta"]["version"] = "v1.1"
    config["meta"]["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    defaults = config.setdefault("defaults", {})
    defaults["session_days"] = session_days
    defaults["session_types_by_day"] = types
    defaults.setdefault("weekly_km", {})
    defaults["weekly_km"]["start"] = weekly["start"]
    defaults["weekly_km"]["peak"] = weekly["peak"]
    defaults["weekly_km"]["max_increase_pct"] = weekly["max_increase_pct"]
    defaults.setdefault("weekly_km", {}).setdefault("deload_every_n_weeks", 4)
    defaults.setdefault("weekly_km", {}).setdefault("deload_drop_pct", 0.18 if aggressiveness != "aggressive" else 0.15)
    defaults.setdefault("taper", {})
    defaults["taper"].setdefault("weeks", 2)
    defaults["taper"].setdefault("drop_pct_week_minus_2", 0.20)
    defaults["taper"].setdefault("drop_pct_week_minus_1", 0.35)
    defaults["intensity_distribution"] = intensity_dist
    defaults.setdefault("session_shares", {"easy": 0.20, "qualita": 0.26, "progressivo": 0.22, "lungo": 0.32})

    planning_defaults = config.setdefault("planning_defaults", {})
    planning_defaults["goal_race_name"] = goal_race_name
    planning_defaults["goal_race_date"] = goal_race_date
    planning_defaults["target_pace"] = target_pace

    # Profile atleta
    profile = {
        "meta": {
            "version": "v1.0",
            "updated_at": datetime.now().isoformat(),
        },
        "athlete": {
            "name": athlete_name,
            "current_5k": current_5k,
            "current_avg_km_per_week": current_avg_km,
            "max_recent_km_per_week": max_recent_km,
            "sleep_hours": sleep_hours,
            "recovery_score": recovery_score,
            "injury_risk": injury_risk,
        },
        "goal": {
            "race_name": goal_race_name,
            "race_date": goal_race_date,
            "target_pace": target_pace,
        },
        "preferences": {
            "run_days_per_week": run_days,
            "strength_days_per_week": force_days,
            "long_run_day": long_run_day,
            "tid_method": method,
            "aggressiveness": aggressiveness,
            "force_twice_non_negotiable": confirm_force,
        },
        "coach_blend_notes": [
            "Daniels: uso zone/ritmi e lavoro qualità strutturato.",
            "Pfitzinger: progressione volume + scarico periodico + long run centrale.",
            "Canova: specificità ritmo gara in fase specific.",
            "Seiler: guardrail TID per evitare eccesso zona grigia.",
            "Hudson: margine adattivo su recupero e stress.",
        ],
    }

    # Report leggibile
    report_lines = [
        "# Running Setup Report",
        "",
        f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Athlete: {athlete_name}",
        f"- Goal: {goal_race_name} ({goal_race_date}) @ {target_pace}",
        "",
        "## Stato Attuale",
        f"- 5km: {current_5k}",
        f"- Volume medio: {current_avg_km:.1f} km/sett",
        f"- Picco recente: {max_recent_km:.1f} km/sett",
        f"- Recupero percepito: {recovery_score}/10",
        f"- Sonno medio: {sleep_hours:.1f} h",
        f"- Rischio infortuni: {injury_risk}",
        "",
        "## Strategia Decisa",
        f"- Metodo TID: {method}",
        f"- Aggressivita: {aggressiveness}",
        f"- Running days: {run_days}/sett",
        f"- Forza days: {force_days}/sett",
        f"- Lungo: {long_run_day}",
        "",
        "## Storico Importato",
        f"- Mode: {training_payload['meta']['mode']}",
        f"- Sessioni: {training_payload['summary']['sessions_count']}",
        f"- Periodo: {training_payload['summary']['date_range']['from']} -> {training_payload['summary']['date_range']['to']}",
        f"- Distanza: {training_payload['summary']['planned_distance_km']} km",
        f"- Durata: {training_payload['summary']['planned_duration_h']} h",
        f"- Merge: {training_payload.get('merge', {})}",
        "",
        "## Parametri Applicati al Motore",
        f"- weekly_km.start: {weekly['start']}",
        f"- weekly_km.peak: {weekly['peak']}",
        f"- weekly_km.max_increase_pct: {weekly['max_increase_pct']}",
        f"- force 2x non negoziabile: {confirm_force}",
        "",
        "## Prossimo Passo",
        "```bash",
        f"./tv running generate --from {datetime.now().strftime('%Y-%m-01')} --to {goal_race_date} --goal-race {goal_race_date} --enforce-tid",
        "./tv running summary",
        "```",
        "",
    ]

    ensure_athlete_dirs()
    PROFILE_FILE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    TRAINING_LOAD_FILE.write_text(json.dumps(training_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_training_load_changelog_entry(training_payload["meta"]["source_files"], training_payload)
    REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

    append_changelog(
        {
            "athlete": athlete_name,
            "goal_race": {"name": goal_race_name, "date": goal_race_date},
            "tid_method": method,
            "aggressiveness": aggressiveness,
            "training_load_import": {
                "mode": training_payload["meta"]["mode"],
                "sessions_count": training_payload["summary"]["sessions_count"],
                "date_from": training_payload["summary"]["date_range"]["from"],
                "date_to": training_payload["summary"]["date_range"]["to"],
            },
            "updated_files": [
                "data/RUNNING_ATHLETE_PROFILE.json",
                "data/RUNNING_PLAN_CONFIG.json",
                "data/training_load.json",
                "knowledge/running-setup-report.md",
            ],
        }
    )

    print("\n[OK] Running setup completato.")
    print(f"- Profile: {PROFILE_FILE}")
    print(f"- Config:  {CONFIG_FILE}")
    print(f"- Training Load: {TRAINING_LOAD_FILE}")
    print(f"- Report:  {REPORT_FILE}")


if __name__ == "__main__":
    main()
