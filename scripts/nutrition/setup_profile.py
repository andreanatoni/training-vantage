#!/usr/bin/env python3
"""Wizard interattivo per raccolta profilo nutrizione atleta (core + BIA avanzata)."""

import argparse
import json
import os
from datetime import datetime, timezone

try:
    from scripts.athlete_context import (
        DEFAULT_ATHLETE_ID,
        athlete_knowledge_dir,
        data_file,
        ensure_athlete_dirs,
        normalize_athlete_id,
        relpath_or_str,
    )
except ModuleNotFoundError:
    from athlete_context import (  # type: ignore
        DEFAULT_ATHLETE_ID,
        athlete_knowledge_dir,
        data_file,
        ensure_athlete_dirs,
        normalize_athlete_id,
        relpath_or_str,
    )


GOAL_CHOICES = [
    ("fat_loss", "Riduzione massa grassa"),
    ("maintenance", "Mantenimento"),
    ("performance", "Performance sportiva"),
    ("recomposition", "Ricomp. corporea"),
]

SEX_CHOICES = [
    ("male", "Uomo"),
    ("female", "Donna"),
    ("other", "Altro"),
]

TRAINING_TIME_CHOICES = [
    ("morning", "Mattina"),
    ("lunch", "Pausa pranzo"),
    ("evening", "Sera"),
    ("mixed", "Orari misti"),
]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Wizard setup profilo nutrizione (core + BIA avanzata).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sovrascrivi profilo esistente senza chiedere conferma.",
    )
    return parser.parse_args(argv)


def iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def runtime_paths_for_athlete(athlete_id):
    os.environ["TV_ATHLETE_ID"] = athlete_id
    return {
        "profile_json": data_file("NUTRITION_PROFILE.json"),
        "profile_md": athlete_knowledge_dir() / "nutrition-profile.md",
    }


def resolve_target_athlete_id(athlete_name):
    current_id = normalize_athlete_id(os.environ.get("TV_ATHLETE_ID", DEFAULT_ATHLETE_ID))
    if current_id != DEFAULT_ATHLETE_ID:
        return current_id
    return normalize_athlete_id(athlete_name)


def ask_text(prompt, required=False, allow_empty=False):
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        if allow_empty:
            return ""
        if not required:
            return ""
        print("Valore richiesto.")


