#!/usr/bin/env python3
"""Tests for meal_options custom_recipe validation rules."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.food.data_validator import validate_all


ROOT = Path(__file__).resolve().parents[1]


class MealOptionsCustomRecipeValidationTests(unittest.TestCase):
    def _prepare_temp_workspace(self) -> tuple[Path, Path]:
        tmp_root = Path(tempfile.mkdtemp(prefix="tv-meal-options-"))
        data_dir = tmp_root / "data"
        knowledge_dir = tmp_root / "knowledge" / "meal_options"

        data_dir.mkdir(parents=True, exist_ok=True)
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "athletes" / "default").mkdir(parents=True, exist_ok=True)

        for src in (ROOT / "data").glob("*.json"):
            shutil.copy(src, data_dir / src.name)

        shutil.copy(
            ROOT / "data" / "athletes" / "default" / "CUSTOM_RECIPES.json",
            data_dir / "athletes" / "default" / "CUSTOM_RECIPES.json",
        )

        for src in (ROOT / "knowledge" / "meal_options").glob("*.json"):
            shutil.copy(src, knowledge_dir / src.name)

        return tmp_root, data_dir

    def test_error_when_ingredient_has_no_food_id_and_not_custom_recipe(self):
        tmp_root, data_dir = self._prepare_temp_workspace()
        try:
            target = tmp_root / "knowledge" / "meal_options" / "rest.json"
            payload = json.loads(target.read_text(encoding="utf-8"))

            modified = False
            for meal in payload.get("plan", {}).get("meals", {}).values():
                for option in meal.get("options", []):
                    for ing in option.get("ingredients", []):
                        if ing.get("food_db_id"):
                            ing.pop("food_db_id", None)
                            ing["type"] = "single"
                            modified = True
                            break
                    if modified:
                        break
                if modified:
                    break

            self.assertTrue(modified, "Expected at least one ingredient with food_db_id")
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            os.environ["TV_ATHLETE_ID"] = "default"
            report = validate_all(data_dir)
            self.assertTrue(
                any("senza food_db_id" in err for err in report.errors),
                f"Expected missing food_db_id error, got: {report.errors[:3]}",
            )
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_error_when_custom_recipe_id_not_found(self):
        tmp_root, data_dir = self._prepare_temp_workspace()
        try:
            target = tmp_root / "knowledge" / "meal_options" / "rest.json"
            payload = json.loads(target.read_text(encoding="utf-8"))

            modified = False
            for meal in payload.get("plan", {}).get("meals", {}).values():
                for option in meal.get("options", []):
                    for ing in option.get("ingredients", []):
                        if ing.get("type") == "custom_recipe":
                            ing["recipe_id"] = "recipe_id_that_does_not_exist"
                            modified = True
                            break
                    if modified:
                        break
                if modified:
                    break

            self.assertTrue(modified, "Expected at least one custom_recipe ingredient")
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            os.environ["TV_ATHLETE_ID"] = "default"
            report = validate_all(data_dir)
            self.assertTrue(
                any("recipe_id 'recipe_id_that_does_not_exist' non trovato" in err for err in report.errors),
                f"Expected invalid recipe_id error, got: {report.errors[:3]}",
            )
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
