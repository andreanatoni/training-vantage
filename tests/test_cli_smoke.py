import json
import os
import subprocess
import sys
import unittest
import importlib.util
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ATHLETE_DATA_DIR = ROOT / "data" / "athletes" / "default"
DEFAULT_ATHLETE_PLANS_DIR = ROOT / "plans" / "nutrition" / "athletes" / "default"
sys.path.insert(0, str(ROOT))
from scripts.food.food_add import (  # noqa: E402
    find_food_by_target,
    find_similar_food_names,
    format_similarity_table,
    is_affirmative,
    make_food_id,
    parse_crea_text,
    parse_reference,
    to_float,
)
from scripts.food.crea_import import parse_crea_index_text  # noqa: E402
from scripts.running.import_training_load import (  # noqa: E402
    build_training_load_payload,
    classify_day_type,
)
from scripts.running.running_setup import (  # noqa: E402
    build_manual_training_payload,
    compute_weekly_km_params,
    estimate_no_history_defaults,
    normalize_days,
    parse_args as parse_running_setup_args,
    resolve_target_athlete_id,
)
from scripts.nutrition.setup_base import (  # noqa: E402
    auto_pick_foods_for_role,
    backfill_template_traces,
    build_option_autodraft,
    infer_when_to_use,
    load_required_nutrition_profile,
    MEAL_ORDER,
    infer_option_tags,
    parse_args as parse_nutrition_setup_args,
    resolve_target_athlete_id as resolve_nutrition_target_athlete_id,
    search_foods,
    suggest_roles_for_option,
    validate_template_quality,
)
from scripts.nutrition.setup_profile import (  # noqa: E402
    parse_args as parse_nutrition_profile_args,
    resolve_target_athlete_id as resolve_nutrition_profile_target_athlete_id,
)
from scripts.nutrition.validate_template import (  # noqa: E402
    validate_template_payload,
)
from scripts.nutrition.rules_engine import (  # noqa: E402
    evaluate_safety,
    suggest_scenario_for_meal,
    suggest_blocks,
)
from scripts.food.sync_food_db import is_markdown_in_sync  # noqa: E402
from scripts.nutrition.plan import (  # noqa: E402
    _build_or_combinations,
    _extract_food_ids_from_template_option,
    load_plan_for_category_with_athlete_template,
)


def run_cmd(*args):
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


@contextmanager
def without_default_template():
    template_path = DEFAULT_ATHLETE_DATA_DIR / "nutrition_base_template.json"
    existed = template_path.exists()
    backup = template_path.read_text(encoding="utf-8") if existed else None
    try:
        if existed:
            template_path.unlink()
        yield
    finally:
        if existed:
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(backup, encoding="utf-8")


