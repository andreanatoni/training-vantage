#!/usr/bin/env python3
"""
/tv week <N>

Mostra piano running per settimana N (W1-W20).
Visualizza:
- Mesociclo
- Sessioni programmate con data, tipo, distanza, struttura
- Status completamento
- Dati Garmin (se presenti)
- Volume settimanale totale
"""

import sys
import json
try:
    from scripts.athlete_context import data_file, get_athlete_id
except ModuleNotFoundError:
    from athlete_context import data_file, get_athlete_id

RUNNING_LOG_FILE = data_file("running-log.json")
ZONES_FILE = data_file("zones.json")


def load_running_log():
    """Carica running log"""
    if not RUNNING_LOG_FILE.exists():
        raise FileNotFoundError(f"running-log non trovato per atleta '{get_athlete_id()}': {RUNNING_LOG_FILE}")
    with open(RUNNING_LOG_FILE, 'r') as f:
        return json.load(f)


def load_zones():
    """Carica zone attuali"""
    if not ZONES_FILE.exists():
        raise FileNotFoundError(f"zones non trovato per atleta '{get_athlete_id()}': {ZONES_FILE}")
    with open(ZONES_FILE, 'r') as f:
        data = json.load(f)
        return data['current']['zones']


def get_week_data(week_num):
    """Ottieni dati settimana"""
    data = load_running_log()

    for week in data['weeks']:
        if week['week'] == f"W{week_num}":
            return week

    return None


def format_session_type(session_type):
    """Formatta tipo sessione con colori (solo testo per ora)"""
    type_map = {
        'D.A.': '🏃 Defaticamento Attivo',
        'Ripetute': '⚡ Ripetute',
        'Progressivo': '📈 Progressivo',
        'Lungo': '🏃‍♂️ Lungo',
        'Tempo': '⏱️  Tempo Run',
        'Qualità': '⭐ Qualità',
        'Test': '🎯 Test',
        'Easy': '😌 Easy Run',
        'Fartlek': '🌀 Fartlek'
    }

    return type_map.get(session_type, session_type)


def calculate_week_volume(week_data):
    """Calcola volume totale settimana"""
    total_km = 0
    for session in week_data['sessions']:
        if session['distance_km']:
            total_km += session['distance_km']

    return total_km


def show_week(week_num):
    """Mostra piano settimana"""

    if week_num < 1 or week_num > 20:
        print(f"Errore: settimana deve essere tra 1 e 20 (richiesta: {week_num})")
        return

    week_data = get_week_data(week_num)

    if not week_data:
        print(f"Errore: settimana W{week_num} non trovata nel piano")
        return

    zones = load_zones()
    volume = calculate_week_volume(week_data)

    # Header
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print(f"║              PIANO RUNNING — SETTIMANA {week_num} ({week_data['mesociclo']})                    ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Atleta: {get_athlete_id()}")
    print()

    # Volume totale
    print(f"Volume totale: {volume:.1f} km")
    print(f"Sessioni: {len(week_data['sessions'])}")
    print()

    # Sessioni
    for i, session in enumerate(week_data['sessions'], 1):
        date = session['date']
        day = session['day_name']
        session_type = session['type']
        distance = session['distance_km']
        structure = session['structure']
        completed = session['completed']
        garmin = session['garmin_data']

        # Status
        status_icon = "✅" if completed else "⬜"

        print(f"{status_icon} Sessione {i} — {day} {date}")
        print(f"   {format_session_type(session_type)}")
        print(f"   Distanza: {distance:.1f} km")
        print(f"   Struttura: {structure}")

        # Dati Garmin se presenti
        if garmin:
            print(f"   📊 Garmin: Pace {garmin.get('pace', 'N/A')}, FC {garmin.get('hr_avg', 'N/A')} bpm")

        # Note
        if session.get('notes'):
            print(f"   📝 Note: {session['notes']}")

        print()

    # Zone reference
    print("ZONE ATTUALI (reference)")
    print("─" * 70)
    print(f"Z1 (Recovery):     {zones['Z1']['from']}+")
    print(f"Z2 (Easy):         {zones['Z2']['from']} - {zones['Z2']['to']}")
    print(f"Z6 (Threshold):    {zones['Z6']['from']} - {zones['Z6']['to']}")
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: week.py <N>")
        print("Esempio: week.py 1")
        print("         week.py 20")
        sys.exit(1)

    try:
        week_num = int(sys.argv[1])
        show_week(week_num)
    except ValueError:
        print("Errore: il numero settimana deve essere un intero (1-20)")
        sys.exit(1)
