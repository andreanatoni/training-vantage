import unittest

from scripts.nutrition.plan import get_plan_adjustment, resolve_phase_adjustment


BASE_CONFIG = {
    "category_to_day_profile": {
        "rest": "rest",
        "qualita": "qualita",
    },
    "day_profiles": {
        "rest": {"deficit_pct_range": [0.12, 0.16], "training_cost_kcal_estimate": 0},
        "qualita": {"deficit_pct_range": [0.0, 0.05], "training_cost_kcal_estimate": 700},
    },
    "energy_availability": {
        "hard_floor_kcal_per_kg_ffm": 30,
        "target_min_kcal_per_kg_ffm": 35,
    },
}


class NutritionPhaseAdjustmentTests(unittest.TestCase):
    def test_resolve_phase_adjustment_uses_profile_first(self):
        cfg = {
            "phase_adjustments": {
                "taper": {
                    "default": {"deficit_pct_delta": -0.02},
                    "qualita": {"deficit_pct_override": 0.0},
                }
            }
        }
        adj = resolve_phase_adjustment(cfg, "taper", "qualita")
        self.assertEqual(adj["scope"], "qualita")
        self.assertEqual(adj["deficit_pct_override"], 0.0)

    def test_get_plan_adjustment_applies_phase_delta(self):
        cfg = dict(BASE_CONFIG)
        cfg["phase_adjustments"] = {
            "taper": {
                "default": {
                    "deficit_pct_delta": -0.03,
                    "note": "recovery-priority",
                }
            }
        }
        body = {"ffm": 60.0}
        adj = get_plan_adjustment("rest", body, cfg, phase="taper")
        self.assertAlmostEqual(adj["deficit_pct"], 0.11, places=3)
        self.assertEqual(adj["phase_adjustment"]["note"], "recovery-priority")

    def test_get_plan_adjustment_applies_phase_override(self):
        cfg = dict(BASE_CONFIG)
        cfg["phase_adjustments"] = {
            "race": {
                "default": {"deficit_pct_override": 0.0}
            }
        }
        body = {"ffm": 60.0}
        adj = get_plan_adjustment("rest", body, cfg, phase="race")
        self.assertEqual(adj["deficit_pct"], 0.0)

    def test_get_plan_adjustment_clamps_negative_deficit(self):
        cfg = dict(BASE_CONFIG)
        cfg["phase_adjustments"] = {"taper": {"default": {"deficit_pct_delta": -1.0}}}
        body = {"ffm": 60.0}
        adj = get_plan_adjustment("rest", body, cfg, phase="taper")
        self.assertEqual(adj["deficit_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()