class CliSmokeTests(unittest.TestCase):
    def test_help(self):
        result = run_cmd("./tv", "help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("USAGE: tv [--athlete <id>] <command> [args]", result.stdout)

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

        running_plan = json.loads((DEFAULT_ATHLETE_DATA_DIR / "running_plan.json").read_text(encoding="utf-8"))
        first_week_with_sessions = next(w for w in running_plan["weeks"] if w["sessions"])
        day_types = [s["day_type"] for s in first_week_with_sessions["sessions"]]
        self.assertGreater(len(day_types), 0)
        allowed = {"easy", "qualita", "progressivo", "lungo", "forza"}
        self.assertTrue(set(day_types).issubset(allowed))

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
        running_plan = json.loads((DEFAULT_ATHLETE_DATA_DIR / "running_plan.json").read_text(encoding="utf-8"))
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
        running_plan = json.loads((DEFAULT_ATHLETE_DATA_DIR / "running_plan.json").read_text(encoding="utf-8"))

        phases = {w["phase"] for w in running_plan["weeks"]}
        self.assertIn("specific", phases)
        self.assertIn("taper", phases)
        self.assertIn("race", phases)

        qualita_specific = [
            s for w in running_plan["weeks"] if w["phase"] == "specific"
            for s in w["sessions"] if s["day_type"] == "qualita"
        ]
        self.assertTrue(any("ritmo gara" in s["structure"].lower() for s in qualita_specific))

    def test_running_long_run_classic_only_disables_race_blocks(self):
        config_path = DEFAULT_ATHLETE_DATA_DIR / "RUNNING_PLAN_CONFIG.json"
        original = config_path.read_text(encoding="utf-8")
        try:
            cfg = json.loads(original)
            cfg.setdefault("defaults", {})["long_run_strategy"] = "classic_only"
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

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
            running_plan = json.loads((DEFAULT_ATHLETE_DATA_DIR / "running_plan.json").read_text(encoding="utf-8"))

            long_runs_specific = [
                s for w in running_plan["weeks"] if w["phase"] == "specific"
                for s in w["sessions"] if s["day_type"] == "lungo"
            ]
            self.assertTrue(long_runs_specific)
            self.assertTrue(all(s.get("workout_label") != "lungo_blocchi_ritmo_gara" for s in long_runs_specific))
            self.assertTrue(any(s.get("workout_label") == "lungo_aerobico" for s in long_runs_specific))
        finally:
            config_path.write_text(original, encoding="utf-8")

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
        running_plan = json.loads((DEFAULT_ATHLETE_DATA_DIR / "running_plan.json").read_text(encoding="utf-8"))
        self.assertIn("tid_summary", running_plan)
        first_with_sessions = next(w for w in running_plan["weeks"] if w["sessions"])
        self.assertIn("tid", first_with_sessions)
        tid = first_with_sessions["tid"]
        for key in ["low_pct", "moderate_pct", "high_pct", "aligned", "warnings"]:
            self.assertIn(key, tid)

    def test_running_setup_manual_payload_without_history(self):
        payload = build_manual_training_payload("test-athlete")
        self.assertEqual(payload["meta"]["mode"], "manual_no_history")
        self.assertEqual(payload["meta"]["athlete_id"], "test-athlete")
        self.assertEqual(payload["summary"]["sessions_count"], 0)
        self.assertEqual(payload["weeks"], [])
        self.assertEqual(payload["sessions"], [])

    def test_running_setup_parse_no_history_flag(self):
        args = parse_running_setup_args(["--no-history"])
        self.assertTrue(args.no_history)

    def test_running_setup_target_athlete_id_uses_name_when_default(self):
        original = os.environ.get("TV_ATHLETE_ID")
        try:
            os.environ["TV_ATHLETE_ID"] = "default"
            self.assertEqual(resolve_target_athlete_id("Matteo"), "matteo")
        finally:
            if original is None:
                os.environ.pop("TV_ATHLETE_ID", None)
            else:
                os.environ["TV_ATHLETE_ID"] = original

    def test_running_setup_target_athlete_id_respects_env_override(self):
        original = os.environ.get("TV_ATHLETE_ID")
        try:
            os.environ["TV_ATHLETE_ID"] = "spizz"
            self.assertEqual(resolve_target_athlete_id("Matteo"), "spizz")
        finally:
            if original is None:
                os.environ.pop("TV_ATHLETE_ID", None)
            else:
                os.environ["TV_ATHLETE_ID"] = original

    def test_running_setup_estimate_no_history_defaults(self):
        est = estimate_no_history_defaults(run_days=3, experience_level="beginner")
        self.assertEqual(est["avg_km"], 14.0)
        self.assertEqual(est["peak_km"], 17.0)
        self.assertEqual(est["min_start_km"], 16.0)

    def test_running_setup_compute_weekly_allows_lower_min_start_when_no_history(self):
        weekly = compute_weekly_km_params(14.0, 17.0, "conservative", min_start_km=16.0)
        self.assertEqual(weekly["start"], 16.0)

    def test_running_setup_normalize_days_clamps_values(self):
        run_days, force_days, clamped = normalize_days(99, -3)
        self.assertEqual(run_days, 6)
        self.assertEqual(force_days, 0)
        self.assertTrue(clamped)

    def test_running_setup_help_lists_no_history(self):
        result = run_cmd("./tv", "running", "setup", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("--no-history", result.stdout)

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
        base_plan = json.loads((DEFAULT_ATHLETE_DATA_DIR / "running_plan.json").read_text(encoding="utf-8"))
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
        enforced_plan = json.loads((DEFAULT_ATHLETE_DATA_DIR / "running_plan.json").read_text(encoding="utf-8"))
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

        with without_default_template():
            plan_week = run_cmd("./tv", "plan", "week", "2026-W11")
            self.assertEqual(plan_week.returncode, 0, msg=plan_week.stderr)
            self.assertIn("Piano week 2026-W11", plan_week.stdout)

        week_dir = DEFAULT_ATHLETE_PLANS_DIR / "weeks" / "2026-W11"
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

        with without_default_template():
            plan_month = run_cmd("./tv", "plan", "month", "2026-03")
            self.assertEqual(plan_month.returncode, 0, msg=plan_month.stderr)
            self.assertIn("Piano month 2026-03", plan_month.stdout)

        month_dir = DEFAULT_ATHLETE_PLANS_DIR / "months" / "2026-03"
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
        if importlib.util.find_spec("pdfplumber") is None:
            self.skipTest("pdfplumber not installed in test environment")
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
            {"id": "yogurt_greco_0_lipidi", "name": "Yogurt greco 0%"},
            {"id": "pane_integrale", "name": "Pane integrale"},
        ]
        by_id = find_food_by_target(foods, "yogurt_greco_0_lipidi")
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
        payload = build_training_load_payload([ROOT / "sources/workouts-2.csv"], [])
        self.assertIn("meta", payload)
        self.assertIn("summary", payload)
        self.assertIn("sessions", payload)
        self.assertIn("profile_costs_kcal", payload)
        self.assertEqual(payload["meta"]["mode"], "trainingpeaks")
        self.assertEqual(payload["summary"]["sessions_count"], 4)


class NutritionSetupTests(unittest.TestCase):
    def test_nutrition_validate_template_help(self):
        result = run_cmd("./tv", "nutrition", "validate-template", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("planner-ready", result.stdout)

    def test_validate_template_payload_happy_path(self):
        valid_food_ids = {"pane_integrale", "yogurt_greco_0_lipidi", "mela"}
        template = {
            "meals": [
                {
                    "meal_id": "breakfast",
                    "options": [
                        {
                            "option_id": "breakfast_opt_1",
                            "tags": [],
                            "rules_trace": {
                                "scenario": "default_day",
                                "reasoning": ["x"],
                                "source_refs": ["knowledge/nutrition-rules.md"],
                                "rules_doc": "knowledge/nutrition-rules.md",
                                "roles_final": ["carb", "protein"],
                            },
                            "blocks": [
                                {"role": "carb", "one_of": [{"food_db_id": "pane_integrale"}]},
                                {"role": "protein", "one_of": [{"food_db_id": "yogurt_greco_0_lipidi"}]},
                            ],
                        }
                    ],
                },
                {"meal_id": "snack_am", "options": [{"option_id": "snack_am_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["fruit"]}, "blocks": [{"role": "fruit", "one_of": [{"food_db_id": "mela"}]}]}]},
                {"meal_id": "lunch", "options": [{"option_id": "lunch_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["carb"]}, "blocks": [{"role": "carb", "one_of": [{"food_db_id": "pane_integrale"}]}]}]},
                {"meal_id": "snack_pm", "options": [{"option_id": "snack_pm_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["fruit"]}, "blocks": [{"role": "fruit", "one_of": [{"food_db_id": "mela"}]}]}]},
                {"meal_id": "dinner", "options": [{"option_id": "dinner_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["protein"]}, "blocks": [{"role": "protein", "one_of": [{"food_db_id": "yogurt_greco_0_lipidi"}]}]}]},
            ]
        }
        errors, warnings = validate_template_payload(template, valid_food_ids)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_validate_template_payload_detects_unknown_food(self):
        valid_food_ids = {"pane_integrale"}
        template = {
            "meals": [
                {"meal_id": "breakfast", "options": [{"option_id": "breakfast_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["carb"]}, "blocks": [{"role": "carb", "one_of": [{"food_db_id": "food_missing"}]}]}]},
                {"meal_id": "snack_am", "options": [{"option_id": "snack_am_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["carb"]}, "blocks": [{"role": "carb", "one_of": [{"food_db_id": "pane_integrale"}]}]}]},
                {"meal_id": "lunch", "options": [{"option_id": "lunch_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["carb"]}, "blocks": [{"role": "carb", "one_of": [{"food_db_id": "pane_integrale"}]}]}]},
                {"meal_id": "snack_pm", "options": [{"option_id": "snack_pm_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["carb"]}, "blocks": [{"role": "carb", "one_of": [{"food_db_id": "pane_integrale"}]}]}]},
                {"meal_id": "dinner", "options": [{"option_id": "dinner_opt_1", "tags": [], "rules_trace": {"scenario": "default_day", "reasoning": ["x"], "source_refs": ["s"], "rules_doc": "d", "roles_final": ["carb"]}, "blocks": [{"role": "carb", "one_of": [{"food_db_id": "pane_integrale"}]}]}]},
            ]
        }
        errors, _warnings = validate_template_payload(template, valid_food_ids)
        self.assertTrue(any("food_db_id sconosciuto" in e for e in errors))

    def test_planner_fails_if_template_exists_but_not_ready(self):
        template_path = DEFAULT_ATHLETE_DATA_DIR / "nutrition_base_template.json"
        existed = template_path.exists()
        backup = template_path.read_text(encoding="utf-8") if existed else None
        try:
            invalid_template = {
                "meta": {"template_version": "1.0.0"},
                "meals": [
                    {"meal_id": "breakfast", "options": []},
                    {"meal_id": "snack_am", "options": []},
                    {"meal_id": "lunch", "options": []},
                    {"meal_id": "snack_pm", "options": []},
                    {"meal_id": "dinner", "options": []},
                ],
            }
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(json.dumps(invalid_template), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_plan_for_category_with_athlete_template("rest")
        finally:
            if existed:
                template_path.write_text(backup, encoding="utf-8")
            elif template_path.exists():
                template_path.unlink()

    def test_extract_food_ids_from_template_option(self):
        option = {
            "blocks": [
                {
                    "role": "carb",
                    "one_of": [
                        {"food_db_id": "pane_integrale"},
                        {"food_db_id": "fette_biscottate"},
                    ],
                },
                {
                    "role": "protein",
                    "one_of": [
                        {"food_db_id": "yogurt_greco_0_lipidi"},
                    ],
                },
            ]
        }
        allowed, must_include = _extract_food_ids_from_template_option(option)
        self.assertEqual(
            allowed,
            ["pane_integrale", "fette_biscottate", "yogurt_greco_0_lipidi"],
        )
        self.assertEqual(must_include, ["pane_integrale", "yogurt_greco_0_lipidi"])

    def test_build_or_combinations_one_choice_per_block(self):
        option = {
            "blocks": [
                {
                    "role": "carb",
                    "one_of": [
                        {"food_db_id": "pane_integrale"},
                        {"food_db_id": "fette_biscottate"},
                    ],
                },
                {
                    "role": "protein",
                    "one_of": [
                        {"food_db_id": "yogurt_greco_0_lipidi"},
                        {"food_db_id": "uova_di_gallina_intero"},
                    ],
                },
            ]
        }
        combos = _build_or_combinations(option, max_combinations=10)
        self.assertEqual(len(combos), 4)
        self.assertIn(["pane_integrale", "yogurt_greco_0_lipidi"], combos)
        self.assertIn(["fette_biscottate", "uova_di_gallina_intero"], combos)

    def test_rules_engine_suggest_blocks_from_profile(self):
        profile = {
            "profile": {"goal": "performance"},
            "training_context": {
                "running_days_per_week": 5,
                "strength_days_per_week": 2,
                "typical_training_time": "evening",
            },
        }
        out = suggest_blocks(profile, "dinner", "post_workout")
        self.assertIn("protein", out["roles"])
        self.assertIn("carb", out["roles"])
        self.assertTrue(out["reasons"])

    def test_rules_engine_suggest_scenario_evening_dinner_post(self):
        profile = {
            "training_context": {
                "running_days_per_week": 4,
                "strength_days_per_week": 1,
                "typical_training_time": "evening",
            }
        }
        out = suggest_scenario_for_meal(profile, "dinner")
        self.assertEqual(out["scenario"], "post_workout")

    def test_rules_engine_hard_stop_on_very_low_bf(self):
        profile = {
            "advanced_bia": {
                "body_fat_pct": 4.0,
                "ffm_kg": 60.0,
            }
        }
        out = evaluate_safety(profile)
        self.assertTrue(out["consult_professional"])
        self.assertGreater(len(out["hard_stop"]), 0)

    def test_setup_base_profile_loader_accepts_minimum_valid_payload(self):
        from tempfile import TemporaryDirectory

        payload = {
            "profile": {"goal": "performance"},
            "body_core": {
                "sex": "male",
                "age_years": 36,
                "height_cm": 175.0,
                "weight_kg": 68.6,
            },
            "training_context": {
                "running_days_per_week": 4,
                "strength_days_per_week": 2,
                "typical_training_time": "evening",
            },
        }
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "NUTRITION_PROFILE.json"
            p.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_required_nutrition_profile(p)
            self.assertEqual(loaded["profile"]["goal"], "performance")

    def test_setup_base_profile_loader_rejects_missing_goal(self):
        from tempfile import TemporaryDirectory

        payload = {
            "profile": {},
            "body_core": {
                "sex": "male",
                "age_years": 36,
                "height_cm": 175.0,
                "weight_kg": 68.6,
            },
            "training_context": {
                "running_days_per_week": 4,
                "strength_days_per_week": 2,
                "typical_training_time": "evening",
            },
        }
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "NUTRITION_PROFILE.json"
            p.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_required_nutrition_profile(p)

    def test_search_foods_by_name(self):
        foods = [
            {"id": "pane_integrale", "name": "Pane integrale"},
            {"id": "yogurt_greco_0_lipidi", "name": "Yogurt greco 0%"},
            {"id": "banana", "name": "Banana"},
        ]
        results = search_foods(foods, "yogurt")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["id"], "yogurt_greco_0_lipidi")

    def test_meal_order_has_five_required_meals(self):
        self.assertEqual(
            MEAL_ORDER,
            ["breakfast", "snack_am", "lunch", "snack_pm", "dinner"],
        )

    def test_nutrition_setup_parse_strict_no_defaults(self):
        args = parse_nutrition_setup_args(["--strict-no-defaults"])
        self.assertTrue(args.strict_no_defaults)

    def test_nutrition_setup_parse_manual_override_flag(self):
        args = parse_nutrition_setup_args(["--allow-manual-block-overrides"])
        self.assertTrue(args.allow_manual_block_overrides)

    def test_nutrition_setup_parse_autodraft_flag(self):
        args = parse_nutrition_setup_args(["--autodraft"])
        self.assertTrue(args.autodraft)

    def test_auto_pick_foods_for_role_prefers_role_hints(self):
        foods = [
            {"id": "pane_integrale", "name": "Pane integrale"},
            {"id": "pollo_petto_cotto", "name": "Pollo petto cotto"},
            {"id": "olio_oliva", "name": "Olio di oliva"},
        ]
        picks = auto_pick_foods_for_role(foods, "protein", limit=1)
        self.assertEqual(picks[0]["id"], "pollo_petto_cotto")

    def test_build_option_autodraft_has_rules_trace_and_blocks(self):
        foods = [
            {"id": "pane_integrale", "name": "Pane integrale"},
            {"id": "pollo_petto_cotto", "name": "Pollo petto cotto"},
            {"id": "olio_oliva", "name": "Olio di oliva"},
            {"id": "caffe_espresso", "name": "Caffe espresso"},
            {"id": "banana", "name": "Banana"},
            {"id": "zucchine_crude", "name": "Zucchine crude"},
        ]
        profile = {
            "profile": {"goal": "performance"},
            "training_context": {
                "running_days_per_week": 4,
                "strength_days_per_week": 1,
                "typical_training_time": "morning",
            },
        }
        names = {f["id"]: f["name"] for f in foods}
        opt = build_option_autodraft(foods, "breakfast", 1, names, profile)
        self.assertTrue(opt["blocks"])
        self.assertTrue(opt["rules_trace"]["autodraft"])
        self.assertIn("scenario", opt["rules_trace"])

    def test_backfill_template_traces_restores_missing_trace(self):
        tpl = {
            "meals": [
                {
                    "meal_id": "breakfast",
                    "options": [
                        {
                            "option_id": "breakfast_opt_1",
                            "blocks": [
                                {"role": "carb", "one_of": [{"food_db_id": "pane_integrale", "label": "Pane"}]},
                            ],
                        }
                    ],
                }
            ]
        }
        names = {"pane_integrale": "Pane integrale"}
        backfill_template_traces(tpl, names)
        trace = tpl["meals"][0]["options"][0]["rules_trace"]
        self.assertIn("scenario", trace)
        self.assertIn("reasoning", trace)

    def test_validate_template_quality_flags_missing_trace(self):
        tpl = {
            "meals": [
                {
                    "meal_id": "breakfast",
                    "options": [
                        {
                            "option_id": "breakfast_opt_1",
                            "blocks": [{"role": "carb", "one_of": []}],
                            "rules_trace": {},
                        }
                    ],
                }
            ]
        }
        errors = validate_template_quality(tpl)
        self.assertGreater(len(errors), 0)

    def test_nutrition_setup_profile_help(self):
        result = run_cmd("./tv", "nutrition", "setup-profile", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("core + BIA avanzata", result.stdout)

    def test_nutrition_setup_profile_parse_force(self):
        args = parse_nutrition_profile_args(["--force"])
        self.assertTrue(args.force)

    def test_nutrition_setup_profile_target_athlete_id_uses_name_when_default(self):
        original = os.environ.get("TV_ATHLETE_ID")
        try:
            os.environ["TV_ATHLETE_ID"] = "default"
            self.assertEqual(resolve_nutrition_profile_target_athlete_id("Matteo"), "matteo")
        finally:
            if original is None:
                os.environ.pop("TV_ATHLETE_ID", None)
            else:
                os.environ["TV_ATHLETE_ID"] = original

    def test_nutrition_setup_profile_target_athlete_id_respects_env_override(self):
        original = os.environ.get("TV_ATHLETE_ID")
        try:
            os.environ["TV_ATHLETE_ID"] = "spizz"
            self.assertEqual(resolve_nutrition_profile_target_athlete_id("Matteo"), "spizz")
        finally:
            if original is None:
                os.environ.pop("TV_ATHLETE_ID", None)
            else:
                os.environ["TV_ATHLETE_ID"] = original

    def test_nutrition_setup_target_athlete_id_uses_name_when_default(self):
        original = os.environ.get("TV_ATHLETE_ID")
        try:
            os.environ["TV_ATHLETE_ID"] = "default"
            self.assertEqual(resolve_nutrition_target_athlete_id("Matteo"), "matteo")
        finally:
            if original is None:
                os.environ.pop("TV_ATHLETE_ID", None)
            else:
                os.environ["TV_ATHLETE_ID"] = original

    def test_nutrition_setup_target_athlete_id_respects_env_override(self):
        original = os.environ.get("TV_ATHLETE_ID")
        try:
            os.environ["TV_ATHLETE_ID"] = "spizz"
            self.assertEqual(resolve_nutrition_target_athlete_id("Matteo"), "spizz")
        finally:
            if original is None:
                os.environ.pop("TV_ATHLETE_ID", None)
            else:
                os.environ["TV_ATHLETE_ID"] = original

    def test_infer_option_tags_auto(self):
        blocks = [
            {"role": "carb", "one_of": [{"food_db_id": "pane_integrale"}]},
            {"role": "protein", "one_of": [{"food_db_id": "prosciutto_crudo"}]},
        ]
        names = {
            "pane_integrale": "Pane integrale",
            "prosciutto_crudo": "Prosciutto crudo",
        }
        tags = infer_option_tags(blocks, names)
        self.assertIn("carb_based", tags)
        self.assertIn("protein_based", tags)
        self.assertIn("post_workout", tags)
        self.assertIn("savory", tags)

    def test_infer_when_to_use_auto(self):
        blocks = [
            {"role": "carb", "one_of": [{"food_db_id": "banana"}]},
            {"role": "protein", "one_of": [{"food_db_id": "yogurt_greco_0_lipidi"}]},
        ]
        tags = ["carb_based", "protein_based", "post_workout", "pre_workout"]
        text = infer_when_to_use("snack_pm", blocks, tags, "pre_workout")
        self.assertIn("pre-allenamento", text)

    def test_suggest_roles_for_breakfast_default_day(self):
        roles = suggest_roles_for_option("breakfast", "default_day")
        self.assertEqual(roles, ["carb", "protein", "beverage", "fat"])


if __name__ == "__main__":
    unittest.main()
