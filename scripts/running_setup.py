#!/usr/bin/env python3
"""
Running setup interattivo stile coach (Daniels + Pfitz + Canova + Seiler + Hudson).

Crea/aggiorna:
- data/RUNNING_ATHLETE_PROFILE.json
- data/RUNNING_PLAN_CONFIG.json
- knowledge/running-setup-report.md
"""

import json
import argparse
import sys
import os
from datetime import datetime

from import_training_load import (
    append_changelog_entry as append_training_load_changelog_entry,
    build_training_load_payload,
    resolve_path as resolve_csv_path,
)
from athlete_context import (
    DEFAULT_ATHLETE_ID,
    athlete_knowledge_dir,
    data_file,
    ensure_athlete_dirs,
    get_athlete_id,
    normalize_athlete_id,
    relpath_or_str,
)

def runtime_paths_for_athlete(athlete_id):
    os.environ["TV_ATHLETE_ID"] = athlete_id
    return {
        "profile": data_file("RUNNING_ATHLETE_PROFILE.json"),
        "config": data_file("RUNNING_PLAN_CONFIG.json"),
        "training_load": data_file("training_load.json"),
        "report": athlete_knowledge_dir() / "running-setup-report.md",
        "changelog": data_file("changelog.json"),
    }


def resolve_target_athlete_id(athlete_name):
    current_id = normalize_athlete_id(os.environ.get("TV_ATHLETE_ID", DEFAULT_ATHLETE_ID))
    if current_id != DEFAULT_ATHLETE_ID:
        return current_id
    return normalize_athlete_id(athlete_name)


def ask_text(question, allow_empty=False):
    while True:
        ans = input(f"{question}: ").strip()
        if ans or allow_empty:
            return ans
        print("Valore richiesto.")


def ask_float(question):
    while True:
        raw = ask_text(question)
        try:
            return float(str(raw).replace(",", "."))
        except ValueError:
            print("Inserisci un numero valido.")


def ask_int(question):
    while True:
        raw = ask_text(question)
        try:
            return int(raw)
        except ValueError:
            print("Inserisci un intero valido.")


def ask_yes_no(question):
    while True:
        raw = ask_text(f"{question} (y/n)")
        txt = raw.lower()
        if txt in ("y", "yes", "si", "s"):
            return True
        if txt in ("n", "no"):
            return False
        print("Risposta non valida. Inserisci y oppure n.")


def ask_choice(question, choices):
    print(question)
    labels = []
    for i, (key, desc) in enumerate(choices, 1):
        labels.append(f"{i}. {key} - {desc}")
    print("\n".join(labels))
    while True:
        raw = ask_text("Seleziona opzione")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx][0]
        except ValueError:
            pass
        print("Selezione non valida.")


def ask_csv_paths(prompt):
    """Richiede 0..N path CSV separati da virgola."""
    raw = ask_text(prompt, allow_empty=True)
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


def build_manual_training_payload(athlete_id):
    """Payload training_load minimale quando non ci sono CSV storici."""
    return {
        "meta": {
            "version": "v2.0",
            "generated_at": datetime.now().isoformat(),
            "athlete_id": athlete_id,
            "source_file": None,
            "source_files": {"trainingpeaks": [], "garmin": []},
            "mode": "manual_no_history",
            "weight_used_kg": None,
        },
        "assumptions": {
            "energy_model": "N/A (manual setup senza storico CSV)",
            "met_by_day_type": {},
        },
        "merge": {"matched": 0, "tp_only": 0, "garmin_only": 0},
        "summary": {
            "sessions_count": 0,
            "date_range": {"from": None, "to": None},
            "planned_distance_km": 0.0,
            "planned_duration_h": 0.0,
            "estimated_energy_kcal": 0,
        },
        "profile_costs_kcal": {},
        "weeks": [],
        "sessions": [],
    }


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


