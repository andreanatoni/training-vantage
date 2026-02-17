"""Shared path helpers, backed by athlete context."""

from scripts.athlete_context import (
    DATA_DIR,
    KNOWLEDGE_DIR,
    PLANS_DIR,
    DEFAULT_ATHLETE_ID,
    athlete_data_dir,
    athlete_knowledge_dir,
    athlete_plans_dir,
    data_file,
    ensure_athlete_dirs,
    get_athlete_id,
    normalize_athlete_id,
    relpath_or_str,
)

__all__ = [
    "DATA_DIR",
    "KNOWLEDGE_DIR",
    "PLANS_DIR",
    "DEFAULT_ATHLETE_ID",
    "athlete_data_dir",
    "athlete_knowledge_dir",
    "athlete_plans_dir",
    "data_file",
    "ensure_athlete_dirs",
    "get_athlete_id",
    "normalize_athlete_id",
    "relpath_or_str",
]

