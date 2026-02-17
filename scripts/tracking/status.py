#!/usr/bin/env python3
"""
/status

Mostra stato attuale del programma:
- Ultima pesata + trend
- Zone attuali + data test
- Settimana corrente nel piano
- Giorni a prossima gara
- Alerts attivi
"""

import re
from datetime import datetime, timedelta
from scripts.common.io import load_json
from scripts.common.paths import athlete_plans_dir, data_file, get_athlete_id
from scripts.integration_config import get_next_race, load_integration_config_strict

# Paths
COMP_FILE = data_file("composition.json")
ZONES_FILE = data_file("zones.json")
RUNNING_LOG_FILE = data_file("running-log.json")

def get_current_week(plan_start_date):
    """Calcola settimana corrente nel piano"""
    today = datetime.now()
    delta = today - plan_start_date
    week_num = (delta.days // 7) + 1

    # Determina mesociclo
    if 1 <= week_num <= 4:
        meso = "M1"
    elif 5 <= week_num <= 8:
        meso = "M2"
    elif 9 <= week_num <= 12:
        meso = "M3"
    elif 13 <= week_num <= 16:
        meso = "M4"
    elif 17 <= week_num <= 20:
        meso = "M5"
    else:
        meso = "Post-piano"

    return week_num, meso


def get_composition_trend(data):
    """Calcola trend ultimi 2-3 mesi"""
    measurements = data['measurements']

    if len(measurements) < 2:
        return None

    # Ultimi 3 mesi
    today = datetime.now()
    three_months_ago = today - timedelta(days=90)

    recent = [
        m for m in measurements
        if datetime.strptime(m['date'], '%Y-%m-%d') >= three_months_ago
    ]

    if len(recent) < 2:
        recent = measurements[-3:]  # Fallback alle ultime 3

    first = recent[0]
    last = recent[-1]

    delta_weight = last['weight'] - first['weight']
    delta_ffm = last['ffm'] - first['ffm']

    days = (datetime.strptime(last['date'], '%Y-%m-%d') -
            datetime.strptime(first['date'], '%Y-%m-%d')).days

    return {
        'period': f"{first['date']} → {last['date']} ({days} giorni)",
        'weight': delta_weight,
        'ffm': delta_ffm,
        'measurements': len(recent)
    }


def check_stale_plans():
    """Verifica piani nutrizionali STALE confrontando META con composition.json"""
    plans_dir = athlete_plans_dir()

    if not plans_dir.exists():
        return []

    stale = []
    comp_data = load_json(COMP_FILE)
    latest = comp_data['measurements'][-1]
    current_ffm = float(latest['ffm'])
    current_bmr = int(latest['bmr'])

    for plan_file in plans_dir.glob("*.md"):
        with open(plan_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Compatibilità con vecchio marker esplicito
        if 'Status: STALE' in content:
            stale.append(f"{plan_file.stem} (status marker)")
            continue

        ffm_match = re.search(r'^\s*FFM:\s*([0-9]+(?:\.[0-9]+)?)\s*kg\s*$', content, re.MULTILINE)
        bmr_match = re.search(r'^\s*BMR:\s*([0-9]+)\s*kcal\s*$', content, re.MULTILINE)

        # Se META mancante non possiamo garantire allineamento -> consideriamo STALE
        if not ffm_match or not bmr_match:
            stale.append(f"{plan_file.stem} (missing META)")
            continue

        plan_ffm = float(ffm_match.group(1))
        plan_bmr = int(bmr_match.group(1))

        ffm_mismatch = abs(plan_ffm - current_ffm) > 0.01
        bmr_mismatch = plan_bmr != current_bmr

        if ffm_mismatch or bmr_mismatch:
            stale.append(
                f"{plan_file.stem} (META FFM {plan_ffm:.2f} vs {current_ffm:.2f}, "
                f"BMR {plan_bmr} vs {current_bmr})"
            )

    return stale


def status():
    """Mostra stato completo"""
    if not COMP_FILE.exists() or not ZONES_FILE.exists():
        print(
            "Dati atleta incompleti. Esegui almeno:\n"
            f"- ./tv --athlete {get_athlete_id()} weigh <peso> <bf%>\n"
            f"- ./tv --athlete {get_athlete_id()} zones <mm:ss>"
        )
        return

    integration = load_integration_config_strict()
    status_cfg = integration["status"]
    alerts_cfg = integration["alerts"]
    plan_start_date = datetime.strptime(status_cfg["plan_start_date"], "%Y-%m-%d")
    plan_total_weeks = int(status_cfg["plan_total_weeks"])
    red_flag_ffm = float(alerts_cfg["ffm_red_flag_kg"])

    # Carica dati
    comp_data = load_json(COMP_FILE)
    zones_data = load_json(ZONES_FILE)

    # Ultima misurazione
    last_meas = comp_data['measurements'][-1]

    # Settimana corrente
    week_num, meso = get_current_week(plan_start_date)

    # Prossima gara
    next_race = get_next_race(integration)

    # Trend
    trend = get_composition_trend(comp_data)

    # Alerts
    alerts = []

    if last_meas['ffm'] < red_flag_ffm:
        alerts.append(f"⚠️  FFM sotto soglia critica ({red_flag_ffm}kg): {last_meas['ffm']:.2f}kg")

    stale_plans = check_stale_plans()
    if stale_plans:
        alerts.append(f"⚠️  {len(stale_plans)} piani nutrizionali STALE (rigenerazione necessaria)")

    if week_num > plan_total_weeks:
        alerts.append(f"⚠️  Settimana {week_num} oltre piano base (W1-W{plan_total_weeks})")

    # Output
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                     TRAINING VANTAGE STATUS                       ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Atleta: {get_athlete_id()}")
    print()

    # Composizione
    print("COMPOSIZIONE CORPOREA")
    print("─" * 70)
    print(f"Ultima misurazione: {last_meas['date']}")
    print(f"  Peso:  {last_meas['weight']:.2f} kg")
    print(f"  BF%:   {last_meas['bf_pct']:.1f}%")
    print(f"  FFM:   {last_meas['ffm']:.2f} kg")
    print(f"  BMR:   {last_meas['bmr']} kcal")
    print()

    if trend:
        print(f"Trend ({trend['period']}):")
        print(f"  Peso: {trend['weight']:+.2f} kg ({trend['measurements']} misurazioni)")
        print(f"  FFM:  {trend['ffm']:+.2f} kg")
        print()

    # Zone
    print("ZONE RUNNING")
    print("─" * 70)
    zones = zones_data['current']
    print(f"Test: {zones['test_date']} | Tempo: {zones['test_time']} ({zones['test_pace']}/km)")
    print()
    print(f"  Z1 (Recovery):     {zones['zones']['Z1']['from']}+")
    print(f"  Z2 (Easy):         {zones['zones']['Z2']['from']} - {zones['zones']['Z2']['to']}")
    print(f"  Z3 (Moderate):     {zones['zones']['Z3']['from']} - {zones['zones']['Z3']['to']}")
    print(f"  Z4 (High Aerobic): {zones['zones']['Z4']['from']} - {zones['zones']['Z4']['to']}")
    print(f"  Z5 (Threshold-):   {zones['zones']['Z5']['from']} - {zones['zones']['Z5']['to']}")
    print(f"  Z6 (Threshold):    {zones['zones']['Z6']['from']} - {zones['zones']['Z6']['to']}")
    print(f"  Z7 (VO2max-):      {zones['zones']['Z7']['from']} - {zones['zones']['Z7']['to']}")
    print(f"  Z8 (VO2max):       {zones['zones']['Z8']['from']} - {zones['zones']['Z8']['to']}")
    print()

    # Piano running
    print("PIANO RUNNING")
    print("─" * 70)
    print(f"Settimana corrente: W{week_num} ({meso})")

    if next_race:
        print(f"Prossima gara:      {next_race['name']}")
        print(f"                    {next_race['date']} ({next_race['days_to_race']} giorni)")
        print(f"                    Target: {next_race['target']}")
    else:
        print("Prossima gara:      Nessuna in calendario")
    print()

    # Alerts
    if alerts:
        print("ALERTS")
        print("─" * 70)
        for alert in alerts:
            print(f"  {alert}")
        print()

        if stale_plans:
            print("  Piani STALE:")
            for plan in stale_plans:
                print(f"   - {plan}")
            print()

    # Footer
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")


if __name__ == '__main__':
    status()
