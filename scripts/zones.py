#!/usr/bin/env python3
"""
/zones [test_time]

Gestione zone running:
- Senza argomenti: mostra zone attuali
- Con test_time (es. "18:26" o "17:55"): calcola nuove zone da test 5km
  - Calcola pace = tempo / 5
  - Applica formule zone
  - Aggiorna zones.json
  - Mostra confronto vecchie vs nuove
  - Segnala piani running che usano zone vecchie
"""

import json
import sys
from datetime import datetime
from athlete_context import data_file, ensure_athlete_dirs, get_athlete_id

# Paths
ZONES_FILE = data_file("zones.json")
CHANGELOG_FILE = data_file("changelog.json")


def parse_time(time_str):
    """Converte stringa tempo in secondi (es. "18:27" → 1107)"""
    parts = time_str.split(':')
    if len(parts) != 2:
        raise ValueError("Formato tempo non valido (usa MM:SS)")

    minutes = int(parts[0])
    seconds = int(parts[1])

    return minutes * 60 + seconds


def seconds_to_pace(seconds):
    """Converte secondi in formato pace MM:SS"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def calculate_zones(test_time_seconds):
    """Calcola zone da tempo test 5km"""

    # Pace test = tempo / 5 km
    pace_seconds = test_time_seconds / 5

    # Formule zone (aggiungi secondi alla pace)
    z6_sec = pace_seconds + 9
    z5_sec = z6_sec + 8
    z4_sec = z6_sec + 20
    z3_sec = z4_sec + 14
    z2_sec = z3_sec + 24
    z1_sec = z2_sec + 31

    # Z7 e Z8 (sottraggi dalla pace)
    z7_from_sec = pace_seconds - 2
    z7_to_sec = pace_seconds - 12
    z8_from_sec = pace_seconds - 12
    z8_to_sec = pace_seconds - 16

    zones = {
        "Z1": {
            "name": "Recovery",
            "from": seconds_to_pace(int(z1_sec)),
            "to": None
        },
        "Z2": {
            "name": "Easy",
            "from": seconds_to_pace(int(z2_sec)),
            "to": seconds_to_pace(int(z1_sec))
        },
        "Z3": {
            "name": "Moderate",
            "from": seconds_to_pace(int(z3_sec)),
            "to": seconds_to_pace(int(z2_sec))
        },
        "Z4": {
            "name": "High Aerobic",
            "from": seconds_to_pace(int(z4_sec)),
            "to": seconds_to_pace(int(z3_sec))
        },
        "Z5": {
            "name": "Threshold-",
            "from": seconds_to_pace(int(z5_sec)),
            "to": seconds_to_pace(int(z4_sec))
        },
        "Z6": {
            "name": "Threshold",
            "from": seconds_to_pace(int(z6_sec)),
            "to": seconds_to_pace(int(z5_sec))
        },
        "Z7": {
            "name": "VO2max-",
            "from": seconds_to_pace(int(z7_from_sec)),
            "to": seconds_to_pace(int(z7_to_sec))
        },
        "Z8": {
            "name": "VO2max",
            "from": seconds_to_pace(int(z8_from_sec)),
            "to": seconds_to_pace(int(z8_to_sec))
        }
    }

    return zones, seconds_to_pace(int(pace_seconds))


def load_zones():
    """Carica dati zone"""
    if not ZONES_FILE.exists():
        return {"current": None, "history": []}
    with open(ZONES_FILE, 'r') as f:
        return json.load(f)


def save_zones(data):
    """Salva dati zone"""
    ensure_athlete_dirs()
    with open(ZONES_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def show_current_zones():
    """Mostra zone attuali"""
    data = load_zones()
    current = data['current']
    if not current:
        print(f"Nessuna zona disponibile per atleta '{get_athlete_id()}'. Esegui: ./tv --athlete {get_athlete_id()} zones 18:26")
        return

    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                         ZONE RUNNING ATTUALI                      ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Test: {current['test_date']} | Tempo: {current['test_time']} ({current['test_pace']}/km)")
    print()

    for zone_id in ['Z1', 'Z2', 'Z3', 'Z4', 'Z5', 'Z6', 'Z7', 'Z8']:
        zone = current['zones'][zone_id]
        name = zone['name'].ljust(13)

        if zone['to'] is None:
            range_str = f"{zone['from']}+"
        else:
            range_str = f"{zone['from']} - {zone['to']}"

        print(f"  {zone_id} ({name}): {range_str}")

    print()
    print(f"Storico test: {len(data['history'])} test registrati")

    if data['history']:
        print()
        print("Ultimi test:")
        for test in data['history'][-3:]:
            note = f" — {test['note']}" if 'note' in test else ""
            print(f"  {test['date']}: {test['time']} ({test['pace']}/km){note}")


def update_zones(test_time_str, note=None):
    """Aggiorna zone con nuovo test"""

    # Parse tempo
    try:
        test_seconds = parse_time(test_time_str)
    except ValueError as e:
        print(f"Errore: {e}")
        print("Usa formato MM:SS (es. 18:27)")
        sys.exit(1)

    # Calcola nuove zone
    new_zones, pace = calculate_zones(test_seconds)

    # Carica dati esistenti
    data = load_zones()
    old_current = data['current']
    if old_current is None:
        old_current = {
            "test_date": datetime.now().strftime('%Y-%m-%d'),
            "test_time": test_time_str,
            "test_pace": pace,
            "zones": new_zones,
        }

    # Prepara nuovi dati
    today = datetime.now().strftime('%Y-%m-%d')

    # Aggiungi vecchio test allo storico (se non è lo stesso giorno)
    if old_current['test_date'] != today:
        history_entry = {
            "date": old_current['test_date'],
            "time": old_current['test_time'],
            "pace": old_current['test_pace']
        }

        if 'note' in old_current:
            history_entry['note'] = old_current['note']

        data['history'].append(history_entry)

    # Nuovo current
    new_current = {
        "test_date": today,
        "test_time": test_time_str,
        "test_pace": pace,
        "zones": new_zones
    }

    if note:
        new_current['note'] = note

    data['current'] = new_current

    # Salva
    save_zones(data)

    # Output confronto
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                    ZONE AGGIORNATE DA NUOVO TEST                  ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Nuovo test: {today} | Tempo: {test_time_str} ({pace}/km)")
    print(f"Test precedente: {old_current['test_date']} | Tempo: {old_current['test_time']} ({old_current['test_pace']}/km)")
    print()

    # Calcola miglioramento
    old_seconds = parse_time(old_current['test_time'])
    delta_seconds = test_seconds - old_seconds

    if delta_seconds < 0:
        print(f"✓ MIGLIORAMENTO: {abs(delta_seconds)} secondi più veloce")
    elif delta_seconds > 0:
        print(f"⚠️  PEGGIORAMENTO: {delta_seconds} secondi più lento")
    else:
        print("Stesso tempo del test precedente")

    print()
    print("CONFRONTO ZONE:")
    print()
    print(f"{'Zona':<4} {'Nome':<13} {'Vecchia':<15} {'Nuova':<15} {'Delta'}")
    print("─" * 70)

    for zone_id in ['Z1', 'Z2', 'Z3', 'Z4', 'Z5', 'Z6', 'Z7', 'Z8']:
        old_z = old_current['zones'][zone_id]
        new_z = new_zones[zone_id]

        name = old_z['name']

        if old_z['to'] is None:
            old_range = f"{old_z['from']}+"
            new_range = f"{new_z['from']}+"
        else:
            old_range = f"{old_z['from']}-{old_z['to']}"
            new_range = f"{new_z['from']}-{new_z['to']}"

        # Calcola delta (solo for "from")
        old_from_sec = parse_time(old_z['from'])
        new_from_sec = parse_time(new_z['from'])
        delta_sec = new_from_sec - old_from_sec

        if delta_sec < 0:
            delta_str = f"{abs(delta_sec)}s più veloce"
        elif delta_sec > 0:
            delta_str = f"{delta_sec}s più lento"
        else:
            delta_str = "invariata"

        print(f"{zone_id:<4} {name:<13} {old_range:<15} {new_range:<15} {delta_str}")

    print()
    print(f"✓ Zone aggiornate in {ZONES_FILE}")
    print()

    # Aggiorna changelog
    update_changelog("zones", {
        "test_date": today,
        "test_time": test_time_str,
        "pace": pace,
        "delta_seconds": delta_seconds
    })


def update_changelog(command, details):
    """Aggiorna changelog.json"""
    ensure_athlete_dirs()
    if CHANGELOG_FILE.exists():
        with open(CHANGELOG_FILE, 'r') as f:
            changelog = json.load(f)
    else:
        changelog = {"entries": []}

    entry = {
        "timestamp": datetime.now().isoformat(),
        "command": command,
        "details": details
    }

    changelog['entries'].append(entry)

    with open(CHANGELOG_FILE, 'w') as f:
        json.dump(changelog, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Mostra zone attuali
        show_current_zones()
    else:
        # Aggiorna con nuovo test
        test_time = sys.argv[1]
        note = sys.argv[2] if len(sys.argv) > 2 else None
        update_zones(test_time, note)
