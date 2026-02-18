#!/usr/bin/env python3
"""
Training Vantage - Tracking Module

Comandi per tracking composizione corporea e zone running:
- /weigh <peso> <bf%>
- /status
- /zones [test_time]
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple


# ============================================================================
# COMPOSITION TRACKING
# ============================================================================

def calculate_ffm_bmr(weight_kg: float, bf_pct: float) -> Tuple[float, float]:
    """
    Calcola FFM e BMR da peso e BF%

    Args:
        weight_kg: Peso in kg
        bf_pct: Body Fat percentage

    Returns:
        Tuple[ffm, bmr]:
        - ffm: Fat-Free Mass in kg
        - bmr: Basal Metabolic Rate (Katch-McArdle formula)
    """
    ffm = weight_kg * (1 - bf_pct / 100)
    bmr = 370 + 21.6 * ffm
    return ffm, bmr


def load_composition_data(data_dir: Path) -> Dict[str, Any]:
    """Load composition.json"""
    composition_file = data_dir / 'composition.json'
    if not composition_file.exists():
        return {'measurements': []}

    with open(composition_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_composition_data(data_dir: Path, data: Dict[str, Any]):
    """Save composition.json"""
    composition_file = data_dir / 'composition.json'
    with open(composition_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_measurement(
    data_dir: Path,
    weight: float,
    bf_pct: float,
    note: str = ""
) -> Dict[str, Any]:
    """
    Registra nuova pesata

    Args:
        data_dir: Path to data directory
        weight: Peso in kg
        bf_pct: Body Fat percentage
        note: Note opzionali

    Returns:
        Dict con measurement + analisi (delta, alerts, etc.)
    """
    # Load existing data
    data = load_composition_data(data_dir)

    # Calculate FFM and BMR
    ffm, bmr = calculate_ffm_bmr(weight, bf_pct)

    # Create new measurement
    measurement = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'weight': weight,
        'bf_pct': bf_pct,
        'ffm': round(ffm, 2),
        'bmr': int(bmr),
        'source': 'manual_cli',
        'note': note
    }

    # Get previous measurement for comparison
    previous = None
    if data['measurements']:
        previous = data['measurements'][-1]

    # Append new measurement
    data['measurements'].append(measurement)

    # Save
    save_composition_data(data_dir, data)

    # Analyze
    analysis = analyze_measurement(measurement, previous, data['measurements'])

    return {
        'measurement': measurement,
        'previous': previous,
        'analysis': analysis
    }


def analyze_measurement(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
    history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analizza misurazione: delta, trend, alerts

    Args:
        current: Current measurement
        previous: Previous measurement (if exists)
        history: All measurements (for trend analysis)

    Returns:
        Dict con analysis results
    """
    analysis = {
        'delta': {},
        'alerts': [],
        'trends': {},
        'needs_plan_regeneration': False
    }

    if not previous:
        return analysis

    # Calculate deltas
    date_current = datetime.strptime(current['date'], '%Y-%m-%d')
    date_previous = datetime.strptime(previous['date'], '%Y-%m-%d')
    days_diff = (date_current - date_previous).days

    if days_diff > 0:
        weeks_diff = days_diff / 7.0

        # Delta weight
        delta_weight = current['weight'] - previous['weight']
        delta_weight_pct = (delta_weight / previous['weight'] * 100)
        delta_weight_pct_week = delta_weight_pct / weeks_diff if weeks_diff > 0 else 0

        # Delta BF%
        delta_bf = current['bf_pct'] - previous['bf_pct']

        # Delta FFM
        delta_ffm = current['ffm'] - previous['ffm']

        # Delta BMR
        delta_bmr = current['bmr'] - previous['bmr']

        analysis['delta'] = {
            'days': days_diff,
            'weeks': round(weeks_diff, 1),
            'weight_kg': round(delta_weight, 2),
            'weight_pct': round(delta_weight_pct, 2),
            'weight_pct_week': round(delta_weight_pct_week, 2),
            'bf_pct': round(delta_bf, 2),
            'ffm_kg': round(delta_ffm, 2),
            'bmr_kcal': delta_bmr
        }

    # RED FLAGS & WARNINGS
    FFM_RED_FLAG = 59.5  # kg
    FFM_FLOOR = 60.0     # kg
    MAX_WEIGHT_LOSS_PCT_WEEK = 0.6

    # Alert 1: FFM below red flag
    if current['ffm'] < FFM_RED_FLAG:
        analysis['alerts'].append({
            'level': 'RED',
            'type': 'ffm_critical',
            'message': f"FFM {current['ffm']:.2f} kg < RED FLAG {FFM_RED_FLAG} kg"
        })
    elif current['ffm'] < FFM_FLOOR:
        distance_to_red = current['ffm'] - FFM_RED_FLAG
        analysis['alerts'].append({
            'level': 'WARNING',
            'type': 'ffm_low',
            'message': f"FFM {current['ffm']:.2f} kg < FLOOR {FFM_FLOOR} kg (a {distance_to_red:.2f} kg da red flag)"
        })

    # Alert 2: Weight loss too rapid
    if 'delta' in analysis and analysis['delta']:
        weight_loss_rate = analysis['delta']['weight_pct_week']
        if weight_loss_rate < -MAX_WEIGHT_LOSS_PCT_WEEK:
            analysis['alerts'].append({
                'level': 'WARNING',
                'type': 'rapid_weight_loss',
                'message': f"Perdita peso {abs(weight_loss_rate):.2f}%/sett > soglia {MAX_WEIGHT_LOSS_PCT_WEEK}%"
            })

    # Alert 3: FFM declining trend (check last 4 measurements)
    if len(history) >= 4:
        last_4 = history[-4:]
        ffm_values = [m['ffm'] for m in last_4]
        if all(ffm_values[i] > ffm_values[i+1] for i in range(len(ffm_values)-1)):
            analysis['alerts'].append({
                'level': 'WARNING',
                'type': 'ffm_declining_trend',
                'message': "FFM in calo per 4+ pesate consecutive"
            })

    # Check if plan regeneration needed (BMR delta > 30 kcal)
    if 'delta' in analysis and analysis['delta'] and abs(analysis['delta']['bmr_kcal']) > 30:
        analysis['needs_plan_regeneration'] = True
        analysis['alerts'].append({
            'level': 'INFO',
            'type': 'bmr_change',
            'message': f"Delta BMR {analysis['delta']['bmr_kcal']:+d} kcal > 30 → considera rigenerazione piani"
        })

    return analysis


