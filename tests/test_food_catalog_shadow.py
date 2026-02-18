import json
import tempfile
import unittest
from pathlib import Path
import shutil
import io
from contextlib import redirect_stdout, redirect_stderr
from scripts.nutrition.meal_balancer import MealBalancerData

ROOT = Path(__file__).resolve().parents[1]
FOOD_CATALOG = ROOT / "data" / "FOOD_CATALOG.json"
FOOD_DB = ROOT / "data" / "FOOD_DB.json"


class FoodCatalogShadowTests(unittest.TestCase):
    def test_food_catalog_shadow_is_coherent(self):
        catalog = json.loads(FOOD_CATALOG.read_text(encoding="utf-8"))
        food_db = json.loads(FOOD_DB.read_text(encoding="utf-8"))

        self.assertTrue(catalog.get("meta", {}).get("derived"), "FOOD_CATALOG must be marked as derived")
        self.assertEqual(catalog.get("meta", {}).get("version"), "v0-shadow")

        db_count = len(food_db.get("foods", []))
        stats = catalog.get("stats", {})

        self.assertEqual(stats.get("foods_total"), db_count)
        self.assertEqual(stats.get("catalog_foods_total"), db_count)
        self.assertEqual(stats.get("missing_mapping_count"), 0)
        self.assertEqual(stats.get("invalid_larn_mapping_count"), 0)

    def test_meal_balancer_uses_catalog_when_available(self):
        data = MealBalancerData(ROOT / "data")
        self.assertTrue(data.catalog_active, "MealBalancer should activate FOOD_CATALOG when valid")
        self.assertEqual(len(data.food_db_index), len(json.loads(FOOD_DB.read_text(encoding="utf-8")).get("foods", [])))
        sample = data.mapping_index.get("caffe_espresso")
        self.assertIsNotNone(sample, "Expected mapped entry for caffe_espresso via FOOD_CATALOG")
        self.assertTrue(sample.get("larn_portion_id"), "larn_portion_id should be present in catalog-derived mapping")

    def test_meal_balancer_fails_without_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            # Copy only unrelated file to ensure strict requirement on FOOD_CATALOG.
            shutil.copy(FOOD_DB, data_dir / "FOOD_DB.json")
            sink = io.StringIO()
            with redirect_stdout(sink), redirect_stderr(sink):
                with self.assertRaises(SystemExit):
                    MealBalancerData(data_dir)


if __name__ == "__main__":
    unittest.main()
