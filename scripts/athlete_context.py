#!/usr/bin/env python3
"""Utility per risoluzione path multi-atleta."""

import os
import re
from pathlib import Path


ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
PLANS_DIR = ROOT_DIR / "plans" / "nutrition"
ATHLETES_SUBDIR = "athletes"
DEFAULT_ATHLETE_ID = "default"


def normalize_athlete_id(raw):
    txt = (raw or DEFAULT_ATHLETE_ID).strip().lower()
    txt = re.sub(r"[^a-z0-9_-]+", "-", txt).strip("-")
    return txt or DEFAULT_ATHLETE_ID


def get_athlete_id():
    return normalize_athlete_id(os.environ.get("TV_ATHLETE_ID", DEFAULT_ATHLETE_ID))


def is_default_athlete():
    return get_athlete_id() == DEFAULT_ATHLETE_ID


def athlete_data_dir():
    if is_default_athlete():
        return DATA_DIR
    return DATA_DIR / ATHLETES_SUBDIR / get_athlete_id()


def athlete_knowledge_dir():
    if is_default_athlete():
        return KNOWLEDGE_DIR
    return KNOWLEDGE_DIR / ATHLETES_SUBDIR / get_athlete_id()


def athlete_plans_dir():
    if is_default_athlete():
        return PLANS_DIR
    return PLANS_DIR / ATHLETES_SUBDIR / get_athlete_id()


def data_file(filename):
    return athlete_data_dir() / filename


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