def get_latest_measurement(data_dir: Path) -> Optional[Dict[str, Any]]:
    """Get latest measurement from composition.json"""
    data = load_composition_data(data_dir)
    if not data['measurements']:
        return None
    return data['measurements'][-1]


# ============================================================================
# ZONES TRACKING
# ============================================================================

def load_zones_data(data_dir: Path) -> Dict[str, Any]:
    """Load zones.json"""
    zones_file = data_dir / 'zones.json'
    if not zones_file.exists():
        return {'current': None, 'history': []}

    with open(zones_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_zones_data(data_dir: Path, data: Dict[str, Any]):
    """Save zones.json"""
    zones_file = data_dir / 'zones.json'
    with open(zones_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_time(time_str: str) -> int:
    """
    Parse time string to total seconds

    Formats supported:
    - "18:27" → 1107 seconds
    - "19:40" → 1180 seconds
    - "3:41" (pace) → 221 seconds

    Args:
        time_str: Time string in format "MM:SS"

    Returns:
        Total seconds (int)
    """
    parts = time_str.split(':')
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}. Expected MM:SS")

    minutes = int(parts[0])
    seconds = int(parts[1])
    return minutes * 60 + seconds


def format_pace(seconds: int) -> str:
    """
    Format seconds to pace string

    Args:
        seconds: Total seconds

    Returns:
        Pace string in format "M:SS"
    """
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def calculate_zones(test_time: str) -> Dict[str, Dict[str, str]]:
    """
    Calculate running zones from 5km test time

    Formule basate su dati reali zones.json (test 18:27, pace 3:41):

    Z8: pace-16s a pace-12s (VO2max)
    Z7: pace-12s a pace+1s (VO2max-)
    Z6: pace+1s a pace+9s (Threshold)
    Z5: pace+9s a pace+21s (Threshold-, +12s from Z6 bottom)
    Z4: pace+21s a pace+35s (High Aerobic, +14s from Z5 bottom)
    Z3: pace+35s a pace+59s (Moderate, +24s from Z4 bottom)
    Z2: pace+59s a pace+90s (Easy, +31s from Z3 bottom)
    Z1: pace+90s+ (Recovery)

    Args:
        test_time: Tempo test 5km in formato "MM:SS" (es. "18:27")

    Returns:
        Dict con zone Z1-Z8 con from/to pace
    """
    # Parse test time
    total_seconds = parse_time(test_time)

    # Calculate pace (time per km)
    pace_seconds = total_seconds // 5

    # Calculate zones (all in seconds, based on real data pattern)
    # Fast zones (Z7, Z8)
    z8_from = pace_seconds - 16
    z8_to = pace_seconds - 12

    z7_from = pace_seconds - 12
    z7_to = pace_seconds + 1

    # Threshold zones (Z6, Z5)
    z6_from = pace_seconds + 1
    z6_to = pace_seconds + 9

    z5_from = pace_seconds + 9
    z5_to = pace_seconds + 21  # Z6 bottom + 12s

    # Slower zones (Z4, Z3, Z2, Z1) - each defined by previous + delta
    z4_from = pace_seconds + 21
    z4_to = pace_seconds + 35  # Z4 from + 14s

    z3_from = pace_seconds + 35
    z3_to = pace_seconds + 59  # Z3 from + 24s

    z2_from = pace_seconds + 59
    z2_to = pace_seconds + 90  # Z2 from + 31s

    z1_from = pace_seconds + 90

    # Format zones
    zones = {
        'Z1': {
            'name': 'Recovery',
            'from': format_pace(z1_from),
            'to': None  # Open-ended (slower)
        },
        'Z2': {
            'name': 'Easy',
            'from': format_pace(z2_from),
            'to': format_pace(z2_to)
        },
        'Z3': {
            'name': 'Moderate',
            'from': format_pace(z3_from),
            'to': format_pace(z3_to)
        },
        'Z4': {
            'name': 'High Aerobic',
            'from': format_pace(z4_from),
            'to': format_pace(z4_to)
        },
        'Z5': {
            'name': 'Threshold-',
            'from': format_pace(z5_from),
            'to': format_pace(z5_to)
        },
        'Z6': {
            'name': 'Threshold',
            'from': format_pace(z6_from),
            'to': format_pace(z6_to)
        },
        'Z7': {
            'name': 'VO2max-',
            'from': format_pace(z7_from),
            'to': format_pace(z7_to)
        },
        'Z8': {
            'name': 'VO2max',
            'from': format_pace(z8_from),
            'to': format_pace(z8_to)
        }
    }

    return zones


def update_zones(
    data_dir: Path,
    test_time: str,
    hr_avg: Optional[int] = None,
    note: str = ""
) -> Dict[str, Any]:
    """
    Update zones from new 5km test

    Args:
        data_dir: Path to data directory
        test_time: Test time in format "MM:SS"
        hr_avg: Average HR during test (optional)
        note: Note about test

    Returns:
        Dict with new zones + comparison with previous
    """
    # Load existing data
    data = load_zones_data(data_dir)

    # Calculate new zones
    zones = calculate_zones(test_time)

    # Calculate pace
    test_seconds = parse_time(test_time)
    pace_seconds = test_seconds // 5
    pace_str = format_pace(pace_seconds)

    # Store previous zones for comparison
    previous_zones = data.get('current')

    # Create new current zones
    new_current = {
        'test_date': datetime.now().strftime('%Y-%m-%d'),
        'test_time': test_time,
        'test_pace': pace_str,
        'zones': zones
    }

    # Add to history
    history_entry = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': test_time,
        'pace': pace_str,
        'note': note
    }
    if hr_avg:
        history_entry['hr_avg'] = hr_avg

    data['history'].append(history_entry)

    # Update current
    data['current'] = new_current

    # Save
    save_zones_data(data_dir, data)

    return {
        'new_zones': new_current,
        'previous_zones': previous_zones,
        'history_entry': history_entry
    }


