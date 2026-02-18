import unittest
from pathlib import Path

from scripts.food.data_validator import validate_all


ROOT = Path(__file__).resolve().parents[1]


class DataValidatorCatalogTests(unittest.TestCase):
    def test_catalog_validation_has_no_errors(self):
        report = validate_all(ROOT / "data", validate_catalog=True)
        catalog_errors = [e for e in report.errors if e.startswith("FOOD_CATALOG:")]
        self.assertEqual(catalog_errors, [], f"Unexpected FOOD_CATALOG errors: {catalog_errors[:3]}")


if __name__ == "__main__":
    unittest.main()
