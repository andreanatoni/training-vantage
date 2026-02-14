#!/usr/bin/env python3
"""
/analyze <file.csv>

Analisi rapida di un export Garmin CSV:
- numero attività
- distanza totale
- tempo totale
- passo medio pesato
- FC media pesata
"""

import csv
import sys
from pathlib import Path


def parse_distance(value):
    if not value:
        return 0.0
    return float(str(value).replace(",", "."))


def parse_time_to_seconds(value):
    if not value:
        return 0
    parts = value.strip().split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    return 0


def format_hms(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_pace(sec_per_km):
    minutes = int(sec_per_km // 60)
    seconds = int(round(sec_per_km % 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/km"


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze.py <file.csv>")
        print("Esempio: analyze.py sources/storico.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"Errore: file non trovato: {csv_path}")
        sys.exit(1)

    total_activities = 0
    total_distance_km = 0.0
    total_time_seconds = 0
    weighted_hr_sum = 0.0
    hr_weight_seconds = 0

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            # CSV Garmin italiano (header tipici)
            distance = parse_distance(row.get("Distanza", "0"))
            moving_time = parse_time_to_seconds(row.get("Tempo in movimento", "0"))
            hr_avg_raw = row.get("FC Media", "").strip()

            total_activities += 1
            total_distance_km += distance
            total_time_seconds += moving_time

            if hr_avg_raw and moving_time > 0:
                try:
                    hr = float(hr_avg_raw.replace(",", "."))
                    weighted_hr_sum += hr * moving_time
                    hr_weight_seconds += moving_time
                except ValueError:
                    pass

    if total_activities == 0:
        print(f"Nessuna attività trovata in {csv_path}")
        return

    avg_pace = total_time_seconds / total_distance_km if total_distance_km > 0 else 0
    avg_hr = (weighted_hr_sum / hr_weight_seconds) if hr_weight_seconds > 0 else 0

    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                      ANALISI EXPORT GARMIN                        ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"File:             {csv_path}")
    print(f"Attività:         {total_activities}")
    print(f"Distanza totale:  {total_distance_km:.1f} km")
    print(f"Tempo totale:     {format_hms(total_time_seconds)}")
    if avg_pace > 0:
        print(f"Passo medio:      {format_pace(avg_pace)}")
    if avg_hr > 0:
        print(f"FC media pesata:  {avg_hr:.0f} bpm")


if __name__ == "__main__":
    main()
