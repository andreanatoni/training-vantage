#!/usr/bin/env python3
"""
Gestione piano running periodizzato (mesocicli + taper).

Comandi:
  running_plan.py generate --from YYYY-MM-DD --to YYYY-MM-DD [--goal-race YYYY-MM-DD] [--start-km N] [--peak-km N]
  running_plan.py week <N>
  running_plan.py month <YYYY-MM>
  running_plan.py summary
"""

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from athlete_context import data_file, ensure_athlete_dirs, get_athlete_id


ROOT = Path(__file__).parent.parent
CONFIG_FILE = data_file("RUNNING_PLAN_CONFIG.json")
PROFILE_FILE = data_file("RUNNING_ATHLETE_PROFILE.json")
PLAN_FILE = data_file("running_plan.json")
CHANGELOG_FILE = data_file("changelog.json")
ZONES_FILE = data_file("zones.json")


DEFAULT_CONFIG = {
    "meta": {
        "version": "v1.0",
        "updated_at": "2026-02-14",
    },
    "defaults": {
        "session_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "session_types_by_day": {
            "Monday": "easy",
            "Tuesday": "forza",
            "Wednesday": "qualita",
            "Thursday": "forza",
            "Friday": "progressivo",
            "Saturday": "lungo",
        },
        "weekly_km": {
            "start": 36.0,
            "peak": 58.0,
            "max_increase_pct": 0.10,
            "deload_every_n_weeks": 4,
            "deload_drop_pct": 0.18,
        },
        "session_shares": {
            "easy": 0.20,
            "qualita": 0.26,
            "progressivo": 0.22,
            "lungo": 0.32,
        },
        "taper": {
            "weeks": 2,
            "drop_pct_week_minus_2": 0.20,
            "drop_pct_week_minus_1": 0.35,
        },
        "intensity_distribution": {
            "build": {
                "target_low_pct": 0.80,
                "target_high_pct": 0.20,
                "max_moderate_pct": 0.10,
                "min_high_pct": 0.15
            },
            "specific": {
                "target_low_pct": 0.75,
                "target_high_pct": 0.20,
                "max_moderate_pct": 0.15,
                "min_high_pct": 0.15
            },
            "taper": {
                "target_low_pct": 0.85,
                "target_high_pct": 0.10,
                "max_moderate_pct": 0.10,
                "min_high_pct": 0.05
            },
            "race": {
                "target_low_pct": 0.80,
                "target_high_pct": 0.15,
                "max_moderate_pct": 0.10,
                "min_high_pct": 0.05
            }
        }
    },
}


STRUCTURE_BY_TYPE = {
    "easy": "Easy aerobico + allunghi",
    "qualita": "Ripetute/ritmo gara con recuperi controllati",
    "progressivo": "L + M + TR progressivo",
    "lungo": "Lungo aerobico (eventuali inserimenti M)",
    "forza": "Forza specifica corsa/calisthenics",
}


PHASE_WORKOUT_LABEL = {
    "easy": {
        "build": "easy_aerobic",
        "specific": "easy_technique",
        "taper": "easy_recovery",
        "race": "easy_shakeout",
    },
    "qualita": {
        "build": "qualita_vo2_threshold",
        "specific": "qualita_ritmo_gara",
        "taper": "qualita_richiamo",
        "race": "gara_obiettivo",
    },
    "progressivo": {
        "build": "progressivo_classico",
        "specific": "progressivo_chiusura_gara",
        "taper": "progressivo_corto",
        "race": "attivazione_pre_gara",
    },
    "lungo": {
        "build": "lungo_aerobico",
        "specific": "lungo_blocchi_ritmo_gara",
        "taper": "lungo_ridotto",
        "race": "no_lungo_settimana_gara",
    },
    "forza": {
        "build": "forza_base",
        "specific": "forza_mantenimento_specifico",
        "taper": "forza_ridotta_attivazione",
        "race": "forza_leggera_mobilita",
    },
}