def estimate_no_history_defaults(run_days, experience_level):
    """Stima prudente volume per atleta senza storico strutturato."""
    run_days = max(2, min(6, int(run_days)))
    if experience_level == "beginner":
        avg_km = max(14.0, run_days * 4.0)
        peak_km = max(avg_km + 3.0, avg_km * 1.20)
        min_start_km = 16.0
    elif experience_level == "trained":
        avg_km = max(22.0, run_days * 6.0)
        peak_km = max(avg_km + 5.0, avg_km * 1.30)
        min_start_km = 20.0
    else:
        # returning: ex-runner che riparte, oppure livello intermedio senza dati storici.
        avg_km = max(18.0, run_days * 5.0)
        peak_km = max(avg_km + 4.0, avg_km * 1.25)
        min_start_km = 18.0
    return {
        "avg_km": round(avg_km, 1),
        "peak_km": round(peak_km, 1),
        "min_start_km": round(min_start_km, 1),
    }


def compute_weekly_km_params(current_avg_km, max_recent_km, aggressiveness, min_start_km=24.0):
    if aggressiveness == "conservative":
        growth = 0.07
        peak_factor = 1.20
    elif aggressiveness == "aggressive":
        growth = 0.11
        peak_factor = 1.40
    else:
        growth = 0.09
        peak_factor = 1.30

    start_km = max(float(min_start_km), round(current_avg_km * 0.95, 1))
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


def append_setup_changelog(changelog_file, details):
    data = load_json(changelog_file, {"entries": []})
    data.setdefault("entries", []).append(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "running setup",
            "details": details,
        }
    )
    changelog_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_days(run_days, force_days):
    """Normalizza giorni settimanali entro range supportati dal motore."""
    run_in = int(run_days)
    force_in = int(force_days)
    run_out = max(1, min(6, run_in))
    force_out = max(0, min(2, force_in))
    return run_out, force_out, (run_in != run_out or force_in != force_out)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="running_setup.py",
        description="Colloquio coach interattivo per configurare profilo e piano running.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Salta import storico CSV e prosegue in modalita manuale.",
    )
    return parser.parse_args(argv)


