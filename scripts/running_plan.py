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


ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
CONFIG_FILE = DATA_DIR / "RUNNING_PLAN_CONFIG.json"
PLAN_FILE = DATA_DIR / "running_plan.json"
CHANGELOG_FILE = DATA_DIR / "changelog.json"
ZONES_FILE = DATA_DIR / "zones.json"


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
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config():
    ensure_config()
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


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
    session["structure"] = structure_for_session(day_type, phase, wl)
    session["pace_target"] = pace_target_for(day_type, phase, zones, wl)
    session["intensity_km"] = split_intensity_km(wl, float(session.get("distance_km", 0.0)))


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


def generate_plan(args: GenerationArgs, cfg: dict, enforce_tid: bool = False):
    week_starts = list(iter_week_starts(args.start_date, args.end_date))
    shares = cfg["defaults"]["session_shares"]
    session_days = cfg["defaults"]["session_days"]
    types_by_day = cfg["defaults"]["session_types_by_day"]
    weekly_cfg = cfg["defaults"]["weekly_km"]
    deload_n = int(weekly_cfg["deload_every_n_weeks"])
    zones = load_zones()

    targets = build_week_targets(len(week_starts), args, cfg)
    weeks = []
    for idx, wstart in enumerate(week_starts, 1):
        wend = wstart + timedelta(days=6)
        target_km = targets[idx - 1]
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
                km = round(max(6.0, min(9.0, target_km * 0.18)), 1)
            else:
                share = float(shares.get(session_type, 0.25))
                km = round(target_km * share, 1)

            structure = structure_for_session(session_type, phase, workout_label)

            sessions.append(
                {
                    "date": session_date.isoformat(),
                    "day_name": day_name,
                    "day_type": session_type,
                    "workout_label": workout_label,
                    "distance_km": km,
                    "structure": structure,
                    "pace_target": pace_target_for(session_type, phase, zones, workout_label),
                    "intensity_km": split_intensity_km(workout_label, km),
                    "source": "auto-generated",
                }
            )

        planned_total = round(sum(s["distance_km"] for s in sessions if s["day_type"] != "forza"), 1)
        running_sessions = [s for s in sessions if s["day_type"] != "forza"]
        if running_sessions and planned_total != round(target_km, 1):
            delta = round(target_km - planned_total, 1)
            running_sessions[-1]["distance_km"] = round(running_sessions[-1]["distance_km"] + delta, 1)

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
                "target_km": round(target_km, 1),
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
    PLAN_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_changelog(details: dict):
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
        raise FileNotFoundError("running_plan.json non trovato. Esegui: ./tv running generate ...")
    return json.loads(PLAN_FILE.read_text(encoding="utf-8"))


def show_week(week_idx: int):
    plan = load_plan()
    weeks = plan.get("weeks", [])
    week = next((w for w in weeks if int(w["week_index"]) == week_idx), None)
    if not week:
        print(f"Settimana {week_idx} non trovata in data/running_plan.json")
        return 1

    print(f"PIANO RUNNING - WEEK {week['week_index']} ({week['iso_week']})")
    print(f"Periodo: {week['start_date']} -> {week['end_date']} | Fase: {week['phase']} | Target: {week['target_km']} km")
    for s in week["sessions"]:
        print(
            f"- {s['date']} {s['day_name']}: {s['day_type']} ({s.get('workout_label', s['day_type'])}) "
            f"| {s['distance_km']} km | {s['structure']} | ritmo: {s.get('pace_target', 'N/A')}"
        )
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
    print(f"Sessioni: {len(sessions)} | Totale km: {sum(float(s['distance_km']) for s in sessions):.1f}")
    for day_type in ["easy", "qualita", "progressivo", "lungo", "forza"]:
        if counts[day_type] > 0:
            print(f"- {day_type}: {counts[day_type]} sessioni | {totals[day_type]:.1f} km")
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
    print(f"Settimane: {len(weeks)} | Km totali: {sum(w['target_km'] for w in weeks):.1f}")
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
        print(f"- {ym}: {month_totals[ym]:.1f} km")
    print("Taper preview:")
    for w in weeks[-3:]:
        print(f"- W{w['week_index']} ({w['iso_week']}): {w['target_km']} km | {w['phase']}")
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
            goal_race=parse_date(args.goal_race) if args.goal_race else None,
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
                "updated_files": ["data/running_plan.json"],
            }
        )
        print(
            f"[OK] running_plan.json generato: settimane={len(payload['weeks'])} "
            f"km_totali={total_km} periodo={gen_args.start_date}->{gen_args.end_date}"
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