# Stima TID per workout label (quote km in zone Seiler-like: low / moderate / high).
INTENSITY_SPLIT_BY_WORKOUT_LABEL = {
    "easy_aerobic": {"low": 0.95, "moderate": 0.05, "high": 0.00},
    "easy_technique": {"low": 0.92, "moderate": 0.06, "high": 0.02},
    "easy_recovery": {"low": 0.98, "moderate": 0.02, "high": 0.00},
    "easy_shakeout": {"low": 0.98, "moderate": 0.02, "high": 0.00},
    "qualita_vo2_threshold": {"low": 0.45, "moderate": 0.05, "high": 0.50},
    "qualita_ritmo_gara": {"low": 0.55, "moderate": 0.25, "high": 0.20},
    "qualita_richiamo": {"low": 0.60, "moderate": 0.10, "high": 0.30},
    "gara_obiettivo": {"low": 0.30, "moderate": 0.40, "high": 0.30},
    "progressivo_classico": {"low": 0.75, "moderate": 0.05, "high": 0.20},
    "progressivo_chiusura_gara": {"low": 0.65, "moderate": 0.15, "high": 0.20},
    "progressivo_corto": {"low": 0.80, "moderate": 0.05, "high": 0.15},
    "attivazione_pre_gara": {"low": 0.85, "moderate": 0.05, "high": 0.10},
    "lungo_aerobico": {"low": 0.92, "moderate": 0.08, "high": 0.00},
    "lungo_blocchi_ritmo_gara": {"low": 0.82, "moderate": 0.08, "high": 0.10},
    "lungo_ridotto": {"low": 0.94, "moderate": 0.06, "high": 0.00},
    "no_lungo_settimana_gara": {"low": 1.00, "moderate": 0.00, "high": 0.00},
    "test_5k": {"low": 0.40, "moderate": 0.10, "high": 0.50},
    "forza_base": {"low": 0.00, "moderate": 0.00, "high": 0.00},
    "forza_mantenimento_specifico": {"low": 0.00, "moderate": 0.00, "high": 0.00},
    "forza_ridotta_attivazione": {"low": 0.00, "moderate": 0.00, "high": 0.00},
    "forza_leggera_mobilita": {"low": 0.00, "moderate": 0.00, "high": 0.00},
}


@dataclass
class GenerationArgs:
    start_date: date
    end_date: date
    goal_race: Optional[date]
    start_km: float
    peak_km: float


def ensure_config():
    if CONFIG_FILE.exists():
        return
    ensure_athlete_dirs()
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config():
    ensure_config()
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_zones():
    """Carica zone ritmo correnti, se disponibili."""
    try:
        data = json.loads(ZONES_FILE.read_text(encoding="utf-8"))
        return data.get("current", {}).get("zones", {})
    except Exception:
        return {}


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def iter_week_starts(start_d: date, end_d: date):
    cur = monday_of(start_d)
    while cur <= end_d:
        yield cur
        cur += timedelta(days=7)


def parse_date(v: str) -> date:
    return datetime.strptime(v, "%Y-%m-%d").date()


def phase_for_week(week_start: date, week_end: date, goal_race: Optional[date]) -> str:
    if not goal_race:
        return "build"
    if week_start <= goal_race <= week_end:
        return "race"
    days_to_race = (goal_race - week_end).days
    if 0 <= days_to_race <= 13:
        return "taper"
    if 14 <= days_to_race <= 56:
        return "specific"
    return "build"


def pace_target_for(day_type: str, phase: str, zones: dict, workout_label: str) -> str:
    """Restituisce indicazione ritmo da zone per tipo seduta."""
    if day_type == "forza":
        return "N/A"
    if workout_label == "test_5k":
        z6 = zones.get("Z6", {})
        return f"Test 5km, riferimento soglia {z6.get('from', 'N/A')}-{z6.get('to', 'N/A')}/km"

    if phase == "race":
        if day_type == "qualita":
            return "Ritmo gara obiettivo (warm-up + race)"
        if day_type == "progressivo":
            z2 = zones.get("Z2", {})
            z4 = zones.get("Z4", {})
            return f"Attivazione Z2->Z4 ({z2.get('from', 'N/A')} -> {z4.get('to', 'N/A')}/km)"

    if day_type == "easy":
        z2 = zones.get("Z2", {})
        return f"Z2 {z2.get('from', 'N/A')}-{z2.get('to', 'N/A')}/km"
    if day_type == "qualita":
        if phase == "specific":
            z5 = zones.get("Z5", {})
            z6 = zones.get("Z6", {})
            return f"Z5-Z6 {z5.get('from', 'N/A')}-{z6.get('to', 'N/A')}/km"
        z6 = zones.get("Z6", {})
        z7 = zones.get("Z7", {})
        return f"Z6-Z7 {z6.get('from', 'N/A')}-{z7.get('to', 'N/A')}/km"
    if day_type == "progressivo":
        z2 = zones.get("Z2", {})
        if phase == "specific":
            z5 = zones.get("Z5", {})
            return f"Z2→Z5 ({z2.get('from', 'N/A')} -> {z5.get('to', 'N/A')}/km)"
        z6 = zones.get("Z6", {})
        return f"Z2→Z6 ({z2.get('from', 'N/A')} -> {z6.get('to', 'N/A')}/km)"
    if day_type == "lungo":
        z2 = zones.get("Z2", {})
        if phase == "specific":
            z4 = zones.get("Z4", {})
            return f"Z2 con blocchi Z4 ({z2.get('from', 'N/A')} + blocchi {z4.get('from', 'N/A')}-{z4.get('to', 'N/A')})"
        return f"Z2 stabile {z2.get('from', 'N/A')}-{z2.get('to', 'N/A')}/km"
    return "N/A"