def main(no_history=False):
    print("=== Running Setup - Colloquio Coach Integrato ===")
    print("Approcci guida: Daniels (zone), Pfitzinger (periodizzazione), Canova (specificita), Seiler (TID), Hudson (adattivita).")
    print()

    athlete_name = ask_text("Nome atleta")
    target_athlete_id = resolve_target_athlete_id(athlete_name)
    paths = runtime_paths_for_athlete(target_athlete_id)
    print(f"Destinazione dati atleta: {target_athlete_id}")
    if target_athlete_id != normalize_athlete_id(athlete_name):
        print(
            "Nota: target atleta forzato da --athlete/TV_ATHLETE_ID "
            f"({target_athlete_id}), nome atleta salvato: {athlete_name}."
        )
    goal_race_name = ask_text("Gara obiettivo principale")
    goal_race_date = ask_text("Data gara obiettivo (YYYY-MM-DD)")
    target_pace = ask_text("Ritmo target gara (es. 4:00/km)")

    print("\nStato attuale performance:")
    if no_history:
        training_payload = build_manual_training_payload(target_athlete_id)
        print("Modalita manuale forzata da flag --no-history (nessun CSV richiesto).")
    else:
        tp_paths = ask_csv_paths("CSV TrainingPeaks (uno o piu', separati da virgola; invio se nessuno)")
        garmin_paths = ask_csv_paths("CSV Garmin (uno o piu', separati da virgola; invio se nessuno)")
        while not tp_paths and not garmin_paths:
            print("Nessun CSV storico inserito.")
            continue_without_history = ask_yes_no("Vuoi continuare senza storico (impostazione manuale)?")
            if continue_without_history:
                break
            print("Inserisci almeno un CSV storico (TrainingPeaks o Garmin).")
            tp_paths = ask_csv_paths("CSV TrainingPeaks")
            garmin_paths = ask_csv_paths("CSV Garmin")

    if not no_history and (tp_paths or garmin_paths):
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
    else:
        if not no_history:
            training_payload = build_manual_training_payload(target_athlete_id)
            print("Procedo in modalita manuale senza storico CSV.")

    print("\nDisponibilita settimanale (giorni disponibili per correre):")
    run_days_raw = ask_int("Quanti giorni running/sett")
    force_days_raw = ask_int("Quanti giorni forza/sett")
    run_days, force_days, was_clamped = normalize_days(run_days_raw, force_days_raw)
    if was_clamped:
        print(
            "Valori giorni normalizzati per limiti motore: "
            f"running {run_days_raw}->{run_days}, forza {force_days_raw}->{force_days}."
        )
    long_run_day = ask_choice(
        "Giorno preferito per lungo",
        [
            ("Saturday", "Classico pre-gara domenica"),
            ("Sunday", "Lungo domenicale"),
            ("Friday", "Anticipo lungo"),
        ],
    )

    no_history_mode = training_payload.get("meta", {}).get("mode") == "manual_no_history"
    no_history_bootstrap_mode = "manual"
    no_history_experience_level = None
    min_start_km = 24.0

    volume_defaults = derive_volume_defaults(training_payload)
    suggested_avg_km = volume_defaults["avg_km"] if volume_defaults["avg_km"] > 0 else None
    suggested_peak_km = volume_defaults["peak_km"] if volume_defaults["peak_km"] > 0 else None

    if no_history_mode:
        min_start_km = 16.0
        if suggested_avg_km is None and suggested_peak_km is None:
            no_history_bootstrap_mode = ask_choice(
                "Nessuno storico: come impostare il volume iniziale?",
                [
                    ("auto", "Stima prudente automatica (consigliato)"),
                    ("manual", "Inserisco manualmente volume medio e picco"),
                ],
            )
            if no_history_bootstrap_mode == "auto":
                no_history_experience_level = ask_choice(
                    "Livello attuale senza storico tracciato",
                    [
                        ("returning", "Ripartenza/intermedio (default consigliato)"),
                        ("beginner", "Principiante o ritorno dopo lunga pausa"),
                        ("trained", "Allenato con continuita ma senza dati importati"),
                    ],
                )
                estimate = estimate_no_history_defaults(run_days, no_history_experience_level)
                suggested_avg_km = estimate["avg_km"]
                suggested_peak_km = estimate["peak_km"]
                min_start_km = estimate["min_start_km"]
                print(
                    "Stima no-history: volume medio suggerito {avg:.1f} km/sett, picco recente suggerito {peak:.1f} km/sett.".format(
                        avg=suggested_avg_km,
                        peak=suggested_peak_km,
                    )
                )
            else:
                print("Modalita manuale: inserisci volume medio e picco recente.")

    avg_label = "Volume medio attuale km/settimana"
    peak_label = "Picco recente km/settimana"
    if suggested_avg_km is not None:
        avg_label += f" (suggerito: {suggested_avg_km:.1f})"
    if suggested_peak_km is not None:
        peak_label += f" (suggerito: {suggested_peak_km:.1f})"

    current_avg_km = ask_float(
        avg_label,
    )
    max_recent_km = ask_float(
        peak_label,
    )
    current_5k = ask_text("PB/ultimo test 5km (mm:ss)")

    method = ask_choice(
        "Metodo preferito per distribuzione intensita (TID)",
        [
            ("polarized", "Seiler-style 80/20"),
            ("balanced", "Ibrido Daniels/Pfitz/Canova"),
            ("pyramidal", "Pfitz-style piramidale"),
        ],
    )
    aggressiveness = ask_choice(
        "Aggressivita progressione volume",
        [
            ("conservative", "Più prudente, rischio infortuni ridotto"),
            ("balanced", "Progressione equilibrata"),
            ("aggressive", "Più spinta, richiede recupero alto"),
        ],
    )
    long_run_strategy = ask_choice(
        "Strategia lunghi in fase specifica",
        [
            ("with_race_blocks", "Mix: lungo classico + lunghi con blocchi ritmo gara"),
            ("classic_only", "Sempre lungo classico (senza blocchi ritmo gara)"),
        ],
    )

    recovery_score = ask_int("Recupero medio percepito (1-10)")
    sleep_hours = ask_float("Ore sonno medie/notte")
    injury_risk = ask_choice(
        "Stato infortuni/fragilita attuale",
        [
            ("low", "Nessun problema rilevante"),
            ("medium", "Fastidi occasionali"),
            ("high", "Fragilita o infortuni ricorrenti"),
        ],
    )
    confirm_force = force_days >= 1

    weekly = compute_weekly_km_params(current_avg_km, max_recent_km, aggressiveness, min_start_km=min_start_km)
    intensity_dist = intensity_distribution_template(method)

    # Costruzione session template giorni rispettando run_days/force_days.
    session_days, types = build_weekly_template(run_days, force_days, long_run_day)

    # Load/merge config esistente
    config = load_json(paths["config"], {})
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
    defaults["long_run_strategy"] = long_run_strategy

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
            "long_run_strategy": long_run_strategy,
            "no_history_bootstrap_mode": no_history_bootstrap_mode if no_history_mode else None,
            "no_history_experience_level": no_history_experience_level if no_history_mode else None,
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
        f"- Strategia lungo (fase specifica): {long_run_strategy}",
        f"- Bootstrap no-history: {no_history_bootstrap_mode}" if no_history_mode else "- Bootstrap no-history: N/A (storico disponibile)",
        f"- Livello no-history: {no_history_experience_level}" if no_history_mode and no_history_experience_level else "- Livello no-history: N/A",
        "",
        "## Storico Importato",
        f"- Mode: {training_payload['meta']['mode']}",
        f"- Sessioni: {training_payload['summary']['sessions_count']}",
        f"- Periodo: {training_payload['summary']['date_range']['from'] or 'N/A'} -> {training_payload['summary']['date_range']['to'] or 'N/A'}",
        f"- Distanza: {training_payload['summary']['planned_distance_km']} km",
        f"- Durata: {training_payload['summary']['planned_duration_h']} h",
        f"- Merge: {training_payload.get('merge', {})}",
        "",
        "## Parametri Applicati al Motore",
        f"- weekly_km.start: {weekly['start']}",
        f"- weekly_km.peak: {weekly['peak']}",
        f"- weekly_km.max_increase_pct: {weekly['max_increase_pct']}",
        f"- force non negoziabile (auto da giorni forza): {confirm_force}",
        "",
        "## Prossimo Passo",
        "```bash",
        f"./tv running generate --from {datetime.now().strftime('%Y-%m-01')} --to {goal_race_date} --goal-race {goal_race_date} --enforce-tid",
        "./tv running summary",
        "```",
        "",
    ]

    ensure_athlete_dirs()
    paths["profile"].write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["config"].write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["training_load"].write_text(json.dumps(training_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if training_payload["meta"].get("mode") != "manual_no_history":
        append_training_load_changelog_entry(training_payload["meta"]["source_files"], training_payload)
    paths["report"].write_text("\n".join(report_lines), encoding="utf-8")

    append_setup_changelog(
        paths["changelog"],
        {
            "athlete": athlete_name,
            "athlete_id": target_athlete_id,
            "goal_race": {"name": goal_race_name, "date": goal_race_date},
            "tid_method": method,
            "aggressiveness": aggressiveness,
            "long_run_strategy": long_run_strategy,
            "no_history_bootstrap_mode": no_history_bootstrap_mode if no_history_mode else None,
            "no_history_experience_level": no_history_experience_level if no_history_mode else None,
            "training_load_import": {
                "mode": training_payload["meta"]["mode"],
                "sessions_count": training_payload["summary"]["sessions_count"],
                "date_from": training_payload["summary"]["date_range"]["from"],
                "date_to": training_payload["summary"]["date_range"]["to"],
            },
            "updated_files": [
                relpath_or_str(paths["profile"]),
                relpath_or_str(paths["config"]),
                relpath_or_str(paths["training_load"]),
                relpath_or_str(paths["report"]),
            ],
        }
    )

    print("\n[OK] Running setup completato.")
    print(f"- Profile: {paths['profile']}")
    print(f"- Config:  {paths['config']}")
    print(f"- Training Load: {paths['training_load']}")
    print(f"- Report:  {paths['report']}")


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(no_history=args.no_history)
