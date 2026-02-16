#!/usr/bin/env python3
"""Utility per risoluzione path multi-atleta."""

import os
import re
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
PLANS_DIR = ROOT_DIR / "plans" / "nutrition"
ATHLETES_SUBDIR = "athletes"
DEFAULT_ATHLETE_ID = "default"
LEGACY_RUNTIME_FILES = {
    "composition.json",
    "zones.json",
    "running-log.json",
    "running_plan.json",
    "training_load.json",
    "RUNNING_PLAN_CONFIG.json",
    "RUNNING_ATHLETE_PROFILE.json",
    "changelog.json",
    "strength-progress.json",
}


def normalize_athlete_id(raw):
    txt = (raw or DEFAULT_ATHLETE_ID).strip().lower()
    txt = re.sub(r"[^a-z0-9_-]+", "-", txt).strip("-")
    return txt or DEFAULT_ATHLETE_ID


def get_athlete_id():
    return normalize_athlete_id(os.environ.get("TV_ATHLETE_ID", DEFAULT_ATHLETE_ID))


def is_default_athlete():
    return get_athlete_id() == DEFAULT_ATHLETE_ID


def athlete_data_dir():
    return DATA_DIR / ATHLETES_SUBDIR / get_athlete_id()


def athlete_knowledge_dir():
    return KNOWLEDGE_DIR / ATHLETES_SUBDIR / get_athlete_id()


def athlete_plans_dir():
    return PLANS_DIR / ATHLETES_SUBDIR / get_athlete_id()


def data_file(filename):
    target = athlete_data_dir() / filename
    # Backward compatibility: migrate legacy default runtime files on first access.
    if (
        get_athlete_id() == DEFAULT_ATHLETE_ID
        and filename in LEGACY_RUNTIME_FILES
        and not target.exists()
    ):
        legacy = DATA_DIR / filename
        if legacy.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
    return target


def ensure_athlete_dirs():
    athlete_data_dir().mkdir(parents=True, exist_ok=True)
    athlete_knowledge_dir().mkdir(parents=True, exist_ok=True)
    athlete_plans_dir().mkdir(parents=True, exist_ok=True)


def relpath_or_str(path):
    p = Path(path)
    try:
        return str(p.relative_to(ROOT_DIR))
    except Exception:
        return str(p)
