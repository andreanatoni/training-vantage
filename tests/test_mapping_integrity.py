import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOOD_DB = ROOT / "data" / "FOOD_DB.json"
MAPPING = ROOT / "data" / "FOOD_DB_TO_LARN_MAPPING.json"
LARN = ROOT / "data" / "LARN_PORTIONS.json"


class MappingIntegrityTests(unittest.TestCase):
    def test_mapping_is_complete_and_valid(self):
        food_db = json.loads(FOOD_DB.read_text(encoding="utf-8"))
        mapping_db = json.loads(MAPPING.read_text(encoding="utf-8"))
        larn_db = json.loads(LARN.read_text(encoding="utf-8"))

        food_ids = {f["id"] for f in food_db.get("foods", []) if f.get("id")}
        valid_larn_ids = {p["id"] for p in larn_db.get("portions", []) if p.get("id")}

        mapping_entries = mapping_db.get("mapping", [])
        mapped_ids = []

        for m in mapping_entries:
            fid = m.get("food_db_id")
            if not fid:
                self.fail("Found mapping entry without food_db_id")

            mapped_ids.append(fid)
            self.assertIn(fid, food_ids, f"Unknown food_db_id in mapping: {fid}")

            larn_id = m.get("larn_portion_id")
            self.assertIsNotNone(larn_id, f"Missing larn_portion_id for {fid}")
            self.assertIn(larn_id, valid_larn_ids, f"Invalid larn_portion_id for {fid}: {larn_id}")

            operational_id = m.get("operational_portion_id")
            self.assertTrue(
                operational_id is None,
                f"operational_portion_id must be None in frozen mapping for {fid}",
            )

        self.assertEqual(len(mapped_ids), len(set(mapped_ids)), "Duplicate food_db_id entries in mapping")
        self.assertEqual(set(mapped_ids), food_ids, "Mapping must cover exactly all FOOD_DB ids")


if __name__ == "__main__":
    unittest.main()
