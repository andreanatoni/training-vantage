#!/usr/bin/env python3
"""
/weigh <peso> <bf%>

Registra nuova misurazione composizione corporea:
- Calcola FFM e BMR
- Aggiorna composition.json
- Mostra delta rispetto a misurazione precedente
- Segnala red flags
"""

import json
import sys
from datetime import datetime
from athlete_context import data_file, ensure_athlete_dirs, get_athlete_id

# Paths
COMP_FILE = data_file("composition.json")
CHANGELOG_FILE = data_file("changelog.json")

# Costanti
RED_FLAG_FFM = 59.5  # kg
RED_FLAG_WEIGHT_LOSS_PCT = 0.6  # % per settimana


def calculate_ffm(weight, bf_pct):
    """Calcola Fat-Free Mass"""
    return weight * (1 - bf_pct / 100)


def calculate_bmr(ffm):
    """Calcola BMR con formula Katch-McArdle"""
    return 370 + (21.6 * ffm)


def load_composition():
    """Carica dati composizione"""
    if not COMP_FILE.exists():
        return {"measurements": []}
    with open(COMP_FILE, 'r') as f:
        return json.load(f)


def save_composition(data):
    """Salva dati composizione"""
    ensure_athlete_dirs()
    with open(COMP_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_delta_days(date1_str, date2_str):
    """Calcola giorni tra due date"""
    d1 = datetime.strptime(date1_str, '%Y-%m-%d')
    d2 = datetime.strptime(date2_str, '%Y-%m-%d')
    return abs((d2 - d1).days)


def weigh(weight, bf_pct, date=None, note=None):
    """Registra nuova pesata"""

    # Usa data odierna se non specificata
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    # Calcola metriche
    ffm = calculate_ffm(weight, bf_pct)
    bmr = int(calculate_bmr(ffm))

    # Carica dati esistenti
    data = load_composition()

    # Misurazione precedente
    prev = data['measurements'][-1] if data['measurements'] else None

    # Nuova misurazione (formato semplificato - solo dati essenziali)
    new_measurement = {
        "date": date,
        "weight": round(weight, 2),
        "bf_pct": round(bf_pct, 1),
        "ffm": round(ffm, 2),
        "bmr": bmr,
        "source": "manual_input"
    }

    if note:
        new_measurement["note"] = note

    # Aggiungi ai dati
    data['measurements'].append(new_measurement)

    # Salva
    save_composition(data)

    # Calcola delta se c'è misurazione precedente
    deltas = {}
    alerts = []

    if prev:
        days = get_delta_days(prev['date'], date)
        weeks = days / 7

        deltas = {
            'weight': round(weight - prev['weight'], 2),
            'bf_pct': round(bf_pct - prev['bf_pct'], 1),
            'ffm': round(ffm - prev['ffm'], 2),
            'bmr': bmr - prev['bmr'],
            'days': days,
            'weeks': round(weeks, 1)
        }

        # Check red flags
        if ffm < RED_FLAG_FFM:
            alerts.append(f"⚠️  RED FLAG: FFM sotto soglia critica ({RED_FLAG_FFM}kg)")

        if deltas['weight'] < 0 and weeks > 0:
            weight_loss_pct_week = abs(deltas['weight']) / prev['weight'] * 100 / weeks
            if weight_loss_pct_week > RED_FLAG_WEIGHT_LOSS_PCT:
                alerts.append(f"⚠️  Calo peso rapido: {weight_loss_pct_week:.1f}%/settimana (soglia {RED_FLAG_WEIGHT_LOSS_PCT}%)")

        if deltas['ffm'] < -0.3:  # Perdita FFM > 300g
            alerts.append(f"⚠️  Perdita FFM: {deltas['ffm']:.2f}kg")

    # Output
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                    NUOVA MISURAZIONE REGISTRATA                   ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Data:           {date}")
    print(f"Peso:           {weight:.2f} kg")
    print(f"BF%:            {bf_pct:.1f}%")
    print(f"FFM:            {ffm:.2f} kg")
    print(f"BMR:            {bmr} kcal")
    print()

    if prev:
        print("DELTA dalla misurazione precedente:")
        print(f"  {prev['date']} ({deltas['days']} giorni, {deltas['weeks']:.1f} settimane)")
        print()
        print(f"  Peso:  {deltas['weight']:+.2f} kg")
        print(f"  BF%:   {deltas['bf_pct']:+.1f}%")
        print(f"  FFM:   {deltas['ffm']:+.2f} kg")
        print(f"  BMR:   {deltas['bmr']:+d} kcal")
        print()

    if alerts:
        print("ALERTS:")
        for alert in alerts:
            print(f"  {alert}")
        print()

    # Aggiorna changelog
    update_changelog("weigh", {
        "date": date,
        "weight": weight,
        "bf_pct": bf_pct,
        "ffm": ffm,
        "bmr": bmr
    })

    print(f"✓ Misurazione salvata in {COMP_FILE}")

    return new_measurement, deltas, alerts


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
    if len(sys.argv) < 3:
        print("Usage: weigh.py <peso> <bf%> [note]")
        print("Example: weigh.py 68.5 13.1 'Dopo settimana scarico'")
        sys.exit(1)

    try:
        weight = float(sys.argv[1])
        bf_pct = float(sys.argv[2])
        note = sys.argv[3] if len(sys.argv) > 3 else None

        weigh(weight, bf_pct, note=note)
        print(f"Atleta: {get_athlete_id()}")
    except ValueError as e:
        print(f"Errore: {e}")
        print("I valori devono essere numerici (es. 68.5 13.1)")
        sys.exit(1)