def structure_for_session(day_type: str, phase: str, workout_label: str) -> str:
    """Descrizione strutturale seduta in funzione della fase."""
    if workout_label == "test_5k":
        return "Settimana scarico: test 5km + riscaldamento/defaticamento"

    if day_type == "easy":
        if phase == "specific":
            return "Easy Z2 + tecnica corsa + 6 allunghi"
        if phase in ("taper", "race"):
            return "Easy breve Z1-Z2, carico neuromuscolare minimo"
        return "Easy aerobico + allunghi"

    if day_type == "qualita":
        if phase == "specific":
            return "Blocchi a ritmo gara (HM/Maratona) con recuperi controllati"
        if phase == "taper":
            return "Richiamo qualita breve (volume ridotto, ritmo brillante)"
        if phase == "race":
            return "Gara obiettivo o simulazione controllata di gara"
        return "Ripetute VO2/soglia con recuperi controllati"

    if day_type == "progressivo":
        if phase == "specific":
            return "Progressivo con chiusura a ritmo gara"
        if phase in ("taper", "race"):
            return "Progressivo corto di attivazione, senza accumulo fatica"
        return "L + M + TR progressivo"

    if day_type == "lungo":
        if phase == "specific":
            return "Lungo con inserimenti a ritmo gara"
        if phase in ("taper", "race"):
            return "Lungo ridotto facile o sostituito da gara"
        return "Lungo aerobico (eventuali inserimenti M)"

    if day_type == "forza":
        if phase == "specific":
            return "Forza mantenimento (volume ridotto, qualita tecnica)"
        if phase in ("taper", "race"):
            return "Forza leggera + mobilita + core (no DOMS)"
        return "Forza specifica corsa/calisthenics"

    return STRUCTURE_BY_TYPE.get(day_type, "Sessione corsa")


def split_intensity_km(workout_label: str, distance_km: float) -> dict:
    """Stima km low/moderate/high per sessione."""
    split = INTENSITY_SPLIT_BY_WORKOUT_LABEL.get(workout_label, {"low": 0.80, "moderate": 0.15, "high": 0.05})
    low = round(distance_km * split["low"], 2)
    moderate = round(distance_km * split["moderate"], 2)
    high = round(distance_km * split["high"], 2)
    # Correggi possibili artefatti di arrotondamento
    drift = round(distance_km - (low + moderate + high), 2)
    if abs(drift) > 0:
        low = round(low + drift, 2)
    return {"low_km": low, "moderate_km": moderate, "high_km": high}


def _split_three(total_km: float, a_pct: float, b_pct: float, c_pct: float):
    total_i = int(round(total_km))
    a = int(round(total_i * a_pct))
    b = int(round(total_i * b_pct))
    c = max(0, total_i - a - b)
    return a, b, c


