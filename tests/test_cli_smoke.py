import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from food_add import (  # noqa: E402
    find_food_by_target,
    find_similar_food_names,
    format_similarity_table,
    is_affirmative,
    make_food_id,
    parse_crea_text,
    parse_reference,
    to_float,
)
from crea_import import parse_crea_index_text  # noqa: E402
from import_training_load import (  # noqa: E402
    build_training_load_payload,
    classify_day_type,
)
from sync_food_db import is_markdown_in_sync  # noqa: E402


def run_cmd(*args):
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class CliSmokeTests(unittest.TestCase):
    def test_help(self):
        result = run_cmd("./tv", "help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("USAGE: tv <command> [args]", result.stdout)

    def test_status(self):
        result = run_cmd("./tv", "status")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("TRAINING VANTAGE STATUS", result.stdout)

    def test_zones_show(self):
        result = run_cmd("./tv", "zones")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ZONE RUNNING ATTUALI", result.stdout)

    def test_week_show(self):
        result = run_cmd("./tv", "week", "1")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("PIANO RUNNING", result.stdout)

    def test_running_generate_summary_week(self):
        result = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-03-01",
            "--to",
            "2026-03-31",
            "--goal-race",
            "2026-04-26",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("running_plan.json", result.stdout)

        summary = run_cmd("./tv", "running", "summary")
        self.assertEqual(summary.returncode, 0, msg=summary.stderr)
        self.assertIn("RUNNING PLAN SUMMARY", summary.stdout)

        week = run_cmd("./tv", "running", "week", "1")
        self.assertEqual(week.returncode, 0, msg=week.stderr)
        self.assertIn("PIANO RUNNING - WEEK 1", week.stdout)

        running_plan = json.loads((ROOT / "data/running_plan.json").read_text(encoding="utf-8"))
        first_week_with_sessions = next(w for w in running_plan["weeks"] if w["sessions"])
        day_types = [s["day_type"] for s in first_week_with_sessions["sessions"]]
        self.assertIn("forza", day_types)
        self.assertEqual(day_types.count("forza"), 2)

    def test_running_deload_week_has_test_5k(self):
        result = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-03-01",
            "--to",
            "2026-05-31",
            "--goal-race",
            "2026-10-18",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        running_plan = json.loads((ROOT / "data/running_plan.json").read_text(encoding="utf-8"))
        has_test = any(
            s.get("workout_label") == "test_5k"
            for w in running_plan["weeks"]
            for s in w["sessions"]
        )
        self.assertTrue(has_test)

    def test_running_phase_specific_content(self):
        result = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-09-01",
            "--to",
            "2026-10-20",
            "--goal-race",
            "2026-10-18",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        running_plan = json.loads((ROOT / "data/running_plan.json").read_text(encoding="utf-8"))

        phases = {w["phase"] for w in running_plan["weeks"]}
        self.assertIn("specific", phases)
        self.assertIn("taper", phases)
        self.assertIn("race", phases)

        qualita_specific = [
            s for w in running_plan["weeks"] if w["phase"] == "specific"
            for s in w["sessions"] if s["day_type"] == "qualita"
        ]
        self.assertTrue(any("ritmo gara" in s["structure"].lower() for s in qualita_specific))

    def test_running_tid_fields(self):
        result = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-03-01",
            "--to",
            "2026-04-30",
            "--goal-race",
            "2026-10-18",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        running_plan = json.loads((ROOT / "data/running_plan.json").read_text(encoding="utf-8"))
        self.assertIn("tid_summary", running_plan)
        first_with_sessions = next(w for w in running_plan["weeks"] if w["sessions"])
        self.assertIn("tid", first_with_sessions)
        tid = first_with_sessions["tid"]
        for key in ["low_pct", "moderate_pct", "high_pct", "aligned", "warnings"]:
            self.assertIn(key, tid)

    def test_running_enforce_tid_improves_or_equal_alignment(self):
        base = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-09-01",
            "--to",
            "2026-10-20",
            "--goal-race",
            "2026-10-18",
        )
        self.assertEqual(base.returncode, 0, msg=base.stderr)
        base_plan = json.loads((ROOT / "data/running_plan.json").read_text(encoding="utf-8"))
        base_aligned = int(base_plan.get("tid_summary", {}).get("aligned_weeks", 0))

        enforced = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-09-01",
            "--to",
            "2026-10-20",
            "--goal-race",
            "2026-10-18",
            "--enforce-tid",
        )
        self.assertEqual(enforced.returncode, 0, msg=enforced.stderr)
        enforced_plan = json.loads((ROOT / "data/running_plan.json").read_text(encoding="utf-8"))
        self.assertTrue(enforced_plan.get("meta", {}).get("enforce_tid"))
        enforced_aligned = int(enforced_plan.get("tid_summary", {}).get("aligned_weeks", 0))
        self.assertGreaterEqual(enforced_aligned, base_aligned)

    def test_plan_week_from_running_plan(self):
        gen = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-03-01",
            "--to",
            "2026-03-31",
            "--goal-race",
            "2026-04-26",
        )
        self.assertEqual(gen.returncode, 0, msg=gen.stderr)

        plan_week = run_cmd("./tv", "plan", "week", "2026-W11")
        self.assertEqual(plan_week.returncode, 0, msg=plan_week.stderr)
        self.assertIn("Piano week 2026-W11", plan_week.stdout)

        week_dir = ROOT / "plans" / "nutrition" / "weeks" / "2026-W11"
        self.assertTrue((week_dir / "week-summary.md").exists())
        self.assertTrue((week_dir / "week-summary.json").exists())
        sample_day = week_dir / "2026-03-11-qualita.json"
        self.assertTrue(sample_day.exists())
        payload = json.loads(sample_day.read_text(encoding="utf-8"))
        self.assertEqual(payload["engine"]["training_cost_source"], "running_plan_day")
        self.assertEqual(payload["engine"]["session_date"], "2026-03-11")
        self.assertIsNotNone(payload["engine"]["phase"])

    def test_plan_month_from_running_plan(self):
        gen = run_cmd(
            "./tv",
            "running",
            "generate",
            "--from",
            "2026-03-01",
            "--to",
            "2026-03-31",
            "--goal-race",
            "2026-04-26",
        )
        self.assertEqual(gen.returncode, 0, msg=gen.stderr)

        plan_month = run_cmd("./tv", "plan", "month", "2026-03")
        self.assertEqual(plan_month.returncode, 0, msg=plan_month.stderr)
        self.assertIn("Piano month 2026-03", plan_month.stdout)

        month_dir = ROOT / "plans" / "nutrition" / "months" / "2026-03"
        self.assertTrue((month_dir / "month-summary.md").exists())
        self.assertTrue((month_dir / "month-summary.json").exists())
        sample_day = month_dir / "2026-03-14-lungo.json"
        self.assertTrue(sample_day.exists())
        payload = json.loads(sample_day.read_text(encoding="utf-8"))
        self.assertEqual(payload["engine"]["training_cost_source"], "running_plan_day")
        self.assertEqual(payload["engine"]["session_date"], "2026-03-14")

    def test_analyze(self):
        result = run_cmd("./tv", "analyze", "sources/storico.csv")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ANALISI EXPORT GARMIN", result.stdout)

    def test_food_check(self):
        result = run_cmd("./tv", "food", "check")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("[CHECK] FOOD_DB OK", result.stdout)

    def test_food_help_contains_crea_commands(self):
        result = run_cmd("./tv", "help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("food crawl-index", result.stdout)
        self.assertIn("food import-crea", result.stdout)

    def test_food_extract_portions(self):
        result = run_cmd("./tv", "food", "extract-portions")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("PORTION_STANDARDS.json", result.stdout)

    def test_load_import_planned_workouts(self):
        result = run_cmd("./tv", "load", "import", "sources/workouts-2.csv")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("training_load.json", result.stdout)


class JsonSchemaLikeTests(unittest.TestCase):
    def test_composition_schema_min(self):
        data = json.loads((ROOT / "data/composition.json").read_text(encoding="utf-8"))
        self.assertIn("measurements", data)
        self.assertIsInstance(data["measurements"], list)
        self.assertGreater(len(data["measurements"]), 0)

        latest = data["measurements"][-1]
        for key in ["date", "weight", "bf_pct", "ffm", "bmr"]:
            self.assertIn(key, latest)

    def test_zones_schema_min(self):
        data = json.loads((ROOT / "data/zones.json").read_text(encoding="utf-8"))
        self.assertIn("current", data)
        self.assertIn("history", data)
        self.assertIn("zones", data["current"])
        for zone_id in ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7", "Z8"]:
            self.assertIn(zone_id, data["current"]["zones"])

    def test_running_log_schema_min(self):
        data = json.loads((ROOT / "data/running-log.json").read_text(encoding="utf-8"))
        self.assertIn("weeks", data)
        self.assertIsInstance(data["weeks"], list)
        self.assertGreater(len(data["weeks"]), 0)
        first = data["weeks"][0]
        for key in ["week", "mesociclo", "sessions"]:
            self.assertIn(key, first)

    def test_portion_standards_schema_min(self):
        data = json.loads((ROOT / "data/PORTION_STANDARDS.json").read_text(encoding="utf-8"))
        for key in [
            "meta",
            "table_1_definitions",
            "table_2_standard_portions",
            "table_3_raw_to_cooked",
            "table_4_pediatric_portions",
            "table_5_household_volumes_ml",
            "table_6_spoon_weights_g",
        ]:
            self.assertIn(key, data)

    def test_food_markdown_in_sync(self):
        self.assertTrue(is_markdown_in_sync())


class FoodAddParserTests(unittest.TestCase):
    def test_parse_crea_text(self):
        sample = """
        <title>AlimentiNUTrizione - Yogurt greco, 0% lipidi</title>
        <table>
          <tr class="corponutriente"><td>Energia (kcal)</td><td>kcal</td><td>51&nbsp;</td></tr>
          <tr class="corponutriente"><td>Proteine (g)</td><td>g</td><td>9.0&nbsp;</td></tr>
          <tr class="corponutriente"><td>Lipidi (g)</td><td>g</td><td>0&nbsp;</td></tr>
          <tr class="corponutriente"><td>Carboidrati disponibili (g)</td><td>g</td><td>4.0&nbsp;</td></tr>
          <tr class="corponutriente"><td>Fibra totale (g)</td><td>g</td><td>0&nbsp;</td></tr>
        </table>
        """
        parsed = parse_crea_text(sample)
        self.assertEqual(parsed["food_name"], "Yogurt greco, 0% lipidi")
        self.assertEqual(parsed["reference"], "100 g")
        self.assertAlmostEqual(parsed["kcal"], 51.0)
        self.assertAlmostEqual(parsed["protein"], 9.0)
        self.assertAlmostEqual(parsed["cho"], 4.0)
        self.assertAlmostEqual(parsed["fat"], 0.0)

    def test_make_food_id(self):
        self.assertEqual(make_food_id("Yogurt greco, 0% lipidi"), "yogurt_greco_0_lipidi")
        self.assertEqual(make_food_id("Ragù di vitello"), "ragu_di_vitello")

    def test_parse_reference(self):
        parsed = parse_reference("170 g vasetto")
        self.assertEqual(parsed["amount"], 170.0)
        self.assertEqual(parsed["unit"], "g")
        self.assertEqual(parsed["label"], "170 g vasetto")
        self.assertEqual(parsed["note"], "vasetto")

    def test_find_similar_food_names(self):
        names = [
            "Yogurt greco 0%",
            "Yogurt magro 0.1%",
            "Pane integrale",
        ]
        similar = find_similar_food_names("Yogurt greco, 0% lipidi", names)
        self.assertGreater(len(similar), 0)
        self.assertEqual(similar[0][0], "Yogurt greco 0%")

    def test_similarity_table(self):
        proposed = {
            "food_name": "Yogurt greco, 0% lipidi",
            "reference": "100 g",
            "kcal": 51.0,
            "protein": 9.0,
            "cho": 4.0,
            "fat": 0.0,
            "fiber": 0.0,
        }
        matches = [
            {
                "score": 0.80,
                "food": {
                    "name": "Yogurt greco 0%",
                    "reference": {"label": "170 g vasetto"},
                    "nutrients_per_reference": {
                        "kcal": 100.0,
                        "P": 17.0,
                        "CHO": 6.0,
                        "F": 0.0,
                        "Fibre": 0.0,
                    },
                },
            }
        ]
        table = format_similarity_table(proposed, matches)
        self.assertIn("| PROPOSTO | Yogurt greco, 0% lipidi |", table)
        self.assertIn("| MATCH | Yogurt greco 0% | 0.80 |", table)

    def test_find_food_by_target(self):
        foods = [
            {"id": "yogurt_greco_0", "name": "Yogurt greco 0%"},
            {"id": "pane_integrale", "name": "Pane integrale"},
        ]
        by_id = find_food_by_target(foods, "yogurt_greco_0")
        by_name = find_food_by_target(foods, "Pane integrale")
        self.assertEqual(by_id["name"], "Yogurt greco 0%")
        self.assertEqual(by_name["id"], "pane_integrale")

    def test_is_affirmative(self):
        self.assertTrue(is_affirmative("y"))
        self.assertTrue(is_affirmative("si"))
        self.assertFalse(is_affirmative("n"))

    def test_to_float_handles_trace(self):
        self.assertEqual(to_float("tr"), 0.0)
        self.assertEqual(to_float("-"), 0.0)
        self.assertAlmostEqual(to_float("0,8"), 0.8)


class CreaImportTests(unittest.TestCase):
    def test_parse_crea_index_text(self):
        sample = """
        <a href="/tabelle-nutrizionali/150030">Yogurt greco, 0% lipidi</a>
        <a href="/tabelle-nutrizionali/202020">&quot;Caramelle&quot;</a>
        <a href="/tabelle-nutrizionali/120010">Avocado</a>
        <a href="/tabelle-nutrizionali/150030">Yogurt greco, 0% lipidi</a>
        <a href="/tabelle-nutrizionali/ricerca-per-ordine-alfabetico">Index</a>
        """
        items = parse_crea_index_text(sample)
        self.assertEqual(len(items), 3)
        ids = {item["crea_id"] for item in items}
        self.assertIn("150030", ids)
        self.assertIn("120010", ids)
        self.assertIn("202020", ids)
        names = {item["name"] for item in items}
        self.assertIn("Caramelle", names)


class TrainingLoadImportTests(unittest.TestCase):
    def test_classify_day_type(self):
        self.assertEqual(classify_day_type("1h20' L", "Run"), "lungo")
        self.assertEqual(classify_day_type("5x1km RM + Rec 1'30\"", "Run"), "qualita")
        self.assertEqual(classify_day_type("3L+3x(1L+1M+1TR)", "Run"), "progressivo")
        self.assertEqual(classify_day_type("13x[0.85L+0.15All]", "Run"), "easy")

    def test_build_training_load_payload(self):
        payload = build_training_load_payload(ROOT / "sources/workouts-2.csv")
        self.assertIn("meta", payload)
        self.assertIn("summary", payload)
        self.assertIn("sessions", payload)
        self.assertIn("profile_costs_kcal", payload)
        self.assertEqual(payload["meta"]["mode"], "planned_only")
        self.assertEqual(payload["summary"]["sessions_count"], 4)


if __name__ == "__main__":
    unittest.main()