def get_current_zones(data_dir: Path) -> Optional[Dict[str, Any]]:
    """Get current zones from zones.json"""
    data = load_zones_data(data_dir)
    return data.get('current')


# ============================================================================
# STATUS DASHBOARD
# ============================================================================

def get_status(data_dir: Path) -> Dict[str, Any]:
    """
    Get comprehensive status dashboard

    Returns:
        Dict with:
        - composition: latest measurement + trend
        - zones: current zones + last test
        - alerts: active alerts
        - next_race: info about next race (if configured)
    """
    status = {}

    # Composition
    composition_data = load_composition_data(data_dir)
    if composition_data['measurements']:
        latest = composition_data['measurements'][-1]
        previous = composition_data['measurements'][-2] if len(composition_data['measurements']) > 1 else None

        analysis = analyze_measurement(latest, previous, composition_data['measurements'])

        status['composition'] = {
            'latest': latest,
            'previous': previous,
            'analysis': analysis
        }
    else:
        status['composition'] = None

    # Zones
    zones_data = load_zones_data(data_dir)
    if zones_data.get('current'):
        current_zones = zones_data['current']
        last_test = zones_data['history'][-1] if zones_data['history'] else None

        status['zones'] = {
            'current': current_zones,
            'last_test': last_test
        }
    else:
        status['zones'] = None

    # Aggregate all alerts
    all_alerts = []
    if status.get('composition') and status['composition']['analysis']['alerts']:
        all_alerts.extend(status['composition']['analysis']['alerts'])

    status['alerts'] = all_alerts

    # TODO: Next race (requires race calendar configuration)
    # For now, return None or read from a config file if available
    status['next_race'] = None

    return status
