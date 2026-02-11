#!/usr/bin/env python3
"""
Converte pianorunning.xlsx in data/running-log.json
Legge il foglio 'Piano-completo' e organizza per settimane e mesocicli
"""

import pandas as pd
import json
from datetime import datetime

# Leggi Excel
xlsx_file = 'sources/pianorunning.xlsx'
df = pd.read_excel(xlsx_file, sheet_name='Piano-completo')

# Pulisci nomi colonne (rimuovi spazi)
df.columns = df.columns.str.strip()

# Rinomina colonne duplicate
# Colonne: ['Giorno', 'Settimana', 'Giorno', 'Workout', 'Distanza', 'Struttura', 'Volume totale']
# Rinomina: prima 'Giorno' = 'Data', seconda 'Giorno' = 'GiornoNome'
col_names = df.columns.tolist()
if col_names.count('Giorno') == 2:
    # Trova indici
    first_idx = col_names.index('Giorno')
    second_idx = col_names.index('Giorno', first_idx + 1)
    col_names[first_idx] = 'Data'
    col_names[second_idx] = 'GiornoNome'
    df.columns = col_names

# Mappatura mesocicli
def get_mesociclo(week_num):
    if 1 <= week_num <= 4:
        return "M1"
    elif 5 <= week_num <= 8:
        return "M2"
    elif 9 <= week_num <= 12:
        return "M3"
    elif 13 <= week_num <= 16:
        return "M4"
    elif 17 <= week_num <= 20:
        return "M5"
    return "Unknown"

# Raggruppa per settimana
weeks_dict = {}

for idx, row in df.iterrows():
    week_num = int(row['Settimana']) if pd.notna(row['Settimana']) else None
    if not week_num:
        continue

    week_key = f"W{week_num}"

    if week_key not in weeks_dict:
        weeks_dict[week_key] = {
            "week": week_key,
            "mesociclo": get_mesociclo(week_num),
            "sessions": []
        }

    # Estrai dati sessione
    data = row['Data']
    giorno_nome = row['GiornoNome']
    workout = row['Workout']
    distanza = row['Distanza']
    struttura = row['Struttura']

    session = {
        "date": data.strftime('%Y-%m-%d') if hasattr(data, 'strftime') else None,
        "day_name": str(giorno_nome) if pd.notna(giorno_nome) else None,
        "type": str(workout).strip() if pd.notna(workout) else None,
        "distance_km": float(distanza) if pd.notna(distanza) and isinstance(distanza, (int, float)) else None,
        "structure": str(struttura).strip() if pd.notna(struttura) else None,
        "completed": False,
        "garmin_data": None,
        "notes": None
    }

    weeks_dict[week_key]["sessions"].append(session)

# Output JSON
output = {
    "plan_version": "v1.0",
    "start_date": "2025-09-30",
    "total_weeks": len(weeks_dict),
    "weeks": [weeks_dict[f"W{i}"] for i in range(1, 21) if f"W{i}" in weeks_dict]
}

with open('data/running-log.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

total_sessions = sum(len(w["sessions"]) for w in output["weeks"])
print(f"✓ Convertite {len(weeks_dict)} settimane, {total_sessions} sessioni totali")
print(f"✓ Output: data/running-log.json")