def ask_float(prompt, min_value=None, max_value=None):
    while True:
        raw = ask_text(prompt, required=True)
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            print("Inserisci un numero valido.")
            continue
        if min_value is not None and value < min_value:
            print(f"Valore minimo: {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"Valore massimo: {max_value}.")
            continue
        return value


def ask_int(prompt, min_value=None, max_value=None):
    while True:
        raw = ask_text(prompt, required=True)
        try:
            value = int(raw)
        except ValueError:
            print("Inserisci un intero valido.")
            continue
        if min_value is not None and value < min_value:
            print(f"Valore minimo: {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"Valore massimo: {max_value}.")
            continue
        return value


def ask_yes_no(prompt, default=None):
    suffix = "(y/n)"
    if default is True:
        suffix = "(Y/n)"
    elif default is False:
        suffix = "(y/N)"
    while True:
        raw = input(f"{prompt} {suffix}: ").strip().lower()
        if not raw and default is not None:
            return default
        if raw in {"y", "yes", "s", "si"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Risposta non valida. Usa y oppure n.")


def ask_choice(prompt, choices):
    for idx, (key, desc) in enumerate(choices, start=1):
        print(f"{idx}. {key} - {desc}")
    while True:
        raw = ask_text(prompt, required=True)
        try:
            pick = int(raw)
        except ValueError:
            print("Inserisci il numero della scelta.")
            continue
        if 1 <= pick <= len(choices):
            return choices[pick - 1][0]
        print("Scelta fuori range.")


def ask_date_yyyy_mm_dd(prompt):
    while True:
        value = ask_text(prompt, required=True)
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            print("Formato non valido. Usa YYYY-MM-DD.")


def write_markdown(path, payload):
    core = payload["body_core"]
    profile = payload["profile"]
    training = payload["training_context"]
    bia = payload.get("advanced_bia")

    lines = [
        "# Nutrition Profile",
        "",
        f"- Athlete ID: `{payload['athlete_id']}`",
        f"- Nome atleta: {profile['athlete_name']}",
        f"- Goal: `{profile['goal']}`",
        f"- Generato: {payload['meta']['generated_at']}",
        "",
        "## Core",
        "",
        f"- Sesso: `{core['sex']}`",
        f"- Eta': {core['age_years']} anni",
        f"- Altezza: {core['height_cm']} cm",
        f"- Peso: {core['weight_kg']} kg",
        "",
        "## Training Context",
        "",
        f"- Running days/week: {training['running_days_per_week']}",
        f"- Strength days/week: {training['strength_days_per_week']}",
        f"- Orario allenamento tipico: `{training['typical_training_time']}`",
        "",
        "## Advanced BIA",
        "",
    ]

    if bia:
        lines.extend(
            [
                f"- Data misura: {bia['measured_at']}",
                f"- Fonte/device: {bia['source_device']}",
                f"- Body Fat: {bia['body_fat_pct']} %",
                f"- FFM: {bia['ffm_kg']} kg",
                f"- BMR (Katch-McArdle): {bia['bmr_katch_kcal']} kcal",
                f"- Massa muscolare: {bia['muscle_mass_kg']} kg",
                f"- Grasso sottocutaneo: {bia['subcutaneous_fat_pct']} %",
                f"- Grasso viscerale: {bia['visceral_fat_level']} livello",
                f"- Acqua corporea: {bia['body_water_pct']} %",
                f"- Massa ossea: {bia['bone_mass_kg']} kg",
                f"- Eta' metabolica: {bia['metabolic_age_years']} anni",
            ]
        )
    else:
        lines.append("- Non fornita")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_wizard(args):
    print("=== Nutrition Setup Profile - Profilazione Atleta ===")

    athlete_name = ask_text("Nome atleta", required=True)
    target_athlete_id = resolve_target_athlete_id(athlete_name)
    paths = runtime_paths_for_athlete(target_athlete_id)
    ensure_athlete_dirs()

    print(f"Atleta target: {target_athlete_id}")

    profile_json = paths["profile_json"]
    if profile_json.exists() and not args.force:
        if not ask_yes_no("Profilo nutrizione gia presente. Vuoi sovrascriverlo?", default=True):
            print("Operazione annullata.")
            return 1

    print("\nProfilo obiettivo:")
    goal = ask_choice("Obiettivo principale", GOAL_CHOICES)

    print("\nDati core:")
    sex = ask_choice("Sesso", SEX_CHOICES)
    age_years = ask_int("Eta' (anni)", min_value=10, max_value=100)
    height_cm = ask_float("Altezza (cm)", min_value=120, max_value=230)
    weight_kg = ask_float("Peso attuale (kg)", min_value=30, max_value=250)

    print("\nContesto allenamento:")
    running_days = ask_int("Quanti giorni running/sett", min_value=0, max_value=7)
    strength_days = ask_int("Quanti giorni forza/sett", min_value=0, max_value=7)
    typical_training_time = ask_choice("Fascia oraria allenamento tipica", TRAINING_TIME_CHOICES)

    advanced_bia = None
    print("\nDati avanzati BIA:")
    if ask_yes_no("Vuoi inserire i dati avanzati impedenziometrici?", default=False):
        measured_at = ask_date_yyyy_mm_dd("Data misurazione BIA (YYYY-MM-DD)")
        source_device = ask_text("Fonte/device (es. Tanita BC-601, Withings, Manuale)", required=True)
        advanced_bia = {
            "measured_at": measured_at,
            "source_device": source_device,
            "body_fat_pct": round(ask_float("Body Fat (%)", min_value=2, max_value=70), 2),
            "ffm_kg": round(ask_float("FFM (kg)", min_value=20, max_value=200), 2),
            "bmr_katch_kcal": int(ask_float("BMR (Katch-McArdle) (kcal)", min_value=800, max_value=4000)),
            "muscle_mass_kg": round(ask_float("Massa muscolare (kg)", min_value=10, max_value=150), 2),
            "subcutaneous_fat_pct": round(ask_float("Grasso sottocutaneo (%)", min_value=2, max_value=60), 2),
            "visceral_fat_level": ask_int("Grasso viscerale (livello)", min_value=1, max_value=59),
            "body_water_pct": round(ask_float("Acqua corporea (%)", min_value=20, max_value=80), 2),
            "bone_mass_kg": round(ask_float("Massa ossea (kg)", min_value=1, max_value=8), 2),
            "metabolic_age_years": ask_int("Eta' metabolica (anni)", min_value=10, max_value=100),
        }

    payload = {
        "meta": {
            "schema_version": "1.0",
            "generated_at": iso_now(),
            "source": "nutrition_setup_profile_wizard",
        },
        "athlete_id": target_athlete_id,
        "profile": {
            "athlete_name": athlete_name,
            "goal": goal,
        },
        "body_core": {
            "sex": sex,
            "age_years": age_years,
            "height_cm": round(height_cm, 1),
            "weight_kg": round(weight_kg, 2),
        },
        "training_context": {
            "running_days_per_week": running_days,
            "strength_days_per_week": strength_days,
            "typical_training_time": typical_training_time,
        },
        "advanced_bia": advanced_bia,
    }

    profile_json.parent.mkdir(parents=True, exist_ok=True)
    profile_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(paths["profile_md"], payload)

    print("\n[OK] Nutrition profile completato.")
    print(f"- Profile JSON: {relpath_or_str(profile_json)}")
    print(f"- Profile MD:   {relpath_or_str(paths['profile_md'])}")
    return 0


def main(argv=None):
    args = parse_args(argv)
    try:
        return run_wizard(args)
    except KeyboardInterrupt:
        print("\nOperazione annullata.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