def detailed_session_plan(day_type: str, phase: str, workout_label: str, km: float) -> str:
    """Dettaglio operativo sintetico seduta (km/reps/recuperi)."""
    km_i = max(0, int(round(km)))
    if day_type == "forza":
        if phase in ("taper", "race"):
            return "2-3 giri: core + mobilita + glute activation (20-30')"
        if phase == "specific":
            return "3-4 esercizi multiarticolari + core (35-45'), RPE 6-7"
        return "Forza generale: 4-5 esercizi + core (40-50')"

    if workout_label == "test_5k":
        warmup = max(2, int(round(km_i * 0.25)))
        cooldown = max(1, km_i - warmup - 5)
        return f"Risc {warmup} km + Test 5 km + Defat {cooldown} km"

    if day_type == "easy":
        return f"Corsa continua facile {km_i} km + 6 allunghi da 80-100 m"

    if day_type == "qualita":
        if workout_label == "qualita_richiamo":
            warmup = max(2, int(round(km_i * 0.25)))
            cooldown = max(1, int(round(km_i * 0.2)))
            remaining = max(2, km_i - warmup - cooldown)
            reps = max(4, min(8, int(round(remaining / 0.6))))
            return f"Risc {warmup} km + {reps}x600 m (rec 200 m jog) + Defat {cooldown} km"
        if workout_label == "qualita_ritmo_gara":
            warmup = max(2, int(round(km_i * 0.2)))
            cooldown = max(1, int(round(km_i * 0.15)))
            remaining = max(4, km_i - warmup - cooldown)
            blocks = max(2, min(4, int(round(remaining / 2.4))))
            block_km = max(1, int(round(remaining / blocks)))
            return f"Risc {warmup} km + {blocks}x{block_km} km a ritmo gara (rec 1 km L) + Defat {cooldown} km"
        warmup = max(2, int(round(km_i * 0.2)))
        cooldown = max(1, int(round(km_i * 0.15)))
        remaining = max(3, km_i - warmup - cooldown)
        rep_km = 1.0 if km_i >= 10 else 0.8
        rec_km = 0.4
        reps = max(4, min(8, int((remaining + rec_km) // (rep_km + rec_km))))
        reps = max(3, reps)
        return f"Risc {warmup} km + {reps}x{int(rep_km*1000)} m (rec {int(rec_km*1000)} m jog) + Defat {cooldown} km"

    if day_type == "progressivo":
        if workout_label == "progressivo_chiusura_gara":
            l_km, m_km, tr_km = _split_three(km, 0.35, 0.30, 0.35)
        elif workout_label == "progressivo_corto":
            l_km, m_km, tr_km = _split_three(km, 0.50, 0.30, 0.20)
        else:
            l_km, m_km, tr_km = _split_three(km, 0.45, 0.30, 0.25)
        return (
            f"Progressivo: {int(round(l_km))} km L + "
            f"{int(round(m_km))} km M + {int(round(tr_km))} km TR"
        )

    if day_type == "lungo":
        if workout_label == "lungo_blocchi_ritmo_gara":
            if km_i >= 16:
                blocks, block = 3, 2
            elif km_i >= 12:
                blocks, block = 2, 2
            else:
                blocks, block = 2, 1
            rec_each = 1
            rec_reps = blocks
            rg = blocks * block
            rec_total = rec_each * rec_reps
            easy_total = max(2, km_i - rg - rec_total)
            easy_a = max(1, int(round(easy_total * 0.65)))
            easy_b = max(1, easy_total - easy_a)
            return (
                f"Lungo: {easy_a} km L + {blocks}x{block} km ritmo gara "
                f"(rec {rec_each} km L x{rec_reps}) + {easy_b} km L"
            )
        if workout_label == "lungo_ridotto":
            return f"Lungo ridotto facile: {km_i} km L continuo"
        return f"Lungo aerobico: {km_i} km L con ultimi 2-3 km in M (opzionale)"

    return f"Seduta continua {km_i} km"


def evaluate_tid(phase: str, sessions: list, cfg: dict) -> dict:
    """Valuta distribuzione intensita' settimanale rispetto ai guardrail TID."""
    tid_cfg = cfg["defaults"].get("intensity_distribution", {})
    phase_cfg = tid_cfg.get(phase, tid_cfg.get("build", {}))

    running_sessions = [s for s in sessions if s["day_type"] != "forza"]
    total_km = round(sum(float(s["distance_km"]) for s in running_sessions), 2)
    if total_km <= 0:
        return {
            "total_running_km": 0.0,
            "low_km": 0.0,
            "moderate_km": 0.0,
            "high_km": 0.0,
            "low_pct": 0.0,
            "moderate_pct": 0.0,
            "high_pct": 0.0,
            "target": phase_cfg,
            "aligned": True,
            "warnings": [],
        }

    low_km = round(sum(s["intensity_km"]["low_km"] for s in running_sessions), 2)
    mod_km = round(sum(s["intensity_km"]["moderate_km"] for s in running_sessions), 2)
    high_km = round(sum(s["intensity_km"]["high_km"] for s in running_sessions), 2)

    low_pct = round(low_km / total_km, 3)
    mod_pct = round(mod_km / total_km, 3)
    high_pct = round(high_km / total_km, 3)

    warnings = []
    max_mod = float(phase_cfg.get("max_moderate_pct", 0.15))
    min_high = float(phase_cfg.get("min_high_pct", 0.10))

    if mod_pct > max_mod:
        warnings.append(f"moderate_pct {mod_pct:.3f} > max {max_mod:.3f} (zona grigia alta)")
    if high_pct < min_high:
        warnings.append(f"high_pct {high_pct:.3f} < min {min_high:.3f} (stimolo alta intensita' basso)")

    return {
        "total_running_km": total_km,
        "low_km": low_km,
        "moderate_km": mod_km,
        "high_km": high_km,
        "low_pct": low_pct,
        "moderate_pct": mod_pct,
        "high_pct": high_pct,
        "target": phase_cfg,
        "aligned": len(warnings) == 0,
        "warnings": warnings,
    }


def refresh_session_from_label(session: dict, phase: str, zones: dict):
    """Ricalcola campi derivati quando cambia workout_label."""
    wl = session.get("workout_label", session.get("day_type", "easy"))
    day_type = session.get("day_type", "easy")
    km = float(session.get("distance_km", 0.0))
    session["structure"] = structure_for_session(day_type, phase, wl)
    session["session_plan"] = detailed_session_plan(day_type, phase, wl, km)
    session["pace_target"] = pace_target_for(day_type, phase, zones, wl)
    session["intensity_km"] = split_intensity_km(wl, km)


def enforce_tid_for_week(phase: str, sessions: list, cfg: dict, zones: dict) -> dict:
    """
    Tenta allineamento TID con piccole modifiche qualitative ai workout label.
    Non cambia giorni o volumi km, cambia solo "tipo qualità" per ridurre zona grigia.
    """
    max_iters = 5
    changed = []
    tid = evaluate_tid(phase, sessions, cfg)
    for _ in range(max_iters):
        if tid["aligned"]:
            break
        warnings = tid.get("warnings", [])
        did_change = False

        # Caso 1: troppa zona grigia -> rendi progressivo meno moderato
        if any("zona grigia alta" in w for w in warnings):
            for s in sessions:
                if s["day_type"] == "progressivo" and s.get("workout_label") == "progressivo_chiusura_gara":
                    s["workout_label"] = "progressivo_classico"
                    refresh_session_from_label(s, phase, zones)
                    changed.append(f"{s['date']}: progressivo_chiusura_gara -> progressivo_classico")
                    did_change = True
                    break
            if not did_change:
                for s in sessions:
                    if s["day_type"] == "progressivo" and s.get("workout_label") == "progressivo_classico":
                        s["workout_label"] = "progressivo_corto"
                        refresh_session_from_label(s, phase, zones)
                        changed.append(f"{s['date']}: progressivo_classico -> progressivo_corto")
                        did_change = True
                        break

        # Caso 2: alta intensita' troppo bassa -> alza componente alta sulla qualita'
        if not did_change and any("stimolo alta intensita' basso" in w for w in warnings):
            for s in sessions:
                if s["day_type"] == "qualita" and s.get("workout_label") in ("qualita_ritmo_gara", "qualita_richiamo"):
                    s["workout_label"] = "qualita_vo2_threshold"
                    refresh_session_from_label(s, phase, zones)
                    changed.append(f"{s['date']}: {s['day_type']} -> qualita_vo2_threshold")
                    did_change = True
                    break

        if not did_change:
            break
        tid = evaluate_tid(phase, sessions, cfg)

    tid["enforcement"] = {
        "applied": len(changed) > 0,
        "changes": changed,
    }
    return tid


def build_week_targets(weeks_count: int, args: GenerationArgs, cfg: dict):
    weekly_cfg = cfg["defaults"]["weekly_km"]
    taper_cfg = cfg["defaults"]["taper"]

    start_km = args.start_km if args.start_km > 0 else float(weekly_cfg["start"])
    peak_km = args.peak_km if args.peak_km > 0 else float(weekly_cfg["peak"])
    max_inc = float(weekly_cfg["max_increase_pct"])
    deload_n = int(weekly_cfg["deload_every_n_weeks"])
    deload_drop = float(weekly_cfg["deload_drop_pct"])

    targets = []
    current = start_km
    for idx in range(1, weeks_count + 1):
        if idx == 1:
            current = start_km
        elif idx % deload_n == 0:
            current = current * (1.0 - deload_drop)
        else:
            current = min(peak_km, current * (1.0 + max_inc))
        targets.append(round(current, 1))

    if args.goal_race:
        taper_weeks = int(taper_cfg["weeks"])
        if taper_weeks >= 2 and weeks_count >= 2:
            idx_wm1 = weeks_count - 1
            idx_wm0 = weeks_count
            if idx_wm1 >= 1:
                base = targets[max(0, idx_wm1 - 2)]
                targets[idx_wm1 - 1] = round(base * (1.0 - float(taper_cfg["drop_pct_week_minus_2"])), 1)
            if idx_wm0 >= 1:
                base = targets[max(0, idx_wm0 - 2)]
                targets[idx_wm0 - 1] = round(base * (1.0 - float(taper_cfg["drop_pct_week_minus_1"])), 1)
    return targets


def session_template_from_preferences(profile: dict, fallback_days: list, fallback_types: dict):
    """Deriva template giorni seduta da preferenze profilo atleta."""
    prefs = profile.get("preferences", {}) if isinstance(profile, dict) else {}
    run_days = prefs.get("run_days_per_week")
    force_days = prefs.get("strength_days_per_week")
    long_run_day = prefs.get("long_run_day")

    if run_days is None and force_days is None and not long_run_day:
        return fallback_days, fallback_types

    try:
        run_days = max(1, min(6, int(run_days if run_days is not None else 4)))
        force_days = max(0, min(2, int(force_days if force_days is not None else 2)))
    except (TypeError, ValueError):
        return fallback_days, fallback_types

    long_run_day = long_run_day if long_run_day in {"Friday", "Saturday", "Sunday"} else "Saturday"

    run_slots = [
        ("Wednesday", "qualita"),
        ("Friday", "progressivo"),
        (long_run_day, "lungo"),
        ("Monday", "easy"),
        ("Sunday", "easy"),
        ("Thursday", "easy"),
    ]
    selected = []
    used = set()
    for day, day_type in run_slots:
        if day in used:
            continue
        selected.append((day, day_type))
        used.add(day)
        if len(selected) >= run_days:
            break

    for day in ["Tuesday", "Thursday"]:
        if len([x for x in selected if x[1] == "forza"]) >= force_days:
            break
        if day not in used and force_days > 0:
            selected.append((day, "forza"))
            used.add(day)

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    types = {d: t for d, t in selected}
    session_days = [d for d in day_order if d in types]
    return session_days, types


def generate_plan(args: GenerationArgs, cfg: dict, enforce_tid: bool = False):
    week_starts = list(iter_week_starts(args.start_date, args.end_date))
    shares = cfg["defaults"]["session_shares"]
    session_days = cfg["defaults"]["session_days"]
    types_by_day = cfg["defaults"]["session_types_by_day"]
    profile = load_json(PROFILE_FILE, {})
    session_days, types_by_day = session_template_from_preferences(profile, session_days, types_by_day)
    weekly_cfg = cfg["defaults"]["weekly_km"]
    deload_n = int(weekly_cfg["deload_every_n_weeks"])
    zones = load_zones()

    targets = build_week_targets(len(week_starts), args, cfg)
    weeks = []
    active_running_types = [types_by_day[d] for d in session_days if types_by_day.get(d) != "forza"]
    base_share_sum = sum(float(shares.get(t, 0.0)) for t in active_running_types)
    normalized_shares = {}
    if base_share_sum > 0:
        for t in set(active_running_types):
            normalized_shares[t] = float(shares.get(t, 0.0)) / base_share_sum
    else:
        even = 1.0 / max(1, len(set(active_running_types)))
        for t in set(active_running_types):
            normalized_shares[t] = even
    for idx, wstart in enumerate(week_starts, 1):
        wend = wstart + timedelta(days=6)
        target_km = int(round(targets[idx - 1]))
        phase = phase_for_week(wstart, wend, args.goal_race)
        is_deload_week = (idx % deload_n == 0)
        sessions = []

        for day_name in session_days:
            day_idx = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(day_name)
            session_date = wstart + timedelta(days=day_idx)
            if not (args.start_date <= session_date <= args.end_date):
                continue
            session_type = types_by_day.get(day_name, "easy")
            workout_label = PHASE_WORKOUT_LABEL.get(session_type, {}).get(phase, session_type)
            if is_deload_week and session_type == "qualita":
                workout_label = "test_5k"

            if session_type == "forza":
                km = 0.0
            elif workout_label == "test_5k":
                # Seduta test in scarico: volumi più contenuti (riscaldamento + test + defaticamento).
                km = float(int(round(max(6.0, min(9.0, target_km * 0.18)))))
            else:
                share = float(normalized_shares.get(session_type, shares.get(session_type, 0.25)))
                km = float(int(round(target_km * share)))

            structure = structure_for_session(session_type, phase, workout_label)
            detail = detailed_session_plan(session_type, phase, workout_label, km)

            sessions.append(
                {
                    "date": session_date.isoformat(),
                    "day_name": day_name,
                    "day_type": session_type,
                    "workout_label": workout_label,
                    "distance_km": km,
                    "structure": structure,
                    "session_plan": detail,
                    "pace_target": pace_target_for(session_type, phase, zones, workout_label),
                    "intensity_km": split_intensity_km(workout_label, km),
                    "source": "auto-generated",
                }
            )

        planned_total = int(round(sum(s["distance_km"] for s in sessions if s["day_type"] != "forza")))
        running_sessions = [s for s in sessions if s["day_type"] != "forza"]
        if running_sessions and planned_total != int(round(target_km)):
            delta = int(round(target_km - planned_total))
            adjusted = int(round(running_sessions[-1]["distance_km"])) + delta
            running_sessions[-1]["distance_km"] = float(max(1, adjusted))
            running_sessions[-1]["session_plan"] = detailed_session_plan(
                running_sessions[-1]["day_type"],
                phase,
                running_sessions[-1]["workout_label"],
                running_sessions[-1]["distance_km"],
            )
            running_sessions[-1]["intensity_km"] = split_intensity_km(
                running_sessions[-1]["workout_label"],
                running_sessions[-1]["distance_km"],
            )

        iso_year, iso_week, _ = wstart.isocalendar()
        tid_info = evaluate_tid(phase, sessions, cfg)
        if enforce_tid:
            tid_info = enforce_tid_for_week(phase, sessions, cfg, zones)

        weeks.append(
            {
                "week_index": idx,
                "iso_week": f"{iso_year}-W{iso_week:02d}",
                "start_date": wstart.isoformat(),
                "end_date": wend.isoformat(),
                "phase": phase,
                "target_km": int(target_km),
                "tid": tid_info,
                "sessions": sessions,
            }
        )

    # Summary TID aggregato (pesato sui km running, non media aritmetica delle settimane)
    aligned_weeks = sum(1 for w in weeks if w.get("tid", {}).get("aligned"))
    total_weeks = len(weeks)
    total_running_km = round(sum(w["tid"]["total_running_km"] for w in weeks), 2) if total_weeks else 0.0
    total_low_km = round(sum(w["tid"]["low_km"] for w in weeks), 2) if total_weeks else 0.0
    total_mod_km = round(sum(w["tid"]["moderate_km"] for w in weeks), 2) if total_weeks else 0.0
    total_high_km = round(sum(w["tid"]["high_km"] for w in weeks), 2) if total_weeks else 0.0
    avg_low = round(total_low_km / total_running_km, 3) if total_running_km > 0 else 0.0
    avg_mod = round(total_mod_km / total_running_km, 3) if total_running_km > 0 else 0.0
    avg_high = round(total_high_km / total_running_km, 3) if total_running_km > 0 else 0.0

    payload = {
        "meta": {
            "version": "v1.0",
            "generated_at": datetime.now().isoformat(),
            "generated_by": "tv running generate",
            "enforce_tid": enforce_tid,
        },
        "planning_window": {
            "from": args.start_date.isoformat(),
            "to": args.end_date.isoformat(),
            "goal_race": args.goal_race.isoformat() if args.goal_race else None,
        },
        "tid_summary": {
            "aligned_weeks": aligned_weeks,
            "total_weeks": total_weeks,
            "total_running_km": total_running_km,
            "avg_low_pct": avg_low,
            "avg_moderate_pct": avg_mod,
            "avg_high_pct": avg_high,
        },
        "weeks": weeks,
    }
    return payload


def save_plan(payload: dict):
    ensure_athlete_dirs()
    PLAN_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_changelog(details: dict):
    ensure_athlete_dirs()
    try:
        data = json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {"entries": []}
    data.setdefault("entries", []).append(
        {
            "timestamp": datetime.now().isoformat(),
            "command": "running generate",
            "details": details,
        }
    )
    CHANGELOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_plan():
    if not PLAN_FILE.exists():
        raise FileNotFoundError(
            f"running_plan.json non trovato per atleta '{get_athlete_id()}'. "
            "Esegui: ./tv running generate ..."
        )
    return json.loads(PLAN_FILE.read_text(encoding="utf-8"))


def show_week(week_idx: int):
    plan = load_plan()
    weeks = plan.get("weeks", [])
    week = next((w for w in weeks if int(w["week_index"]) == week_idx), None)
    if not week:
        print(f"Settimana {week_idx} non trovata in {PLAN_FILE}")
        return 1

    print(f"PIANO RUNNING - WEEK {week['week_index']} ({week['iso_week']})")
    print(f"Periodo: {week['start_date']} -> {week['end_date']} | Fase: {week['phase']} | Target: {int(round(week['target_km']))} km")
    print()

    def load_tag(day_type: str, workout_label: str) -> str:
        if day_type == "forza":
            return "S&C"
        if workout_label in ("qualita_vo2_threshold", "test_5k"):
            return "HIGH"
        if day_type == "lungo":
            return "MED-HIGH"
        if day_type == "progressivo":
            return "MED"
        return "LOW"

    headers = ["#", "Data", "Giorno", "Tipo", "Load", "Km", "Ritmo"]
    rows = []
    for idx, s in enumerate(week["sessions"], 1):
        km_i = int(round(float(s["distance_km"])))
        rows.append(
            [
                str(idx),
                s["date"],
                s["day_name"][:3],
                s["day_type"].upper(),
                load_tag(s["day_type"], s.get("workout_label", s["day_type"])),
                str(km_i),
                s.get("pace_target", "N/A"),
            ]
        )

    widths = [len(h) for h in headers]
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(c))

    def fmt_row(cols):
        return " | ".join(col.ljust(widths[i]) for i, col in enumerate(cols))

    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt_row(r))

    print()
    print("Dettaglio Sedute")
    print("-" * 80)
    for idx, s in enumerate(week["sessions"], 1):
        print(f"{idx}) {s['date']} {s['day_name']} - {s['day_type'].upper()} [{s.get('workout_label', s['day_type'])}]")
        print(f"   Focus: {s['structure']}")
        if s.get("session_plan"):
            print(f"   Piano: {s['session_plan']}")
        print()
    return 0


def show_month(month_yyyy_mm: str):
    plan = load_plan()
    weeks = plan.get("weeks", [])
    sessions = []
    for w in weeks:
        for s in w["sessions"]:
            if s["date"].startswith(month_yyyy_mm + "-"):
                sessions.append(s)

    if not sessions:
        print(f"Nessuna sessione trovata per {month_yyyy_mm}")
        return 1

    totals = defaultdict(float)
    counts = defaultdict(int)
    for s in sessions:
        totals[s["day_type"]] += float(s["distance_km"])
        counts[s["day_type"]] += 1

    print(f"PIANO RUNNING - MONTH {month_yyyy_mm}")
    print(f"Sessioni: {len(sessions)} | Totale km: {int(round(sum(float(s['distance_km']) for s in sessions)))}")
    for day_type in ["easy", "qualita", "progressivo", "lungo", "forza"]:
        if counts[day_type] > 0:
            print(f"- {day_type}: {counts[day_type]} sessioni | {int(round(totals[day_type]))} km")
    return 0


def show_summary():
    plan = load_plan()
    weeks = plan.get("weeks", [])
    if not weeks:
        print("Piano vuoto.")
        return 1

    month_totals = defaultdict(float)
    test_weeks = 0
    tid_issues = 0
    for w in weeks:
        if any(s.get("workout_label") == "test_5k" for s in w["sessions"]):
            test_weeks += 1
        if not w.get("tid", {}).get("aligned", True):
            tid_issues += 1
        for s in w["sessions"]:
            ym = s["date"][:7]
            month_totals[ym] += float(s["distance_km"])

    print("RUNNING PLAN SUMMARY")
    print(
        "Periodo: {from_d} -> {to_d} | Goal race: {goal}".format(
            from_d=plan["planning_window"]["from"],
            to_d=plan["planning_window"]["to"],
            goal=plan["planning_window"]["goal_race"] or "N/A",
        )
    )
    print(f"Settimane: {len(weeks)} | Km totali: {int(round(sum(w['target_km'] for w in weeks)))}")
    print(f"Settimane scarico con test 5km: {test_weeks}")
    tid_summary = plan.get("tid_summary", {})
    if tid_summary:
        print(
            "TID medio (low/mod/high): {low:.1f}% / {mod:.1f}% / {high:.1f}% | allineate: {ok}/{tot} | issue: {issue}".format(
                low=tid_summary.get("avg_low_pct", 0) * 100,
                mod=tid_summary.get("avg_moderate_pct", 0) * 100,
                high=tid_summary.get("avg_high_pct", 0) * 100,
                ok=tid_summary.get("aligned_weeks", 0),
                tot=tid_summary.get("total_weeks", 0),
                issue=tid_issues,
            )
        )
    print("Volumi mensili:")
    for ym in sorted(month_totals.keys()):
        print(f"- {ym}: {int(round(month_totals[ym]))} km")
    print("Taper preview:")
    for w in weeks[-3:]:
        print(f"- W{w['week_index']} ({w['iso_week']}): {int(round(w['target_km']))} km | {w['phase']}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="running_plan.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--from", dest="from_date", required=True)
    g.add_argument("--to", dest="to_date", required=True)
    g.add_argument("--goal-race", dest="goal_race", required=False)
    g.add_argument("--start-km", dest="start_km", type=float, default=0.0)
    g.add_argument("--peak-km", dest="peak_km", type=float, default=0.0)
    g.add_argument("--enforce-tid", dest="enforce_tid", action="store_true")

    w = sub.add_parser("week")
    w.add_argument("week_index", type=int)

    m = sub.add_parser("month")
    m.add_argument("month_yyyy_mm")

    sub.add_parser("summary")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "generate":
        cfg = load_config()
        gen_args = GenerationArgs(
            start_date=parse_date(args.from_date),
            end_date=parse_date(args.to_date),
            goal_race=parse_date(args.goal_race) if args.goal_race else (
                parse_date(cfg.get("planning_defaults", {}).get("goal_race_date"))
                if cfg.get("planning_defaults", {}).get("goal_race_date")
                else None
            ),
            start_km=float(args.start_km),
            peak_km=float(args.peak_km),
        )
        if gen_args.start_date > gen_args.end_date:
            print("Errore: --from deve essere <= --to")
            return 1

        payload = generate_plan(gen_args, cfg, enforce_tid=bool(args.enforce_tid))
        save_plan(payload)
        total_km = round(sum(w["target_km"] for w in payload["weeks"]), 1)
        append_changelog(
            {
                "from": gen_args.start_date.isoformat(),
                "to": gen_args.end_date.isoformat(),
                "goal_race": gen_args.goal_race.isoformat() if gen_args.goal_race else None,
                "weeks": len(payload["weeks"]),
                "total_target_km": total_km,
                "enforce_tid": bool(args.enforce_tid),
                "updated_files": [str(PLAN_FILE)],
                "athlete_id": get_athlete_id(),
            }
        )
        print(
            f"[OK] running_plan.json generato: settimane={len(payload['weeks'])} "
            f"km_totali={total_km} periodo={gen_args.start_date}->{gen_args.end_date} atleta={get_athlete_id()}"
        )
        return 0

    if args.cmd == "week":
        return show_week(args.week_index)

    if args.cmd == "month":
        return show_month(args.month_yyyy_mm)

    if args.cmd == "summary":
        return show_summary()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
