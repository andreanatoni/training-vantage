import json
import unittest
from pathlib import Path

from scripts.nutrition.meal_options_repository import (
    CATEGORY_SOURCES,
    MEAL_OPTIONS_DIR,
    build_all_from_stale,
    load_plan_for_category,
)


class MealOptionsRepositoryTests(unittest.TestCase):
    def test_build_and_load_structured_meal_options(self):
        generated = build_all_from_stale()
        self.assertEqual(len(generated), len(CATEGORY_SOURCES))

        for category in CATEGORY_SOURCES:
            path = MEAL_OPTIONS_DIR / f"{category}.json"
            self.assertTrue(path.exists(), f"Missing meal options file for {category}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("plan", payload)
            plan = load_plan_for_category(category)
            self.assertIn("meals", plan)
            self.assertIn("target_kcal", plan)

    def test_load_fails_when_structured_file_missing(self):
        category = "forza"
        path = MEAL_OPTIONS_DIR / f"{category}.json"
        backup = path.read_text(encoding="utf-8")
        path.unlink()
        try:
            with self.assertRaises(FileNotFoundError):
                load_plan_for_category(category)
        finally:
            path.write_text(backup, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
